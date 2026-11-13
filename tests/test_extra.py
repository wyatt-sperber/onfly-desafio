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
