# Estudo 2 dos níveis de TPO — composto, desvio, toque virgem, escada e presos (BTCUSDT 15m, 2020-01 a 2026-09)

Gerado por `scripts/estudo_niveis_tpo_2.py`. Um toque por linha em `data/estudo_niveis_tpo_2.csv`. Complementa `data/estudo_niveis_tpo_resumo.md` (5 min), que deu 0 de 180.

## Regra exata

```
SEGUNDO ESTUDO DOS NÍVEIS DE TPO — as hipóteses que o primeiro (scripts/estudo_niveis_tpo.py, 5 min) não cobriu.
BTCUSDT 15 min (Binance), 2020-01 a 2026-09. Critério escrito ANTES de rodar; nenhum parâmetro foi iterado.

Base comum (vale para H1..H5):
  - Composto = merge dos 10 dias anteriores (core/range_tradeiros.contexto com range_adaptativo=False, n_dias=10):
    VAL, VAH e POC conhecidos à meia-noite UTC do dia D. H1 também mede o merge ADAPTATIVO (contexto_adaptativo).
  - Controle: 6 níveis sorteados por dia, uniformes em [mínima, máxima] dos 10 dias anteriores (semente fixa).
  - Toque: candle de 15 min de D com low <= nível <= high e o fechamento de algum dos 16 candles anteriores (4 h)
    a >= 0,5% do nível. Só o PRIMEIRO toque assim de cada nível por dia. "Chegada" = lado do fechamento mais
    distante nas 4 h (acima / abaixo).
  - Direção do trade: VAL -> compra (sempre); VAH -> venda (sempre); POC e controle -> reação (chegou de cima ->
    compra; de baixo -> venda). O controle também é medido como "compra em nível sorteado" e "venda em nível
    sorteado" sem olhar a chegada (régua para VAL/VAH).
  - Reação: R = 1% e 2% do nível. Corrida 1:1 = anda R a favor antes de R contra; 2:1 = 2R a favor antes de 1R
    contra. Limite 192 candles (2 dias); sem decisão = neutro (fora de p). Pessimista: favor e contra no mesmo
    candle -> contra; o próprio candle do toque já conta para o stop (favor só a partir do candle seguinte).
  - Custo de ida e volta 0,06% = 0,06 R (R=1%) e 0,03 R (R=2%). Bruto 1:1 = 2p-1; 2:1 = 3p-1. Líquido = bruto - custo.
  - ★ = p da linha >= 2 EP acima da linha de controle correspondente (mesmo período, R e corrida); ▼ = 2 EP abaixo.
  - Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09 (H5: treino começa em
    2020-07-20, quando começa o long/short da Bybit).
  - CRITÉRIO DE APROVAÇÃO: líquido > 0 nos 3 períodos com >= 30 toques decididos em cada período.

H1 Tempo maior: VAL compra, VAH venda, POC reação, nos dois compostos (fixo 10 dias e adaptativo); também só nos
   dias em que o range é "válido" (ctx.valido: equilíbrio).
H2 Desvio × dentro (composto fixo): toque no VAL dividido em (a) DESVIO CONFIRMADO = algum dos 16 candles
   anteriores fechou ABAIXO do VAL e o candle do toque fechou de volta >= VAL — como a confirmação só existe no
   fechamento, a ENTRADA é no fechamento desse candle (R medido a partir dele, favor e contra desde o candle seguinte);
   (b) DENTRO = nenhum fechamento abaixo do VAL nas 4 h e chegada de cima, entrada no nível; (c) FORA = algum dos 16
   candles anteriores fechou abaixo do VAL, sem exigir reentrada, entrada no nível ((a) está contido em (c)).
   VAH espelhado. Controle com as MESMAS bandeiras e entradas em relação ao nível sorteado.
   Nota: a primeira rodada (20/10, 09:40) definia (a) com entrada no NÍVEL condicionada ao fechamento do mesmo
   candle — olhar o futuro. O artefato apareceu no controle (nível sorteado + "reentrou": líquido > 0 nos 3
   períodos, até +0,24 R). A regra foi corrigida ANTES de qualquer leitura das hipóteses e vale igual para controle e
   níveis; nada mais mudou.
H3 Toque virgem (composto fixo): nº de toques anteriores no nível desde o início de D-3 até o candle anterior ao
   toque (um toque conta quando o preço encosta no nível depois de ter fechado a >= 0,5% dele): 0 (virgem), 1, 2+.
   Controle quebrado igual.
H4 Escada (composto fixo): 5 limitadas em nível ± 0,25% (degraus de 0,125%), armadas a partir do candle do toque,
   preenchidas quando o candle alcança o preço (compra: low <= preço). Stop = médio × (1 - R), alvo = médio ×
   (1 + mult·R), recalculados a cada preenchimento. Favor não conta no candle em que houve preenchimento. Resultado
   em R do médio por unidade preenchida (e também por unidade cheia = × fração preenchida); custo 0,06% por unidade.
   Comparado com a entrada única no nível (H1) e com a escada em nível sorteado.
H5 Presos (composto fixo, desde 2020-07-20): long/short de contas da Bybit (1 h, hora fechada) contra a mediana dos
   30 dias anteriores: VAL com vendidos presos (lsr < mediana) × sem; VAH com comprados presos (lsr > mediana) × sem.
   Também OI subindo nas 6 h anteriores × caindo, e funding "do lado" (VAL: funding < mediana de 30 d; VAH: > mediana).
   Controle: compra/venda em nível sorteado com as mesmas bandeiras.

Saídas: data/estudo_niveis_tpo_2.csv (um toque por linha) e data/estudo_niveis_tpo_2_resumo.md.
```

## Volume

| período | dias | toques (todos) | VAL/VAH/POC fixo10 | VAL/VAH/POC adapt | controle |
|---|---:|---:|---:|---:|---:|
| treino | 1392 | 6130 | 1277 | 2500 | 2353 |
| validacao | 520 | 2271 | 483 | 918 | 870 |
| holdout | 399 | 1692 | 349 | 664 | 679 |

- Composto fixo: largura média do valor 6.78% do POC; range válido (equilíbrio) em 10% dos dias. Composto adaptativo: 2.0 dias em média.
- R=1%: sem decisão em 2 dias: 0.8% (1:1), 3.8% (2:1); escada: fração preenchida média 95%.
- R=2%: sem decisão em 2 dias: 10.6% (1:1), 24.8% (2:1); escada: fração preenchida média 97%.

## Veredito pelo critério escrito antes

- **H1 Tempo maior — composto fixo10**: **0 de 16** combinações com líquido > 0 nos 3 períodos (≥ 30 decididos por período). Melhor pior-período: VAL compra R=2% 1:1 (+0.025 / -0.023 / -0.040 R). ★ 4 / ▼ 5 em 72 testes contra o controle.
- **H1 Tempo maior — composto adapt**: **0 de 24** combinações com líquido > 0 nos 3 períodos (≥ 30 decididos por período). Melhor pior-período: POC reação de cima (compra) R=1% 2:1 (-0.028 / +0.024 / +0.047 R). ★ 1 / ▼ 2 em 72 testes contra o controle.
- **H2 Desvio × dentro (composto fixo10)**: **2 de 13** combinações com líquido > 0 nos 3 períodos (≥ 30 decididos por período). Melhor pior-período: VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível R=1% 2:1 (+0.033 / +0.162 / +0.111 R). ★ 0 / ▼ 4 em 72 testes contra o controle.
- **H3 Toque virgem (composto fixo10)**: **0 de 12** combinações com líquido > 0 nos 3 períodos (≥ 30 decididos por período). Melhor pior-período: VAL compra, toques 2+ (3º toque ou mais) R=2% 1:1 (+0.006 / +0.011 / -0.044 R). ★ 5 / ▼ 8 em 108 testes contra o controle.
- **H4 Escada de 5 limitadas (composto fixo10)**: **0 de 16** combinações com líquido > 0 nos 3 períodos (≥ 30 decididos por período). Melhor pior-período: VAL compra R=2% 1:1 (+0.025 / -0.023 / -0.040 R). ★ 3 / ▼ 0 em 48 testes contra o controle.
- **H5 Presos (composto fixo10, desde 2020-07-20)**: **1 de 36** combinações com líquido > 0 nos 3 períodos (≥ 30 decididos por período). Melhor pior-período: VAL compra, funding não R=2% 1:1 (+0.115 / +0.130 / +0.023 R). ★ 1 / ▼ 1 em 144 testes contra o controle.

## Conclusão

(prosa escrita depois de rodar; nenhum parâmetro foi alterado depois de ver o holdout — a única mudança foi a correção
do olhar-futuro da H2a, descrita na regra, aplicada igual ao controle)

1. **Nenhuma das cinco hipóteses passa.** De 117 combinações linha×R×corrida com amostra, 3 deram líquido > 0 nos 3
   períodos (2 na H2, 1 na H5) e nenhuma ficou 2 EP acima do controle sorteado em período algum; com 117 testes,
   3 positivas é o esperado do acaso.
2. **H1 (15 min, R 1–2%, 2 dias): VAL/VAH/POC do composto de 10 dias = nível sorteado** (0 de 16). O composto adaptativo
   quase sempre vira o perfil de ontem (1 dia em metade dos dias, 2,0 em média) e também dá 0 de 24. O range "válido"
   pelo critério de equilíbrio existe em só 10% dos dias (n 11–40 por período: sem leitura). Vender a VAH é pior que
   comprar o VAL em todo período, e a mesma assimetria está no controle (viés de alta de 2020–23), não no nível.
3. **H2 (desvio × dentro): sem vantagem.** A primeira rodada tinha olhar-futuro na "reentrada" e o controle sorteado
   ficou positivo nos 3 períodos (artefato); corrigida, o desvio confirmado tem 71/26/20 toques no VAL (amostra
   insuficiente) e no holdout reagiu em 25% (▼). "Dentro" dá −0,010/−0,054/−0,159 R no melhor formato.
4. A única linha com 3 períodos positivos é **"VAL com fechamento abaixo nas 4 h, entrada no nível"** em 2 dos 4
   formatos (R=1% 2:1: +0,033/+0,162/+0,111; R=2% 1:1: +0,085/+0,027/+0,149), n = 225, sem ★ (0,6–1,5 EP acima do
   controle) e com os outros 2 formatos negativos. É candidato a um reteste pré-registrado em dados novos, não aprovação.
5. **H3 (toque virgem): 0 de 12.** O 1º toque tem 64/25/18 toques no VAL (sem leitura); 2º e 3º+ não diferem do controle
   com o mesmo número de toques; não aparece o gradiente "cada toque enfraquece a borda".
6. **H4 (escada de 5 limitadas em ±0,25%): é a mesma operação que a entrada única** quando R é 1–2%: 99–100% dos toques
   com o mesmo resultado em 1:1, preenchimento médio 95–98%, 0 de 16. A zona é estreita demais para o R; a tese das
   fatias largas (1,5 ATR, 11/09) não foi testada aqui.
7. **H5 (presos): lsr contra a mediana não separa** VAL nem VAH (vendidos presos no VAL, R=1% 1:1: −0,014/−0,097/−0,239 R;
   comprados presos na VAH: −0,175/−0,323/+0,107). OI subindo e funding "do lado" também não; a única linha positiva
   (VAL com funding NÃO do lado, R=2% 1:1) é o complemento da hipótese, 1 em 36, sem ★.
