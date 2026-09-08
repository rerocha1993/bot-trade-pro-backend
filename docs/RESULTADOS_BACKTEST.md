# Resultados de backtest (registro)

Configuração comum: 1h, daytrade, conservador, entrada por ordem limitada, banca 10 000, risco 1% por trade,
taxas maker/taker da Bybit, slippage 0,02% em ordens a mercado, modelo de calibração de Elliott ligado.

## 2012-2026 completo (Bitstamp 1h, 129 447 candles, modelo calibrado com todo o período)

| Métrica | Valor |
|---|---|
| Trades | 2 540 |
| Taxa de acerto | 31,7% |
| Resultado | +19 948 USDT (+199%) |
| Fator de lucro | 1,09 |
| Drawdown máximo | 40,3% |

| Ano | Trades | P&L | Acerto | R médio |
|---|---|---|---|---|
| 2012 | 165 | -3 656 | 14% | -0,61 |
| 2013 | 235 | +4 929 | 36% | 0,39 |
| 2014 | 135 | +2 340 | 36% | 0,20 |
| 2015 | 164 | +5 928 | 36% | 0,43 |
| 2016 | 155 | -158 | 28% | 0,18 |
| 2017 | 215 | +11 558 | 36% | 0,52 |
| 2018 | 152 | -3 366 | 27% | -0,06 |
| 2019 | 152 | +4 882 | 34% | 0,27 |
| 2020 | 176 | +4 596 | 35% | 0,21 |
| 2021 | 167 | -10 105 | 27% | -0,16 |
| 2022 | 174 | -845 | 30% | 0,02 |
| 2023 | 163 | +1 751 | 36% | 0,15 |
| 2024 | 185 | +1 551 | 32% | 0,17 |
| 2025 | 177 | +223 | 31% | 0,08 |
| 2026 (até set) | 124 | +347 | 36% | 0,12 |

Leitura: ganha nos anos de tendência limpa (2013, 2015, 2017, 2019, 2020), perde nos topos serrilhados (2018, 2021) e em
2012, cujos dados da Bitstamp são pouco líquidos. O drawdown de 40% concentra-se em 2021-2022.

## Fora da amostra 2024-2026 (modelo treinado só até 2023)

| Configuração | Trades | Retorno | Fator de lucro | Drawdown |
|---|---|---|---|---|
| Sem calibração | 478 | +6,8% | 1,05 | 11,7% |
| Calibração, mínimo 45% | 486 | +10,0% | 1,07 | 9,5% |
| Calibração, mínimo 70% | 425 | +5,0% | 1,04 | 10,4% |

## Validação de moeda nova (gate)

ETHUSDT 15m, daytrade conservador, 120 dias: 192 trades, acerto 28,6%, -8,65%, PF 0,75, DD 11,7% -> **reprovado**.

## Experimentos 2013-2026 (Bitstamp, descartando 2012)

| Configuração | Trades | Acerto | Retorno | Fator de lucro | R médio | Drawdown |
|---|---|---|---|---|---|---|
| 1h daytrade conservador (2012-2026, referência) | 2 540 | 31,7% | +199% | 1,09 | 0,11 | 40,3% |
| 4h swing conservador | 564 | 28,7% | +192% | 1,19 | 0,28 | 25,3% |
| 4h swing seletivo (só tipos com acerto histórico ≥ 65%, R:R ≥ 1,5) | 453 | 28,3% | +169% | 1,24 | 0,32 | 22,6% |
| 1h daytrade seletivo (2013-2026) | 1 856 | 32,4% | +211% | 1,11 | 0,22 | 31,6% |

Leitura: subir o grau (4h) melhora qualidade (fator de lucro e R médio) e reduz o drawdown pela metade com 4x menos trades.
O modo seletivo melhora ainda o fator de lucro e o drawdown à custa de retorno bruto. Anos ruins em 4h: 2021 e 2025.

## Modo inverse (short-only em range, P&L em BTC), 4h, range escolhido automaticamente

Carteira parte de 1 BTC. Escada de Fibonacci padrão (10/25/40/60/80/100%), short de base até 50% x probabilidade,
folga de stop 2%, range proposto pelos dois últimos pivôs primários (22%) no diário. No bot real o range é APROVADO
pelo usuário; aqui a aprovação é automática, portanto estes números são um piso.

