"""Testes adicionais: cenários não cobertos pelos testes fornecidos."""

import csv
import json
import os
import re
import subprocess
import sys

import pytest
from helpers import BASE, COLUMNS, SRC_DIR, run_cli

from onfly_report import cli


def test_le_todas_as_linhas_acima_de_200(tmp_path):
    """O leitor processa arquivos com mais de 200 linhas."""
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


# ---------------------------------------------------------------------------
# Utilitários para exercitar o CLI diretamente (códigos de saída, argumentos padrão).
# ---------------------------------------------------------------------------

RATES_OK = "currency,rate_to_brl\nBRL,1.000000\nUSD,5.420000\nEUR,5.880000\n"


def _executar(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _preparar(tmp_path, rows=None, columns=COLUMNS, rates=RATES_OK):
    """Grava reservas e taxas; rows=None não cria o arquivo de reservas, rates=None não cria o de taxas."""
    entrada, taxas, saida = tmp_path / "reservas.csv", tmp_path / "rates.csv", tmp_path / "report.json"
    if rows is not None:
        with entrada.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows({**BASE, **row} for row in rows)
    if rates is not None:
        taxas.write_text(rates, encoding="utf-8")
    return ["--input", str(entrada), "--rates", str(taxas), "--output", str(saida)], saida


def test_top_hotels_empate_soma_por_hotel_e_menos_hoteis_que_top(tmp_path):
    """Empate de valor desempata por hotel_id asc; reservas do mesmo hotel somam; top maior que o nº de hotéis."""
    report = run_cli(
        tmp_path,
        [
            # H02 entra antes de H01, ambos com 500.00: a ordem de inserção não pode decidir o empate
            {"reservation_id": "R-1", "hotel_id": "H02", "hotel_name": "Hotel B", "amount": "500.00"},
            {"reservation_id": "R-2", "hotel_id": "H01", "hotel_name": "Hotel A", "amount": "500.00"},
            # H03 tem duas reservas (1 + 2 noites) que somam 700.00
            {"reservation_id": "R-3", "hotel_id": "H03", "hotel_name": "Hotel C", "amount": "300.00"},
            {
                "reservation_id": "R-4",
                "hotel_id": "H03",
                "hotel_name": "Hotel C",
                "amount": "400.00",
                "checkin_date": "2025-01-20",
                "checkout_date": "2025-01-22",
            },
        ],
        top=10,
    )
    assert report["top_hotels"] == [
        {"hotel_id": "H03", "hotel_name": "Hotel C", "room_nights": 3, "total_brl": "700.00"},
        {"hotel_id": "H01", "hotel_name": "Hotel A", "room_nights": 1, "total_brl": "500.00"},
        {"hotel_id": "H02", "hotel_name": "Hotel B", "room_nights": 1, "total_brl": "500.00"},
    ]


@pytest.mark.parametrize("top", ["0", "-1", "abc"])
def test_top_invalido_sai_com_2(tmp_path, top):
    """--top deve ser inteiro >= 1; senão, argumento inválido (exit 2) e nenhum relatório."""
    args, saida = _preparar(tmp_path, rows=[{}])
    resultado = _executar([*args, "--top", top], tmp_path)
    assert resultado.returncode == 2, resultado.stderr
    assert not saida.exists()


def test_argumento_obrigatorio_ausente_sai_com_2(tmp_path):
    """--rates é obrigatório."""
    args, saida = _preparar(tmp_path, rows=[{}])
    resultado = _executar(args[:2], tmp_path)
    assert resultado.returncode == 2, resultado.stderr
    assert "--rates" in resultado.stderr  # o argparse aponta o argumento ausente
    assert not saida.exists()


@pytest.mark.parametrize(
    ("rows", "columns"),
    [
        pytest.param(None, COLUMNS, id="arquivo_inexistente"),
        pytest.param([{}], [c for c in COLUMNS if c != "amount"], id="coluna_faltando"),
        pytest.param([{"amount": "abc"}], COLUMNS, id="valor_invalido"),
        pytest.param([{"checkin_date": "2025-13-40"}], COLUMNS, id="data_invalida"),
        pytest.param([{"rooms": "x"}], COLUMNS, id="quartos_invalido"),
    ],
)
def test_reservas_invalidas_saem_com_2(tmp_path, rows, columns):
    """Arquivo de reservas ausente, sem coluna ou com linha inválida: erro de entrada (exit 2)."""
    args, saida = _preparar(tmp_path, rows=rows, columns=columns)
    resultado = _executar(args, tmp_path)
    assert resultado.returncode == 2, resultado.stderr
    assert not saida.exists()


@pytest.mark.parametrize(
    "rates",
    [
        pytest.param(None, id="arquivo_inexistente"),
        pytest.param("currency,taxa\nBRL,1\n", id="coluna_faltando"),
        pytest.param("currency,rate_to_brl\nBRL,0\n", id="taxa_zero"),
        pytest.param("currency,rate_to_brl\nBRL,-1\n", id="taxa_negativa"),
        pytest.param("currency,rate_to_brl\nBRL,abc\n", id="taxa_nao_numerica"),
        pytest.param("currency,rate_to_brl\n,1.0\n", id="linha_incompleta"),
        pytest.param("currency,rate_to_brl\n", id="tabela_vazia"),
    ],
)
def test_tabela_de_cambio_invalida_sai_com_2(tmp_path, rates):
    """Tabela de câmbio ausente, sem coluna, com taxa inválida ou vazia: erro de entrada (exit 2)."""
    args, saida = _preparar(tmp_path, rows=[{}], rates=rates)
    resultado = _executar(args, tmp_path)
    assert resultado.returncode == 2, resultado.stderr
    assert not saida.exists()


def test_erro_inesperado_sai_com_1(tmp_path, monkeypatch):
    """Uma exceção não prevista ao gerar o relatório é exit 1 (não 2 nem 0) e não grava relatório."""

    def build_quebrado(self):
        raise RuntimeError("falha artificial")

    monkeypatch.setattr(cli.ReportBuilder, "build", build_quebrado)
    args, saida = _preparar(tmp_path, rows=[{}])
    assert cli.main(args) == 1
    assert not saida.exists()


def test_falha_ao_gravar_relatorio_sai_com_1(tmp_path):
    """Se o destino do relatório não pode ser gravado (é um diretório), o CLI sai com 1."""
    args, saida = _preparar(tmp_path, rows=[{}])
    saida.mkdir()
    resultado = _executar(args, tmp_path)
    assert resultado.returncode == 1, resultado.stderr


def test_cambio_usa_a_taxa_de_cada_moeda(tmp_path):
    """BRL, USD (5.42) e EUR (5.88) em hotéis distintos: cada moeda usa a sua própria taxa."""
    report = run_cli(
        tmp_path,
        [
            {"reservation_id": "R-1", "hotel_id": "H01", "currency": "BRL", "amount": "100.00"},
            {"reservation_id": "R-2", "hotel_id": "H02", "currency": "USD", "amount": "10.00"},
            {"reservation_id": "R-3", "hotel_id": "H03", "currency": "EUR", "amount": "10.00"},
        ],
    )
    assert report["summary"]["total_amount_brl"] == "213.00"
    assert [(h["hotel_id"], h["total_brl"]) for h in report["top_hotels"]] == [
        ("H01", "100.00"),
        ("H03", "58.80"),
        ("H02", "54.20"),
    ]


def test_contrato_do_cli_padroes_e_formato_do_relatorio(tmp_path):
    """Sem --top nem --output: top 5 e output/report.json; formato exato do relatório e do resumo no stdout."""
    rows = [{"reservation_id": f"R-{i}", "hotel_id": f"H0{i}", "hotel_name": f"Hotel {i}"} for i in range(1, 8)]
    args, _ = _preparar(tmp_path, rows=rows)
    resultado = _executar(args[:4], tmp_path)  # só --input e --rates; cwd = tmp_path
    assert resultado.returncode == 0, resultado.stderr

    report = json.loads((tmp_path / "output" / "report.json").read_text(encoding="utf-8"))
    assert list(report) == ["report_version", "generated_at", "summary", "by_month", "top_hotels"]
    assert report["report_version"] == "1.0"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}-03:00", report["generated_at"])
    assert list(report["summary"]) == [
        "total_reservations",
        "confirmed_reservations",
        "cancelled_reservations",
        "no_show_reservations",
        "total_room_nights",
        "total_amount_brl",
        "average_nightly_rate_brl",
    ]
    assert list(report["by_month"][0]) == ["month", "reservations", "room_nights", "total_brl"]
    assert list(report["top_hotels"][0]) == ["hotel_id", "hotel_name", "room_nights", "total_brl"]
    assert len(report["top_hotels"]) == 5
    assert [h["hotel_id"] for h in report["top_hotels"]] == ["H01", "H02", "H03", "H04", "H05"]
    dinheiro = [report["summary"]["total_amount_brl"], report["summary"]["average_nightly_rate_brl"]]
    dinheiro += [m["total_brl"] for m in report["by_month"]] + [h["total_brl"] for h in report["top_hotels"]]
    assert all(re.fullmatch(r"\d+\.\d{2}", valor) for valor in dinheiro)
    assert resultado.stdout.strip() == "Reservas: 7 | Confirmadas: 7 | Noites: 7 | Total BRL: 700.00"
