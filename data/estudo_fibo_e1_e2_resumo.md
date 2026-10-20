# Fibonacci E1 (escada 0,5–0,786 depois de quebra) + E2 (régua de saída) — passo 4 do plano de gestão

Gerado por `scripts/estudo_fibo_e1_e2.py` (regra exata no docstring, escrita antes de rodar). BTCUSDT Binance, perna e gatilho em 15 min e 1 h, execução em 5 min, dias úteis, 2020-01 a 2026-09. Custo real (maker 0,02%, taker 0,055% + 0,02%, funding linear), leitura pessimista. Sem veto de evento macro.

## Funil

| TF | gatilhos (dias úteis) | L < 0,8% | stop < 0,4% | alvo < 2R | sem fatia | aviso sai | preencheu | no terço |
|---|---|---|---|---|---|---|---|---|
| 15m | 14235 | 4899 | 1417 | 0 | 1 | 7918 | 4051 | 1572 |
| 1h | 3448 | 78 | 99 | 0 | 2 | 3269 | 1793 | 659 |

## E1 — entrada em escada com a régua como saída (R líquido por trade preenchido)

(1) faixa sorteada na mesma perna (média de 20); (2) direção sorteada; (3) entrada única em 0,618. Critério: líquido > 0 nos 3 períodos com n ≥ 30 e, em treino e validação, ≥ cada controle + 2 EP.

| variante | período | n | acerto | média R ± EP | (1) faixa | (2) direção | (3) 0,618 (n) | ≥(1)+2EP | ≥(2)+2EP | ≥(3)+2EP |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 15m base | treino | 2777 | 57% | +0.031 ± +0.021 | -0.015 | -0.177 | -0.152 (2053) | sim | sim | sim |
| E1 15m base | validacao | 828 | 55% | -0.044 ± +0.039 | -0.094 | -0.154 | -0.184 (612) | não | sim | sim |
| E1 15m base | holdout | 446 | 60% | +0.039 ± +0.051 | -0.009 | -0.203 | -0.212 (316) | não | sim | sim |
| E1 15m terco | treino | 1064 | 57% | +0.021 ± +0.034 | -0.032 | -0.163 | -0.161 (762) | não | sim | sim |
| E1 15m terco | validacao | 334 | 54% | -0.019 ± +0.063 | -0.067 | -0.179 | -0.147 (244) | não | sim | sim |
| E1 15m terco | holdout | 174 | 66% | +0.136 ± +0.080 | +0.058 | -0.202 | -0.088 (130) | não | sim | sim |
| E1 1h base | treino | 1079 | 57% | +0.069 ± +0.034 | +0.034 | -0.095 | -0.153 (827) | não | sim | sim |
| E1 1h base | validacao | 400 | 59% | +0.108 ± +0.058 | +0.067 | -0.130 | -0.077 (337) | não | sim | sim |
| E1 1h base | holdout | 314 | 57% | +0.066 ± +0.067 | +0.040 | -0.102 | -0.077 (250) | não | sim | sim |
| E1 1h terco | treino | 394 | 58% | +0.066 ± +0.055 | +0.039 | -0.079 | -0.223 (296) | não | sim | sim |
| E1 1h terco | validacao | 156 | 58% | +0.077 ± +0.090 | +0.034 | -0.152 | -0.120 (130) | não | sim | sim |
| E1 1h terco | holdout | 109 | 60% | +0.177 ± +0.118 | +0.156 | -0.142 | +0.072 (89) | não | sim | não |

### E1 por lado (base, todos os períodos de treino+validação; informativo)

| TF | lado | n | média R (régua) | direção sorteada | faixa sorteada |
|---|---|---|---|---|---|
| 15m | compra | 1740 | +0.048 | -0.166 | -0.002 |
| 15m | venda | 1865 | -0.018 | -0.178 | -0.062 |
| 1h | compra | 733 | +0.097 | -0.104 | +0.067 |
| 1h | venda | 746 | +0.064 | -0.105 | +0.019 |

### E1 ano a ano (base)