8. Leitura geral: o controle mostra o drift (compra em nível sorteado 47–52% de reação, venda 41–51%) e cada linha de
   nível acompanha o controle do mesmo lado. Resultado negativo é resultado: não ligar nada disso sem hipótese nova.


## H1 Tempo maior — composto fixo10

### R = 1% (custo 0.06 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 2353 | 2337 | 47.5±1.0 | -0.109 | 32.5±1.0 | -0.084 |
| controle: venda em nível sorteado | 2353 | 2337 | 40.7±1.0 | -0.247 | 27.7±0.9 | -0.228 |
| controle: reação de cima (compra) | 1208 | 1199 | 50.6±1.4 | -0.047 | 33.9±1.4 | -0.044 |
| controle: reação de baixo (venda) | 1145 | 1138 | 45.2±1.5 | -0.157 | 29.6±1.4 | -0.172 |
| VAL compra | 359 | 352 | 53.7±2.7★ | +0.014 | 34.4±2.6 | -0.027 |
| VAH venda | 398 | 397 | 41.8±2.5 | -0.224 | 25.0±2.2 | -0.310 |
| POC reação de cima (compra) | 276 | 274 | 52.2±3.0 | -0.016 | 34.6±2.9 | -0.023 |
| POC reação de baixo (venda) | 244 | 240 | 56.7±3.2★ | +0.073 | 37.2±3.2★ | +0.057 |
| VAL compra, só range válido | 40 | 36 | 44.4±8.3 | -0.171 | 28.1±7.9 | -0.216 |
| VAH venda, só range válido | 41 | 41 | 41.5±7.7 | -0.231 | 24.4±6.7 | -0.328 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 870 | 868 | 48.3±1.7 | -0.095 | 31.6±1.6 | -0.112 |
| controle: venda em nível sorteado | 870 | 868 | 45.0±1.7 | -0.159 | 29.3±1.6 | -0.181 |
| controle: reação de cima (compra) | 466 | 464 | 49.1±2.3 | -0.077 | 31.6±2.2 | -0.113 |
| controle: reação de baixo (venda) | 404 | 404 | 46.5±2.5 | -0.129 | 28.4±2.3 | -0.208 |
| VAL compra | 144 | 143 | 50.3±4.2 | -0.053 | 35.7±4.0 | +0.011 |
| VAH venda | 144 | 144 | 41.0±4.1 | -0.241 | 29.2±3.9 | -0.184 |
| POC reação de cima (compra) | 95 | 95 | 45.3±5.1 | -0.155 | 35.1±4.9 | -0.007 |
| POC reação de baixo (venda) | 100 | 99 | 48.5±5.0 | -0.090 | 28.7±4.7 | -0.198 |
| VAL compra, só range válido | 17 | 17 | 52.9±12.1 | -0.001 | 35.3±11.6 | -0.001 |
| VAH venda, só range válido | 17 | 17 | 23.5±10.3▼ | -0.589 | 6.7±6.4▼ | -0.860 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 679 | 675 | 48.9±1.9 | -0.082 | 33.0±1.9 | -0.071 |
| controle: venda em nível sorteado | 679 | 675 | 47.6±1.9 | -0.109 | 32.1±1.8 | -0.096 |
| controle: reação de cima (compra) | 350 | 348 | 48.6±2.7 | -0.089 | 31.8±2.6 | -0.105 |
| controle: reação de baixo (venda) | 329 | 327 | 49.2±2.8 | -0.075 | 33.3±2.7 | -0.060 |
| VAL compra | 113 | 113 | 46.0±4.7 | -0.140 | 30.3±4.4 | -0.152 |
| VAH venda | 103 | 101 | 52.5±5.0 | -0.010 | 33.3±5.0 | -0.060 |
| POC reação de cima (compra) | 66 | 64 | 53.1±6.2 | +0.003 | 33.9±6.0 | -0.044 |
| POC reação de baixo (venda) | 67 | 67 | 49.3±6.1 | -0.075 | 35.9±6.0 | +0.018 |
| VAL compra, só range válido | 11 | 11 | 27.3±13.4 | -0.515 | 0.0±0.0▼ | -1.060 |
| VAH venda, só range válido | 13 | 12 | 50.0±14.4 | -0.060 | 25.0±15.3 | -0.310 |

### R = 2% (custo 0.03 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 2353 | 2133 | 52.4±1.1 | +0.018 | 32.2±1.1 | -0.064 |
| controle: venda em nível sorteado | 2353 | 2131 | 44.9±1.1 | -0.133 | 27.2±1.0 | -0.215 |
| controle: reação de cima (compra) | 1208 | 1086 | 49.6±1.5 | -0.037 | 30.9±1.5 | -0.104 |
| controle: reação de baixo (venda) | 1145 | 1045 | 43.3±1.5 | -0.165 | 26.1±1.4 | -0.248 |
| VAL compra | 359 | 311 | 52.7±2.8 | +0.025 | 35.6±2.9 | +0.037 |
| VAH venda | 398 | 361 | 41.3±2.6 | -0.205 | 25.5±2.4 | -0.264 |
| POC reação de cima (compra) | 276 | 254 | 51.2±3.1 | -0.006 | 33.0±3.1 | -0.039 |
| POC reação de baixo (venda) | 244 | 222 | 48.6±3.4 | -0.057 | 29.2±3.3 | -0.155 |
| VAL compra, só range válido | 40 | 24 | 58.3±10.1 | +0.137 | 45.0±11.1 | +0.320 |
| VAH venda, só range válido | 41 | 38 | 36.8±7.8 | -0.293 | 19.4±7.1 | -0.449 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 870 | 790 | 50.6±1.8 | -0.017 | 31.8±1.8 | -0.076 |
| controle: venda em nível sorteado | 870 | 789 | 47.7±1.8 | -0.077 | 26.1±1.7 | -0.246 |
| controle: reação de cima (compra) | 466 | 438 | 45.9±2.4 | -0.112 | 27.1±2.3 | -0.218 |
| controle: reação de baixo (venda) | 404 | 352 | 42.3±2.6 | -0.183 | 22.1±2.5 | -0.367 |
| VAL compra | 144 | 135 | 50.4±4.3 | -0.023 | 33.6±4.6 | -0.021 |
| VAH venda | 144 | 124 | 43.5±4.5 | -0.159 | 26.7±4.3 | -0.230 |
| POC reação de cima (compra) | 95 | 88 | 46.6±5.3 | -0.098 | 27.5±5.4 | -0.204 |
| POC reação de baixo (venda) | 100 | 85 | 50.6±5.4 | -0.018 | 35.3±5.8★ | +0.029 |
| VAL compra, só range válido | 17 | 16 | 56.2±12.4 | +0.095 | 36.4±14.5 | +0.061 |
| VAH venda, só range válido | 17 | 12 | 16.7±10.8▼ | -0.697 | 16.7±10.8 | -0.530 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 679 | 561 | 48.8±2.1 | -0.053 | 24.8±2.1 | -0.285 |
| controle: venda em nível sorteado | 679 | 564 | 50.9±2.1 | -0.012 | 27.5±2.2 | -0.205 |
| controle: reação de cima (compra) | 350 | 295 | 47.8±2.9 | -0.074 | 21.5±2.8 | -0.386 |
| controle: reação de baixo (venda) | 329 | 266 | 50.0±3.1 | -0.030 | 28.6±3.1 | -0.171 |
| VAL compra | 113 | 101 | 49.5±5.0 | -0.040 | 24.7±5.0 | -0.290 |
| VAH venda | 103 | 75 | 52.0±5.8 | +0.010 | 28.1±6.0 | -0.188 |
| POC reação de cima (compra) | 66 | 52 | 48.1±6.9 | -0.068 | 14.3±5.9 | -0.601 |
| POC reação de baixo (venda) | 67 | 51 | 58.8±6.9 | +0.146 | 39.5±7.9 | +0.154 |
| VAL compra, só range válido | 11 | 9 | 11.1±10.5▼ | -0.808 | 11.1±10.5 | -0.697 |
| VAH venda, só range válido | 13 | 7 | 42.9±18.7 | -0.173 | 20.0±17.9 | -0.430 |

### Consistência nos 3 períodos — H1 Tempo maior — composto fixo10

Só linhas com ≥ 30 decididos em cada período. `min` = pior período. 

**Líquido positivo nos 3 períodos: 0 de 16 combinações linha×R×corrida.**

Top 5 por pior período:

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2% | 1:1 | VAL compra | 616 | +0.025 | -0.023 | -0.040 | -0.040 |  |
| 1% | 2:1 | POC reação de cima (compra) | 437 | -0.023 | -0.007 | -0.044 | -0.044 |  |
| 2% | 1:1 | POC reação de baixo (venda) | 411 | -0.057 | -0.018 | +0.146 | -0.057 |  |
| 1% | 1:1 | POC reação de baixo (venda) | 411 | +0.073 | -0.090 | -0.075 | -0.090 | ★ |
| 2% | 1:1 | POC reação de cima (compra) | 437 | -0.006 | -0.098 | -0.068 | -0.098 |  |

## H1 Tempo maior — composto adapt

### R = 1% (custo 0.06 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 2353 | 2337 | 47.5±1.0 | -0.109 | 32.5±1.0 | -0.084 |
| controle: venda em nível sorteado | 2353 | 2337 | 40.7±1.0 | -0.247 | 27.7±0.9 | -0.228 |
| controle: reação de cima (compra) | 1208 | 1199 | 50.6±1.4 | -0.047 | 33.9±1.4 | -0.044 |
| controle: reação de baixo (venda) | 1145 | 1138 | 45.2±1.5 | -0.157 | 29.6±1.4 | -0.172 |
| VAL compra | 786 | 779 | 48.5±1.8 | -0.090 | 32.2±1.7 | -0.094 |
| VAH venda | 819 | 814 | 46.3±1.7★ | -0.134 | 29.6±1.6 | -0.171 |
| POC reação de cima (compra) | 491 | 488 | 50.6±2.3 | -0.048 | 34.4±2.2 | -0.028 |
| POC reação de baixo (venda) | 404 | 396 | 48.2±2.5 | -0.095 | 32.0±2.4 | -0.101 |
| VAL compra, só range válido | 181 | 179 | 49.2±3.7 | -0.077 | 30.9±3.5 | -0.134 |
| VAH venda, só range válido | 201 | 198 | 44.9±3.5 | -0.161 | 28.6±3.3 | -0.203 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 870 | 868 | 48.3±1.7 | -0.095 | 31.6±1.6 | -0.112 |
| controle: venda em nível sorteado | 870 | 868 | 45.0±1.7 | -0.159 | 29.3±1.6 | -0.181 |
| controle: reação de cima (compra) | 466 | 464 | 49.1±2.3 | -0.077 | 31.6±2.2 | -0.113 |
| controle: reação de baixo (venda) | 404 | 404 | 46.5±2.5 | -0.129 | 28.4±2.3 | -0.208 |
| VAL compra | 283 | 282 | 48.6±3.0 | -0.088 | 31.3±2.8 | -0.122 |
| VAH venda | 312 | 311 | 46.9±2.8 | -0.121 | 30.3±2.6 | -0.152 |
| POC reação de cima (compra) | 159 | 158 | 52.5±4.0 | -0.009 | 36.1±3.9 | +0.024 |
| POC reação de baixo (venda) | 164 | 163 | 46.0±3.9 | -0.140 | 28.7±3.6 | -0.198 |
| VAL compra, só range válido | 74 | 74 | 39.2±5.7 | -0.276 | 27.1±5.3 | -0.246 |
| VAH venda, só range válido | 63 | 63 | 47.6±6.3 | -0.108 | 33.3±6.1 | -0.060 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 679 | 675 | 48.9±1.9 | -0.082 | 33.0±1.9 | -0.071 |
| controle: venda em nível sorteado | 679 | 675 | 47.6±1.9 | -0.109 | 32.1±1.8 | -0.096 |
| controle: reação de cima (compra) | 350 | 348 | 48.6±2.7 | -0.089 | 31.8±2.6 | -0.105 |
| controle: reação de baixo (venda) | 329 | 327 | 49.2±2.8 | -0.075 | 33.3±2.7 | -0.060 |
| VAL compra | 208 | 205 | 42.9±3.5 | -0.201 | 26.5±3.2 | -0.264 |
| VAH venda | 217 | 215 | 46.5±3.4 | -0.130 | 29.6±3.2 | -0.173 |
| POC reação de cima (compra) | 127 | 125 | 53.6±4.5 | +0.012 | 36.9±4.4 | +0.047 |
| POC reação de baixo (venda) | 112 | 111 | 54.1±4.7 | +0.021 | 39.3±4.7 | +0.118 |
| VAL compra, só range válido | 50 | 49 | 46.9±7.1 | -0.121 | 23.4±6.2 | -0.358 |
| VAH venda, só range válido | 56 | 56 | 50.0±6.7 | -0.060 | 28.8±6.3 | -0.195 |

