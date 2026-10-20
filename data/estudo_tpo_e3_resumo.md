# TPO E3 — a América contra a manhã (passo 3 do plano de gestão)

Gerado por `scripts/estudo_tpo_e2_e3.py` (regra exata no docstring, escrita antes de rodar). BTCUSDT 5 min Binance, dias úteis, 2020-01 a 2026-09. Custo real, leitura pessimista, sem veto de evento.

## Funil

| lado | dias com forma | gatilho | stop < 0,4% | sem alvo a 2R | sem fatia | aviso sai | preencheu |
|---|---|---|---|---|---|---|---|
| venda | 61 | 30 | 3 | 0 | 0 | 27 | 21 |
| compra | 35 | 11 | 0 | 0 | 0 | 11 | 9 |

## Resultado (R líquido por trade preenchido)

(1) = nível sorteado na faixa da manhã (20 sorteios por dia, regra inteira refeita); (2) = direção sorteada. Critério por lado: líquido > 0 nos 3 períodos com n ≥ 30 e, em treino e validação, ≥ (1) + 2 EP e ≥ (2) + 2 EP.

| linha | período | n | acerto (>0) | média R ± EP | (1) nível sorteado (n) | (2) direção sorteada (n) | ≥ (1)+2EP | ≥ (2)+2EP | sem 1R |
|---|---|---|---|---|---|---|---|---|---|
| E3 venda (forma P) | treino | 11 | 36% | -0.309 ± +0.356 | +0.146 (47) | -0.123 (11) | não | não | -0.414 |
| E3 venda (forma P) | validacao | 5 | 0% | -1.152 ± +0.029 | -0.578 (18) | -0.305 (5) | não | não | -1.152 |
| E3 venda (forma P) | holdout | 5 | 60% | +0.033 ± +0.536 | -0.621 (39) | -0.253 (5) | não | não | -0.442 |
| E3 compra (forma b) | treino | 4 | 25% | -0.717 ± +0.381 | +0.003 (15) | -0.339 (4) | não | não | -0.264 |
| E3 compra (forma b) | validacao | 3 | 100% | +0.415 ± +0.036 | +0.442 (3) | -0.345 (3) | não | sim | -0.451 |
| E3 compra (forma b) | holdout | 2 | 0% | -1.163 ± +0.064 | -1.075 (15) | -0.078 (2) | não | não | -1.163 |
| E3 (os dois lados) | treino | 15 | 33% | -0.418 ± +0.278 | +0.112 (62) | -0.180 (15) | não | não | -0.374 |
| E3 (os dois lados) | validacao | 8 | 38% | -0.564 ± +0.288 | -0.432 (21) | -0.320 (8) | não | não | -0.889 |
| E3 (os dois lados) | holdout | 7 | 43% | -0.309 ± +0.431 | -0.747 (54) | -0.203 (7) | não | não | -0.648 |

### Ano a ano

| ano | venda n | venda média | compra n | compra média |
|---|---|---|---|---|
| 2020 | 2 | -1.114 | 1 | -1.120 |
| 2021 | 2 | +0.267 | 0 | - |
| 2022 | 5 | +0.104 | 3 | -0.582 |
| 2023 | 2 | -1.111 | 0 | - |
| 2024 | 2 | -1.089 | 3 | +0.415 |
| 2025 | 5 | -0.874 | 0 | - |
| 2026 | 3 | +0.318 | 2 | -1.163 |

## Veredito pelo critério

- **E3 venda (forma P): INCONCLUSIVA** — treino: n=11 < 30; validacao: n=5 < 30; holdout: n=5 < 30
- **E3 compra (forma b): INCONCLUSIVA** — treino: n=4 < 30; validacao: n=3 < 30; holdout: n=2 < 30
- **E3 (os dois lados): INCONCLUSIVA** — treino: n=15 < 30; validacao: n=8 < 30; holdout: n=7 < 30
## Conclusão (escrita à mão; rodar o script de novo apaga esta seção)

1. **Veredito: INCONCLUSIVA por amostra, e negativa onde há dado.** 30 trades preenchidos em 6,7 anos (15 / 8 / 7 por período). Nenhum período chega a 30.
2. Os dois lados juntos: −0,42 R no treino, −0,56 na validação e −0,31 no holdout. A venda (forma P) dá −0,31 / −1,15 / +0,03.
3. Fica abaixo do nível sorteado na faixa da manhã no treino (+0,11) e abaixo da direção sorteada em todos os períodos. O POC da manhã não acrescenta nada como gatilho.
4. A forma exigida é rara: 96 dias com manhã P/b fora do valor de ontem e dentro do composto; só 41 tiveram fechamento da América através do POC até 16:00.
5. O especialista já tinha avisado que é a regra mais parecida com o que falhou (POC de sessão no 1º toque = sorteio; extremo de sessão pior que o sorteio). O resultado confirma.
6. Sem 1R fica pior (−0,37 / −0,89 / −0,65): não é a gestão que estraga.
7. Recomendação: E3 sai da fila de avisos. O POC e a máxima/mínima da manhã ficam no mapa só como alvo e stop (seção 3 de docs/especialistas/tpo.md).
8. Não vale reteste: além de pouca amostra, o sinal tem o sinal errado nos dois períodos com mais dados.
