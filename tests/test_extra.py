"""O leitor processa arquivos com mais de 200 linhas."""

from helpers import run_cli


def test_le_todas_as_linhas_acima_de_200(tmp_path):
    """O leitor processa o arquivo inteiro, sem limite de linhas."""
    rows = [{"reservation_id": f"R-{i}"} for i in range(250)]
    report = run_cli(tmp_path, rows)
    assert report["summary"]["total_reservations"] == 250
    assert report["summary"]["confirmed_reservations"] == 250
    assert report["summary"]["total_room_nights"] == 250
    assert report["summary"]["total_amount_brl"] == "25000.00"

def test_noites_multiplicam_pelo_numero_de_quartos(tmp_path):
    """room_nights multiplica as noites pelos quartos; a média usa as noites de quarto."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-1",
                "checkin_date": "2025-03-10",
                "checkout_date": "2025-03-12",
                "rooms": "3",
                "amount": "600.00",
            }
        ],
    )
    assert report["summary"]["total_room_nights"] == 6
    assert report["summary"]["average_nightly_rate_brl"] == "100.00"
    assert report["by_month"][0]["room_nights"] == 6
    assert report["top_hotels"][0]["room_nights"] == 6


def test_noites_na_virada_de_ano(tmp_path):
    """A diferença de datas atravessa o ano; não pode usar dia do mês nem dia do ano."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-1",
                "checkin_date": "2025-12-30",
                "checkout_date": "2026-01-02",
                "rooms": "1",
                "amount": "300.00",
            }
        ],
    )
    assert report["summary"]["total_room_nights"] == 3
    assert report["summary"]["average_nightly_rate_brl"] == "100.00"


def test_by_month_usa_mes_do_checkin_e_ordena_ascendente(tmp_path):
    """by_month agrupa pelo mês do check-in, soma por mês e ordena por month ascendente."""
    report = run_cli(
        tmp_path,
        [
            # entra em fevereiro (check-in), mesmo terminando em março; 10 noites
            {"reservation_id": "R-1", "checkin_date": "2025-02-20", "checkout_date": "2025-03-02", "amount": "100.00"},
            # entra em janeiro, mesmo terminando em fevereiro; 3 noites x 2 quartos
            {
                "reservation_id": "R-2",
                "checkin_date": "2025-01-30",
                "checkout_date": "2025-02-02",
                "rooms": "2",
                "amount": "200.00",
            },
            {"reservation_id": "R-3", "checkin_date": "2025-02-05", "checkout_date": "2025-02-06", "amount": "50.50"},
        ],
    )
    assert report["by_month"] == [
        {"month": "2025-01", "reservations": 1, "room_nights": 6, "total_brl": "200.00"},
        {"month": "2025-02", "reservations": 2, "room_nights": 11, "total_brl": "150.50"},
    ]


def test_arredondamento_half_up_na_serializacao(tmp_path):
    """USD 0.75 x 5.42 = 4.065 exato: half-up dá 4.07; a média 2.0325 dá 2.03 (total exato, não o arredondado)."""
    report = run_cli(
        tmp_path,
        [
            {
                "reservation_id": "R-1",
                "currency": "USD",
                "amount": "0.75",
                "checkin_date": "2025-03-10",
                "checkout_date": "2025-03-12",
            }
        ],
    )
    assert report["summary"]["total_amount_brl"] == "4.07"
    assert report["summary"]["average_nightly_rate_brl"] == "2.03"
    assert report["by_month"][0]["total_brl"] == "4.07"
    assert report["top_hotels"][0]["total_brl"] == "4.07"


def test_arredondamento_so_no_final_nao_por_reserva(tmp_path):
    """Duas reservas de 4.065 somam 8.13 exato; arredondar cada uma antes daria 8.14."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "currency": "USD", "amount": "0.75"},
            {"reservation_id": "R-2", "currency": "USD", "amount": "0.75"},
        ],
    )
    assert report["summary"]["total_amount_brl"] == "8.13"
    assert report["by_month"][0]["total_brl"] == "8.13"
    assert report["top_hotels"][0]["total_brl"] == "8.13"


def test_nao_faturaveis_ficam_fora_de_by_month_e_top_hotels(tmp_path):
    """CANCELLED e NO_SHOW não criam nem alteram mês ou hotel, nem no mesmo hotel e mês de um CONFIRMED."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "hotel_name": "Hotel A", "amount": "100.00"},
            {
                "reservation_id": "R-2",
                "hotel_id": "H01",
                "hotel_name": "Hotel A",
                "status": "CANCELLED",
                "amount": "900.00",
            },
            {
                "reservation_id": "R-3",
                "hotel_id": "H02",
                "hotel_name": "Hotel B",
                "status": "NO_SHOW",
                "amount": "500.00",
                "checkin_date": "2025-02-10",
                "checkout_date": "2025-02-11",
            },
        ],
    )
    assert report["by_month"] == [{"month": "2025-01", "reservations": 1, "room_nights": 1, "total_brl": "100.00"}]
    assert report["top_hotels"] == [
        {"hotel_id": "H01", "hotel_name": "Hotel A", "room_nights": 1, "total_brl": "100.00"}
    ]


def test_sem_reservas_confirmadas_media_zero_e_listas_vazias(tmp_path):
    """Sem noites faturáveis a média é "0.00" (sem divisão por zero) e by_month/top_hotels ficam vazios."""
    report = run_cli(tmp_path, [{"reservation_id": "R-1", "status": "CANCELLED"}])
    assert report["summary"] == {
        "total_reservations": 1,
        "confirmed_reservations": 0,
        "cancelled_reservations": 1,
        "no_show_reservations": 0,
        "total_room_nights": 0,
        "total_amount_brl": "0.00",
        "average_nightly_rate_brl": "0.00",
    }
    assert report["by_month"] == []
    assert report["top_hotels"] == []
