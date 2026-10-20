# TPO E2 — cauda no bloco de 30 min na borda (passo 3 do plano de gestão)

Gerado por `scripts/estudo_tpo_e2_e3.py` (regra exata no docstring, escrita antes de rodar). BTCUSDT 5 min Binance, dias úteis, blocos das 08:00 às 20:00 UTC, 2020-01 a 2026-09. Custo real (maker 0,02%, taker 0,055% + 0,02% de slippage, funding linear), leitura pessimista. Sem veto de evento macro (não há tabela no projeto).

## Funil

| grupo | lado | eventos com cauda | stop < 0,4% | sem alvo a 2R | sem fatia | aviso sai | preencheu |
|---|---|---|---|---|---|---|---|
| E2 | compra | 101 | 11 | 9 | 0 | 81 | 80 |
| E2 | venda | 92 | 19 | 2 | 0 | 71 | 69 |
| sem_nivel | compra | 1678 | 427 | 330 | 0 | 921 | 879 |
| sem_nivel | venda | 1257 | 336 | 191 | 0 | 730 | 698 |

## Resultado (R líquido por trade preenchido, 1R realiza 50% e stop no médio)

(a) = mesma cauda sem nível (população); (b) = direção sorteada (média de mesma e oposta). Critério: líquido > 0 nos 3 períodos com n ≥ 30 e, em treino e validação, ≥ (a) + 2 EP e ≥ (b) + 2 EP.

| linha | período | n | acerto (>0) | média R ± EP | (a) cauda sem nível (n) | (b) direção sorteada (n) | ≥ (a)+2EP | ≥ (b)+2EP | sem 1R |
|---|---|---|---|---|---|---|---|---|---|
| E2 (compra+venda) | treino | 101 | 64% | +0.227 ± +0.109 | -0.008 (1075) | -0.135 (101) | sim | sim | +0.366 |
| E2 (compra+venda) | validacao | 29 | 66% | +0.057 ± +0.177 | -0.068 (341) | -0.156 (29) | não | não | -0.166 |
| E2 (compra+venda) | holdout | 19 | 74% | +0.409 ± +0.236 | +0.049 (161) | -0.193 (19) | não | sim | +0.458 |
| E2 compra | treino | 48 | 69% | +0.221 ± +0.145 | +0.002 (595) | -0.184 (48) | não | sim | +0.240 |
| E2 compra | validacao | 21 | 62% | +0.000 ± +0.212 | -0.030 (191) | -0.125 (21) | não | não | -0.330 |
| E2 compra | holdout | 11 | 82% | +0.702 ± +0.321 | +0.033 (93) | -0.205 (11) | sim | sim | +0.860 |
| E2 venda | treino | 53 | 60% | +0.232 ± +0.164 | -0.019 (480) | -0.090 (53) | não | não | +0.481 |
| E2 venda | validacao | 8 | 75% | +0.206 ± +0.336 | -0.116 (150) | -0.235 (8) | não | não | +0.264 |
| E2 venda | holdout | 8 | 62% | +0.007 ± +0.311 | +0.071 (68) | -0.176 (8) | não | não | -0.095 |

### Controle (a') informativo: cauda sem nível com o fechamento no quartil de fora do composto

| período | n | acerto | média R ± EP |
|---|---|---|---|
| treino | 456 | 53% | -0.097 ± +0.048 |
| validacao | 154 | 52% | -0.045 ± +0.096 |
| holdout | 69 | 57% | +0.080 ± +0.146 |

### Por nível (E2, todos os períodos; informativo)

| nível | n | acerto | média R ± EP |
|---|---|---|---|
| composto_VAH | 26 | 58% | +0.128 ± +0.221 |
| composto_VAL | 44 | 77% | +0.361 ± +0.131 |
| naked | 16 | 62% | +0.058 ± +0.261 |
| ontem_VAH | 35 | 66% | +0.302 ± +0.194 |
| ontem_VAL | 28 | 57% | +0.060 ± +0.226 |

### Ano a ano (E2)

| ano | n | média R | (a) média | (b) média |
|---|---|---|---|---|
| 2020 | 27 | +0.295 | +0.004 | -0.234 |
| 2021 | 26 | +0.322 | +0.040 | -0.056 |
| 2022 | 23 | +0.129 | -0.109 | -0.224 |
| 2023 | 25 | +0.145 | +0.032 | -0.027 |
| 2024 | 19 | +0.053 | -0.098 | -0.215 |
| 2025 | 17 | +0.135 | +0.088 | -0.149 |
| 2026 | 12 | +0.512 | -0.026 | -0.131 |

### Saídas (E2)

| saída | n | média R |
|---|---|---|
| alvo | 22 | +1.743 |
| horario | 38 | +0.558 |
| medio | 42 | +0.403 |
| stop | 42 | -1.171 |
| tempo | 5 | +1.008 |

## Veredito pelo critério

- **E2 (compra+venda): INCONCLUSIVA** — validacao: n=29 < 30; holdout: n=19 < 30
- **E2 compra: REPROVADA** — treino: não fica 2 EP acima de todos os controles; validacao: n=21 < 30; holdout: n=11 < 30
- **E2 venda: REPROVADA** — treino: não fica 2 EP acima de todos os controles; validacao: n=8 < 30; holdout: n=8 < 30
## Conclusão (escrita à mão; rodar o script de novo apaga esta seção)

1. **Veredito: INCONCLUSIVA.** Líquido positivo nos 3 períodos (+0,23 / +0,06 / +0,41 R), mas validação e holdout têm 29 e 19 trades (< 30). Pelo critério, nunca "aprovada" com isso.
2. No treino (n = 101) fica 2 EP acima dos dois controles: cauda sem nível −0,01 R (n = 1.075) e direção sorteada −0,14 R. Na validação, não (EP de 0,18 com n = 29).
3. Por lado, compra e venda são reprovadas no treino (n ≈ 50 cada, EP grande). O sinal só aparece com os dois lados juntos.
4. O controle (a) responde à pergunta do especialista: a cauda **sem** nível é zero ou negativa nos 3 períodos (−0,01 / −0,07 / +0,05). A cauda sozinha não paga; o que separa é estar numa borda do mapa **vindo de longe**. Ressalva: (a) também não exige "de longe", então o estudo não separa o nível do "veio de longe".
5. Frequência real: 193 eventos em 6,7 anos (~0,6 por semana), não as 3 a 6 por semana estimadas. Isso explica o n curto fora do treino.
6. Melhores bordas (informativo, sem teste): VAL do composto +0,36 R (n = 44) e VAH de ontem +0,30 R (n = 35). Naked POC e VAL de ontem ficam perto de zero.
7. Sem 1R, a média sobe no treino (+0,37) e cai na validação (−0,17): realizar em 1R não é o que decide.
8. Próximo passo honesto: regra congelada como está, reteste pré-registrado em dado novo (2017-09..2019-12, nunca olhado, e os avisos ao vivo contados na tela `/avisos`) até ter ≥ 30 por período. Sem mexer em 0,30% / 60% / 4 h.
