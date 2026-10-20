# Estudo Fluxo D — nódulo abandonado (presos pelo footprint) — resultado

Gerado por `scripts/estudo_presos_footprint.py` em 2026-10-20 14:54 UTC. Regra e critério no docstring (escritos antes de rodar; nenhum parâmetro iterado). Negócios da Bybit BTCUSDT linear, 10/08–08/09/2026.

## Veredito pelo critério escrito antes

- **5m × P**: reprovada — compra_presa: n=0 < 40 (inconclusivo); venda_presa: n=0 < 40 (inconclusivo); J1: líquido - (n=0); J1: 1R -% < (a) -% + 10; J1: não está 2 EP acima de (a)
- **5m × T**: reprovada — compra_presa: n=8 < 40 (inconclusivo); venda_presa: n=8 < 40 (inconclusivo); J1: não está 2 EP acima de (a); J1: não está 2 EP acima de (c); J2: líquido -1.748 (n=9)
- **30m × P**: reprovada — compra_presa: n=0 < 40 (inconclusivo); venda_presa: n=1 < 40 (inconclusivo); J1: líquido - (n=0); J1: 1R -% < (a) -% + 10; J1: não está 2 EP acima de (a)
- **30m × T**: reprovada — compra_presa: n=1 < 40 (inconclusivo); venda_presa: n=2 < 40 (inconclusivo); J1: líquido - (n=0); J1: 1R -% < (a) -% + 10; J1: não está 2 EP acima de (a)

## Conclusão (escrita à mão depois da rodada; o script regenera o resto do arquivo, não esta seção)

**Fluxo D — não aprovada nas 4 combinações; formalmente inconclusiva por amostra, e o que existe aponta contra.**
1. A regra escrita é rara: no 5 min há 1.283 nódulos em 30 dias (~43/dia), mas só 74 viram presos (absorvido + abandonado) e 16 chegam à entrada; no 30 min são 20 e 3. Nenhum lado chega aos 40 trades exigidos.
2. O gargalo é o abandono: dos 230 nódulos compradores absorvidos no 5 min, 33 têm as 2 barras seguintes fechando ≥ 0,3% abaixo (57 se bastasse uma das duas). O piso de 500 mil USD não corta nada: a mediana do nódulo é 4,5 mi USD. Depois do abandono, 24 dos 74 não voltam ao nível em 24 h e 20 voltam fora da sessão.
3. Variante P (plano 2.5: stop ≥ 0,4% e alvo ≥ 2R): 0 trades no 5 min (o stop típico é 0,24%) e 1 no 30 min. Como aviso, ela quase nunca sai.
4. Variante T (alvo 1R) no 5 min: 16 trades, 1R antes do stop em 25%, −1,13 R ± 0,26 por trade. O nível sorteado da mesma barra (a) dá 23% e −1,15 R: o nódulo não acrescenta os 10 pontos exigidos. Fica abaixo também da direção sorteada (c), com −0,55 R.
5. O controle (b), nódulo igual NÃO preso, bate 1R mais vezes (41,5%, −0,78 R, n=284) que o preso: o contrário da hipótese.
6. Custo: com stop de 0,24%, a entrada a mercado e a saída custam ~0,4 R por trade. Mesmo com acerto de sorteio, o 5 min não paga.
7. Por janela, J2 tem 9 trades em −1,75 R; por lado, compradores presos −0,91 R (n=8) e vendedores presos −1,35 R (n=8).
8. Pela regra do plano ("se reprovar nos 30 dias, não se gasta coleta"), os 60–90 dias de 2020–2026 NÃO foram baixados. Com ~0,5 trade por dia, chegar a 40 por lado pediria ~150 dias só para poder ler o resultado.

## Funil

| TF | candidatos D (nódulo+absorvido+abandonado) | com entrada | entrada P (stop ≥ 0,4% e alvo ≥ 2R) | controle (a) entradas | controle (b) candidatos | (b) entradas |
|---|---|---|---|---|---|---|
| 5m | 74 | 16 | 0 | 247 | 1209 | 284 |
| 30m | 20 | 3 | 1 | 19 | 307 | 65 |

## Por janela (R líquido por trade; controle (c) = média de 20 sorteios de direção na mesma entrada)

P = plano 2.5 (stop ≥ 0,4%, alvo ≥ 2R, 50% no 1R, stop na entrada). T = Tradeiros (alvo 1R, sai inteiro). (a) = nível sorteado da mesma barra, 20 sorteios por evento (n conta todos os sorteios). (b) = nódulo igual não preso.

