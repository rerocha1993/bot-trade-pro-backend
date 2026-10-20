# Estudo TPO E1 + Regime F1 — resultado

Gerado por `scripts/estudo_tpo_e1.py` em 2026-10-20 14:45 UTC. Regra exata e critério no docstring do script (escritos antes de rodar; nenhum parâmetro iterado).

## Veredito pelo critério escrito antes

- TPO E1 **dia × fechamento**: reprovada — treino: líquido -0.190 ≤ 0; treino: não está 2 EP acima da direção sorteada; treino: não está 2 EP acima da área deslocada; validacao: n=23 < 30 (inconclusivo)
- TPO E1 **dia × reteste**: reprovada — treino: não está 2 EP acima da direção sorteada; treino: não está 2 EP acima da área deslocada; validacao: n=28 < 30 (inconclusivo); holdout: n=23 < 30 (inconclusivo)
- TPO E1 **america × fechamento**: reprovada — treino: líquido -0.137 ≤ 0; treino: não está 2 EP acima da direção sorteada; treino: não está 2 EP acima da área deslocada; validacao: n=10 < 30 (inconclusivo)
- TPO E1 **america × reteste**: reprovada — treino: não está 2 EP acima da direção sorteada; treino: não está 2 EP acima da área deslocada; validacao: n=20 < 30 (inconclusivo); holdout: n=16 < 30 (inconclusivo)
- Regime F1 sobre **fixo10 VAL 1:1**: não separa — validacao: filtrado n=22 < 30; validacao: invertido não é pior que o sem-filtro; holdout: filtrado n=25 < 30; holdout: invertido não é pior que o sem-filtro
- Regime F1 sobre **fixo10 VAL 2:1**: não separa — validacao: filtrado n=21 < 30; holdout: filtrado n=25 < 30; holdout: filtrado supera só 3/20 sorteados
- Regime F1 sobre **fixo10 VAH 1:1**: não separa — treino: filtrado -0.224 ≤ 0; validacao: filtrado n=27 < 30; validacao: invertido não é pior que o sem-filtro; holdout: filtrado n=24 < 30
- Regime F1 sobre **fixo10 VAH 2:1**: não separa — treino: filtrado -0.151 ≤ 0; treino: invertido não é pior que o sem-filtro; validacao: filtrado n=24 < 30; validacao: invertido não é pior que o sem-filtro
- Regime F1 sobre **adapt VAL 1:1**: não separa — treino: filtrado -0.263 ≤ 0; treino: invertido não é pior que o sem-filtro; validacao: filtrado -0.005 ≤ 0; holdout: filtrado -0.346 ≤ 0
- Regime F1 sobre **adapt VAL 2:1**: não separa — treino: filtrado -0.406 ≤ 0; treino: invertido não é pior que o sem-filtro; validacao: filtrado -0.171 ≤ 0; holdout: filtrado -0.255 ≤ 0
- Regime F1 sobre **adapt VAH 1:1**: não separa — treino: filtrado -0.163 ≤ 0
- Regime F1 sobre **adapt VAH 2:1**: não separa — treino: filtrado -0.216 ≤ 0

## Conclusão (escrita à mão depois da rodada; o script regenera o resto do arquivo, não esta seção)

**TPO E1 — reprovada nas 4 variantes.**
1. As quatro falham já no treino 2020–23, o único período com amostra (34–69 trades): nenhuma fica 2 EP acima da direção sorteada nem da área deslocada.
2. Entrada no fechamento perde no treino (−0,19 R na abertura do dia; −0,14 R na América). Entrada no reteste fica positiva no treino (+0,17 / +0,02 R), mas a 1,0 e 0,1 EP do zero: não se separa de nada.
3. O filtro "largura ≥ 2× stop" corta 27–74% dos eventos (mais na entrada no fechamento): sobram 7–18 trades por ano por variante (não 1–3 por semana), e validação/holdout ficam com 5–28 trades, inconclusivos.
4. Dia × reteste, a melhor no treino, vai a −0,57 R no holdout (n=23). América × reteste é a única positiva nos 3 períodos (+0,02 / +0,10 / +0,17 R), com EP de 0,15–0,36 R: é sorteio.
5. O controle de área deslocada fica quase sempre entre −0,03 e −0,44 R (uma célula em +0,04): a mecânica (stop na excursão, 1R, alvo na borda oposta) já perde sozinha, e a área de ontem não acrescenta nada mensurável a ela.
6. Compra e venda trocam de sinal entre períodos, e o ano a ano alterna; sem o 1R (alvo inteiro) o quadro é o mesmo.
7. Veto de evento não aplicado (não há tabela de eventos) e o quartil do composto não foi exigido; nenhum dos dois cria vantagem onde o treino é zero.
8. Leitura: "abriu fora e voltou" é mais um fato de candle que empata com o sorteio. O aviso continua "sem % medido".

