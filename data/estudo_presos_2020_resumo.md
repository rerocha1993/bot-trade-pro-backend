# Presos no footprint 2020–2026 e TPO E2 + presos

Gerado por `scripts/estudo_presos_2020.py` em 2026-10-20 21:31 UTC (regra exata e critério no docstring, escritos antes de rodar; nenhum parâmetro iterado; holdout lido uma vez). Footprint por minuto da Bybit BTCUSDT linear, 2020-03-25 a 2026-10-19: 3427045 minutos. Custo real, leitura pessimista em 1 min, funding linear (a tabela de funding termina em 2026-09-11; depois conta zero).

Buracos > 60 min sem minuto gravado: 1 (2026-10-19 23:59 por 1009 min)

## Veredito pelo critério

- **presos 30m compra+venda: REPROVADA** — treino: líquido -0.351 <= 0; treino: não fica 2 EP acima de todos os controles; validacao: líquido -0.320 <= 0; holdout: líquido -0.407 <= 0
- **presos 30m compra: REPROVADA** — treino: líquido -0.359 <= 0; treino: não fica 2 EP acima de todos os controles; validacao: líquido -0.341 <= 0; validacao: não fica 2 EP acima de todos os controles; holdout: líquido -0.411 <= 0
- **presos 30m venda: REPROVADA** — treino: líquido -0.341 <= 0; treino: não fica 2 EP acima de todos os controles; validacao: líquido -0.293 <= 0; validacao: não fica 2 EP acima de todos os controles; holdout: líquido -0.401 <= 0
- **presos 5m compra+venda: REPROVADA** — treino: líquido -0.716 <= 0; treino: não fica 2 EP acima de todos os controles; validacao: líquido -0.604 <= 0; validacao: não fica 2 EP acima de todos os controles; holdout: líquido -0.595 <= 0
- **presos 5m compra: REPROVADA** — treino: líquido -0.703 <= 0; treino: não fica 2 EP acima de todos os controles; validacao: líquido -0.590 <= 0; validacao: não fica 2 EP acima de todos os controles; holdout: líquido -0.652 <= 0
- **presos 5m venda: REPROVADA** — treino: líquido -0.730 <= 0; treino: não fica 2 EP acima de todos os controles; validacao: líquido -0.620 <= 0; validacao: não fica 2 EP acima de todos os controles; holdout: líquido -0.534 <= 0
- **E2+presos30 compra+venda: INCONCLUSIVA** — treino: n=23 < 30; validacao: n=8 < 30; holdout: n=12 < 30
- **E2+presos30 compra: INCONCLUSIVA** — treino: n=12 < 30; validacao: n=6 < 30; holdout: n=7 < 30
- **E2+presos30 venda: INCONCLUSIVA** — treino: n=11 < 30; validacao: n=2 < 30; holdout: n=5 < 30
- **E2+presos5 compra+venda: REPROVADA** — treino: não fica 2 EP acima de todos os controles; validacao: n=9 < 30; holdout: n=6 < 30
- **E2+presos5 compra: INCONCLUSIVA** — treino: n=21 < 30; validacao: n=6 < 30; holdout: n=5 < 30
- **E2+presos5 venda: INCONCLUSIVA** — treino: n=16 < 30; validacao: n=3 < 30; holdout: n=1 < 30

## Parte 1 — presos no footprint (reteste do nível preso, stop além da vela + 0,10%, alvo 2R, 24 h)

### Funil

| TF | nós (fluxo.presos) | fora dos períodos | buraco no dado | confirmados (abandono) | não abandonados | (b) não postos (post-only) |
|---|---|---|---|---|---|---|
| 30m | 31453 | 295 | 0 | 6396 | 24762 | 9361 |
| 5m | 130325 | 1093 | 0 | 33139 | 96093 | 35725 |

### Preenchimento e tamanho do R