| TF | variante | grupo | janela | n | 1R antes do stop | média R ± EP | controle (c) direção |
|---|---|---|---|---|---|---|---|
| 5m | P | D | J1 | 0 | -% | - ± 0.000 | - |
| 5m | P | (a) nível sorteado | J1 | 0 | -% | - | |
| 5m | P | (b) não preso | J1 | 0 | -% | - | |
| 5m | P | D | J2 | 0 | -% | - ± 0.000 | - |
| 5m | P | (a) nível sorteado | J2 | 6 | +0.0% | -1.357 | |
| 5m | P | (b) não preso | J2 | 2 | +100.0% | +1.124 | |
| 5m | P | D | J3 | 0 | -% | - ± 0.000 | - |
| 5m | P | (a) nível sorteado | J3 | 0 | -% | - | |
| 5m | P | (b) não preso | J3 | 1 | +0.0% | -1.231 | |
| 5m | P | D | 30 dias | 0 | -% | - ± 0.000 | - |
| 5m | P | (a) nível sorteado | 30 dias | 6 | +0.0% | -1.357 | |
| 5m | P | (b) não preso | 30 dias | 3 | +66.7% | +0.339 | |
| 5m | T | D | J1 | 1 | +100.0% | +0.589 ± 0.000 | -0.418 |
| 5m | T | (a) nível sorteado | J1 | 32 | +18.8% | -0.481 | |
| 5m | T | (b) não preso | J1 | 64 | +39.1% | -0.854 | |
| 5m | T | D | J2 | 9 | +0.0% | -1.748 ± 0.114 | -0.671 |
| 5m | T | (a) nível sorteado | J2 | 140 | +10.7% | -1.602 | |
| 5m | T | (b) não preso | J2 | 111 | +43.2% | -0.698 | |
| 5m | T | D | J3 | 6 | +50.0% | -0.492 ± 0.473 | -0.394 |
| 5m | T | (a) nível sorteado | J3 | 75 | +48.0% | -0.586 | |
| 5m | T | (b) não preso | J3 | 109 | +41.3% | -0.822 | |
| 5m | T | D | 30 dias | 16 | +25.0% | -1.131 ± 0.262 | -0.551 |
| 5m | T | (a) nível sorteado | 30 dias | 247 | +23.1% | -1.148 | |
| 5m | T | (b) não preso | 30 dias | 284 | +41.5% | -0.781 | |
| 30m | P | D | J1 | 0 | -% | - ± 0.000 | - |
| 30m | P | (a) nível sorteado | J1 | 0 | -% | - | |
| 30m | P | (b) não preso | J1 | 0 | -% | - | |
| 30m | P | D | J2 | 0 | -% | - ± 0.000 | - |
| 30m | P | (a) nível sorteado | J2 | 0 | -% | - | |
| 30m | P | (b) não preso | J2 | 0 | -% | - | |
| 30m | P | D | J3 | 1 | +0.0% | -0.056 ± 0.000 | -0.128 |
| 30m | P | (a) nível sorteado | J3 | 11 | +0.0% | -1.129 | |
| 30m | P | (b) não preso | J3 | 1 | +0.0% | -1.369 | |
| 30m | P | D | 30 dias | 1 | +0.0% | -0.056 ± 0.000 | -0.128 |
| 30m | P | (a) nível sorteado | 30 dias | 11 | +0.0% | -1.129 | |
| 30m | P | (b) não preso | 30 dias | 1 | +0.0% | -1.369 | |
| 30m | T | D | J1 | 0 | -% | - ± 0.000 | - |
| 30m | T | (a) nível sorteado | J1 | 0 | -% | - | |
| 30m | T | (b) não preso | J1 | 16 | +56.2% | -0.373 | |
| 30m | T | D | J2 | 1 | +0.0% | -1.225 ± 0.000 | -0.184 |
| 30m | T | (a) nível sorteado | J2 | 0 | -% | - | |
| 30m | T | (b) não preso | J2 | 22 | +45.5% | -0.422 | |
| 30m | T | D | J3 | 2 | +0.0% | -1.105 ± 1.049 | -0.535 |
| 30m | T | (a) nível sorteado | J3 | 19 | +0.0% | -1.561 | |
| 30m | T | (b) não preso | J3 | 27 | +37.0% | -0.607 | |
| 30m | T | D | 30 dias | 3 | +0.0% | -1.145 ± 0.607 | -0.418 |
| 30m | T | (a) nível sorteado | 30 dias | 19 | +0.0% | -1.561 | |
| 30m | T | (b) não preso | 30 dias | 65 | +44.6% | -0.487 | |

## Por lado (30 dias)

| TF | variante | grupo | lado | n | 1R antes do stop | média R |
|---|---|---|---|---|---|---|
| 5m | P | D | compra_presa | 0 | -% | - |
| 5m | P | a | compra_presa | 0 | -% | - |
| 5m | P | b | compra_presa | 0 | -% | - |
| 5m | P | D | venda_presa | 0 | -% | - |
| 5m | P | a | venda_presa | 6 | +0.0% | -1.357 |
| 5m | P | b | venda_presa | 3 | +66.7% | +0.339 |
| 5m | T | D | compra_presa | 8 | +37.5% | -0.910 |
| 5m | T | a | compra_presa | 137 | +28.5% | -1.088 |
| 5m | T | b | compra_presa | 148 | +38.5% | -0.848 |
| 5m | T | D | venda_presa | 8 | +12.5% | -1.351 |
| 5m | T | a | venda_presa | 110 | +16.4% | -1.224 |
| 5m | T | b | venda_presa | 136 | +44.9% | -0.707 |
| 30m | P | D | compra_presa | 0 | -% | - |
| 30m | P | a | compra_presa | 0 | -% | - |
| 30m | P | b | compra_presa | 1 | +0.0% | -1.369 |
| 30m | P | D | venda_presa | 1 | +0.0% | -0.056 |
| 30m | P | a | venda_presa | 11 | +0.0% | -1.129 |
| 30m | P | b | venda_presa | 0 | -% | - |
| 30m | T | D | compra_presa | 1 | +0.0% | -1.225 |
| 30m | T | a | compra_presa | 0 | -% | - |
| 30m | T | b | compra_presa | 41 | +51.2% | -0.375 |
| 30m | T | D | venda_presa | 2 | +0.0% | -1.105 |
| 30m | T | a | venda_presa | 19 | +0.0% | -1.561 |
| 30m | T | b | venda_presa | 24 | +33.3% | -0.679 |

## Como saíram (grupo D)

| TF | variante | n | alvo | entrada (zero a zero) | stop | prazo | stop médio % | RR do alvo P médio |
|---|---|---|---|---|---|---|---|---|
| 5m | T | 16 | 4 | 0 | 12 | 0 | 0.24% | 3.63 |
| 30m | P | 1 | 0 | 0 | 0 | 1 | 1.03% | 2.88 |
| 30m | T | 3 | 0 | 0 | 2 | 1 | 0.61% | 5.44 |
