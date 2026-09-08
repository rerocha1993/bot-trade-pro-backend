# O trader: como o sistema passou a "pensar" antes de contar ondas

## O problema que existia

A memória de contagens (ciclo semanal e primário diário, sem look-ahead) acertava a direção do ano seguinte em só
3 de 9 (ciclo) e 4 de 10 (primário). O erro era sistemático: **vender nos fundos** (2015-01, 2019-01, 2023-01, 2024-01).
Subordinar o primário ao ciclo (`MemoriaHierarquica`) não resolveu (4 de 10), porque os dois graus extrapolam a última
perna: depois de uma queda de 80%, o melhor ajuste mecânico é sempre "onda 3 de baixa em andamento".

Elliott mecânico não é Elliott. O que faltava é a camada que um elliottista humano usa antes de contar: **em que ponto do
superciclo estamos**, medido em escala logarítmica.

## O contexto de superciclo (`core/elliott_pro/superciclo.py`)

Nada olha o futuro: o estado em cada candle usa só o passado.

| Regra | Valor | Base |
|---|---|---|
| Topo de ciclo | topo histórico seguido de queda >= 60% | bears de BTC: 2011 -94%, 2013 -87%, 2018 -84%, 2022 -78% |
| Correção curta não é fim de ciclo | precisa durar >= 9 meses até o rompimento do topo | 2013 (266 -> 65 em 7 meses) foi sub-onda |
| Profundidade da correção | retração LOG da perna de alta anterior (fundo -> topo) | 2015: 0,45 · 2018: 0,38 · 2022: 0,50 (Fibonacci 0,382..0,5) |
| Zona de término (`fundo_terminal`) | 2 de 3: retração log >= 0,382, tempo >= 9 meses, queda >= 60% | guias de término de onda 2/4 |
| Correção terminou (`novo_impulso`) | >= 6 meses do topo e preço recupera >= 0,382 (log) da queda | um 5 ondas de alta de grau menor já aconteceu |
| Onda 2/4 da perna nova (`zona_onda_2`) | recuo 0,382..0,786 (log) da perna nova | 2019-12: recuo 0,45 |
| Perna madura (`impulso_maduro`) | extensão log >= 0,618 da perna do ciclo anterior | 2017: 0,82 · 2021: 0,63 · 2025: 0,68 (retornos decrescentes) |
| Correção recém-iniciada (`correcao_inicial`) | topo confirmado há < 3 meses ou retração < 0,2 | 2013-12, 2018-02 |

"Madura" não é venda: é *não perseguir; vender quando as contagens de grau menor virarem*. Por isso em `impulso_maduro`
a direção vem das contagens (sell se >= 50% bear, senão hold), e em `fundo_terminal`/`novo_impulso` o trader não deixa
vender, mesmo com as contagens gritando "onda 3 de baixa".

## O trader (`MemoriaHierarquica.trader`, `services/trader_service.py`)

Ordem de leitura: superciclo (log) -> ciclo semanal (40%) -> primário diário (22%) subordinado ao ciclo -> multiplicadores
do superciclo sobre as hipóteses vivas (continuação de baixa x0,2 em fundo terminal, continuação de alta x0,5 em impulso
maduro, etc.). A memória é persistida em `data/trader_<PAR>.pkl`: construção completa desde 2011 em ~4 s, depois só os
candles diários novos. `POST /api/elliott/trader/reconstruir` refaz do zero (usar após mudar regras ou calibração).

## Resultado do teste objetivo (sem look-ahead)

Direção no fim de cada ano contra a variação dos 12 meses seguintes (`scripts/evoluir_contagens.py`):

