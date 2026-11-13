# Declaração de uso de IA

## Ferramentas e modelos

- Claude Code v2.1.323, Claude Sonnet 5.5 (esforço médio): sessões 01 e 02, exportadas nesta pasta.

## O que a IA fez

- No Claude Code, investigou a divergência de 200/300 reservas, configurou a medição de cobertura, analisou quais regras do README estavam desprotegidas, escreveu os testes adicionais e provou cada um com mutações.

## O que eu fiz
- Configurei o ambiente, apliquei as correções dos 4 primeiros defeitos e fiz os commits.
- Validei o CLI no arquivo real e na amostra do README.
- Conduzi as sessões, revisei cada diff antes de aprovar e corrigi a IA quando ela errou (o teste de regressão, a regra da virada de ano, a prioridade de rooms e o caso da moeda sem taxa).
- Revisei e ajustei o README-ENTREGA.