### R = 2% (custo 0.03 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 2353 | 2133 | 52.4±1.1 | +0.018 | 32.2±1.1 | -0.064 |
| controle: venda em nível sorteado | 2353 | 2131 | 44.9±1.1 | -0.133 | 27.2±1.0 | -0.215 |
| controle: reação de cima (compra) | 1208 | 1086 | 49.6±1.5 | -0.037 | 30.9±1.5 | -0.104 |
| controle: reação de baixo (venda) | 1145 | 1045 | 43.3±1.5 | -0.165 | 26.1±1.4 | -0.248 |
| VAL compra | 786 | 729 | 50.1±1.9 | -0.029 | 32.6±1.9 | -0.053 |
| VAH venda | 819 | 741 | 46.4±1.8 | -0.102 | 28.0±1.8 | -0.191 |
| POC reação de cima (compra) | 491 | 447 | 51.7±2.4 | +0.004 | 29.7±2.3 | -0.139 |
| POC reação de baixo (venda) | 404 | 373 | 44.8±2.6 | -0.135 | 24.6±2.4 | -0.293 |
| VAL compra, só range válido | 181 | 161 | 47.8±3.9 | -0.073 | 32.3±4.1 | -0.060 |
| VAH venda, só range válido | 201 | 177 | 46.3±3.7 | -0.103 | 23.1±3.5 | -0.336 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 870 | 790 | 50.6±1.8 | -0.017 | 31.8±1.8 | -0.076 |
| controle: venda em nível sorteado | 870 | 789 | 47.7±1.8 | -0.077 | 26.1±1.7 | -0.246 |
| controle: reação de cima (compra) | 466 | 438 | 45.9±2.4 | -0.112 | 27.1±2.3 | -0.218 |
| controle: reação de baixo (venda) | 404 | 352 | 42.3±2.6 | -0.183 | 22.1±2.5 | -0.367 |
| VAL compra | 283 | 253 | 46.2±3.1 | -0.105 | 27.8±3.1 | -0.196 |
| VAH venda | 312 | 280 | 48.6±3.0 | -0.059 | 25.5±3.0 | -0.266 |
| POC reação de cima (compra) | 159 | 148 | 48.6±4.1 | -0.057 | 32.5±4.2 | -0.054 |
| POC reação de baixo (venda) | 164 | 145 | 42.8±4.1 | -0.175 | 26.4±4.0 | -0.237 |
| VAL compra, só range válido | 74 | 61 | 37.7±6.2▼ | -0.276 | 18.0±5.4▼ | -0.490 |
| VAH venda, só range válido | 63 | 57 | 47.4±6.6 | -0.083 | 24.4±6.7 | -0.298 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle: compra em nível sorteado | 679 | 561 | 48.8±2.1 | -0.053 | 24.8±2.1 | -0.285 |
| controle: venda em nível sorteado | 679 | 564 | 50.9±2.1 | -0.012 | 27.5±2.2 | -0.205 |
| controle: reação de cima (compra) | 350 | 295 | 47.8±2.9 | -0.074 | 21.5±2.8 | -0.386 |
| controle: reação de baixo (venda) | 329 | 266 | 50.0±3.1 | -0.030 | 28.6±3.1 | -0.171 |
| VAL compra | 208 | 182 | 40.7±3.6 | -0.217 | 20.1±3.3 | -0.426 |
| VAH venda | 217 | 180 | 45.6±3.7 | -0.119 | 23.9±3.6 | -0.312 |
| POC reação de cima (compra) | 127 | 109 | 49.5±4.8 | -0.039 | 21.6±4.8 | -0.381 |
| POC reação de baixo (venda) | 112 | 91 | 56.0±5.2 | +0.091 | 36.0±5.5 | +0.050 |
| VAL compra, só range válido | 50 | 43 | 39.5±7.5 | -0.239 | 18.2±6.7 | -0.485 |
| VAH venda, só range válido | 56 | 46 | 41.3±7.3 | -0.204 | 27.0±7.3 | -0.219 |

### Consistência nos 3 períodos — H1 Tempo maior — composto adapt

Só linhas com ≥ 30 decididos em cada período. `min` = pior período. 

**Líquido positivo nos 3 períodos: 0 de 24 combinações linha×R×corrida.**

Top 5 por pior período:

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1% | 2:1 | POC reação de cima (compra) | 777 | -0.028 | +0.024 | +0.047 | -0.028 |  |
| 1% | 1:1 | POC reação de cima (compra) | 777 | -0.048 | -0.009 | +0.012 | -0.048 |  |
| 2% | 1:1 | POC reação de cima (compra) | 777 | +0.004 | -0.057 | -0.039 | -0.057 |  |
| 2% | 1:1 | VAH venda | 1348 | -0.102 | -0.059 | -0.119 | -0.119 |  |
| 1% | 1:1 | VAH venda | 1348 | -0.134 | -0.121 | -0.130 | -0.134 | ★ |

## H2 Desvio × dentro (composto fixo10)

### R = 1% (custo 0.06 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra (a) fechou abaixo e reentrou [entrada no fechamento] | 624 | 621 | 54.4±2.0 | +0.029 | 38.8±2.0 | +0.103 |
| controle compra (b) de cima sem fechar abaixo | 1035 | 1026 | 51.8±1.6 | -0.025 | 34.5±1.5 | -0.025 |
| controle compra (c) fechou abaixo nas 4 h, entrada no nível | 1318 | 1311 | 44.2±1.4 | -0.175 | 31.0±1.3 | -0.130 |
| controle venda (a) fechou acima e reentrou [entrada no fechamento] | 569 | 564 | 50.5±2.1 | -0.049 | 34.3±2.0 | -0.031 |
| controle venda (b) de baixo sem fechar acima | 977 | 972 | 45.2±1.6 | -0.157 | 30.1±1.5 | -0.158 |
| controle venda (c) fechou acima nas 4 h, entrada no nível | 1376 | 1365 | 37.4±1.3 | -0.311 | 26.1±1.2 | -0.276 |
| VAL compra (a) DESVIO confirmado [entrada no fechamento] | 71 | 69 | 59.4±5.9 | +0.128 | 49.3±6.1 | +0.418 |
| VAL compra (b) DENTRO: de cima sem fechar abaixo | 232 | 230 | 57.0±3.3 | +0.079 | 33.3±3.2 | -0.060 |
| VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 127 | 122 | 47.5±4.5 | -0.109 | 36.4±4.4 | +0.033 |
| VAH venda (a) DESVIO confirmado [entrada no fechamento] | 90 | 90 | 48.9±5.3 | -0.082 | 29.2±4.8 | -0.184 |
| VAH venda (b) DENTRO: de baixo sem fechar acima | 212 | 212 | 42.5±3.4 | -0.211 | 26.2±3.1 | -0.274 |
| VAH venda (c) FORA: fechou acima nas 4 h, entrada no nível | 186 | 185 | 41.1±3.6 | -0.238 | 23.6±3.1 | -0.351 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra (a) fechou abaixo e reentrou [entrada no fechamento] | 235 | 235 | 49.4±3.3 | -0.073 | 30.3±3.0 | -0.152 |
| controle compra (b) de cima sem fechar abaixo | 395 | 393 | 48.9±2.5 | -0.083 | 33.5±2.4 | -0.055 |
| controle compra (c) fechou abaixo nas 4 h, entrada no nível | 475 | 475 | 47.8±2.3 | -0.104 | 30.0±2.1 | -0.160 |
| controle venda (a) fechou acima e reentrou [entrada no fechamento] | 246 | 243 | 49.4±3.2 | -0.072 | 34.3±3.1 | -0.031 |
| controle venda (b) de baixo sem fechar acima | 342 | 342 | 45.0±2.7 | -0.159 | 27.4±2.4 | -0.238 |
| controle venda (c) fechou acima nas 4 h, entrada no nível | 528 | 526 | 45.1±2.2 | -0.159 | 30.5±2.0 | -0.144 |
| VAL compra (a) DESVIO confirmado [entrada no fechamento] | 26 | 26 | 50.0±9.8 | -0.060 | 32.0±9.3 | -0.100 |
| VAL compra (b) DENTRO: de cima sem fechar abaixo | 89 | 88 | 48.9±5.3 | -0.083 | 32.6±5.1 | -0.083 |
| VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 55 | 55 | 52.7±6.7 | -0.005 | 40.7±6.7 | +0.162 |
| VAH venda (a) DESVIO confirmado [entrada no fechamento] | 28 | 28 | 32.1±8.8 | -0.417 | 25.9±8.4 | -0.282 |
| VAH venda (b) DENTRO: de baixo sem fechar acima | 84 | 84 | 39.3±5.3 | -0.274 | 29.1±5.1 | -0.187 |
| VAH venda (c) FORA: fechou acima nas 4 h, entrada no nível | 60 | 60 | 43.3±6.4 | -0.193 | 29.3±6.0 | -0.181 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra (a) fechou abaixo e reentrou [entrada no fechamento] | 184 | 184 | 48.9±3.7 | -0.082 | 36.4±3.6 | +0.031 |
| controle compra (b) de cima sem fechar abaixo | 309 | 307 | 47.2±2.8 | -0.115 | 31.4±2.7 | -0.119 |
| controle compra (c) fechou abaixo nas 4 h, entrada no nível | 370 | 368 | 50.3±2.6 | -0.055 | 34.3±2.5 | -0.031 |
| controle venda (a) fechou acima e reentrou [entrada no fechamento] | 190 | 189 | 52.9±3.6 | -0.002 | 35.4±3.6 | +0.001 |
| controle venda (b) de baixo sem fechar acima | 288 | 286 | 49.3±3.0 | -0.074 | 32.7±2.9 | -0.079 |
| controle venda (c) fechou acima nas 4 h, entrada no nível | 391 | 389 | 46.3±2.5 | -0.135 | 31.7±2.4 | -0.108 |
| VAL compra (a) DESVIO confirmado [entrada no fechamento] | 20 | 20 | 25.0±9.7▼ | -0.560 | 10.5±7.0▼ | -0.744 |
| VAL compra (b) DENTRO: de cima sem fechar abaixo | 70 | 70 | 42.9±5.9 | -0.203 | 25.0±5.3 | -0.310 |
| VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 43 | 43 | 51.2±7.6 | -0.037 | 39.0±7.6 | +0.111 |
| VAH venda (a) DESVIO confirmado [entrada no fechamento] | 18 | 18 | 55.6±11.7 | +0.051 | 47.1±12.1 | +0.352 |
| VAH venda (b) DENTRO: de baixo sem fechar acima | 66 | 64 | 53.1±6.2 | +0.003 | 32.1±6.2 | -0.096 |
| VAH venda (c) FORA: fechou acima nas 4 h, entrada no nível | 37 | 37 | 51.4±8.2 | -0.033 | 35.3±8.2 | -0.001 |