**Regime F1 — não separa (8 de 8 linhas reprovadas).**
1. A regra da seção 2.3 classifica muito diferente do esperado: R = 17% (Ásia) / 10% (América) contra 45–55% esperados, V = 4% contra 10–15%, e 18–21% dos dias não caem em tipo nenhum (N).
2. Filtrado em R/V nunca fica positivo nos 3 períodos; no treino (n 65–136) é negativo em 6 das 8 linhas.
3. O invertido (A/D) não é sistematicamente pior que o sem-filtro: perde a comparação em pelo menos um período em 5 linhas.
4. Contra os 20 sorteios de rótulo, o filtrado vence de 0/20 a 20/20 sem padrão: é o que o acaso faz com 8 linhas.
5. O único desenho parecido com separação, "adapt VAH venda" (filtrado +0,02 a +0,26 R em validação e holdout, 20/20 no holdout 2:1), é negativo no treino com n=136 (−0,16 / −0,22 R): reprovado, e não vira candidato sem pré-registro.
6. Por tipo de dia, nenhum tipo tem líquido positivo com amostra, exceto X (+0,15 R, n=43), que o regime manda não operar.
7. Validação e holdout têm 20–27 toques filtrados no composto fixo de 10 dias: abaixo de 30, inconclusivo mesmo se fosse positivo.
8. Leitura: o tipo de dia pela 1ª hora não diz quando a borda paga. Serve como etiqueta descritiva no aviso, sem efeito medido.

## Parte 1 — TPO E1 (abriu fora do valor de ontem e voltou)

### Funil (dias úteis 2020-01..2026-09)

| sessão | entrada | eventos (abriu fora e 2 blocos dentro) | aviso sai | largura < 2× stop | alvo < 2R | sem fatia | preencheu |
|---|---|---|---|---|---|---|---|
| dia | fechamento | 240 | 97 | 126 | 17 | 0 | 97 |
| dia | reteste | 240 | 176 | 64 | 0 | 0 | 120 |
| america | fechamento | 254 | 49 | 188 | 17 | 0 | 49 |
| america | reteste | 254 | 138 | 116 | 0 | 0 | 92 |

### Resultado por variante e período (R líquido por trade preenchido, com 1R e stop no médio)

EP = erro padrão da média. Controle D = direção sorteada (média de 20 sorteios, mesma entrada); controle A = área de valor deslocada ao acaso (20 sorteios, regra inteira refeita). Critério: líquido > 0 nos 3 períodos (n ≥ 30) e, em treino e validação, ≥ D + 2 EP e ≥ A + 2 EP.

| variante | período | n | acerto (>0) | média R ± EP | controle D | controle A (n) | ≥ D+2EP | ≥ A+2EP | sem 1R (média) |
|---|---|---|---|---|---|---|---|---|---|
| dia × fechamento | treino | 55 | +52.7% | -0.190 ± 0.141 | -0.237 | -0.225 (315) | não | não | -0.172 |
| dia × fechamento | validacao | 23 | +47.8% | -0.113 ± 0.280 | -0.261 | -0.074 (120) | não | não | +0.142 |
| dia × fechamento | holdout | 19 | +47.4% | -0.305 ± 0.265 | -0.315 | -0.441 (107) | não | não | -0.387 |
| dia × reteste | treino | 69 | +60.9% | +0.165 ± 0.162 | -0.115 | -0.090 (472) | não | não | +0.085 |
| dia × reteste | validacao | 28 | +67.9% | +0.053 ± 0.215 | -0.357 | -0.066 (188) | não | não | -0.037 |
| dia × reteste | holdout | 23 | +39.1% | -0.574 ± 0.175 | -0.270 | -0.221 (176) | não | não | -0.465 |
| america × fechamento | treino | 34 | +50.0% | -0.137 ± 0.178 | -0.125 | -0.151 (300) | não | não | -0.203 |
| america × fechamento | validacao | 10 | +70.0% | +0.398 ± 0.407 | -0.217 | +0.037 (107) | não | não | +0.343 |
| america × fechamento | holdout | 5 | +100.0% | +0.525 ± 0.288 | -0.204 | -0.246 (65) | sim | sim | +0.012 |
| america × reteste | treino | 56 | +60.7% | +0.017 ± 0.147 | -0.217 | -0.027 (483) | não | não | +0.064 |
| america × reteste | validacao | 20 | +50.0% | +0.096 ± 0.330 | -0.133 | -0.054 (193) | não | não | +0.189 |
| america × reteste | holdout | 16 | +62.5% | +0.165 ± 0.363 | -0.613 | -0.135 (136) | sim | não | +0.380 |

