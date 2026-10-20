# OB E2 — varredura de liquidez + volta (passo 5 do plano de gestão)

Gerado por `scripts/estudo_ob_e2.py` (regra exata no docstring, escrita antes de rodar). BTCUSDT Binance: liquidez e varredura em 1 h, CHoCH e OB em 15 min, direção em 4 h, execução em 5 min; dias úteis, 2020-01 a 2026-09. Custo real, leitura pessimista, sem veto de evento macro.

## Funil (varreduras confirmadas em dia útil com o 4 h permitindo)

- varreduras: 759 (venda 367, compra 392)
- sem swing 15m: 0
- sem CHoCH: 643
- sem OB: 0
- deslocamento < 1 ATR: 0
- sem FVG: 28
- zona vazia: 0
- com CHoCH + OB + deslocamento + FVG: 88
- entrada A: stop < 0,4% 29, sem alvo a 2R 1, sem fatia 0, aviso sai 58, preencheu 18, no quartil 9
- entrada B: stop < 0,4% 0, sem alvo a 2R 14, sem fatia 0, aviso sai 74, preencheu 74, no quartil 33

## Resultado (R líquido por trade preenchido, 1R realiza 50% e stop no médio)

(1) OB sem qualificação (detector antigo, população); (2) zona sorteada (só A, média de 20); (3) direção sorteada; (4) varredura sem CHoCH (a mercado na volta). Critério: líquido > 0 nos 3 períodos com n ≥ 30 e, em treino e validação, ≥ cada controle aplicável + 2 EP.

| variante | período | n | acerto | média R ± EP | (1) OB simples (n) | (2) zona | (3) direção | (4) sem CHoCH (n) | passa controles |
|---|---|---|---|---|---|---|---|---|---|
| OB E2 A base | treino | 14 | 64% | +0.120 ± +0.269 | +0.108 (406) | -0.096 | -0.034 | -0.172 (373) | não |
| OB E2 A base | validacao | 1 | 100% | +0.400 ± - | -0.160 (88) | -0.367 | -0.438 | -0.138 (149) | não |
| OB E2 A base | holdout | 3 | 100% | +1.386 ± +0.495 | -0.016 (33) | +1.262 | -0.145 | -0.223 (121) | não |
| OB E2 A quartil | treino | 6 | 100% | +0.798 ± +0.175 | +0.201 (84) | +0.615 | -0.002 | -0.187 (179) | não |
| OB E2 A quartil | validacao | 1 | 100% | +0.400 ± - | -0.244 (17) | -0.367 | -0.438 | -0.089 (60) | não |
| OB E2 A quartil | holdout | 2 | 100% | +1.029 ± +0.592 | +1.410 (3) | +1.084 | -0.037 | -0.252 (51) | não |
| OB E2 B base | treino | 41 | 49% | -0.014 ± +0.149 | +0.108 (406) | — | -0.093 | -0.172 (373) | não |
| OB E2 B base | validacao | 19 | 53% | +0.368 ± +0.258 | -0.160 (88) | — | -0.011 | -0.138 (149) | não |
| OB E2 B base | holdout | 14 | 64% | +0.117 ± +0.266 | -0.016 (33) | — | -0.166 | -0.223 (121) | não |
| OB E2 B quartil | treino | 18 | 61% | +0.411 ± +0.195 | +0.201 (84) | — | -0.015 | -0.187 (179) | não |
| OB E2 B quartil | validacao | 6 | 50% | +0.157 ± +0.441 | -0.244 (17) | — | -0.085 | -0.089 (60) | não |
| OB E2 B quartil | holdout | 9 | 56% | -0.123 ± +0.312 | +1.410 (3) | — | -0.200 | -0.252 (51) | não |

### Por tipo de liquidez e lado (entrada A, base, todos os períodos; informativo)

| tipo | lado | n | acerto | média R ± EP |
|---|---|---|---|---|
| iguais | compra | 2 | 100% | +0.917 ± +0.511 |
| iguais | venda | 1 | 100% | +1.509 ± - |
| ontem | compra | 8 | 38% | -0.375 ± +0.374 |
| ontem | venda | 2 | 100% | +1.267 ± +0.834 |
| semana | compra | 1 | 100% | +0.455 ± - |
| semana | venda | 4 | 100% | +0.726 ± +0.180 |

