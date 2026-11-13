# Entrega: consolidador de reservas Onfly

## Defeitos corrigidos

| # | Arquivo | Defeito | Causa raiz |
|-|-|-|-|
| 1 | `services/stay_calculator.py` | Noites erradas na virada de mês | Subtraía só o dia do mês (`checkout.day - checkin.day`); 30/01 a 02/02 dava −28 em vez de 3. |
| 2 | `services/currency_converter.py` | Valores em BRL errados | Dividia pela taxa em vez de multiplicar, e passava por `float` em vez de `Decimal`. |
| 3 | `services/status_policy.py` | NO_SHOW entrava nos totais | A regra excluía só CANCELLED; o README diz que só CONFIRMED é faturável. |
| 4 | `services/report_builder.py` | Ranking de hotéis invertido | Ordenava por valor crescente; agora ordena por `(-valor, hotel_id)`, decrescente com desempate por id crescente. |
| 5 | `repositories/csv_reservation_repository.py` | Relatório ignorava reservas | Um limite fixo parava a leitura na linha 200; o arquivo real tem 300 reservas. |

## Como investiguei

1. Rodei os testes e li os valores errados: −28 em vez de 3 apontou o cálculo por dia do mês; 118.45 em vez de 642.00 (100 + 100 ÷ 5,42) apontou a divisão pela taxa; 120.00 em vez de 100.00 mostrou o NO_SHOW somado; a lista H04, H03, H02 mostrou o ranking invertido.
2. Corrigi um defeito por vez, rodando os testes e fazendo um commit para cada correção.
3. Com os 5 testes passando, rodei o CLI no arquivo real: o resumo mostrava 200 reservas, mas `(Import-Csv data/reservas_hoteis.csv).Count` retornava 300. Investiguei a divergência e achei o limite fixo de 200 linhas no leitor, um defeito que nenhum teste fornecido detectava.
4. Escrevi testes para as regras do README que os testes fornecidos não verificavam e medi a cobertura.

## Como validar

```powershell
pip install -r requirements-dev.txt
pytest -q

$env:PYTHONPATH = "src"   # no Linux/Mac: PYTHONPATH=src antes do comando
python -m onfly_report --input data/exemplo-validacao.csv --rates data/taxas_cambio.csv --output output/exemplo.json
python -m onfly_report --input data/reservas_hoteis.csv --rates data/taxas_cambio.csv --output output/report.json
```

Resultados esperados:
- Amostra: `Reservas: 12 | Confirmadas: 9 | Noites: 28 | Total BRL: 7566.00`, com `by_month` e `top_hotels` iguais às tabelas do README (conferido campo a campo).
- Arquivo real: `Reservas: 300 | Confirmadas: 235 | Noites: 1347 | Total BRL: 396170.00`.

## Resultado do pytest

```
..................................                                    [100%]
34 passed in 4.71s
```

5 testes fornecidos (sem alteração) + 29 testes novos em `tests/test_extra.py`.

## Testes adicionados

- **Cobertura:** de 85% para 98% (linhas e branches, incluindo o subprocesso do CLI, com `coverage` e `patch = ["subprocess"]`).
- **Prova por mutação:** 38 defeitos injetados manualmente, um por vez, todos detectados. Os scripts da mutação não foram versionados.
- **O que os testes protegem:** leitura de mais de 200 linhas; noites × quartos; virada de ano; `by_month` (mês do check-in, ordem, somas); arredondamento half-up só na serialização (USD 0,75 → 4.07; 2 × USD 0,75 → 8.13); exclusão de CANCELLED e NO_SHOW de `by_month` e `top_hotels`; média "0.00" sem confirmadas; desempate e soma no ranking; taxas de BRL, USD e EUR; códigos de saída 2 e 1; contrato do CLI (padrões de `--top` e `--output`, chaves, `report_version`, `generated_at` com -03:00).

## Observações

- **Moeda sem taxa:** hoje gera `KeyError`, tratado como erro inesperado (código 1). O README define código 2 para entrada inválida, mas também diz que todas as moedas do dataset têm taxa. Como o caso está fora do contrato, não travei esse comportamento em teste.
- **Fora da cobertura, de propósito:** o `__main__` do `cli.py` e dois tratamentos de falha de disco (`OSError`/`csv.Error`), difíceis de provocar de forma portátil.