| Regras de proposta | Desde | BTC final | Ranges / stops | Drawdown em BTC |
|---|---|---|---|---|
| pivôs apenas | 2017 | 0,53 (-47%) | 21 / 19 | 58% |
| + Elliott corretivo e regime não-tendência | 2017 | 0,78 (-22%) | 8 / 7 | 31% |
| + sem range com ciclo semanal em alta | 2017 | 0,90 (-10%) | 7 / 7 | 27% |
| + sem range com ciclo semanal em alta | 2022 | 1,02 (+2%) | 3 / 3 | 19% |

Por ano (variante completa, desde 2013): ganha BTC em 2014, 2015, 2018 e 2022 (anos de baixa/correção), perde em
2013, 2016, 2017, 2020 e 2024 (rompimentos para cima). Conclusão: a estratégia acumula BTC quando o range é uma
correção de verdade e perde em ciclo de alta; a escolha do range precisa ser do usuário (com a contagem mestre
travada), não automática.

## Grade inversa SEM stop (entradas e saídas escalonadas, toda recompra com lucro em BTC), 4h, range automático

Carteira parte de 1 BTC. "Realizado" só sobe; "marcado" inclui as fatias abertas ao preço final.

| Regras | Desde | BTC realizado | BTC marcado | Em dólar (média) | Grades / concluídas | Saídas de cenário |
|---|---|---|---|---|---|---|
| livre | 2017 | 1,11 | 0,11 | 99% | 1 / 0 | 0 |
| livre | 2022 | 1,24 | 0,39 | 80% | 4 / 3 | 0 |
| corretivo + ciclo | 2022 | 1,25 | 0,43 | 76% | 3 / 2 | 0 |
| corretivo + saída de cenário | 2017 | 0,53 | 0,53 | 11% | 19 / 13 | 6 |
| corretivo + ciclo + saída de cenário | 2017 | 0,63 | 0,63 | 8% | 12 / 8 | 4 |
| corretivo + ciclo + saída de cenário | 2022 | 1,06 | 1,06 | 5% | 4 / 3 | 1 |

Leitura: sem saída, a grade que rompe para cima deixa a carteira em dólar por anos (2017: 100% em dólar até hoje).
Com saída de cenário, a saída chega tarde e custa caro nas altas (2019: -0,43 BTC). A grade acumula BTC apenas dentro de
correções confirmadas (2018, 2022); a escolha do range e o momento de sair precisam ser decisão humana apoiada pela
contagem mestre travada, não automáticos.

## Dial de hedge (carteira 100% BTC; short inverso só como proteção em barreiras com exaustão), 4h, 2018-2026

Regras automáticas: hedge 0% em impulso de alta; vende escalonado só na metade superior da faixa suporte-barreira,
em fase de topo segundo Elliott ou barreira com ≥ 3 fontes, com ≥ 2 sinais de exaustão (Fear & Greed, VWAP z, RSI,
acima da VAH, prob. bear); teto 50% (100% só com ciclo/primário de baixa); recompra fatia a fatia sempre com lucro;
desmonta no rompimento com estrutura de alta.

| Limiar de exaustão | Desde | BTC final | Hedge médio | Queda máx. em BTC | Custo de rompimentos |
|---|---|---|---|---|---|
| 0,50 | 2018 | 0,99 | 0,1% | 4,4% | -0,03 |
| 0,35 | 2018 | 0,97 | 0,6% | 11,0% | -0,10 |
| 0,20 | 2018 | 0,91 | 0,8% | 17,4% | -0,16 |
| 0,20 a 0,35 | 2022 | 1,03 | 0,7% | 6,2% | 0,00 |

Leitura: com as travas de confluência o dial quase não protege (e não destrói a carteira); afrouxando, os rompimentos
custam mais do que os ciclos rendem. Em modo automático, o hedge na força não acumula BTC neste histórico; o valor da
ferramenta está no modo semi-manual: o sistema mostra barreira, confluências e exaustão (GET /inverse/dial) e o usuário
decide quando começar a montar; a grade executa as fatias e as recompras com lucro.