### R = 2% (custo 0.03 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra (a) fechou abaixo e reentrou [entrada no fechamento] | 624 | 577 | 54.9±2.1 | +0.069 | 33.4±2.1 | -0.028 |
| controle compra (b) de cima sem fechar abaixo | 1035 | 929 | 49.8±1.6 | -0.033 | 31.9±1.6 | -0.073 |
| controle compra (c) fechou abaixo nas 4 h, entrada no nível | 1318 | 1204 | 54.4±1.4 | +0.058 | 32.5±1.5 | -0.056 |
| controle venda (a) fechou acima e reentrou [entrada no fechamento] | 569 | 515 | 49.1±2.2 | -0.047 | 31.0±2.2 | -0.100 |
| controle venda (b) de baixo sem fechar acima | 977 | 891 | 43.4±1.7 | -0.161 | 27.0±1.6 | -0.219 |
| controle venda (c) fechou acima nas 4 h, entrada no nível | 1376 | 1240 | 45.9±1.4 | -0.112 | 27.3±1.3 | -0.212 |
| VAL compra (a) DESVIO confirmado [entrada no fechamento] | 71 | 67 | 59.7±6.0 | +0.164 | 32.7±6.3 | -0.048 |
| VAL compra (b) DENTRO: de cima sem fechar abaixo | 232 | 198 | 51.0±3.6 | -0.010 | 34.5±3.6 | +0.005 |
| VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 127 | 113 | 55.8±4.7 | +0.085 | 37.5±4.9 | +0.095 |
| VAH venda (a) DESVIO confirmado [entrada no fechamento] | 90 | 83 | 43.4±5.4 | -0.163 | 27.1±5.3 | -0.216 |
| VAH venda (b) DENTRO: de baixo sem fechar acima | 212 | 195 | 39.5±3.5 | -0.240 | 22.2±3.1 | -0.365 |
| VAH venda (c) FORA: fechou acima nas 4 h, entrada no nível | 186 | 166 | 43.4±3.8 | -0.163 | 29.5±3.7 | -0.144 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra (a) fechou abaixo e reentrou [entrada no fechamento] | 235 | 209 | 50.2±3.5 | -0.025 | 34.9±3.6 | +0.016 |
| controle compra (b) de cima sem fechar abaixo | 395 | 371 | 47.2±2.6 | -0.087 | 28.8±2.6 | -0.166 |
| controle compra (c) fechou abaixo nas 4 h, entrada no nível | 475 | 419 | 53.7±2.4 | +0.044 | 34.5±2.6 | +0.005 |
| controle venda (a) fechou acima e reentrou [entrada no fechamento] | 246 | 222 | 50.9±3.4 | -0.012 | 26.8±3.3 | -0.226 |
| controle venda (b) de baixo sem fechar acima | 342 | 302 | 41.4±2.8 | -0.202 | 22.2±2.6 | -0.365 |
| controle venda (c) fechou acima nas 4 h, entrada no nível | 528 | 487 | 51.5±2.3 | +0.001 | 28.6±2.3 | -0.172 |
| VAL compra (a) DESVIO confirmado [entrada no fechamento] | 26 | 24 | 54.2±10.2 | +0.053 | 33.3±11.1 | -0.030 |
| VAL compra (b) DENTRO: de cima sem fechar abaixo | 89 | 82 | 48.8±5.5 | -0.054 | 34.3±5.8 | -0.000 |
| VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 55 | 53 | 52.8±6.9 | +0.027 | 32.5±7.4 | -0.055 |
| VAH venda (a) DESVIO confirmado [entrada no fechamento] | 28 | 25 | 36.0±9.6 | -0.310 | 29.2±9.3 | -0.155 |
| VAH venda (b) DENTRO: de baixo sem fechar acima | 84 | 72 | 41.7±5.8 | -0.197 | 26.2±5.6 | -0.243 |
| VAH venda (c) FORA: fechou acima nas 4 h, entrada no nível | 60 | 52 | 46.2±6.9 | -0.107 | 27.3±6.7 | -0.212 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra (a) fechou abaixo e reentrou [entrada no fechamento] | 184 | 157 | 51.0±4.0 | -0.011 | 28.0±4.1 | -0.191 |
| controle compra (b) de cima sem fechar abaixo | 309 | 259 | 47.5±3.1 | -0.080 | 20.1±2.9 | -0.427 |
| controle compra (c) fechou abaixo nas 4 h, entrada no nível | 370 | 302 | 50.0±2.9 | -0.030 | 28.6±3.0 | -0.171 |
| controle venda (a) fechou acima e reentrou [entrada no fechamento] | 190 | 153 | 56.2±4.0 | +0.094 | 36.4±4.4 | +0.063 |
| controle venda (b) de baixo sem fechar acima | 288 | 232 | 48.3±3.3 | -0.064 | 27.2±3.3 | -0.213 |
| controle venda (c) fechou acima nas 4 h, entrada no nível | 391 | 332 | 52.7±2.7 | +0.024 | 27.7±2.8 | -0.199 |
| VAL compra (a) DESVIO confirmado [entrada no fechamento] | 20 | 17 | 23.5±10.3▼ | -0.559 | 0.0±0.0▼ | -1.030 |
| VAL compra (b) DENTRO: de cima sem fechar abaixo | 70 | 62 | 43.5±6.3 | -0.159 | 26.0±6.2 | -0.250 |
| VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 43 | 39 | 59.0±7.9 | +0.149 | 21.7±8.6 | -0.378 |
| VAH venda (a) DESVIO confirmado [entrada no fechamento] | 18 | 15 | 53.3±12.9 | +0.037 | 22.2±13.9 | -0.363 |
| VAH venda (b) DENTRO: de baixo sem fechar acima | 66 | 47 | 55.3±7.3 | +0.076 | 30.6±7.7 | -0.113 |
| VAH venda (c) FORA: fechou acima nas 4 h, entrada no nível | 37 | 28 | 46.4±9.4 | -0.101 | 23.8±9.3 | -0.316 |

### Consistência nos 3 períodos — H2 Desvio × dentro (composto fixo10)

Só linhas com ≥ 30 decididos em cada período. `min` = pior período. 

**Líquido positivo nos 3 períodos: 2 de 13 combinações linha×R×corrida.**

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1% | 2:1 | VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 225 | +0.033 | +0.162 | +0.111 | +0.033 |  |
| 2% | 1:1 | VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 225 | +0.085 | +0.027 | +0.149 | +0.027 |  |

Top 5 por pior período:

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1% | 2:1 | VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 225 | +0.033 | +0.162 | +0.111 | +0.033 |  |
| 2% | 1:1 | VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 225 | +0.085 | +0.027 | +0.149 | +0.027 |  |
| 1% | 1:1 | VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível | 225 | -0.109 | -0.005 | -0.037 | -0.109 |  |
| 2% | 1:1 | VAL compra (b) DENTRO: de cima sem fechar abaixo | 391 | -0.010 | -0.054 | -0.159 | -0.159 |  |
| 1% | 1:1 | VAL compra (b) DENTRO: de cima sem fechar abaixo | 391 | +0.079 | -0.083 | -0.203 | -0.203 |  |

## H3 Toque virgem (composto fixo10)