### Por lado (todas as sessões e entradas separadas; média R líquida, n)

| variante | lado | treino | validação | holdout |
|---|---|---|---|---|
| dia × fechamento | compra | -0.270 (23) | -0.530 (10) | -0.595 (8) |
| dia × fechamento | venda | -0.132 (32) | +0.208 (13) | -0.094 (11) |
| dia × reteste | compra | +0.180 (31) | -0.252 (13) | -0.443 (13) |
| dia × reteste | venda | +0.153 (38) | +0.318 (15) | -0.744 (10) |
| america × fechamento | compra | -0.115 (18) | +0.531 (5) | +0.243 (4) |
| america × fechamento | venda | -0.161 (16) | +0.266 (5) | +1.652 (1) |
| america × reteste | compra | +0.026 (25) | +0.473 (10) | -0.034 (11) |
| america × reteste | venda | +0.009 (31) | -0.281 (10) | +0.603 (5) |

### Ano a ano (média R líquida, n)

| variante | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| dia × fechamento | -0.34 (10) | +0.40 (11) | -0.41 (19) | -0.24 (15) | -0.66 (13) | +0.40 (16) | -0.48 (13) |
| dia × reteste | +0.34 (16) | +0.59 (18) | -0.36 (20) | +0.16 (15) | -0.48 (16) | +0.28 (19) | -0.58 (16) |
| america × fechamento | -0.04 (10) | -0.02 (5) | -0.15 (10) | -0.29 (9) | -0.03 (7) | +1.08 (4) | +0.62 (4) |
| america × reteste | +0.13 (14) | +0.20 (8) | +0.06 (18) | -0.22 (16) | -0.07 (14) | +0.28 (11) | +0.22 (11) |

### Como saíram (todas as variantes, todos os períodos)

| variante | n | alvo | médio (zero a zero após 1R) | stop | tempo | tomou 1R | R planejado médio | RR planejado médio |
|---|---|---|---|---|---|---|---|---|
| dia × fechamento | 97 | 13 | 32 | 47 | 5 | 50 | 0.84% | 3.63 |
| dia × reteste | 120 | 19 | 47 | 50 | 4 | 70 | 0.65% | 5.83 |
| america × fechamento | 49 | 8 | 17 | 16 | 8 | 28 | 1.07% | 2.97 |
| america × reteste | 92 | 16 | 33 | 36 | 7 | 54 | 0.66% | 4.69 |

## Parte 2 — Regime F1 (tipo de dia pela 1ª hora como filtro das bordas)

Frequência dos tipos (dias úteis e fds, 2020–2026):

| sessão | F | X | D | A | V | C | R | N | ? |
|---|---|---|---|---|---|---|---|---|---|
| asia | 29% | 7% | 8% | 10% | 4% | 3% | 17% | 21% | 1% |
| america | 29% | 7% | 10% | 19% | 4% | 2% | 10% | 18% | 1% |

Líquido em R por toque decidido (n decididos). Sem filtro = mesmas horas elegíveis (01:00–13:30 e 14:30–24:00), todos os dias. Sorteado = média dos 20 e quantos dos 20 o filtrado supera.