### Ano a ano (entrada A e B, base)

| ano | A n | A média | B n | B média | (4) sem CHoCH média |
|---|---|---|---|---|---|
| 2020 | 2 | -0.318 | 8 | +0.251 | -0.226 |
| 2021 | 3 | +0.290 | 12 | +0.405 | +0.020 |
| 2022 | 6 | +0.166 | 7 | -0.360 | -0.287 |
| 2023 | 3 | +0.150 | 14 | -0.350 | -0.165 |
| 2024 | 0 | - | 10 | +1.201 | -0.155 |
| 2025 | 3 | +0.819 | 15 | -0.466 | -0.092 |
| 2026 | 1 | +2.101 | 8 | +0.449 | -0.308 |

### Controles por período e lado (informativo)

| controle | período | lado | n | média R ± EP |
|---|---|---|---|---|
| ob_simples | holdout | compra | 19 | +0.075 ± +0.279 |
| ob_simples | holdout | venda | 14 | -0.140 ± +0.383 |
| ob_simples | treino | compra | 198 | +0.145 ± +0.077 |
| ob_simples | treino | venda | 208 | +0.072 ± +0.086 |
| ob_simples | validacao | compra | 41 | -0.115 ± +0.166 |
| ob_simples | validacao | venda | 47 | -0.198 ± +0.160 |
| sem_choch | holdout | compra | 65 | -0.191 ± +0.144 |
| sem_choch | holdout | venda | 56 | -0.260 ± +0.142 |
| sem_choch | treino | compra | 197 | -0.247 ± +0.080 |
| sem_choch | treino | venda | 176 | -0.087 ± +0.085 |
| sem_choch | validacao | compra | 74 | -0.465 ± +0.118 |
| sem_choch | validacao | venda | 75 | +0.185 ± +0.138 |

## Veredito pelo critério

- **OB E2 A base: INCONCLUSIVA** — treino: n=14 < 30; validacao: n=1 < 30; holdout: n=3 < 30
- **OB E2 A quartil: INCONCLUSIVA** — treino: n=6 < 30; validacao: n=1 < 30; holdout: n=2 < 30
- **OB E2 B base: REPROVADA** — treino: líquido -0.014 ≤ 0; treino: não fica 2 EP acima de todos os controles; validacao: n=19 < 30; holdout: n=14 < 30
- **OB E2 B quartil: INCONCLUSIVA** — treino: n=18 < 30; validacao: n=6 < 30; holdout: n=9 < 30
## Conclusão (escrita à mão; rodar o script de novo apaga esta seção)

1. **Veredito: A (reteste) INCONCLUSIVA nas duas variantes; B (a mercado) base REPROVADA (treino −0,01 R, n = 41); B no quartil INCONCLUSIVA.**
2. A regra quase não acontece: 759 varreduras válidas em dia útil com o 4 h permitindo, 88 com CHoCH + OB + FVG (~0,25 por semana) e só **18 retestes preenchidos** em 6,7 anos. A estimativa do especialista era de 1 a 3 por semana.
3. O gargalo é o CHoCH: 643 das 759 varreduras não fecham abaixo do swing de 15 min em 2 h. Quando fecha, o reteste da zona do OB em 4 h é raro (18 de 58).
4. O controle mais informativo: **a varredura com volta, sem CHoCH, perde nos 3 períodos** (−0,17 / −0,14 / −0,22 R; n = 373 / 149 / 121). A tese "varreu e voltou = presos" não paga sozinha.
5. Com CHoCH a mercado (B): −0,01 / +0,37 / +0,12 R com n = 41 / 19 / 14. Não fica acima do OB simples no treino (+0,11).
6. O OB sem qualificação (detector antigo, com stop ≥ 0,4% e alvo a 2R) dá +0,11 no treino e −0,16 / −0,02 depois: zero, como no scalp de 11/09.
7. Os números de A (+0,12 / +0,40 / +1,39) vêm de 14 / 1 / 3 trades: não dizem nada.
8. O motor de swing/BOS/FVG/CHoCH (conselho/estrutura.py) fica pronto para o OB E1 (OB qualificado em 1 h), que tem mais eventos. A E2 só volta com outra definição de liquidez/CHoCH, e isso seria uma estratégia nova, pré-registrada.