### R = 1% (custo 0.06 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, toques 0 (virgem) | 405 | 403 | 46.9±2.5 | -0.122 | 34.3±2.4 | -0.032 |
| controle venda, toques 0 (virgem) | 405 | 403 | 31.5±2.3 | -0.430 | 23.4±2.1 | -0.359 |
| controle reação, toques 0 (virgem) | 405 | 403 | 45.7±2.5 | -0.147 | 33.2±2.4 | -0.065 |
| controle compra, toques 1 (2º toque) | 308 | 303 | 46.2±2.9 | -0.136 | 32.6±2.7 | -0.081 |
| controle venda, toques 1 (2º toque) | 308 | 303 | 44.6±2.9 | -0.169 | 30.8±2.7 | -0.135 |
| controle reação, toques 1 (2º toque) | 308 | 303 | 48.8±2.9 | -0.083 | 32.5±2.8 | -0.084 |
| controle compra, toques 2+ (3º toque ou mais) | 1640 | 1631 | 47.9±1.2 | -0.101 | 32.1±1.2 | -0.098 |
| controle venda, toques 2+ (3º toque ou mais) | 1640 | 1631 | 42.2±1.2 | -0.216 | 28.3±1.1 | -0.212 |
| controle reação, toques 2+ (3º toque ou mais) | 1640 | 1631 | 48.4±1.2 | -0.092 | 31.3±1.2 | -0.121 |
| VAL compra, toques 0 (virgem) | 64 | 63 | 54.0±6.3 | +0.019 | 32.2±6.1 | -0.094 |
| VAH venda, toques 0 (virgem) | 81 | 81 | 39.5±5.4 | -0.270 | 27.8±5.0 | -0.225 |
| POC reação, toques 0 (virgem) | 24 | 24 | 54.2±10.2 | +0.023 | 26.1±9.2 | -0.277 |
| VAL compra, toques 1 (2º toque) | 44 | 44 | 59.1±7.4 | +0.122 | 39.5±7.5 | +0.126 |
| VAH venda, toques 1 (2º toque) | 45 | 45 | 44.4±7.4 | -0.171 | 31.1±6.9 | -0.127 |
| POC reação, toques 1 (2º toque) | 28 | 27 | 51.9±9.6 | -0.023 | 34.6±9.3 | -0.022 |
| VAL compra, toques 2+ (3º toque ou mais) | 251 | 245 | 52.7±3.2 | -0.007 | 34.0±3.1 | -0.039 |
| VAH venda, toques 2+ (3º toque ou mais) | 272 | 271 | 42.1±3.0 | -0.219 | 23.1±2.6 | -0.367 |
| POC reação, toques 2+ (3º toque ou mais) | 468 | 463 | 54.4±2.3★ | +0.029 | 36.4±2.3 | +0.031 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, toques 0 (virgem) | 119 | 119 | 56.3±4.5 | +0.066 | 38.5±4.5 | +0.094 |
| controle venda, toques 0 (virgem) | 119 | 119 | 37.0±4.4 | -0.321 | 22.2±3.8 | -0.393 |
| controle reação, toques 0 (virgem) | 119 | 119 | 49.6±4.6 | -0.068 | 28.2±4.2 | -0.214 |
| controle compra, toques 1 (2º toque) | 129 | 129 | 48.1±4.4 | -0.099 | 35.4±4.2 | +0.003 |
| controle venda, toques 1 (2º toque) | 129 | 129 | 41.1±4.3 | -0.238 | 24.8±3.9 | -0.316 |
| controle reação, toques 1 (2º toque) | 129 | 129 | 48.1±4.4 | -0.099 | 32.0±4.2 | -0.100 |
| controle compra, toques 2+ (3º toque ou mais) | 622 | 620 | 46.8±2.0 | -0.125 | 29.5±1.9 | -0.176 |
| controle venda, toques 2+ (3º toque ou mais) | 622 | 620 | 47.4±2.0 | -0.112 | 31.6±1.9 | -0.111 |
| controle reação, toques 2+ (3º toque ou mais) | 622 | 620 | 47.6±2.0 | -0.108 | 30.1±1.9 | -0.158 |
| VAL compra, toques 0 (virgem) | 25 | 25 | 44.0±9.9 | -0.180 | 20.8±8.3 | -0.435 |
| VAH venda, toques 0 (virgem) | 27 | 27 | 51.9±9.6 | -0.023 | 44.4±9.6★ | +0.273 |
| POC reação, toques 0 (virgem) | 16 | 16 | 37.5±12.1 | -0.310 | 6.2±6.1▼ | -0.872 |
| VAL compra, toques 1 (2º toque) | 13 | 13 | 61.5±13.5 | +0.171 | 38.5±13.5 | +0.094 |
| VAH venda, toques 1 (2º toque) | 30 | 30 | 40.0±8.9 | -0.260 | 32.1±8.8 | -0.096 |
| POC reação, toques 1 (2º toque) | 10 | 10 | 60.0±15.5 | +0.140 | 60.0±15.5 | +0.740 |
| VAL compra, toques 2+ (3º toque ou mais) | 106 | 105 | 50.5±4.9 | -0.050 | 38.8±4.8 | +0.105 |
| VAH venda, toques 2+ (3º toque ou mais) | 87 | 87 | 37.9±5.2 | -0.301 | 23.2±4.7 | -0.365 |
| POC reação, toques 2+ (3º toque ou mais) | 169 | 168 | 47.0±3.9 | -0.120 | 32.7±3.7 | -0.079 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, toques 0 (virgem) | 113 | 112 | 42.0±4.7 | -0.221 | 28.6±4.4 | -0.203 |
| controle venda, toques 0 (virgem) | 113 | 112 | 53.6±4.7 | +0.011 | 37.6±4.6 | +0.068 |
| controle reação, toques 0 (virgem) | 113 | 112 | 51.8±4.7 | -0.024 | 35.2±4.7 | -0.003 |
| controle compra, toques 1 (2º toque) | 122 | 120 | 57.5±4.5 | +0.090 | 43.0±4.6 | +0.229 |
| controle venda, toques 1 (2º toque) | 122 | 120 | 36.7±4.4 | -0.327 | 23.5±4.0 | -0.356 |
| controle reação, toques 1 (2º toque) | 122 | 120 | 42.5±4.5 | -0.210 | 28.1±4.2 | -0.218 |
| controle compra, toques 2+ (3º toque ou mais) | 444 | 443 | 48.3±2.4 | -0.094 | 31.4±2.3 | -0.119 |
| controle venda, toques 2+ (3º toque ou mais) | 444 | 443 | 49.0±2.4 | -0.080 | 33.1±2.3 | -0.067 |
| controle reação, toques 2+ (3º toque ou mais) | 444 | 443 | 49.9±2.4 | -0.062 | 33.1±2.3 | -0.067 |
| VAL compra, toques 0 (virgem) | 18 | 18 | 55.6±11.7 | +0.051 | 18.8±9.8 | -0.497 |
| VAH venda, toques 0 (virgem) | 19 | 18 | 44.4±11.7 | -0.171 | 38.9±11.5 | +0.107 |
| POC reação, toques 0 (virgem) | 7 | 7 | 57.1±18.7 | +0.083 | 42.9±18.7 | +0.226 |
| VAL compra, toques 1 (2º toque) | 17 | 17 | 41.2±11.9 | -0.236 | 29.4±11.1 | -0.178 |
| VAH venda, toques 1 (2º toque) | 25 | 25 | 64.0±9.6★ | +0.220 | 28.6±9.9 | -0.203 |
| POC reação, toques 1 (2º toque) | 13 | 13 | 15.4±10.0▼ | -0.752 | 8.3±8.0▼ | -0.810 |
| VAL compra, toques 2+ (3º toque ou mais) | 78 | 78 | 44.9±5.6 | -0.163 | 32.9±5.4 | -0.073 |
| VAH venda, toques 2+ (3º toque ou mais) | 59 | 58 | 50.0±6.6 | -0.060 | 33.3±6.6 | -0.060 |
| POC reação, toques 2+ (3º toque ou mais) | 113 | 111 | 55.0±4.7 | +0.039 | 37.4±4.7 | +0.061 |

### R = 2% (custo 0.03 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, toques 0 (virgem) | 405 | 369 | 55.0±2.6 | +0.070 | 31.9±2.6 | -0.073 |
| controle venda, toques 0 (virgem) | 405 | 369 | 39.0±2.5 | -0.250 | 22.8±2.3 | -0.347 |
| controle reação, toques 0 (virgem) | 405 | 369 | 45.0±2.6 | -0.130 | 27.2±2.5 | -0.215 |
| controle compra, toques 1 (2º toque) | 308 | 266 | 53.0±3.1 | +0.030 | 36.6±3.2 | +0.067 |
| controle venda, toques 1 (2º toque) | 308 | 266 | 44.7±3.0 | -0.135 | 27.9±2.9 | -0.193 |
| controle reação, toques 1 (2º toque) | 308 | 266 | 44.0±3.0 | -0.150 | 26.2±2.9 | -0.243 |
| controle compra, toques 2+ (3º toque ou mais) | 1640 | 1498 | 51.7±1.3 | +0.003 | 31.5±1.3 | -0.084 |
| controle venda, toques 2+ (3º toque ou mais) | 1640 | 1496 | 46.3±1.3 | -0.104 | 28.2±1.2 | -0.185 |
| controle reação, toques 2+ (3º toque ou mais) | 1640 | 1496 | 47.3±1.3 | -0.083 | 29.2±1.3 | -0.154 |
| VAL compra, toques 0 (virgem) | 64 | 50 | 52.0±7.1 | +0.010 | 44.4±7.4 | +0.303 |
| VAH venda, toques 0 (virgem) | 81 | 76 | 39.5±5.6 | -0.241 | 21.5±5.1 | -0.384 |
| POC reação, toques 0 (virgem) | 24 | 22 | 40.9±10.5 | -0.212 | 10.5±7.0▼ | -0.714 |
| VAL compra, toques 1 (2º toque) | 44 | 41 | 58.5±7.7 | +0.141 | 39.4±8.5 | +0.152 |
| VAH venda, toques 1 (2º toque) | 45 | 42 | 47.6±7.7 | -0.078 | 34.2±7.7 | -0.004 |
| POC reação, toques 1 (2º toque) | 28 | 23 | 47.8±10.4 | -0.073 | 35.0±10.7 | +0.020 |
| VAL compra, toques 2+ (3º toque ou mais) | 251 | 220 | 51.8±3.4 | +0.006 | 32.8±3.4 | -0.046 |
| VAH venda, toques 2+ (3º toque ou mais) | 272 | 243 | 40.7±3.2 | -0.215 | 25.2±2.9 | -0.273 |
| POC reação, toques 2+ (3º toque ou mais) | 468 | 431 | 50.6±2.4 | -0.018 | 32.1±2.4 | -0.067 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, toques 0 (virgem) | 119 | 113 | 55.8±4.7 | +0.085 | 43.3±5.0 | +0.269 |
| controle venda, toques 0 (virgem) | 119 | 113 | 43.4±4.7 | -0.163 | 25.5±4.4 | -0.265 |
| controle reação, toques 0 (virgem) | 119 | 113 | 38.1±4.6 | -0.269 | 21.6±4.2 | -0.381 |
| controle compra, toques 1 (2º toque) | 129 | 118 | 57.6±4.5 | +0.123 | 32.6±5.1 | -0.053 |
| controle venda, toques 1 (2º toque) | 129 | 118 | 42.4±4.5 | -0.183 | 16.8±3.8 | -0.525 |
| controle reação, toques 1 (2º toque) | 129 | 118 | 48.3±4.6 | -0.064 | 17.9±4.2 | -0.494 |
| controle compra, toques 2+ (3º toque ou mais) | 622 | 559 | 48.1±2.1 | -0.068 | 29.3±2.1 | -0.151 |
| controle venda, toques 2+ (3º toque ou mais) | 622 | 558 | 49.6±2.1 | -0.037 | 28.2±2.1 | -0.183 |
| controle reação, toques 2+ (3º toque ou mais) | 622 | 559 | 44.7±2.1 | -0.136 | 26.8±2.1 | -0.225 |
| VAL compra, toques 0 (virgem) | 25 | 24 | 37.5±9.9 | -0.280 | 21.1±9.4▼ | -0.398 |
| VAH venda, toques 0 (virgem) | 27 | 26 | 53.8±9.8 | +0.047 | 30.0±10.2 | -0.130 |
| POC reação, toques 0 (virgem) | 16 | 16 | 31.2±11.6 | -0.405 | 7.7±7.4 | -0.799 |
| VAL compra, toques 1 (2º toque) | 13 | 13 | 61.5±13.5 | +0.201 | 28.6±17.1 | -0.173 |
| VAH venda, toques 1 (2º toque) | 30 | 26 | 53.8±9.8 | +0.047 | 42.9±10.8★ | +0.256 |
| POC reação, toques 1 (2º toque) | 10 | 9 | 77.8±13.9★ | +0.526 | 50.0±20.4 | +0.470 |
| VAL compra, toques 2+ (3º toque ou mais) | 106 | 98 | 52.0±5.0 | +0.011 | 37.0±5.4 | +0.081 |
| VAH venda, toques 2+ (3º toque ou mais) | 87 | 72 | 36.1±5.7▼ | -0.308 | 20.3±5.0 | -0.421 |
| POC reação, toques 2+ (3º toque ou mais) | 169 | 148 | 48.6±4.1 | -0.057 | 33.1±4.3 | -0.038 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, toques 0 (virgem) | 113 | 91 | 42.9±5.2 | -0.173 | 16.2±4.5 | -0.545 |
| controle venda, toques 0 (virgem) | 113 | 92 | 56.5±5.2 | +0.100 | 38.2±5.9 | +0.117 |
| controle reação, toques 0 (virgem) | 113 | 91 | 56.0±5.2 | +0.091 | 32.8±5.7 | -0.045 |
| controle compra, toques 1 (2º toque) | 122 | 102 | 59.8±4.9 | +0.166 | 39.7±5.5 | +0.162 |
| controle venda, toques 1 (2º toque) | 122 | 102 | 40.2±4.9 | -0.226 | 23.8±4.6 | -0.316 |
| controle reação, toques 1 (2º toque) | 122 | 102 | 43.1±4.9 | -0.167 | 24.1±4.7 | -0.307 |
| controle compra, toques 2+ (3º toque ou mais) | 444 | 368 | 47.3±2.6 | -0.084 | 22.7±2.5 | -0.348 |
| controle venda, toques 2+ (3º toque ou mais) | 444 | 370 | 52.4±2.6 | +0.019 | 26.0±2.6 | -0.250 |
| controle reação, toques 2+ (3º toque ou mais) | 444 | 368 | 48.6±2.6 | -0.057 | 23.3±2.5 | -0.332 |
| VAL compra, toques 0 (virgem) | 18 | 15 | 40.0±12.6 | -0.230 | 25.0±12.5 | -0.280 |
| VAH venda, toques 0 (virgem) | 19 | 15 | 73.3±11.4 | +0.437 | 54.5±15.0 | +0.606 |
| POC reação, toques 0 (virgem) | 7 | 6 | 66.7±19.2 | +0.303 | 0.0±0.0▼ | -1.030 |
| VAL compra, toques 1 (2º toque) | 17 | 15 | 60.0±12.6 | +0.170 | 12.5±11.7▼ | -0.655 |
| VAH venda, toques 1 (2º toque) | 25 | 15 | 46.7±12.9 | -0.097 | 33.3±13.6 | -0.030 |
| POC reação, toques 1 (2º toque) | 13 | 9 | 44.4±16.6 | -0.141 | 33.3±15.7 | -0.030 |
| VAL compra, toques 2+ (3º toque ou mais) | 78 | 71 | 49.3±5.9 | -0.044 | 26.4±6.1 | -0.238 |
| VAH venda, toques 2+ (3º toque ou mais) | 59 | 45 | 46.7±7.4 | -0.097 | 17.6±6.5 | -0.501 |
| POC reação, toques 2+ (3º toque ou mais) | 113 | 88 | 53.4±5.3 | +0.038 | 27.9±5.7 | -0.194 |