| base | corrida | período | sem filtro (todas as horas) | sem filtro (horas elegíveis) | FILTRADO R/V | INVERTIDO A/D | sorteado (média) | filtrado > sorteados |
|---|---|---|---|---|---|---|---|---|
| fixo10 VAL compra | 1:1 | treino | +0.014 (352) | +0.061 (273) | +0.099 (69) | -0.082 (45) | +0.108 | 8/20 |
| fixo10 VAL compra | 1:1 | validacao | -0.053 (143) | -0.069 (113) | -0.060 (22) | -0.010 (40) | -0.015 | 7/20 |
| fixo10 VAL compra | 1:1 | holdout | -0.140 (113) | -0.168 (83) | -0.260 (25) | +0.308 (19) | -0.071 | 3/20 |
| fixo10 VAL compra | 2:1 | treino | -0.027 (337) | +0.040 (259) | +0.002 (65) | -0.153 (43) | +0.122 | 4/20 |
| fixo10 VAL compra | 2:1 | validacao | +0.011 (140) | -0.051 (110) | +0.226 (21) | -0.113 (38) | -0.004 | 13/20 |
| fixo10 VAL compra | 2:1 | holdout | -0.152 (109) | -0.208 (81) | -0.340 (25) | -0.354 (17) | -0.109 | 3/20 |
| fixo10 VAH venda | 1:1 | treino | -0.224 (397) | -0.226 (283) | -0.224 (67) | -0.276 (51) | -0.246 | 10/20 |
| fixo10 VAH venda | 1:1 | validacao | -0.241 (144) | -0.208 (108) | -0.319 (27) | -0.020 (25) | -0.178 | 3/20 |
| fixo10 VAH venda | 1:1 | holdout | -0.010 (101) | -0.034 (78) | +0.190 (24) | -0.113 (19) | -0.022 | 16/20 |
| fixo10 VAH venda | 2:1 | treino | -0.310 (388) | -0.310 (276) | -0.151 (66) | -0.295 (51) | -0.321 | 16/20 |
| fixo10 VAH venda | 2:1 | validacao | -0.184 (137) | -0.199 (101) | -0.185 (24) | +0.190 (24) | -0.172 | 9/20 |
| fixo10 VAH venda | 2:1 | holdout | -0.060 (90) | -0.178 (68) | -0.160 (20) | -0.113 (19) | -0.267 | 13/20 |
| adapt VAL compra | 1:1 | treino | -0.090 (779) | -0.058 (525) | -0.263 (133) | -0.048 (81) | -0.071 | 0/20 |
| adapt VAL compra | 1:1 | validacao | -0.088 (282) | -0.070 (202) | -0.005 (55) | -0.083 (43) | -0.111 | 17/20 |
| adapt VAL compra | 1:1 | holdout | -0.201 (205) | -0.201 (149) | -0.346 (42) | -0.060 (36) | -0.202 | 4/20 |
| adapt VAL compra | 2:1 | treino | -0.094 (767) | -0.072 (516) | -0.406 (133) | +0.003 (79) | -0.080 | 0/20 |
| adapt VAL compra | 2:1 | validacao | -0.122 (275) | -0.106 (195) | -0.171 (54) | -0.274 (42) | -0.155 | 9/20 |
| adapt VAL compra | 2:1 | holdout | -0.264 (196) | -0.353 (140) | -0.255 (41) | -0.266 (34) | -0.366 | 15/20 |
| adapt VAH venda | 1:1 | treino | -0.134 (814) | -0.141 (555) | -0.163 (136) | -0.227 (84) | -0.116 | 7/20 |
| adapt VAH venda | 1:1 | validacao | -0.121 (311) | -0.141 (209) | +0.023 (48) | -0.227 (48) | -0.148 | 18/20 |
| adapt VAH venda | 1:1 | holdout | -0.130 (215) | -0.114 (167) | +0.076 (44) | -0.291 (26) | -0.156 | 19/20 |
| adapt VAH venda | 2:1 | treino | -0.171 (793) | -0.196 (538) | -0.216 (135) | -0.365 (82) | -0.161 | 7/20 |
| adapt VAH venda | 2:1 | validacao | -0.152 (304) | -0.138 (205) | +0.049 (46) | -0.310 (48) | -0.218 | 17/20 |
| adapt VAH venda | 2:1 | holdout | -0.173 (203) | -0.154 (159) | +0.257 (41) | -0.340 (25) | -0.205 | 20/20 |

Informação (não entra no veredito): líquido 1:1 por tipo de dia, composto fixo10, VAL+VAH juntos, todos os períodos.

| tipo | n decididos | líquido 1:1 |
|---|---|---|
| R | 191 | -0.065 |
| V | 43 | -0.176 |
| C | 40 | -0.160 |
| A | 115 | -0.017 |
| D | 84 | -0.155 |
| X | 43 | +0.149 |
| N | 225 | -0.233 |
| F | 196 | -0.029 |