| TF | grupo | ordens | preencheram | R mediano (% do preço) | custo mínimo em R (maker + taker no stop, mediana) |
|---|---|---|---|---|---|
| 30m | presos | 6396 | 4477 | 0.256% | 0.37 |
| 30m | a_sorteado | 113089 | 77507 | 0.245% | 0.39 |
| 30m | b_nao_abandonado | 15401 | 13582 | 0.186% | 0.51 |
| 5m | presos | 33139 | 28740 | 0.153% | 0.62 |
| 5m | a_sorteado | 580097 | 500087 | 0.155% | 0.61 |
| 5m | b_nao_abandonado | 60368 | 57300 | 0.130% | 0.73 |

### Resultado (R líquido por trade preenchido)

(a) nível sorteado da mesma vela (20 por evento; n conta os sorteios); (b) nó igual não abandonado; (c) direção sorteada (esperança: média de mesma e oposta). EP = desvio/raiz(n); EPd = EP agrupado por dia (informativo). 20× = em quantos dos 20 sorteios do conjunto (lado sorteado) o real fica acima.

| TF | lado | período | n | acerto | média R ± EP | EPd | (a) (n) | (b) (n) | (c) | ≥a+2EP | ≥b+2EP | ≥c+2EP | real > sorteios |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30m | compra+venda | treino | 3040 | 32% | -0.351 ± +0.028 | +0.028 | -0.367 (52831) | -0.524 (5757) | -0.482 | não | sim | sim | 20/20 |
| 30m | compra+venda | validacao | 808 | 34% | -0.320 ± +0.054 | +0.056 | -0.473 (13943) | -0.529 (3743) | -0.436 | sim | sim | sim | 20/20 |
| 30m | compra+venda | holdout | 629 | 32% | -0.407 ± +0.061 | +0.059 | -0.404 (10733) | -0.483 (4082) | -0.489 | não | não | não | 19/20 |
| 30m | compra | treino | 1629 | 32% | -0.359 ± +0.037 | +0.038 | -0.385 (28539) | -0.521 (2792) | -0.483 | não | sim | sim | 20/20 |
| 30m | compra | validacao | 454 | 33% | -0.341 ± +0.073 | +0.078 | -0.475 (7866) | -0.496 (1857) | -0.434 | não | sim | não | 18/20 |
| 30m | compra | holdout | 362 | 32% | -0.411 ± +0.081 | +0.080 | -0.408 (6143) | -0.514 (2040) | -0.488 | não | não | não | 18/20 |
| 30m | venda | treino | 1411 | 33% | -0.341 ± +0.041 | +0.043 | -0.345 (24292) | -0.526 (2965) | -0.482 | não | sim | sim | 20/20 |
| 30m | venda | validacao | 354 | 34% | -0.293 ± +0.082 | +0.080 | -0.470 (6077) | -0.562 (1886) | -0.438 | sim | sim | não | 18/20 |
| 30m | venda | holdout | 267 | 32% | -0.401 ± +0.094 | +0.091 | -0.399 (4590) | -0.452 (2042) | -0.491 | não | não | não | 18/20 |
| 5m | compra+venda | treino | 16355 | 27% | -0.716 ± +0.012 | +0.013 | -0.655 (283883) | -0.766 (18984) | -0.766 | não | sim | sim | 20/20 |
| 5m | compra+venda | validacao | 7502 | 30% | -0.604 ± +0.018 | +0.019 | -0.598 (130807) | -0.668 (20007) | -0.691 | não | sim | sim | 20/20 |
| 5m | compra+venda | holdout | 4883 | 31% | -0.595 ± +0.022 | +0.022 | -0.581 (85397) | -0.659 (18309) | -0.681 | não | sim | sim | 20/20 |
| 5m | compra | treino | 8199 | 27% | -0.703 ± +0.018 | +0.018 | -0.654 (143852) | -0.747 (9081) | -0.747 | não | sim | sim | 20/20 |
| 5m | compra | validacao | 3847 | 31% | -0.590 ± +0.025 | +0.026 | -0.597 (67290) | -0.663 (9749) | -0.707 | não | sim | sim | 20/20 |
| 5m | compra | holdout | 2530 | 29% | -0.652 ± +0.031 | +0.031 | -0.645 (44453) | -0.676 (9107) | -0.702 | não | não | não | 20/20 |
| 5m | venda | treino | 8156 | 27% | -0.730 ± +0.017 | +0.019 | -0.657 (140031) | -0.782 (9903) | -0.785 | não | sim | sim | 20/20 |
| 5m | venda | validacao | 3655 | 30% | -0.620 ± +0.026 | +0.027 | -0.600 (63517) | -0.672 (10258) | -0.674 | não | sim | sim | 20/20 |
| 5m | venda | holdout | 2353 | 33% | -0.534 ± +0.033 | +0.033 | -0.512 (40944) | -0.642 (9202) | -0.660 | não | sim | sim | 20/20 |