### Consistência nos 3 períodos — H3 Toque virgem (composto fixo10)

Só linhas com ≥ 30 decididos em cada período. `min` = pior período. 

**Líquido positivo nos 3 períodos: 0 de 12 combinações linha×R×corrida.**

Top 5 por pior período:

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2% | 1:1 | VAL compra, toques 2+ (3º toque ou mais) | 435 | +0.006 | +0.011 | -0.044 | -0.044 |  |
| 2% | 1:1 | POC reação, toques 2+ (3º toque ou mais) | 750 | -0.018 | -0.057 | +0.038 | -0.057 |  |
| 1% | 2:1 | VAL compra, toques 2+ (3º toque ou mais) | 435 | -0.039 | +0.105 | -0.073 | -0.073 |  |
| 1% | 2:1 | POC reação, toques 2+ (3º toque ou mais) | 750 | +0.031 | -0.079 | +0.061 | -0.079 |  |
| 1% | 1:1 | POC reação, toques 2+ (3º toque ou mais) | 750 | +0.029 | -0.120 | +0.039 | -0.120 | ★ |

## H4 Escada de 5 limitadas (composto fixo10)

### R = 1% (custo 0.06 R por toque)

#### treino

| linha | n | preench. média | dec 1:1 | escada 1:1 (R do médio) | × cheia | única 1:1 | dec 2:1 | escada 2:1 (R do médio) | × cheia | única 2:1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| controle compra (reação de cima) | 1208 | 95% | 1198 | -0.063±0.029 | -0.114 | -0.047 | 1157 | -0.057±0.042 | -0.121 | -0.044 |
| controle venda (reação de baixo) | 1145 | 95% | 1136 | -0.171±0.029 | -0.219 | -0.157 | 1107 | -0.182±0.041 | -0.238 | -0.172 |
| VAL compra | 359 | 96% | 352 | -0.009±0.053 | -0.044 | +0.014 | 337 | -0.027±0.078 | -0.069 | -0.027 |
| VAH venda | 398 | 97% | 396 | -0.257±0.049 | -0.286 | -0.224 | 387 | -0.316±0.066 | -0.346 | -0.310 |
| POC compra (reação de cima) | 276 | 93% | 274 | -0.031±0.060 | -0.093 | -0.016 | 269 | -0.045±0.087 | -0.110 | -0.023 |
| POC venda (reação de baixo) | 244 | 94% | 240 | +0.032±0.064★ | -0.023 | +0.073 | 231 | +0.044±0.095★ | -0.032 | +0.057 |

#### validacao

| linha | n | preench. média | dec 1:1 | escada 1:1 (R do médio) | × cheia | única 1:1 | dec 2:1 | escada 2:1 (R do médio) | × cheia | única 2:1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| controle compra (reação de cima) | 466 | 94% | 464 | -0.094±0.046 | -0.148 | -0.077 | 453 | -0.120±0.065 | -0.192 | -0.113 |
| controle venda (reação de baixo) | 404 | 94% | 403 | -0.152±0.050 | -0.205 | -0.129 | 390 | -0.214±0.068 | -0.260 | -0.208 |
| VAL compra | 144 | 96% | 143 | -0.067±0.084 | -0.101 | -0.053 | 140 | +0.011±0.122 | -0.022 | +0.011 |
| VAH venda | 144 | 98% | 144 | -0.241±0.082 | -0.264 | -0.241 | 137 | -0.184±0.117 | -0.215 | -0.184 |
| POC compra (reação de cima) | 95 | 95% | 95 | -0.155±0.103 | -0.206 | -0.155 | 94 | -0.007±0.148 | -0.081 | -0.007 |
| POC venda (reação de baixo) | 100 | 94% | 99 | -0.131±0.101 | -0.190 | -0.090 | 94 | -0.198±0.141 | -0.252 | -0.198 |

#### holdout

| linha | n | preench. média | dec 1:1 | escada 1:1 (R do médio) | × cheia | única 1:1 | dec 2:1 | escada 2:1 (R do médio) | × cheia | única 2:1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| controle compra (reação de cima) | 350 | 95% | 348 | -0.112±0.054 | -0.160 | -0.089 | 329 | -0.130±0.077 | -0.184 | -0.105 |
| controle venda (reação de baixo) | 329 | 94% | 326 | -0.091±0.055 | -0.146 | -0.075 | 309 | -0.070±0.080 | -0.144 | -0.060 |
| VAL compra | 113 | 96% | 113 | -0.140±0.094 | -0.181 | -0.140 | 109 | -0.152±0.133 | -0.194 | -0.152 |
| VAH venda | 103 | 94% | 101 | -0.010±0.100 | -0.066 | -0.010 | 90 | -0.060±0.150 | -0.112 | -0.060 |
| POC compra (reação de cima) | 66 | 94% | 64 | +0.002±0.126 | -0.053 | +0.002 | 62 | -0.044±0.182 | -0.106 | -0.044 |
| POC venda (reação de baixo) | 67 | 94% | 66 | -0.121±0.124 | -0.180 | -0.075 | 64 | +0.018±0.181 | -0.055 | +0.018 |

### R = 2% (custo 0.03 R por toque)

#### treino

| linha | n | preench. média | dec 1:1 | escada 1:1 (R do médio) | × cheia | única 1:1 | dec 2:1 | escada 2:1 (R do médio) | × cheia | única 2:1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| controle compra (reação de cima) | 1208 | 97% | 1085 | -0.042±0.030 | -0.076 | -0.037 | 943 | -0.107±0.045 | -0.144 | -0.104 |
| controle venda (reação de baixo) | 1145 | 97% | 1044 | -0.172±0.031 | -0.202 | -0.165 | 920 | -0.251±0.043 | -0.287 | -0.248 |
| VAL compra | 359 | 98% | 311 | +0.025±0.057 | +0.002 | +0.025 | 267 | +0.037±0.088 | +0.014 | +0.037 |
| VAH venda | 398 | 98% | 360 | -0.208±0.052 | -0.224 | -0.205 | 324 | -0.271±0.073 | -0.283 | -0.264 |
| POC compra (reação de cima) | 276 | 97% | 254 | -0.014±0.063 | -0.049 | -0.006 | 224 | -0.039±0.094 | -0.097 | -0.039 |
| POC venda (reação de baixo) | 244 | 96% | 221 | -0.062±0.067 | -0.101 | -0.057 | 191 | -0.166±0.099 | -0.216 | -0.155 |

#### validacao

| linha | n | preench. média | dec 1:1 | escada 1:1 (R do médio) | × cheia | única 1:1 | dec 2:1 | escada 2:1 (R do médio) | × cheia | única 2:1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| controle compra (reação de cima) | 466 | 96% | 437 | -0.115±0.048 | -0.152 | -0.112 | 360 | -0.230±0.070 | -0.274 | -0.218 |
| controle venda (reação de baixo) | 404 | 98% | 351 | -0.187±0.053 | -0.212 | -0.183 | 284 | -0.386±0.073 | -0.409 | -0.367 |
| VAL compra | 144 | 98% | 135 | -0.023±0.086 | -0.040 | -0.023 | 107 | -0.021±0.138 | -0.050 | -0.021 |
| VAH venda | 144 | 98% | 124 | -0.159±0.089 | -0.176 | -0.159 | 105 | -0.230±0.130 | -0.241 | -0.230 |
| POC compra (reação de cima) | 95 | 96% | 88 | -0.098±0.107 | -0.138 | -0.098 | 69 | -0.204±0.163 | -0.255 | -0.204 |
| POC venda (reação de baixo) | 100 | 97% | 85 | -0.018±0.109 | -0.048 | -0.018 | 68 | +0.029±0.175★ | -0.006 | +0.029 |

#### holdout

| linha | n | preench. média | dec 1:1 | escada 1:1 (R do médio) | × cheia | única 1:1 | dec 2:1 | escada 2:1 (R do médio) | × cheia | única 2:1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| controle compra (reação de cima) | 350 | 97% | 294 | -0.091±0.058 | -0.122 | -0.074 | 218 | -0.397±0.083 | -0.419 | -0.386 |
| controle venda (reação de baixo) | 329 | 96% | 266 | -0.038±0.061 | -0.081 | -0.030 | 205 | -0.181±0.095 | -0.224 | -0.171 |
| VAL compra | 113 | 98% | 101 | -0.040±0.100 | -0.063 | -0.040 | 73 | -0.290±0.152 | -0.317 | -0.290 |
| VAH venda | 103 | 97% | 75 | +0.010±0.116 | -0.021 | +0.010 | 57 | -0.188±0.180 | -0.229 | -0.188 |
| POC compra (reação de cima) | 66 | 96% | 52 | -0.068±0.140 | -0.106 | -0.068 | 35 | -0.601±0.180 | -0.601 | -0.601 |
| POC venda (reação de baixo) | 67 | 96% | 51 | +0.146±0.139 | +0.101 | +0.146 | 38 | +0.154±0.241 | +0.040 | +0.154 |

### Consistência nos 3 períodos — H4 Escada de 5 limitadas (composto fixo10)

Só linhas com ≥ 30 decididos em cada período. `min` = pior período. Líquido = média em R do médio por unidade preenchida.

**Líquido positivo nos 3 períodos: 0 de 16 combinações linha×R×corrida.**

Top 5 por pior período:

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2% | 1:1 | VAL compra | 616 | +0.025 | -0.023 | -0.040 | -0.040 |  |
| 1% | 2:1 | POC compra (reação de cima) | 437 | -0.045 | -0.007 | -0.044 | -0.045 |  |
| 2% | 1:1 | POC venda (reação de baixo) | 411 | -0.062 | -0.018 | +0.146 | -0.062 |  |
| 2% | 1:1 | POC compra (reação de cima) | 437 | -0.014 | -0.098 | -0.068 | -0.098 |  |
| 1% | 1:1 | POC venda (reação de baixo) | 411 | +0.032 | -0.131 | -0.121 | -0.131 | ★ |

## H5 Presos (composto fixo10, desde 2020-07-20)