| Fim de ano | Preço | Trader | Estado | 12 meses depois |
|---|---|---|---|---|
| 2012 | 13 | buy | impulso_alta | +5429% |
| 2013 | 732 | sell | correcao_inicial | -56% |
| 2014 | 321 | buy | fundo_terminal | +34% |
| 2015 | 431 | buy | novo_impulso | +123% |
| 2016 | 966 | buy | novo_impulso | +1336% |
| 2017 | 13.880 | sell | impulso_maduro | -73% |
| 2018 | 3.693 | buy | fundo_terminal | +94% |
| 2019 | 7.168 | buy | zona_onda_2 | +303% |
| 2020 | 28.993 | buy | impulso_alta | +59% |
| 2021 | 46.214 | sell | impulso_maduro | -64% |
| 2022 | 16.528 | buy | fundo_terminal | +156% |
| 2023 | 42.258 | buy | novo_impulso | +119% |
| 2024 | 93.381 | hold | impulso_maduro | -6% |

Fins de ano: 12 de 12. Fins de trimestre (49 datas, teste de robustez): 45 de 49. Os erros trimestrais são "hold" em
fase madura (2017-06/09, 2021-09, 2025-06), que o critério penaliza quando o preço anda mais de 30%, e um repique de 2014.

Leitura hoje (2026-09-06, preço ~79,8 mil): `impulso_maduro` (perna 15,5 mil -> 126 mil = 0,68 da perna anterior),
ciclo semanal "onda 1 de baixa concluída, onda 2 em andamento", primário subordinado 65% bear -> **sell/hedge**.
Se a queda desde 126 mil passar de 60% (~50,5 mil) o estado vira correção confirmada.

## Ressalvas honestas

- BTC tem só **três ciclos completos**. Os limiares (60%, 0,382, 9 meses, 0,618, 6 meses) são guias de Elliott e da forma
  conhecida dos ciclos de BTC, não otimização numérica, mas com três ciclos qualquer regra parece boa demais. O teste de
  trimestres (92%) reduz, não elimina, esse risco.
- Em outros pares o contexto só vale com histórico longo de ciclos completos; para ETH e altcoins o trader usa o histórico
  disponível na Bybit e tende a ficar em `impulso_alta`/`correcao_em_curso` (sem ciclo anterior para medir maturidade).
- "Madura" pode durar mais de um ano (2017-03 a 2017-12; 2024-03 a 2025-10). O sistema não persegue, mas também não vende
  até as contagens virarem. Isso é o comportamento pedido (hedge só com exaustão), e custa parte da alta final.

## Onde a leitura entra

- `AnaliseMultiGrau(trader=...)` (`core/elliott_pro/multidegree.py`): conservador bloqueia venda em `fundo_terminal`,
  `novo_impulso` e `zona_onda_2` e compra em `correcao_inicial`; turbo opera contra com metade do tamanho; em
  `impulso_maduro` compras entram com metade (`fator_tamanho`). Campos `vies_trader`, `estado_superciclo`, `fator_tamanho`
  no alinhamento; `trader` gravado em `DecisoesBot.detalhes`.
- `HedgeDial` (`core/hedge_dial.py`): `fundo_terminal`, `novo_impulso`, `impulso_alta`, `zona_onda_2` = hedge 0% (deixa
  andar); `impulso_maduro` = hedge permitido com exaustão e confluência, teto 100% com exaustão >= 0,6;
  `correcao_inicial`/`correcao_em_curso` = hedge sem exigir exaustão, teto 100%.
- Backtest do dial 2017-2026 (`scripts/backtest_hedge.py --desde 2017`, carteira 1 BTC): antes, entre -9% e +3% de BTC
  e, com a leitura antiga de "impulso", -44% (hedgeou a alta de 2017). Agora **+77% de BTC** (1,78 BTC), hedge médio 14%,
  custo de rompimentos zero, drawdown marcado 55% (hedge de 66-100% montado em nov/dez 2017 entre 9 e 11 mil enquanto o preço
  foi a 19,7 mil; realizado em 2018 a 1,40 BTC). Por ano: 2017 1,01 · 2018 1,40 · 2019-2020 sem hedge · 2021 1,61 ·
  2022 1,69 · 2023 sem hedge · 2025 1,77 · 2026 1,82 (realizado).
- API: `GET /api/elliott/trader?par=BTCUSDT[&preco=]`, `GET /api/elliott/mestre` (campo `trader`), `GET /inverse/dial`
  (campo `superciclo`), `POST /api/elliott/trader/reconstruir`.
