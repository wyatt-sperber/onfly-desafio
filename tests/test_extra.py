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