### R = 1% (custo 0.06 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, lsr: presos contra | 926 | 922 | 48.9±1.6 | -0.082 | 34.0±1.6 | -0.039 |
| controle venda, lsr: presos contra | 1076 | 1064 | 43.0±1.5 | -0.199 | 30.0±1.4 | -0.160 |
| controle compra, lsr: sem presos | 1077 | 1065 | 47.0±1.5 | -0.119 | 31.9±1.4 | -0.103 |
| controle venda, lsr: sem presos | 927 | 923 | 37.8±1.6 | -0.304 | 25.4±1.4 | -0.299 |
| controle compra, OI 6h subindo | 1022 | 1016 | 48.5±1.6 | -0.090 | 33.6±1.5 | -0.051 |
| controle venda, OI 6h subindo | 1022 | 1016 | 39.1±1.5 | -0.279 | 27.2±1.4 | -0.244 |
| controle compra, OI 6h caindo | 1013 | 1003 | 48.4±1.6 | -0.093 | 33.3±1.5 | -0.060 |
| controle venda, OI 6h caindo | 1013 | 1003 | 41.3±1.6 | -0.234 | 27.8±1.4 | -0.226 |
| controle compra, funding do lado | 764 | 757 | 46.9±1.8 | -0.122 | 32.5±1.7 | -0.086 |
| controle venda, funding do lado | 659 | 654 | 40.5±1.9 | -0.250 | 27.5±1.8 | -0.235 |
| controle compra, funding não | 1271 | 1262 | 49.4±1.4 | -0.073 | 34.1±1.3 | -0.037 |
| controle venda, funding não | 1376 | 1365 | 40.0±1.3 | -0.260 | 27.5±1.2 | -0.235 |
| VAL compra, lsr: vendidos presos | 110 | 109 | 52.3±4.8 | -0.014 | 35.8±4.7 | +0.015 |
| VAL compra, lsr: sem vendidos presos | 206 | 201 | 56.2±3.5★ | +0.064 | 35.6±3.4 | +0.007 |
| VAL compra, OI 6h subindo | 165 | 163 | 56.4±3.9 | +0.069 | 37.2±3.9 | +0.055 |
| VAL compra, OI 6h caindo | 151 | 147 | 53.1±4.1 | +0.001 | 34.0±3.9 | -0.039 |
| VAL compra, funding do lado | 122 | 119 | 53.8±4.6 | +0.016 | 30.4±4.3 | -0.147 |
| VAL compra, funding não | 194 | 191 | 55.5±3.6 | +0.050 | 38.9±3.6 | +0.108 |
| VAH venda, lsr: comprados presos | 131 | 131 | 44.3±4.3 | -0.175 | 27.1±3.9 | -0.246 |
| VAH venda, lsr: sem comprados presos | 190 | 189 | 42.9±3.6 | -0.203 | 25.9±3.2 | -0.282 |
| VAH venda, OI 6h subindo | 148 | 148 | 42.6±4.1 | -0.209 | 26.2±3.7 | -0.274 |
| VAH venda, OI 6h caindo | 185 | 184 | 42.9±3.6 | -0.201 | 24.9±3.2 | -0.314 |
| VAH venda, funding do lado | 114 | 114 | 48.2±4.7 | -0.095 | 34.2±4.5 | -0.033 |
| VAH venda, funding não | 219 | 218 | 39.9±3.3 | -0.262 | 20.9±2.8▼ | -0.432 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, lsr: presos contra | 395 | 395 | 47.8±2.5 | -0.103 | 32.2±2.4 | -0.094 |
| controle venda, lsr: presos contra | 475 | 473 | 43.8±2.3 | -0.185 | 28.6±2.1 | -0.201 |
| controle compra, lsr: sem presos | 475 | 473 | 48.6±2.3 | -0.087 | 31.1±2.2 | -0.127 |
| controle venda, lsr: sem presos | 395 | 395 | 46.6±2.5 | -0.128 | 30.1±2.3 | -0.156 |
| controle compra, OI 6h subindo | 404 | 404 | 44.1±2.5 | -0.179 | 31.2±2.3 | -0.125 |
| controle venda, OI 6h subindo | 404 | 404 | 47.8±2.5 | -0.105 | 31.8±2.3 | -0.106 |
| controle compra, OI 6h caindo | 466 | 464 | 51.9±2.3 | -0.021 | 32.0±2.2 | -0.100 |
| controle venda, OI 6h caindo | 466 | 464 | 42.7±2.3 | -0.207 | 27.2±2.1 | -0.245 |
| controle compra, funding do lado | 391 | 389 | 48.3±2.5 | -0.093 | 32.1±2.4 | -0.097 |
| controle venda, funding do lado | 343 | 343 | 46.6±2.7 | -0.127 | 28.9±2.5 | -0.193 |
| controle compra, funding não | 479 | 479 | 48.2±2.3 | -0.095 | 31.2±2.1 | -0.125 |
| controle venda, funding não | 527 | 525 | 44.0±2.2 | -0.180 | 29.6±2.0 | -0.173 |
| VAL compra, lsr: vendidos presos | 27 | 27 | 48.1±9.6 | -0.097 | 30.8±9.1 | -0.137 |
| VAL compra, lsr: sem vendidos presos | 117 | 116 | 50.9±4.6 | -0.043 | 36.8±4.5 | +0.045 |
| VAL compra, OI 6h subindo | 60 | 60 | 40.0±6.3 | -0.260 | 28.8±5.9 | -0.196 |
| VAL compra, OI 6h caindo | 84 | 83 | 57.8±5.4 | +0.097 | 40.7±5.5 | +0.162 |
| VAL compra, funding do lado | 88 | 88 | 47.7±5.3 | -0.105 | 33.7±5.1 | -0.048 |
| VAL compra, funding não | 56 | 55 | 54.5±6.7 | +0.031 | 38.9±6.6 | +0.107 |
| VAH venda, lsr: comprados presos | 57 | 57 | 36.8±6.4 | -0.323 | 25.5±5.9 | -0.296 |
| VAH venda, lsr: sem comprados presos | 87 | 87 | 43.7±5.3 | -0.186 | 31.7±5.1 | -0.109 |
| VAH venda, OI 6h subindo | 80 | 80 | 36.2±5.4 | -0.335 | 23.7±4.9 | -0.349 |
| VAH venda, OI 6h caindo | 64 | 64 | 46.9±6.2 | -0.122 | 36.1±6.1 | +0.022 |
| VAH venda, funding do lado | 68 | 68 | 45.6±6.0 | -0.148 | 39.4±6.0 | +0.122 |
| VAH venda, funding não | 76 | 76 | 36.8±5.5 | -0.323 | 19.7±4.7 | -0.468 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, lsr: presos contra | 349 | 347 | 49.6±2.7 | -0.069 | 35.3±2.6 | +0.000 |
| controle venda, lsr: presos contra | 330 | 328 | 48.5±2.8 | -0.090 | 33.8±2.7 | -0.047 |
| controle compra, lsr: sem presos | 330 | 328 | 48.2±2.8 | -0.097 | 30.4±2.6 | -0.147 |
| controle venda, lsr: sem presos | 349 | 347 | 46.7±2.7 | -0.126 | 30.7±2.5 | -0.140 |
| controle compra, OI 6h subindo | 311 | 309 | 49.8±2.8 | -0.063 | 35.4±2.8 | +0.001 |
| controle venda, OI 6h subindo | 311 | 309 | 46.6±2.8 | -0.128 | 31.4±2.7 | -0.117 |
| controle compra, OI 6h caindo | 368 | 366 | 48.1±2.6 | -0.098 | 30.9±2.5 | -0.132 |
| controle venda, OI 6h caindo | 368 | 366 | 48.4±2.6 | -0.093 | 32.8±2.5 | -0.077 |
| controle compra, funding do lado | 328 | 325 | 45.8±2.8 | -0.143 | 30.3±2.6 | -0.151 |
| controle venda, funding do lado | 308 | 307 | 44.3±2.8 | -0.174 | 29.8±2.7 | -0.165 |
| controle compra, funding não | 351 | 350 | 51.7±2.7 | -0.026 | 35.4±2.6 | +0.003 |
| controle venda, funding não | 371 | 368 | 50.3±2.6 | -0.055 | 34.1±2.5 | -0.037 |
| VAL compra, lsr: vendidos presos | 39 | 39 | 41.0±7.9 | -0.239 | 29.7±7.5 | -0.168 |
| VAL compra, lsr: sem vendidos presos | 74 | 74 | 48.6±5.8 | -0.087 | 30.6±5.4 | -0.143 |
| VAL compra, OI 6h subindo | 53 | 53 | 47.2±6.9 | -0.117 | 29.4±6.4 | -0.178 |
| VAL compra, OI 6h caindo | 60 | 60 | 45.0±6.4 | -0.160 | 31.0±6.1 | -0.129 |
| VAL compra, funding do lado | 68 | 68 | 45.6±6.0 | -0.148 | 29.2±5.6 | -0.183 |
| VAL compra, funding não | 45 | 45 | 46.7±7.4 | -0.127 | 31.8±7.0 | -0.105 |
| VAH venda, lsr: comprados presos | 24 | 24 | 58.3±10.1 | +0.107 | 36.8±11.1 | +0.045 |
| VAH venda, lsr: sem comprados presos | 79 | 77 | 50.6±5.7 | -0.047 | 32.4±5.6 | -0.088 |
| VAH venda, OI 6h subindo | 37 | 36 | 41.7±8.2 | -0.227 | 22.6±7.5 | -0.383 |
| VAH venda, OI 6h caindo | 66 | 65 | 58.5±6.1 | +0.109 | 39.0±6.3 | +0.109 |
| VAH venda, funding do lado | 47 | 47 | 53.2±7.3 | +0.004 | 33.3±7.3 | -0.060 |
| VAH venda, funding não | 56 | 54 | 51.9±6.8 | -0.023 | 33.3±6.8 | -0.060 |

### R = 2% (custo 0.03 R por toque)