### Ano a ano (presos, compra+venda)

| TF | ano | n | média R | compra n / média | venda n / média | (a) | (b) | (c) |
|---|---|---|---|---|---|---|---|---|
| 30m | 2020 | 329 | -0.315 | 182 / -0.404 | 147 / -0.204 | -0.356 | -0.684 | -0.466 |
| 30m | 2021 | 2214 | -0.358 | 1180 / -0.355 | 1034 / -0.361 | -0.365 | -0.498 | -0.484 |
| 30m | 2022 | 393 | -0.319 | 210 / -0.337 | 183 / -0.298 | -0.381 | -0.490 | -0.472 |
| 30m | 2023 | 104 | -0.447 | 57 / -0.390 | 47 / -0.516 | -0.375 | -0.558 | -0.537 |
| 30m | 2024 | 475 | -0.284 | 277 / -0.340 | 198 / -0.205 | -0.479 | -0.538 | -0.465 |
| 30m | 2025 | 615 | -0.404 | 352 / -0.411 | 263 / -0.395 | -0.477 | -0.493 | -0.422 |
| 30m | 2026 | 347 | -0.378 | 187 / -0.346 | 160 / -0.414 | -0.333 | -0.493 | -0.518 |
| 5m | 2020 | 1194 | -0.924 | 659 / -0.864 | 535 / -0.997 | -0.710 | -0.775 | -0.940 |
| 5m | 2021 | 11137 | -0.695 | 5566 / -0.690 | 5571 / -0.700 | -0.638 | -0.813 | -0.759 |
| 5m | 2022 | 2985 | -0.725 | 1447 / -0.690 | 1538 / -0.759 | -0.685 | -0.699 | -0.748 |
| 5m | 2023 | 1039 | -0.675 | 527 / -0.669 | 512 / -0.681 | -0.694 | -0.661 | -0.690 |
| 5m | 2024 | 4706 | -0.590 | 2427 / -0.565 | 2279 / -0.617 | -0.586 | -0.665 | -0.695 |
| 5m | 2025 | 4831 | -0.616 | 2487 / -0.632 | 2344 / -0.598 | -0.600 | -0.676 | -0.676 |
| 5m | 2026 | 2848 | -0.593 | 1463 / -0.666 | 1385 / -0.516 | -0.585 | -0.640 | -0.694 |

### Saídas (presos)

| TF | saída | n | média R | horas (mediana) |
|---|---|---|---|---|
| 30m | alvo | 1451 | +1.842 | 0.3 |
| 30m | stop | 3017 | -1.411 | 0.1 |
| 30m | tempo | 9 | +0.363 | 24.0 |
| 5m | alvo | 8206 | +1.744 | 0.1 |
| 5m | stop | 20533 | -1.630 | 0.0 |
| 5m | tempo | 1 | -0.006 | 24.0 |

## Parte 2 — TPO E2 (cauda na borda) + presos do lado da cauda

