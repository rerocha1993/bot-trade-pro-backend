# Passos 3, 4, 5 e início do 6 do plano de gestão — tabela única (20/10/2026)

Critério comum (docs/especialistas/plano_gestao.md §4): custo real, leitura pessimista, treino 2020–23 / validação
2024–jun/25 / holdout jul/25–set/26, ≥ 30 preenchidos por período, líquido > 0 nos 3, 2 EP acima de cada controle em
treino e validação, holdout olhado uma vez, nenhum parâmetro iterado. R líquido médio por trade preenchido.
Detalhe em `data/estudo_<nome>_resumo.md`; regra exata no docstring de cada script.

| # | Estratégia | Variantes | n (T / V / H) | Líquido R (T / V / H) | Controle decisivo (T / V / H) | Veredito |
|---|---|---|---|---|---|---|
| 3 | **TPO E2** cauda no bloco de 30 min na borda | 1 (+ por lado) | 101 / 29 / 19 | +0,23 / +0,06 / +0,41 | cauda sem nível −0,01 / −0,07 / +0,05; direção −0,14 / −0,16 / −0,19 | **INCONCLUSIVA** (n < 30 em V e H; passa os dois controles no treino). Único com sinal nos 3 períodos → reteste pré-registrado |
| 3 | **TPO E3** América contra a manhã | venda (P), compra (b) | 15 / 8 / 7 (os dois lados) | −0,42 / −0,56 / −0,31 | nível sorteado +0,11 / −0,43 / −0,75 | **INCONCLUSIVA por amostra, negativa** → sai da fila |
| 4 | **Fibonacci E1** escada 0,5–0,786 depois de quebra | 15m/1h × base/terço | 1h base: 1.079 / 400 / 314 | 1h base: +0,07 / +0,11 / +0,07 (15m base: +0,03 / −0,04 / +0,04) | faixa sorteada na mesma perna (1h) +0,03 / +0,07 / +0,04 | **REPROVADA (4/4)**: a proporção não bate a faixa sorteada |
| 4 | **Fibonacci E2** régua de saída | mesmas 4 | mesmas entradas | (b)−(a) entre −0,05 e +0,03 | (b)−(d) níveis sorteados ≈ 0 | **REPROVADA (4/4)**: régua = alvo fixo 2R = níveis sorteados |
| 5 | **OB E2** varredura + volta | A/B × base/quartil | A base: 14 / 1 / 3; B base: 41 / 19 / 14 | B base: −0,01 / +0,37 / +0,12 | varredura sem CHoCH −0,17 / −0,14 / −0,22; OB simples +0,11 / −0,16 / −0,02 | **B base REPROVADA; demais INCONCLUSIVAS** (18 retestes em 6,7 anos) |
| 6 | **Elliott** "passou 0,786 → não é onda 2" (descritivo) | 1h, 4h | 2.250 (1h), 532 (4h) cruzamentos | perde a origem: 73% (1h), 73% (4h) | data sorteada, mesmas distâncias: 70% / 72% | **VALE pelo limiar de 70%, mas é geometria** (1–3 pp acima do sorteio; 80–90% só em 0,886, onde o sorteio dá 80–81%) |

Leitura do conjunto:
- Nenhuma das quatro é aprovada. Só a TPO E2 não é negativa e fica acima dos controles onde há amostra (treino).
- Três respostas de "controle" valem mais que os vereditos: (1) a cauda sem nível é zero, então o que separa na E2 é a
  borda vinda de longe, não a cauda; (2) a faixa sorteada na mesma perna empata com 0,5–0,786, então Fibonacci não é
  gatilho nem régua; (3) a varredura com volta sem CHoCH perde nos 3 períodos, então "varreu = presos" não paga.
- O mercado continua pagando odds justas em tudo que é proporção/nível. O ingrediente que sobra com sinal é um fato em
  candle fechado (rejeição vista vindo de longe numa borda) com amostra pequena demais para decidir.