#### treino

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, lsr: presos contra | 926 | 845 | 56.0±1.7 | +0.090 | 36.9±1.8 | +0.076 |
| controle venda, lsr: presos contra | 1076 | 966 | 48.0±1.6 | -0.069 | 29.6±1.6 | -0.141 |
| controle compra, lsr: sem presos | 1077 | 967 | 49.2±1.6 | -0.046 | 28.5±1.6 | -0.175 |
| controle venda, lsr: sem presos | 927 | 846 | 42.0±1.7 | -0.191 | 24.7±1.6 | -0.289 |
| controle compra, OI 6h subindo | 1022 | 919 | 53.1±1.6 | +0.032 | 32.3±1.7 | -0.061 |
| controle venda, OI 6h subindo | 1022 | 919 | 44.2±1.6 | -0.146 | 26.2±1.5 | -0.245 |
| controle compra, OI 6h caindo | 1013 | 924 | 52.5±1.6 | +0.020 | 33.0±1.7 | -0.041 |
| controle venda, OI 6h caindo | 1013 | 924 | 45.2±1.6 | -0.125 | 27.6±1.5 | -0.202 |
| controle compra, funding do lado | 764 | 689 | 52.1±1.9 | +0.012 | 33.9±1.9 | -0.014 |
| controle venda, funding do lado | 659 | 586 | 45.4±2.1 | -0.122 | 28.2±2.0 | -0.185 |
| controle compra, funding não | 1271 | 1154 | 53.2±1.5 | +0.034 | 31.9±1.5 | -0.074 |
| controle venda, funding não | 1376 | 1257 | 44.4±1.4 | -0.142 | 26.3±1.3 | -0.240 |
| VAL compra, lsr: vendidos presos | 110 | 99 | 56.6±5.0 | +0.101 | 39.3±5.2 | +0.150 |
| VAL compra, lsr: sem vendidos presos | 206 | 178 | 53.4±3.7 | +0.037 | 34.5±3.9 | +0.004 |
| VAL compra, OI 6h subindo | 165 | 143 | 54.5±4.2 | +0.061 | 37.4±4.4 | +0.092 |
| VAL compra, OI 6h caindo | 151 | 134 | 54.5±4.3 | +0.060 | 35.1±4.5 | +0.023 |
| VAL compra, funding do lado | 122 | 104 | 50.0±4.9 | -0.030 | 33.3±4.8 | -0.030 |
| VAL compra, funding não | 194 | 173 | 57.2±3.8 | +0.115 | 38.3±4.1 | +0.119 |
| VAH venda, lsr: comprados presos | 131 | 120 | 48.3±4.6 | -0.063 | 31.5±4.5 | -0.086 |
| VAH venda, lsr: sem comprados presos | 190 | 171 | 40.4±3.8 | -0.223 | 23.7±3.4 | -0.319 |
| VAH venda, OI 6h subindo | 148 | 131 | 43.5±4.3 | -0.160 | 25.0±4.0 | -0.280 |
| VAH venda, OI 6h caindo | 185 | 171 | 41.5±3.8 | -0.200 | 27.1±3.6 | -0.217 |
| VAH venda, funding do lado | 114 | 103 | 48.5±4.9 | -0.059 | 32.2±4.9 | -0.063 |
| VAH venda, funding não | 219 | 199 | 39.2±3.5 | -0.246 | 23.2±3.1 | -0.334 |

#### validacao

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, lsr: presos contra | 395 | 354 | 52.0±2.7 | +0.010 | 35.5±2.8 | +0.035 |
| controle venda, lsr: presos contra | 475 | 435 | 48.0±2.4 | -0.069 | 28.8±2.4 | -0.166 |
| controle compra, lsr: sem presos | 475 | 436 | 49.5±2.4 | -0.039 | 28.8±2.4 | -0.166 |
| controle venda, lsr: sem presos | 395 | 354 | 47.2±2.7 | -0.086 | 22.5±2.5 | -0.354 |
| controle compra, OI 6h subindo | 404 | 376 | 51.1±2.6 | -0.009 | 32.4±2.7 | -0.059 |
| controle venda, OI 6h subindo | 404 | 376 | 47.1±2.6 | -0.089 | 26.6±2.5 | -0.233 |
| controle compra, OI 6h caindo | 466 | 414 | 50.2±2.5 | -0.025 | 31.3±2.5 | -0.090 |
| controle venda, OI 6h caindo | 466 | 413 | 48.2±2.5 | -0.066 | 25.7±2.4 | -0.259 |
| controle compra, funding do lado | 391 | 358 | 51.7±2.6 | +0.004 | 31.0±2.7 | -0.099 |
| controle venda, funding do lado | 343 | 310 | 47.7±2.8 | -0.075 | 24.6±2.7 | -0.292 |
| controle compra, funding não | 479 | 432 | 49.8±2.4 | -0.035 | 32.4±2.5 | -0.057 |
| controle venda, funding não | 527 | 479 | 47.6±2.3 | -0.078 | 27.1±2.2 | -0.217 |
| VAL compra, lsr: vendidos presos | 27 | 25 | 44.0±9.9 | -0.150 | 39.1±10.2 | +0.144 |
| VAL compra, lsr: sem vendidos presos | 117 | 110 | 51.8±4.8 | +0.006 | 32.1±5.1 | -0.066 |
| VAL compra, OI 6h subindo | 60 | 57 | 40.4±6.5 | -0.223 | 22.2±6.2 | -0.363 |
| VAL compra, OI 6h caindo | 84 | 78 | 57.7±5.6 | +0.124 | 41.9±6.3 | +0.228 |
| VAL compra, funding do lado | 88 | 85 | 45.9±5.4 | -0.112 | 28.6±5.4 | -0.173 |
| VAL compra, funding não | 56 | 50 | 58.0±7.0 | +0.130 | 43.2±8.1 | +0.267 |
| VAH venda, lsr: comprados presos | 57 | 49 | 36.7±6.9 | -0.295 | 21.3±6.0 | -0.392 |
| VAH venda, lsr: sem comprados presos | 87 | 75 | 48.0±5.8 | -0.070 | 31.0±6.1 | -0.099 |
| VAH venda, OI 6h subindo | 80 | 69 | 44.9±6.0 | -0.131 | 26.8±5.9 | -0.226 |
| VAH venda, OI 6h caindo | 64 | 55 | 41.8±6.7 | -0.194 | 26.5±6.3 | -0.234 |
| VAH venda, funding do lado | 68 | 61 | 52.5±6.4 | +0.019 | 30.0±6.5 | -0.130 |
| VAH venda, funding não | 76 | 63 | 34.9±6.0 | -0.332 | 23.6±5.7 | -0.321 |

#### holdout

| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |
|---|---:|---:|---:|---:|---:|---:|
| controle compra, lsr: presos contra | 349 | 292 | 52.7±2.9 | +0.025 | 29.6±3.1 | -0.142 |
| controle venda, lsr: presos contra | 330 | 269 | 55.4±3.0 | +0.078 | 32.0±3.3 | -0.071 |
| controle compra, lsr: sem presos | 330 | 269 | 44.6±3.0 | -0.138 | 19.5±2.8 | -0.445 |
| controle venda, lsr: sem presos | 349 | 295 | 46.8±2.9 | -0.094 | 23.7±2.8 | -0.319 |
| controle compra, OI 6h subindo | 311 | 261 | 53.3±3.1 | +0.035 | 28.2±3.2 | -0.184 |
| controle venda, OI 6h subindo | 311 | 261 | 46.7±3.1 | -0.095 | 25.0±3.0 | -0.280 |
| controle compra, OI 6h caindo | 368 | 300 | 45.0±2.9 | -0.130 | 21.9±2.7 | -0.372 |
| controle venda, OI 6h caindo | 368 | 303 | 54.5±2.9 | +0.059 | 29.9±3.1 | -0.134 |
| controle compra, funding do lado | 328 | 272 | 49.3±3.0 | -0.045 | 26.8±3.0 | -0.227 |
| controle venda, funding do lado | 308 | 261 | 49.8±3.1 | -0.034 | 25.3±3.1 | -0.272 |
| controle compra, funding não | 351 | 289 | 48.4±2.9 | -0.061 | 22.9±2.9 | -0.344 |
| controle venda, funding não | 371 | 303 | 51.8±2.9 | +0.006 | 29.4±3.0 | -0.147 |
| VAL compra, lsr: vendidos presos | 39 | 34 | 50.0±8.6 | -0.030 | 30.8±9.1 | -0.107 |
| VAL compra, lsr: sem vendidos presos | 74 | 67 | 49.3±6.1 | -0.045 | 21.3±6.0 | -0.392 |
| VAL compra, OI 6h subindo | 53 | 46 | 47.8±7.4 | -0.073 | 26.5±7.6 | -0.236 |
| VAL compra, OI 6h caindo | 60 | 55 | 50.9±6.7 | -0.012 | 23.1±6.7 | -0.338 |
| VAL compra, funding do lado | 68 | 63 | 47.6±6.3 | -0.078 | 23.9±6.3 | -0.313 |
| VAL compra, funding não | 45 | 38 | 52.6±8.1 | +0.023 | 25.9±8.4 | -0.252 |
| VAH venda, lsr: comprados presos | 24 | 17 | 47.1±12.1 | -0.089 | 25.0±12.5 | -0.280 |
| VAH venda, lsr: sem comprados presos | 79 | 58 | 53.4±6.5 | +0.039 | 28.9±6.8 | -0.163 |
| VAH venda, OI 6h subindo | 37 | 26 | 42.3±9.7 | -0.184 | 23.8±9.3 | -0.316 |
| VAH venda, OI 6h caindo | 66 | 49 | 57.1±7.1 | +0.113 | 30.6±7.7 | -0.113 |
| VAH venda, funding do lado | 47 | 35 | 51.4±8.4 | -0.001 | 30.8±9.1 | -0.107 |
| VAH venda, funding não | 56 | 40 | 52.5±7.9 | +0.020 | 25.8±7.9 | -0.256 |

### Consistência nos 3 períodos — H5 Presos (composto fixo10, desde 2020-07-20)

Só linhas com ≥ 30 decididos em cada período. `min` = pior período. 

**Líquido positivo nos 3 períodos: 1 de 36 combinações linha×R×corrida.**

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2% | 1:1 | VAL compra, funding não | 295 | +0.115 | +0.130 | +0.023 | +0.023 |  |

Top 5 por pior período:

| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2% | 1:1 | VAL compra, funding não | 295 | +0.115 | +0.130 | +0.023 | +0.023 |  |
| 2% | 1:1 | VAL compra, OI 6h caindo | 295 | +0.060 | +0.124 | -0.012 | -0.012 |  |
| 2% | 1:1 | VAL compra, lsr: sem vendidos presos | 397 | +0.037 | +0.006 | -0.045 | -0.045 |  |
| 2% | 1:1 | VAH venda, funding do lado | 229 | -0.059 | +0.019 | -0.001 | -0.059 |  |
| 1% | 2:1 | VAH venda, funding do lado | 229 | -0.033 | +0.122 | -0.060 | -0.060 |  |

## Controle (níveis sorteados) por período — compra e venda sem olhar a chegada

| R | período | direção | n | dec | reação 1:1 % | líq 1:1 | reação 2:1 % | líq 2:1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 1% | treino | compra em nível sorteado | 2353 | 2337 | 47.5±1.0 | -0.109 | 32.5±1.0 | -0.084 |
| 1% | treino | venda em nível sorteado | 2353 | 2337 | 40.7±1.0 | -0.247 | 27.7±0.9 | -0.228 |
| 1% | validacao | compra em nível sorteado | 870 | 868 | 48.3±1.7 | -0.095 | 31.6±1.6 | -0.112 |
| 1% | validacao | venda em nível sorteado | 870 | 868 | 45.0±1.7 | -0.159 | 29.3±1.6 | -0.181 |
| 1% | holdout | compra em nível sorteado | 679 | 675 | 48.9±1.9 | -0.082 | 33.0±1.9 | -0.071 |
| 1% | holdout | venda em nível sorteado | 679 | 675 | 47.6±1.9 | -0.109 | 32.1±1.8 | -0.096 |
| 2% | treino | compra em nível sorteado | 2353 | 2133 | 52.4±1.1 | +0.018 | 32.2±1.1 | -0.064 |
| 2% | treino | venda em nível sorteado | 2353 | 2131 | 44.9±1.1 | -0.133 | 27.2±1.0 | -0.215 |
| 2% | validacao | compra em nível sorteado | 870 | 790 | 50.6±1.8 | -0.017 | 31.8±1.8 | -0.076 |
| 2% | validacao | venda em nível sorteado | 870 | 789 | 47.7±1.8 | -0.077 | 26.1±1.7 | -0.246 |
| 2% | holdout | compra em nível sorteado | 679 | 561 | 48.8±2.1 | -0.053 | 24.8±2.1 | -0.285 |
| 2% | holdout | venda em nível sorteado | 679 | 564 | 50.9±2.1 | -0.012 | 27.5±2.2 | -0.205 |