### Funil (blocos com aviso E2/sem_nivel e footprint da Bybit, desde 2020-03-26)

| grupo | lado | avisos | preencheram | com presos 30 min | com presos 5 min confirmados |
|---|---|---|---|---|---|
| E2 | compra | 79 | 78 | 25 | 32 |
| E2 | venda | 66 | 64 | 18 | 20 |
| sem_nivel | compra | 882 | 840 | 288 | 343 |
| sem_nivel | venda | 688 | 656 | 203 | 264 |

### Resultado P30 (principal) — R líquido por trade (regra de gestão da E2)

(i) cauda na borda SEM presos; (ii) presos SEM borda (cauda sem nível + presos); (iii) direção sorteada (cd do estudo E2).

| lado | período | n | acerto | média R ± EP | (i) (n) | (ii) (n) | (iii) | ≥i+2EP | ≥ii+2EP | ≥iii+2EP | real > sorteios |
|---|---|---|---|---|---|---|---|---|---|---|---|
| compra+venda | treino | 23 | 61% | +0.272 ± +0.275 | +0.217 (71) | +0.016 (306) | -0.048 | não | não | não | 19/20 |
| compra+venda | validacao | 8 | 62% | +0.122 ± +0.408 | +0.032 (21) | -0.057 (104) | -0.052 | não | não | não | 12/20 |
| compra+venda | holdout | 12 | 75% | +0.374 ± +0.309 | +0.469 (7) | +0.061 (81) | -0.218 | não | não | não | 20/20 |
| compra | treino | 12 | 75% | +0.409 ± +0.314 | +0.131 (34) | -0.044 (170) | -0.001 | não | não | não | 18/20 |
| compra | validacao | 6 | 50% | -0.131 ± +0.491 | +0.053 (15) | +0.020 (69) | -0.051 | não | não | não | 8/20 |
| compra | holdout | 7 | 71% | +0.462 ± +0.467 | +1.123 (4) | -0.030 (49) | -0.205 | não | não | não | 20/20 |
| venda | treino | 11 | 45% | +0.121 ± +0.474 | +0.296 (37) | +0.091 (136) | -0.098 | não | não | não | 13/20 |
| venda | validacao | 2 | 100% | +0.881 ± +0.521 | -0.019 (6) | -0.207 (35) | -0.053 | não | sim | não | 13/20 |
| venda | holdout | 5 | 80% | +0.252 ± +0.409 | -0.402 (3) | +0.201 (32) | -0.238 | não | não | não | 18/20 |

### Resultado P5 (informativo) — R líquido por trade (regra de gestão da E2)

(i) cauda na borda SEM presos; (ii) presos SEM borda (cauda sem nível + presos); (iii) direção sorteada (cd do estudo E2).

| lado | período | n | acerto | média R ± EP | (i) (n) | (ii) (n) | (iii) | ≥i+2EP | ≥ii+2EP | ≥iii+2EP | real > sorteios |
|---|---|---|---|---|---|---|---|---|---|---|---|
| compra+venda | treino | 37 | 65% | +0.257 ± +0.197 | +0.213 (57) | +0.088 (370) | -0.078 | não | não | não | 20/20 |
| compra+venda | validacao | 9 | 56% | -0.125 ± +0.351 | +0.139 (20) | -0.106 (154) | -0.137 | não | não | não | 11/20 |
| compra+venda | holdout | 6 | 83% | +0.919 ± +0.434 | +0.174 (13) | +0.160 (83) | -0.199 | não | não | sim | 20/20 |
| compra | treino | 21 | 67% | +0.156 ± +0.205 | +0.244 (25) | -0.006 (216) | -0.126 | não | não | não | 17/20 |
| compra | validacao | 6 | 50% | -0.229 ± +0.448 | +0.092 (15) | +0.026 (79) | -0.104 | não | não | não | 8/20 |
| compra | holdout | 5 | 80% | +0.845 ± +0.524 | +0.584 (6) | +0.218 (48) | -0.272 | não | não | sim | 20/20 |
| venda | treino | 16 | 62% | +0.390 ± +0.374 | +0.189 (32) | +0.219 (154) | -0.014 | não | não | não | 15/20 |
| venda | validacao | 3 | 67% | +0.082 ± +0.666 | +0.281 (5) | -0.244 (75) | -0.203 | não | não | não | 12/20 |
| venda | holdout | 1 | 100% | +1.293 ± - | -0.177 (7) | +0.079 (35) | +0.164 | não | não | não | 11/20 |