| TF | ano | n | média R | direção sorteada |
|---|---|---|---|---|
| 15m | 2020 | 705 | +0.054 | -0.177 |
| 15m | 2021 | 990 | +0.033 | -0.172 |
| 15m | 2022 | 742 | +0.014 | -0.188 |
| 15m | 2023 | 340 | +0.016 | -0.172 |
| 15m | 2024 | 599 | -0.038 | -0.154 |
| 15m | 2025 | 379 | +0.019 | -0.179 |
| 15m | 2026 | 296 | -0.009 | -0.195 |
| 1h | 2020 | 281 | +0.095 | -0.098 |
| 1h | 2021 | 242 | +0.129 | -0.059 |
| 1h | 2022 | 267 | -0.024 | -0.139 |
| 1h | 2023 | 289 | +0.082 | -0.081 |
| 1h | 2024 | 273 | +0.118 | -0.115 |
| 1h | 2025 | 248 | +0.064 | -0.119 |
| 1h | 2026 | 193 | +0.083 | -0.119 |

## E2 — a régua contra outras saídas, nas mesmas entradas

Médias em R. Diferenças pareadas (mesmo trade) com EP. (a) alvo fixo 2R; (b) régua; (c) 1R + stop no médio + resto em 2R; (d) régua com níveis sorteados (mesma distribuição de distância). Critério: em treino e validação (b)−(a) > 2 EP e (b)−(d) > 2 EP nas entradas reais, e (b)−(a) NÃO > 2 EP nas entradas de direção sorteada.

| variante | período | n | (a) | (b) | (c) | (d) | (b)−(a) ± EP | (b)−(d) ± EP | sorteadas: (b)−(a) ± EP |
|---|---|---|---|---|---|---|---|---|---|
| E2 15m base | treino | 2777 | +0.060 | +0.031 | +0.042 | +0.038 | -0.028 ± +0.013 | -0.007 ± +0.002 | -0.057 ± +0.011 |
| E2 15m base | validacao | 828 | -0.024 | -0.044 | -0.016 | -0.032 | -0.020 ± +0.024 | -0.011 ± +0.004 | -0.025 ± +0.021 |
| E2 15m base | holdout | 446 | +0.028 | +0.039 | +0.054 | +0.040 | +0.012 ± +0.035 | -0.000 ± +0.004 | -0.049 ± +0.029 |
| E2 15m terco | treino | 1064 | +0.072 | +0.021 | +0.038 | +0.028 | -0.051 ± +0.021 | -0.007 ± +0.004 | -0.076 ± +0.019 |
| E2 15m terco | validacao | 334 | -0.009 | -0.019 | +0.001 | -0.007 | -0.011 ± +0.036 | -0.012 ± +0.005 | -0.055 ± +0.034 |
| E2 15m terco | holdout | 174 | +0.156 | +0.136 | +0.167 | +0.137 | -0.021 ± +0.063 | -0.002 ± +0.007 | -0.047 ± +0.048 |
| E2 1h base | treino | 1079 | +0.058 | +0.069 | +0.067 | +0.069 | +0.011 ± +0.021 | +0.000 ± +0.003 | -0.051 ± +0.018 |
| E2 1h base | validacao | 400 | +0.151 | +0.108 | +0.114 | +0.108 | -0.043 ± +0.036 | +0.001 ± +0.007 | +0.067 ± +0.029 |
| E2 1h base | holdout | 314 | +0.078 | +0.066 | +0.060 | +0.084 | -0.012 ± +0.037 | -0.018 ± +0.005 | +0.013 ± +0.033 |
| E2 1h terco | treino | 394 | +0.096 | +0.066 | +0.075 | +0.066 | -0.030 ± +0.036 | +0.001 ± +0.006 | -0.016 ± +0.030 |
| E2 1h terco | validacao | 156 | +0.088 | +0.077 | +0.107 | +0.078 | -0.011 ± +0.055 | -0.001 ± +0.010 | +0.069 ± +0.048 |
| E2 1h terco | holdout | 109 | +0.150 | +0.177 | +0.170 | +0.189 | +0.027 ± +0.060 | -0.012 ± +0.011 | +0.019 ± +0.058 |

