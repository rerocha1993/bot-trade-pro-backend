# Elliott — "passou de 0,786 → não é onda 2" (hipótese do Tradeiros; passo 6 do plano, início)

Gerado por `scripts/estudo_elliott_0786.py` (regra e critério no docstring, escritos antes de rodar). Estudo descritivo sobre `data/cenarios/{1h,4h}.jsonl.gz` (motor de Elliott do projeto, sem olhar o futuro), continuação medida nos mesmos candles BTCUSD Bitstamp. Horizonte de 60 candles.

## Hipóteses de onda 2

| TF | hipóteses (viés, invalidação) únicas | alta | baixa | impulso | corretivo completo | principal | L mediano | E reconstruído = motor (impulso) |
|---|---|---|---|---|---|---|---|---|
| 1h | 3012 | 1471 | 1541 | 1305 | 1707 | 1287 | 2.34% | 100% de 491 |
| 4h | 694 | 331 | 363 | 316 | 378 | 292 | 5.84% | 100% de 128 |

## P(perde a origem | cruzou θ)

Principal = perdeu ÷ todos os cruzamentos (± EP binomial); decididos = perdeu ÷ (perdeu + sobreviveu). Sorteio = mesmas distâncias a partir de datas sorteadas do mesmo período (20 por cruzamento). Passeio = ruína do jogador a partir de exatamente θ. Critério da regra: θ = 0,786 com principal ≥ 70% e n ≥ 30.

### 1h

| corte | θ | cruzamentos | perdeu a origem (principal) | entre decididos (n) | sorteio | passeio | ≥ sorteio + 2 EP |
|---|---|---|---|---|---|---|---|
| todos | 0.5 | 2831 | 57% ± 1 | 59% (2727) | 55% | 50% | não |
| todos | 0.618 | 2660 | 61% ± 1 | 63% (2564) | 59% | 62% | não |
| todos | 0.786 | 2250 | 73% ± 1 | 75% (2188) | 70% | 79% | sim |
| todos | 0.886 | 1949 | 84% ± 1 | 86% (1908) | 80% | 89% | sim |
| treino | 0.786 | 1042 | 70% ± 1 | 73% (1002) | 69% | 79% | não |
| validacao | 0.786 | 668 | 75% ± 2 | 77% (653) | 72% | 79% | sim |
| holdout | 0.786 | 540 | 74% ± 2 | 75% (533) | 72% | 79% | não |
| bull | 0.786 | 1094 | 73% ± 1 | 75% (1065) | 69% | 79% | sim |
| bear | 0.786 | 1156 | 73% ± 1 | 75% (1123) | 71% | 79% | não |
| impulso | 0.786 | 1061 | 74% ± 1 | 76% (1027) | 72% | 79% | não |
| corretivo_completo | 0.786 | 1189 | 72% ± 1 | 74% (1161) | 69% | 79% | não |
| principal | 0.786 | 851 | 72% ± 2 | 75% (826) | 70% | 79% | não |

Desfechos em θ = 0,786: perdeu 1635, sobreviveu 553, indefinido 48, ambiguo 14

### 4h

| corte | θ | cruzamentos | perdeu a origem (principal) | entre decididos (n) | sorteio | passeio | ≥ sorteio + 2 EP |
|---|---|---|---|---|---|---|---|
| todos | 0.5 | 661 | 58% ± 2 | 61% (635) | 57% | 50% | não |
| todos | 0.618 | 624 | 62% ± 2 | 64% (600) | 60% | 62% | não |
| todos | 0.786 | 532 | 73% ± 2 | 75% (521) | 72% | 79% | não |
| todos | 0.886 | 473 | 83% ± 2 | 84% (466) | 81% | 89% | não |
| treino | 0.786 | 257 | 73% ± 3 | 76% (246) | 72% | 79% | não |
| validacao | 0.786 | 151 | 76% ± 3 | 76% (151) | 71% | 79% | não |
| holdout | 0.786 | 124 | 71% ± 4 | 71% (124) | 74% | 79% | não |
| bull | 0.786 | 252 | 73% ± 3 | 74% (248) | 71% | 79% | não |
| bear | 0.786 | 280 | 74% ± 3 | 76% (273) | 73% | 79% | não |
| impulso | 0.786 | 263 | 70% ± 3 | 72% (257) | 73% | 79% | não |
| corretivo_completo | 0.786 | 269 | 77% ± 3 | 78% (264) | 71% | 79% | sim |
| principal | 0.786 | 197 | 77% ± 3 | 79% (193) | 71% | 79% | sim |

Desfechos em θ = 0,786: perdeu 391, sobreviveu 130, indefinido 9, ambiguo 2

## Veredito pelo critério

- **1h: VALE (≥ 70%)** — n = 2250, perdeu a origem em 73% ± 1 pp; data sorteada 70%; passeio aleatório 79%.
- **4h: VALE (≥ 70%)** — n = 532, perdeu a origem em 73% ± 2 pp; data sorteada 72%; passeio aleatório 79%.
## Conclusão (escrita à mão; rodar o script de novo apaga esta seção)

1. **Pelo critério escrito antes, a regra VALE** no 1 h e no 4 h: depois de a onda 2 passar 0,786, a origem da onda 1 é perdida em 73% dos casos (n = 2.250 e 532).
2. Mas **quase não diz nada sobre Elliott**: a mesma geometria em datas sorteadas (stop e alvo às mesmas distâncias percentuais do fechamento do cruzamento) perde a origem em 70% (1 h) e 72% (4 h).
3. A diferença é de 1 a 3 pontos: 2 EP no 1 h (73 × 70%), dentro do erro no 4 h (73 × 72%). A coluna "passeio" (79%, a partir de exatamente θ) não é comparável, porque o fechamento do cruzamento costuma estar além de 0,786.
4. Os "80–90%" do Tradeiros não aparecem em 0,786. Aparecem em 0,886 (83–84%), onde o sorteio dá 80–81%. É distância ao stop, não leitura de onda.
5. O padrão é estável: 70–76% nos 3 períodos, nos dois vieses, em impulso e em corretivo completo, e 72–77% quando a onda 2 é a contagem principal.
6. Uso prático: "passou 0,786 → reduz/sai" é gestão de risco razoável (a chance de voltar ao topo antes da origem cai para ~25%), mas não é sinal de venda nem prova de contagem errada. Comprar ali com stop na origem é aposta de geometria: o acerto é o que a distância dá, sem vantagem.
7. Limites: só 2021-06/10 a 2026-09 (cobertura de data/cenarios); E reconstruído confere 100% com o motor nos cenários de impulso; horizonte fixo de 60 candles (indefinidos < 2%).
8. Não muda o motor: o stop operacional em 0,786 (camada "perde probabilidade" de contagem_metodo.md §10.3, item 5) pode existir, mas como stop, e com o % do sorteio ao lado, não como probabilidade de Elliott.