## Conclusão (escrita à mão depois da rodada; rodar o script de novo preserva esta seção)

1. **Presos no footprint (30 min e 5 min, os dois lados): REPROVADA.** Líquido negativo nos 3 períodos e nos 6 recortes: 30 min −0,35 / −0,32 / −0,41 R (n 3.040 / 808 / 629); 5 min −0,72 / −0,60 / −0,60 R (n 16.355 / 7.502 / 4.883). Amostra não é o problema: são 6.396 eventos confirmados em 30 min e 33.139 em 5 min.
2. **Bruto (sem taxa) é zero:** 30 min −0,03 / +0,02 / −0,04 R; 5 min −0,19 / −0,09 / −0,07 R. O R mediano é 0,26% (30 min) e 0,15% (5 min); entrada maker + stop taker custam 0,37 R e 0,62 R por trade. Não há vantagem bruta para o custo comer: o custo só a torna negativa.
3. **O nó não acrescenta nada ao lugar:** o nível sorteado no mesmo terço da mesma vela (a) dá o mesmo resultado (30 min −0,37 / −0,47 / −0,40; 5 min −0,66 / −0,60 / −0,58). No 5 min o sorteado é até um pouco melhor que o nó. O que existe é o efeito genérico "reteste da ponta de uma vela que se afastou", não o volume preso.
4. O real bate o nó NÃO abandonado (b) e a direção sorteada (c) por ~0,1–0,2 R no treino e na validação (e fica acima de 18–20 dos 20 sorteios), mas isso vem do lugar (o mesmo vale para o nível sorteado) e não leva o líquido a positivo; no holdout do 30 min nem isso (−0,41 contra −0,40 do sorteado).
5. Ano a ano o 30 min fica entre −0,28 e −0,45 R em todos os anos de 2020 a 2026, compra e venda iguais: não é efeito de tendência nem de regime.
6. **E2 + presos 30 min (principal): INCONCLUSIVA por amostra** (n 23 / 8 / 12; +0,27 / +0,12 / +0,37 R). Não fica 2 EP acima de nenhum controle em nenhum período; contra a própria E2 sem presos (i) a diferença é de +0,05 R no treino (+0,27 contra +0,22) e negativa no holdout. Os presos não filtram a E2; só cortam 70% da amostra. E2 + presos 5 min confirmados (informativo): REPROVADA no treino (não passa os controles).
7. Leitura honesta: com o histórico inteiro (6,5 anos, 3,4 milhões de minutos), "presos" como nó absorvido + abandono, operado no reteste com stop além da vela e alvo 2R, é sorteio antes de custo e perda depois. Pela regra da ressalva de docs/tradeiros/presos_footprint.md 5.4, a leitura de presos pelo footprint cai neste projeto como gatilho; não insistir com outro corte (fator, BTC mínimo, abandono, stop) sem hipótese nova.
8. Fica de pé, como antes, só a TPO E2 sozinha (inconclusiva por amostra). Os presos podem continuar no conselho apenas como etiqueta de contexto, com o rótulo "medido: sem vantagem (2020–2026)". O footprint baixado (dados/negocios/bybit, 699 MB, sem buraco de 2020-03-25 a 2026-10-19) serve para medir o VP V2 (delta por nível no composto) do plano sem novo download.