### Saídas da régua (base)

| TF | saída | n | média R |
|---|---|---|---|
| 15m | alvo | 869 | +1.636 |
| 15m | medio | 1376 | +0.410 |
| 15m | stop | 1722 | -1.147 |
| 15m | tempo | 84 | +0.698 |
| 1h | alvo | 401 | +1.723 |
| 1h | medio | 610 | +0.441 |
| 1h | stop | 754 | -1.116 |
| 1h | tempo | 28 | +0.719 |

## Veredito pelo critério

- **E1 15m base: REPROVADA** — validacao: líquido -0.044 ≤ 0; validacao: não fica 2 EP acima de todos os controles
- **E1 15m terco: REPROVADA** — treino: não fica 2 EP acima de todos os controles; validacao: líquido -0.019 ≤ 0; validacao: não fica 2 EP acima de todos os controles
- **E1 1h base: REPROVADA** — treino: não fica 2 EP acima de todos os controles; validacao: não fica 2 EP acima de todos os controles
- **E1 1h terco: REPROVADA** — treino: não fica 2 EP acima de todos os controles; validacao: não fica 2 EP acima de todos os controles
- **E2 15m base: REPROVADA** — treino: (b) não bate (a) por 2 EP; treino: (b) não bate (d) por 2 EP; validacao: (b) não bate (a) por 2 EP; validacao: (b) não bate (d) por 2 EP
- **E2 15m terco: REPROVADA** — treino: (b) não bate (a) por 2 EP; treino: (b) não bate (d) por 2 EP; validacao: (b) não bate (a) por 2 EP; validacao: (b) não bate (d) por 2 EP
- **E2 1h base: REPROVADA** — treino: (b) não bate (a) por 2 EP; treino: (b) não bate (d) por 2 EP; validacao: (b) não bate (a) por 2 EP; validacao: (b) não bate (d) por 2 EP; validacao: (b) também bate (a) nas entradas sorteadas
- **E2 1h terco: REPROVADA** — treino: (b) não bate (a) por 2 EP; treino: (b) não bate (d) por 2 EP; validacao: (b) não bate (a) por 2 EP; validacao: (b) não bate (d) por 2 EP
## Conclusão (escrita à mão; rodar o script de novo apaga esta seção)

1. **E1: REPROVADA nas 4 variantes** (15m/1h × base/terço). **E2: REPROVADA nas 4.** Amostra grande: 4.051 preenchidos em 15 min e 1.793 em 1 h.
2. A escada (−0,04 a +0,18 R por linha) fica acima da direção sorteada (−0,08 a −0,20) e da entrada única em 0,618 em quase todas as linhas. Mas **não fica acima da faixa sorteada na mesma perna**, que é o controle que mede o Fibonacci.
3. No 1 h, base: +0,07 / +0,11 / +0,07 R nos 3 períodos; a faixa sorteada dá +0,03 / +0,07 / +0,04. A proporção 0,5–0,786 não acrescenta nada; o que sobra é a mecânica "recuo depois de quebra, a favor da perna, stop na origem".
4. Em 15 min o resultado é ~0 (+0,03 / −0,04 / +0,04) e negativo na validação. O custo (~0,12 R por trade com stop de ~0,5%) come o pouco que existe.
5. E2 (régua 1R + topo + 1,618) não bate o alvo fixo de 2R em nenhuma variante: (b)−(a) entre −0,05 e +0,03 R. Também não bate os níveis sorteados à mesma distância: (b)−(d) ≈ 0.
6. Isso confirma o que a calibração de Elliott já tinha mostrado: a saída não cria esperança. A distância do alvo em R importa; o nível de Fibonacci onde ele cai, não.
7. O contexto "terço do composto" não muda nada de forma consistente (reduz n e melhora só o holdout).
8. Resultado útil: Fibonacci sai de gatilho e de régua. Candidato a estudo próprio, pré-registrado e sem Fibonacci: "recuo em faixa sorteada depois de quebra de micro em 1 h". É positivo nos 3 períodos no controle, mas ninguém o testou contra os seus próprios controles.
