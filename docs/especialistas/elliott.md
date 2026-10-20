# Especialista Elliott no conselho de avisos — diagnóstico, três usos e regra de tempo gráfico

Data: 20/10/2026. Autor: especialista-elliott (persona de `.claude/agents/especialista-elliott.md`).
Para quem: usuário com capital pequeno, scalp e day trade, que quer **avisos** e não robô, e que trata Elliott
como "a lei" no day trade e no swing (não no 1 min). Base: `core/elliott_pro` (ZigZag ATR → padrões → cenários
concorrentes → multi-grau → calibração), `docs/TRADER_ELLIOTT.md`, `docs/tradeiros/perfil_por_regime.md` (§2.3 e
§3.4), `docs/CONSELHO_ESPECIALISTAS.md`, e o que já foi medido em `.claude/agents/perito-btc.md`.

Nada aqui promete lucro. Tudo que não tem a marca **MEDIDO** é **HIPÓTESE** até passar pela régua do projeto
(critério escrito antes, custo real, três períodos, direção sorteada em 20 sorteios, real acima de ~95% dos sorteios
no holdout).

---

## 1. Diagnóstico em 10 linhas

1. A calibração (`core/elliott_pro/calibracao.py`) prevê **P(1º alvo antes da invalidação em 60 candles)** e acerta: nas contagens confiantes 9 em 10 batem o alvo, fora da amostra (**MEDIDO**, `scripts/calibracao_lucro.py`).
2. Mas o modelo usa `dist_alvo_atr`, `dist_inv_atr` e `rr` como variáveis: ele aprendeu, sobretudo, que **alvo colado no preço bate quase sempre** (88% com alvo 0,3% e stop 2,5%). Probabilidade certa, geometria desfavorável.
3. Transformado em trade, p × rr − (1 − p) fica em ~0 R antes do custo em todas as faixas de probabilidade. Subir o limiar não ajuda; filtrar por valor esperado piora (**MEDIDO**). São **odds justas**: o mercado já precifica a contagem que se lê só no candle.
4. A regra do grupo de contagens (stop onde o grupo morre, alvo onde diverge) deu acerto ~33% com R:R ~2 em 4h e 1h: empate bruto, negativo líquido (**MEDIDO**, `core/assimetria.py`). Em 1 min a contagem troca de fase em 45% das leituras: ruído (**MEDIDO**).
5. O único grau em que o Elliott do projeto tem valor demonstrado é o **maior**: o contexto de superciclo em log acertou 12/12 fins de ano e 45/49 trimestres sem olhar o futuro (**MEDIDO**, `core/elliott_pro/superciclo.py`), e o dial de hedge com essa leitura fez +77% de BTC em 2017–2026.
6. Implicação: **Elliott agrega onde ele define a jogada, não onde ele dispara o gatilho.** Agrega em (a) direção permitida e veto de grau maior; (b) invalidação como stop estrutural (preço onde a leitura inteira está errada, não um múltiplo de ATR); (c) alvo por Fibonacci (onde o movimento costuma acabar; reduz a aleatoriedade da saída); (d) a zona de entrada da onda 2 (0,5–0,618), que é um preço limitado abaixo do fechamento, não "entra no fechamento quando o motor diz X".
7. Não agrega como gatilho: "o cenário X ficou primário no fechamento" = entrada a mercado com p e rr que se cancelam. Foi isso que a calibração e a regra do grupo mediram, e foi isso que deu zero.
8. Por isso o conselho de `docs/CONSELHO_ESPECIALISTAS.md` §4.2 está certo em tratar Elliott como **mapa** dos outros avisos, com um único aviso próprio: o setup de onda 2. Este documento detalha esse aviso e mais dois.
9. O que a calibração **não cobre** e os três usos abaixo exploram: entrada limitada numa zona pré-calculada (preço melhor que o fechamento), stop e alvo de contagens diferentes (stop da onda 2, alvo da onda 3), e confluência com informação de fora do candle (VAH do composto, funding, presos).
10. Risco de fundo, dito antes de medir: tudo que lê só o candle pagou odds justas neste projeto (Elliott, TPO em 5 e 15 min, VWAP, OB, Fibonacci). O setup de onda 2 lê só o candle; a vantagem, se existir, tem de vir da assimetria stop/alvo e da entrada limitada, não da previsão.

---

## 2. Os três usos de maior potencial ainda não medidos

Vocabulário do motor (`core/elliott_pro/scenarios.py`, `multidegree.py`): cada cenário traz `vies` (bull/bear =
próximo movimento), `fase` (onda_1, onda_2, inicio/meio/final_onda_3, onda_4, onda_5, correcao_a/b/c, triangulo,
consolidacao), `direcao` (buy/sell/hold), `probabilidade` (normalizada entre as contagens vivas), `prob_sucesso`
(calibrada), `invalidacao` (preço) e `alvos` (preços por Fibonacci). O resumo traz `prob_bull`, `prob_bear` e o
consenso (≥ 60% de um lado). O ZigZag usa fator 2,0 × ATR em 15m/1h e 2,2 em 4h/1d, janela de 300 candles fechados.
Os cenários de cada candle de 1h e 4h desde 2021 já estão gravados em `data/cenarios/1h.jsonl.gz` e `4h.jsonl.gz`
(`scripts/cenarios_historicos.py`); dá para estender a 2012 com o Bitstamp.

### 2.1 Uso 1 — Setup de onda 2 (o trade do Tradeiros) — HIPÓTESE

**Grau e tempo gráfico.** Intermediário/menor: **4h como grau do setup**, 1h para refinar a zona das fatias.
Versão de day trade: 1h como setup, 15m para as fatias. Não existe versão de scalp (ver §3).

**Contexto exigido (grau maior).** Para compra: superciclo em `fundo_terminal`, `novo_impulso`, `zona_onda_2`,
`impulso_alta` ou `impulso_maduro` (em `impulso_maduro` metade do tamanho, como o `fator_tamanho` já faz); **nunca**
em `correcao_inicial`. Grau acima do setup (1d para o 4h; 4h para o 1h) com `prob_bear` < 60% (não contrário). Para
venda, o espelho: nunca em `fundo_terminal`, `novo_impulso` ou `zona_onda_2`.

**Identificação pelo motor existente (regra exata).** No tempo gráfico do setup, existe um cenário vivo com:
- `fase == "onda_2"` e `direcao == "hold"`. O motor gera isso de dois jeitos: (a) impulso em andamento com 2 pernas
  confirmadas (`_impulsos_em_andamento`, `len(legs) == 2`): `invalidacao` = início da onda 1, `alvos` = 0,5 e 0,618
  de retração da onda 1 (é a **zona de término da onda 2**, não alvo de trade); (b) correção completa (zigzag/flat/
  WXY) seguida de um pivô posterior (`_derivar_de_completo`, classe corretiva, `offset == 1`): `invalidacao` = fim
  da correção (= início da onda 1 nova).
- Onda 1 com tamanho ≥ 3 × limiar do ZigZag (hoje o motor aceita 1,5 ×; abaixo de 3 × o pivô da onda 1 só é
  confirmado quando a retração já passou de 0,5, e a zona já foi). Isso é um **filtro novo** a registrar antes
  de medir, não um parâmetro a ajustar.
- A soma das probabilidades dos cenários cujo `vies` é o da onda 1 (`prob_bull` para compra) ≥ 50%. Não exige
  consenso de 60%: a onda 2 por definição é o momento em que as contagens de baixa ganham peso.
- Preferência do Tradeiros, como qualificador (não como condição): **volume caindo** na onda 2 (média de volume
  dos últimos 3 candles < mediana dos candles da onda 1). Delta não existe no histórico (só 30 dias de negócios):
  fica de fora da medição.

**Gatilho em candle fechado.** Primeiro candle fechado do tempo gráfico do setup cujo **mínimo** entrou na zona
0,5–0,618 da onda 1 (compra) **sem fechar abaixo de 0,786**, com o cenário `onda_2` ainda vivo (preço não fechou
abaixo da `invalidacao`). A partir daí as limitadas ficam armadas até: fechamento abaixo de 0,786 (cancela e
espera o reteste), fechamento abaixo da invalidação (morreu), ou fechamento acima do **fim da onda 1** sem
preenchimento (onda 3 saiu sem a gente: não perseguir; o aviso vira "meio do nada").

**Zona de entrada.** 3 a 5 limitadas entre 0,5 e 0,666 da onda 1 (golden pocket inclusive), degraus iguais. Médio
esperado ≈ 0,56 de retração.

**Stop.** Duas versões, as duas pré-registradas:
- **Estrutural** = `invalidacao` do cenário (início da onda 1) menos slippage. Distância ≈ 0,44 × onda 1 a partir do
  médio. É a invalidação do motor, sem invenção.
- **Curta** = fechamento abaixo de 0,786 da onda 1 (o "fundo" que o Tradeiros usa). Distância ≈ 0,23 × onda 1.
  Mais R:R, menos acerto. É a que o Tradeiros descreve; a estrutural é a que o motor entrega.

**Alvo por Fibonacci.** Alvo 1 = fim da onda 1 + 1,0 × onda 1 (o 1º `alvo` do cenário "onda 3 em andamento",
medido do fundo da onda 2 — conservador, usa o fundo que ainda não se conhece como o nível de 0,618). Alvo 2 =
**1,618 × onda 1 a partir do médio de entrada** (o alvo que o pedido fixa). Tirar o risco em 1 R (25–50%, stop no
médio), o resto no alvo 2.

**R:R típico** (onda 1 = 1,0; médio a 0,44 de preço). Stop estrutural: risco 0,44, alvo 2 a 2,06 → ganho 1,62 →
**R:R ≈ 3,7** (alvo 1: ≈ 2,3). Stop curto: risco 0,23 → **R:R ≈ 7** (alvo 1: ≈ 4,3). Acerto de empate antes do custo:
21% (3,7), 12% (7). O Tradeiros aceita 20–40% de acerto com ≥ 3 R; é exatamente esta conta.

**Frequência (estimativa, a confirmar no replay).** No 4h, pivôs de 2,2 × ATR ocorrem a cada 3–8 dias: 1–3 setups
por mês, dos quais talvez metade chega à zona. No 1h, 3–8 por mês. Em 10 anos de 4h, algo entre 150 e 300 trades:
pouco para três períodos e compra/venda separadas. É o primeiro risco de medição (ver §4).

**De onde vem a vantagem (hipótese).** Não da previsão (a calibração mostrou que não há), mas de três coisas que a
calibração não mediu: (1) entrada limitada numa zona abaixo do fechamento, (2) stop de uma contagem (onda 2) e alvo
de outra (onda 3), (3) só o setup que o mercado persegue mais (fundo de onda 2 é onde "a sardinha" vende e os
presos ficam contra). Se o grau maior estiver a favor, a onda 3 é o movimento mais longo e mais provável da
sequência; o setup vende a assimetria, não a direção.

**O que mata.** (a) A "onda 1" ser na verdade uma onda C (correção, não impulso): o motor marca isso como cenário
alternativo com `vies` contrário; por isso a regra pede ≥ 50% do lado da onda 1. (b) Onda 2 em flat corrente ou
curta (0,382): o preço não chega na zona, sem perda, mas sem trade. (c) Onda 2 profunda (0,786–1,0): mata o stop
curto; a estrutural sobrevive mas o alvo demora. (d) Mercado em `correcao_inicial`/queda de grau maior: a maioria
das "ondas 2" de alta vira onda 2 de baixa. (e) Em 1h/15m, o ZigZag reclassifica pivôs e a onda 1 some da contagem
no candle seguinte (o que aconteceu no 1 min): medir a **estabilidade da fase** antes de contar o trade.

**Dados necessários.** Já existem: 4h e 1h do Bitstamp desde 2012, Binance desde 2017; `data/cenarios/*.jsonl.gz`
desde 2021 (estender a 2013). Volume dos candles para o qualificador. Nada de livro nem delta.

**Como medir.** Replay sobre `data/cenarios/<tf>.jsonl.gz` (um estado por candle, sem olhar o futuro): quando
aparece um cenário `onda_2` que satisfaz a regra, arma as limitadas no candle seguinte; preenche quando o mínimo do
candle atinge o preço; stop antes do alvo no candle ambíguo; custo maker na entrada, maker no alvo, taker + 0,02% no
stop; funding quando atravessa 00/08/16h UTC. Quatro formatos fixos (2 stops × 2 alvos), tirar o risco ligado e
desligado = 8 variantes, **nenhuma outra**. **Controle 1:** mesma zona e mesmo stop com a **direção sorteada**
(20 sorteios). **Controle 2:** onda 1 **sorteada** (perna aleatória do ZigZag do mesmo tamanho) com a mesma zona —
mede se a onda 2 "de verdade" segura mais que uma retração qualquer. Períodos: treino 2013–2019, validação
2020–jun/2024, holdout jul/2024–set/2026; compra e venda separadas; ano a ano. Aprova só se líquido > 0 nos três
períodos, acima do p95 dos dois controles no holdout, com ≥ 30 trades decididos por período.

### 2.2 Uso 2 — Elliott como veto e direção dos avisos de TPO e fluxo — HIPÓTESE (com partes MEDIDAS)

**Grau e tempo gráfico.** O aviso vem do TPO/fluxo em 5m/15m; a leitura de Elliott vem de **1h (contexto) e 4h
(macro)** mais o superciclo (1d, log). Nunca do tempo gráfico do aviso.

**Contexto exigido.** Nenhum além do próprio Elliott: este uso é o contexto.

**Regra de combinação (fixada antes de medir).** Para cada aviso de compra num nível (VAL, POC, naked POC,
abertura, borda com presos a favor):
1. **Veto de ciclo (MEDIDO no grau maior):** `estado_superciclo` em `correcao_inicial` → veta compra. Em
   `fundo_terminal`, `novo_impulso`, `zona_onda_2` → veta **venda** (só realização de hedge). É a regra que acertou
   12/12 anos; aqui ela só corta avisos, não cria.
2. **Veto de contexto (HIPÓTESE):** no 4h, `prob_bear` ≥ 60% **ou** cenário primário em `correcao_a`/`correcao_c`
   com `vies` bear → veta compra. No 1h, `fase` em `onda_5` com extensão > 1,618 × onda 1 (o motor já marca
   `esticada`, `direcao == "hold"`) → veta compra; espelho para venda.
3. **Direção permitida:** 1h e 4h com `prob_bull` ≥ 60% → aviso de compra **inteiro**; nenhum dos dois ≥ 60% em
   lado algum → aviso **metade** ("meio do mapa"); 1h contra e 4h neutro → metade; 4h contra → veto (item 2).
4. **Alvo:** o aviso de TPO usa como alvo o menor entre o seu (POC/VAH/VAL seguinte) e o **1º `alvo` de Elliott do
   1h** do lado do aviso; se esse alvo estiver a menos de 1,5 × a distância do stop → **veto por falta de espaço**.
5. **Stop:** fica o do nível (abaixo da VAL/cauda). A `invalidacao` de Elliott do 1h entra só como **segundo aviso**
   ("a leitura morre em X"): se X está mais perto do que o stop do nível, o aviso diz "stop curto disponível em X".

**Gatilho, zona, stop e alvo** são os do aviso-base (TPO ou fluxo); Elliott não gera nenhum dos quatro.

**R:R típico.** O do aviso-base; o item 4 impede R:R < 1,5.

**Frequência.** Reduz os avisos: estimo que o veto de contexto corte 30–40% dos toques e a metade de tamanho
afete outros 30%.

**De onde viria a vantagem.** O único filtro de direção que já separou alguma coisa neste projeto foi o superciclo
(grau de ciclo) e os presos (fora do candle). A hipótese é que o toque na VAL, que sozinho empata com o sorteio
(0/180 em 5 min, 0/117 em 15 min), segure mais quando o 4h **não** está em correção contra. Honestidade: um filtro
não cria vantagem onde a base é zero; ele só pode tirar os piores toques. Se o toque na VAL é moeda ao ar em todos
os regimes, o filtro não salva. Ele pode valer mais para o **fluxo** (presos: VAL segura 74% × 64%, n = 40) do que
para o TPO puro.

**O que mata.** (a) 4h/1h em `indefinido` ou sem consenso na maior parte do tempo (o motor dá `hold` quando
nenhum lado tem 60%): o filtro vira "metade" quase sempre e não separa nada. (b) Atraso: o 4h só confirma o pivô
com 2,2 × ATR, então a correção de grau maior já andou quando o veto aparece. (c) Multiplicar recortes (nível ×
lado × fase × consenso) e achar 3 positivos em 100 por acaso. Por isso a regra acima é uma só, com 5 itens fixos.

**Dados necessários.** Já existem: `data/estudo_niveis_tpo.csv` (36.335 toques em 5 min) e
`data/estudo_niveis_tpo_2.csv` (um toque por linha em 15 min), com timestamp; `data/cenarios/1h.jsonl.gz` e
`4h.jsonl.gz` desde 2021; trader de superciclo em `data/trader_BTCUSDT.pkl` (estado por dia).

**Como medir.** Sem rodar nada novo de TPO: juntar a cada toque dos dois CSVs o estado de Elliott do **último
candle de 1h e 4h fechado antes do toque** e o estado do superciclo do dia anterior. Aplicar a regra (veto / metade /
inteiro) e recalcular líquido por período para: todos os toques, só os "inteiros", só os "vetados" (devem ser
piores, senão o veto não vale nada). **Controle:** a mesma regra com o estado de Elliott de uma **data sorteada**
(20 sorteios) — mede se o filtro verdadeiro separa mais que um filtro aleatório com a mesma taxa de veto. Períodos
dos próprios estudos (treino 2020–23, validação 2024–jun/25, holdout jul/25–set/26; Elliott gravado desde 2021
limita o treino a 2021–23, ou estende-se o `cenarios_historicos.py` a 2020). Critério: toques "inteiros" com líquido
> 0 nos três períodos **e** acima do p95 do controle, **e** "vetados" abaixo de "inteiros" nos três.

### 2.3 Uso 3 — Onda 5 esticada + VAH do composto + funding caro = venda/hedge — HIPÓTESE

**Grau e tempo gráfico.** **4h** como grau do setup (onda 5 intermediária), 1d como grau maior, composto de 10 dias
do TPO (`core/range_tradeiros.contexto`) para a VAH. Para capital pequeno, serve como venda em linear com stop ou
como hedge parcial em inverse (20–40% da carteira, no formato do Tradeiros); o aviso é o mesmo.

**Contexto exigido.** Superciclo em `impulso_maduro` ou `correcao_em_curso` (os únicos estados em que o dial já
permite hedge; **MEDIDO** no grau de ciclo: em `fundo_terminal`/`novo_impulso`/`zona_onda_2` ninguém vende). 1d
**não** em `inicio_onda_3`/`meio_onda_3` de alta (o grau maior limita o menor: não se vende o meio de uma onda 3).

**Identificação pelo motor existente.** No 4h, cenário vivo com `fase == "onda_5"` e extensão ≥ 1,0 × onda 1
(o motor calcula `ext = |preço − L4| / onda 1`; marca `esticada` acima de 1,618 e rebaixa o score em 0,6). Uso
1,0 e não 1,618 porque em BTC a 3 é a estendida e a 5 costuma igualar a 1; 1,618 é raro. **Ou** cenário "impulso
completo: correção A em andamento" (`fase == "correcao_a"`, `vies` bear) ainda com `offset == 0`. `invalidacao` do
cenário de onda 5 = fundo da onda 4 (L4); é ela que vira **alvo** do trade.

**Confluência exigida (as três ao mesmo tempo, fixas):**
1. Preço a menos de 0,5% da VAH do composto de 10 dias **ou acima dela** (fora do valor para cima).
2. Funding da Bybit do próximo pagamento ≥ percentil 80 dos últimos 90 dias (comprado pagando caro; o vendido
   **recebe**: aqui o funding é a favor do trade, não custo).
3. OI subindo nas últimas 24h (sardinha entrando comprada no topo), do `oi_bybit_1h.json`.

**Gatilho em candle fechado.** Primeiro candle de 4h que **fecha de volta abaixo da VAH** depois de ter negociado
acima dela (desvio, no vocabulário do Tradeiros), com as três confluências válidas no fechamento anterior. Sem
desvio (preço aceita acima da VAH com volume construído) não há aviso: é rompimento, e o método não vende
rompimento aceito.

**Zona de entrada.** 3 a 5 vendas limitadas entre a VAH e a máxima do desvio (escada subindo, como a grade do
inverse). Médio ≈ VAH + 40% da distância até a máxima.

**Stop.** Acima da máxima do desvio + 0,25 × ATR(14) do 4h. **Não** a invalidação de Elliott (que para uma venda em
onda 5 seria o topo da onda 5 ainda não confirmado, igual à máxima do desvio na prática). Se um novo candle de 4h
fechar acima da máxima, o stop foi atingido e **não se re-entra** até novo desvio.

**Alvo por Fibonacci.** Alvo 1 = POC do composto (realização de 1 R, se o POC estiver a ≥ 1 R). Alvo 2 = **fundo da
onda 4** (`invalidacao` do cenário de onda 5 = L4) **ou** 0,382 de retração do impulso inteiro (o 1º `alvo` do
cenário `correcao_a`), o que vier primeiro.

**R:R típico.** Com desvio de 1–2% acima da VAH e onda 4 a 5–8% abaixo: **R:R 2,5–4**. Empate antes do custo em
20–29% de acerto; o funding recebido melhora o líquido quando a posição atravessa pagamentos.

**Frequência.** Baixa: onda 5 em 4h com as três confluências, 1–3 por mês em alta madura; quase nada em queda
(então o aviso dorme meses). Desde 2020 (início do funding e OI gravados) talvez 60–120 avisos no total.

**De onde viria a vantagem.** Confluência de três leituras independentes: forma (5 ondas completas, o movimento
que o Elliott mais acerta terminar), valor (fora da VAH = preço caro no composto, com rejeição) e posicionamento
(comprado alavancado pagando funding alto com OI subindo = combustível para squeeze de baixa). Os três juntos são o
que o Tradeiros chama de "topinho" para realizar. Separados, cada um já empatou com o sorteio neste projeto (VAH do
composto 0/16; funding "do lado" 1/36); a aposta é só na interseção.

**O que mata.** (a) Parabólica: 2017-11/12, 2021-01/02, 2024-02/03 — onda 5 esticando para 2,618 e 3 stops seguidos
antes do topo. O veto do 1d em onda 3 ajuda, mas não resolve. (b) Onda 3 estendida mal rotulada como onda 5: o motor
exige 3 > 1, mas numa parabólica a "5" pode ser 3 de grau maior. (c) Poucos avisos: 60–120 em 6 anos não separam
compra/venda nem três períodos com força; o teste vai sair "inconclusivo" com probabilidade alta. (d) Funding alto
que persiste semanas (2021) sem queda.

**Dados necessários.** Já existem: 4h Binance/Bitstamp, composto de 10 dias (`core/range_tradeiros`), funding
(2020–), OI 1h (2020–), cenários de 4h (2021–; estender a 2020).

**Como medir.** Replay 4h de 2020–2026 com a regra acima, custo real, funding contabilizado candle a candle, stop
antes do alvo. **Controle 1:** direção sorteada nos mesmos candles (20 sorteios). **Controle 2:** as mesmas três
confluências **sem** a fase de Elliott (qualquer fase): mede se a onda 5 acrescenta algo à VAH + funding + OI, que é
a pergunta deste uso. Períodos: treino 2020–2022, validação 2023–jun/2025, holdout jul/2025–set/2026 (o holdout
pega a queda de 126k a 57,8k: terreno favorável a venda, por isso olhar também o ano a ano e o controle). Critério:
líquido > 0 nos três, acima do p95 do controle 1 e acima do controle 2 em treino e validação.

---

## 3. Regra de tempo gráfico

| Tempo gráfico | Elliott vale para | Por quê (o que já foi medido) |
|---|---|---|
| **1 min** | **nada** | troca de fase em 45% das leituras (**MEDIDO**); o usuário já tirou Elliott do scalp; o ZigZag de 1,8 × ATR em 1 min marca pivô a cada poucos minutos e a onda 1 some no candle seguinte |
| **5 min** | nada como contagem | não medido em isolamento, mas é o mesmo regime do 1 min; scalp 5m por indicadores: 0 de 6 setups (**MEDIDO**); e o pivô de 5 min não sobrevive à sessão |
| **15 min** | só as **fatias** dentro de um setup de 1h; nunca contagem própria | a calibração inclui 15m só como feature; nenhum lucro medido em BTC 15m; o perfil `daytrade` do motor usa 15m como operacional e 4h como contexto, e o único teste desse perfil em 15m (ETHUSDT, 120 dias) foi reprovado (PF 0,75); em BTC 1h o mesmo perfil ficou em fator de lucro 1,05–1,09 (odds justas), e subir para 4h melhorou qualidade (**MEDIDO**, `docs/RESULTADOS_BACKTEST.md`) |
| **1 h** | Uso 1 (versão day trade), Uso 2 (contexto do aviso de scalp/day) | calibração correta e ~0 R (**MEDIDO**); regra do grupo negativa (**MEDIDO**); vale como mapa de direção/invalidação/alvo, não como gatilho; é o grau "menor" do Tradeiros |
| **4 h** | Uso 1 (setup principal), Uso 2 (macro), Uso 3 | o único sinal não negativo medido em Elliott operacional: consenso a favor +0,04 R/trade, no limite do acaso (**MEDIDO**); grau intermediário do Tradeiros; pivôs de 2,2 × ATR duram dias, a contagem é estável |
| **1 d / 1 w** | veto, direção de hedge, estado do ciclo | superciclo 12/12 anos, 45/49 trimestres (**MEDIDO**); dial de hedge +77% de BTC (**MEDIDO**); não dá entrada de day trade |

Regra em uma frase: **Elliott entra no conselho de 1h para cima; abaixo de 1h ele só desce a zona e a invalidação
que o 1h/4h já calcularam.** Para o usuário isso significa que o "aviso de Elliott" é um aviso de day trade que
dura horas a dias, com risco dimensionado pelo stop (0,3–1% da banca), e não um aviso de scalp. O scalp continua
sem gatilho de Elliott, e por enquanto sem gatilho de candle algum (TPO 5m e 15m = sorteio).

Sobre a "lei": no day trade e no swing Elliott **manda** no que é permitido (direção, veto, até onde vai), e é isso
que os números sustentam no grau maior. Ele não manda no **quando**: o quando ainda precisa vir de nível + fluxo
(presos, livro), que são as únicas leituras que mostraram diferença.

---

## 4. Ranking, escolha para começar e risco principal

| # | Uso | Potencial (0–10) | Por quê a nota |
|---|---|---|---|
| 1 | **Onda 2 em 4h (1h para fatias), stop na invalidação, alvo 1,618** | **6** | única jogada com assimetria estrutural (R:R 3,7–7) que a calibração **não** mediu; é o trade declarado do Tradeiros; dados prontos; mas lê só o candle, e tudo que leu só o candle empatou |
| 2 | Onda 5 esticada + VAH + funding caro (venda/hedge, 4h) | **5** | confluência com informação de fora do candle (funding, OI) e com o único Elliott que funcionou (grau maior, hedge); mas amostra pequena e holdout enviesado para venda |
| 3 | Elliott como veto/direção dos avisos de TPO e fluxo | **3** (scalp) / **5** (day trade) | o mais barato de medir (só juntar colunas aos CSVs existentes); porém a base (toque em nível) é zero e um filtro não cria vantagem; vale mais sobre os presos do que sobre o TPO puro |

**Começar pelo Uso 1.** Motivos: é a tese do usuário ("Elliott é a lei no day trade") posta à prova na forma em que
o Tradeiros a usa; a regra é uma só, com 8 variantes fixas e dois controles; roda sobre `data/cenarios/4h.jsonl.gz`
sem código novo de leitura (só o replay das limitadas, que `core/gestao_trade.py` já sabe fazer); e o resultado, seja
qual for, decide o lugar de Elliott no conselho: se a onda 2 em 4h não bate a retração sorteada, Elliott fica só como
mapa (Uso 2) e o aviso próprio sai do desenho.

Na sequência: Uso 2 (uma tarde de trabalho, sobre o que já existe), depois Uso 3 se o superciclo entrar em
`impulso_maduro` de novo (hoje a leitura é de correção, o aviso dormiria).

**Risco principal, comum aos três:** amostra pequena em 4h (150–300 trades em 10 anos no Uso 1; 60–120 no Uso 3),
que dá erro padrão de 4–7 pontos no acerto e deixa um resultado "positivo" indistinguível do sorteio. A régua da
direção sorteada é a defesa, e o resultado mais provável, pelo histórico do projeto, é "não separa do acaso". Risco
específico do Uso 1: o ZigZag confirmar a onda 1 tarde demais (zona já atravessada) e o replay gerar poucas
entradas; o filtro de onda 1 ≥ 3 × limiar corrige na regra, não depois de olhar o resultado. Risco de método:
cair na tentação de ajustar 0,5–0,618 para 0,382–0,786, trocar 1,618 por 1,0, mudar o fator do ZigZag — qualquer
ajuste depois de olhar o holdout anula a medição.

**O que não está prometido.** Nenhum dos três usos tem lucro demonstrado. O que está demonstrado é o contrário para
tudo que lê só o candle, e o Uso 1 lê só o candle. A diferença, se houver, tem de aparecer contra a retração sorteada
e contra a direção sorteada; se não aparecer, Elliott fica no conselho como mapa (direção, invalidação, alvo, veto de
ciclo) e o usuário segue sem aviso próprio de Elliott, como o desenho de `docs/CONSELHO_ESPECIALISTAS.md` já prevê.

---

## 5. Ajustes depois da live TZND78d0dVY (Maroja, 16/10/2026)

Fonte: `docs/tradeiros/fichas/TZND78d0dVY.md` e `docs/tradeiros/contagem_metodo.md`. O que está abaixo **muda o desenho**
das três estratégias dos §§2.1–2.3; não muda o que já foi medido (§1) nem a régua de medição (§4). Tudo continua
**HIPÓTESE**. A live não traz número novo medido; traz o jeito deles de contar, e isso corrige quatro coisas que eu tinha
descrito de modo mais estreito: a regra de onda 2, a invalidação, as estrelas e o grau.

### 5.1 Regra de onda 2 (Uso 1)

1. **A onda 2 deles tem estrutura interna, e a entrada depende dela.** Eles não compram "a onda 2"; compram a **C** da
   onda 2 (ou a camada de Fibonacci que a C deve alcançar). Na live: a primeira perna caiu em 5 ("diagonal") e por isso
   virou **A**, não a onda 2 inteira; agora esperam B (3 ondas, sem renovar 87,4k) e C em 5 com C ≥ 1,0 × A
   [TZND78d0dVY 32:41–34:30, 93:40–93:47]. O Uso 1 como eu escrevi arma as limitadas quando o **mínimo** entra em
   0,5–0,618 — isso compra a A. **Ajuste:** exigir, no tempo gráfico abaixo do setup (1h para o 4h; 4h para o 1d), que a
   correção já tenha A e B confirmadas pelo ZigZag (cenário `correcao_c` vivo, ou `correcao_b` com B < 1,0 × A) e
   que a zona 0,5–0,618 da onda 1 **coincida** com 1,0–1,618 × A projetado do fim da B. Sem A-B, não há aviso.
   Variante a registrar junto: a regra original (só a retração), para medir se a estrutura A-B-C acrescenta algo.
2. **0,382 entra como primeira camada, pequena.** "Qualquer coisa entre 76 e 72 já é perfeito" e "0,382 se o mercado
   reluta" [31:42–32:33]. **Ajuste:** camadas fixas 0,382 (20%), 0,5 (30%), 0,618 (30%), 0,666–0,786 (20%), com stop
   por camada (§5.2). Não é "ajustar a zona depois de olhar": é o desenho deles, registrado antes de medir.
3. **Qualificador de prova da onda 1** (eles: 5 subondas, volume na 3, mudança de estrutura, RSI divergente na 5
   [27:29–29:56]). O filtro "onda 1 ≥ 3 × limiar" fica, e vira: a perna da onda 1 precisa ter **≥ 5 pivôs no ZigZag de
   1,5 ×** (subdivisão em 5) **e** fechar acima do último topo do grau acima (mudança de estrutura). Volume e RSI entram
   só como colunas para olhar depois, não como condição.
4. **Alvo 1 muda de 1,0 × onda 1 para o naked POC / topo da onda 1.** Eles realizam o scalp no naked POC seguinte e o
   swing "contra a máxima" [68:21–69:41, 76:45–77:00]. **Ajuste:** alvo 1 = fim da onda 1 (o "topo anterior"), onde
   tiram 25–50% e levam o stop ao médio; alvo 2 continua 1,618 × onda 1.
5. **O gatilho de confirmação entra como variante separada (Uso 1-B).** A mão grande deles só entra quando a C fecha
   **e** o preço ganha o topo anterior da correção, comprando a volta [93:15–94:10]; é o mesmo gatilho de xybIvLoZ13s
   (quebra de microestrutura + reteste 0,5–0,786). **Ajuste:** Uso 1-B = cenário corretivo completo + fechamento do
   setup acima do último topo da correção; limitadas em 0,5–0,786 da perna de rompimento; stop abaixo do fundo da C;
   alvo 1,618 × onda 1 do fundo da C. Menos entradas, entrada pior, stop mais curto: medir os dois lado a lado.

### 5.2 Invalidação (Usos 1 e 2)

1. **Três camadas, não duas.** Eu tinha "estrutural" (origem da 1) e "curta" (0,786). Eles têm: perde probabilidade em
   **0,618** ("já perde muita"), perde quase tudo em **0,786** ("80–90% das vezes não é onda 2"), morre na **origem**
   [97:22–97:49]. E o stop do trade fica na camada da ordem, não na morte: compra contra 74k com stop em 68k (abaixo de
   0,618), compra em 69–67k com stop abaixo de 64k (0,786) [76:22–76:27, 98:27]. **Ajuste:** no Uso 1, stop por
   camada = próximo nível de Fibonacci abaixo da camada menos 0,25 × ATR do setup (camada 0,382 → stop abaixo de 0,5;
   0,5 → abaixo de 0,618; 0,618 → abaixo de 0,786; 0,786 → abaixo da origem). A variante "estrutural" (tudo na
   origem) fica como controle. As 8 variantes do §2.1 viram 3 formatos de stop × 2 alvos × tirar-risco ligado/desligado
   = 12; nenhuma outra.
2. **Perder o nível não é vender; é comprar o repique e vender o pullback.** "Passou 0,786 não vou vender; é nódulo de
   volume, compro, se perder o pullback aí vendo" [97:49–98:27]. No desenho de avisos isso vira **um segundo aviso**,
   não uma regra de saída: quando o preço fecha abaixo da camada, o aviso diz "camada perdida: realizar no repique
   até X (o nível perdido) e reavaliar". Não entra na medição do Uso 1 (seria um sistema a mais); fica anotado.
3. **A invalidação de uma contagem é a confirmação da outra, e vem com condição de força** ("perder 75k acelerando",
   "romper 82k e formar volume acima"). **Ajuste no Uso 2:** o veto de contexto do 4h não deve virar no primeiro
   fechamento abaixo da invalidação; exige fechamento abaixo **e** candle com range > 1,5 × ATR ou volume > 1,5 × a
   mediana de 20 (a "força"). Sem força, o estado fica "em disputa" = aviso pela metade. É regra nova, fixada antes.
4. **Invalidação por tempo** (correção "longa demais") não entra em nenhum uso: não há número deles, e o motor não
   guarda duração de perna. Fica em `contagem_metodo.md` §10.3 item 6 como mudança de motor, não de estratégia.

### 5.3 Estrelas e probabilidade (Usos 1 e 2)

1. **As estrelas deles e a probabilidade calibrada do motor respondem perguntas diferentes.** Estrelas = "qual
   contagem está certa" (ordinal, não soma 100%, sobe e desce por subdivisão, tempo e força). Calibrada = P(1º alvo
   antes da invalidação em 60 candles), que premia alvo colado (§1). **Ajuste:** nenhum uso converte uma na outra. O
   Uso 1 usa a soma `prob_bull` ≥ 50% só como "a onda 1 é a leitura dominante"; o Uso 2 usa `prob_bull`/`prob_bear`
   ≥ 60% só como direção. A probabilidade calibrada **sai** das condições (ela mede geometria, não contagem).
2. **Poda:** eles operam com duas contagens vivas. O motor gera dezenas e exibe cinco. **Ajuste no Uso 2:** o veto e a
   direção passam a olhar só os **dois** cenários de maior probabilidade com próximo movimento distinto (um bull, um
   bear, quando existirem); se os dois pedem o mesmo próximo movimento (como hoje: pullback sem renovar 87,4k, depois
   queda), o aviso usa esse movimento comum e a invalidação comum, igual ao §6 de `contagem_metodo.md`. A regra do grupo
   de contagens já foi **MEDIDA** negativa como gatilho (`core/assimetria.py`); aqui ela é só **filtro de direção** de
   um aviso que vem do nível, não um gatilho. Se o Uso 2 não separar do controle, isso também morre.
3. **Consenso contrário e fractal** ("43k não vem", "igual a 2020") não entram em nada: sentimento e memória de
   situações já foram **MEDIDOS** sem relação com a direção.

### 5.4 Grau (os três usos)

1. **A onda 2 que eles operam com mão grande é de grau primário (diário):** onda 1 = 57,8k→87,4k em três meses; a
   zona 76–67k dura semanas; o A-B-C interno é lido em 4h/1h [31:21–34:30]. O Uso 1 em 4h pega ondas 2 de grau
   intermediário (dias). **Ajuste:** o Uso 1 ganha uma **versão 1d** (setup no diário com ZigZag 2,2 × ATR, A-B-C no
   4h, fatias no 1h), além das versões 4h e 1h. Frequência no 1d: 1–3 por ano em BTC, ou seja, imensurável sozinha
   (amostra < 30 em 10 anos) — por isso o Uso 1 continua sendo medido em 4h e 1h, e a versão 1d fica como **aviso de
   swing com veto**, sem pretensão de prova estatística. É nesse grau que o Elliott do projeto já mostrou valor
   (superciclo), e é onde eles põem o capital.
2. **Veto do grau maior precisa bater com a leitura deles.** Hoje eles leem "flat de ciclo terminado em 57,8k, onda 1
   feita, onda 2 em curso". Pela régua de `superciclo.py` (retração log ≥ 0,382, ≥ 9 meses do topo, queda ≥ 60%:
   2 de 3), o fundo de 57,8k pontua só 1 de 3 (retração log 0,37; 9 meses; queda 54%), mas a recuperação de 0,53 em
   log da queda, com ≥ 6 meses do topo, pode marcar `novo_impulso`. **Ação antes de qualquer medição:** rodar o
   superciclo no 1d até 16/10/2026 e registrar o estado; se der `correcao_em_curso`, o Uso 1-1d e o Uso 2 vetam a
   compra que eles estão fazendo, e a divergência precisa ser decidida (régua do motor × leitura deles) antes de
   usar o veto como aviso. Não ajustar a régua para "dar 57,8k": ela acertou 12/12 anos como está.
3. **Scalp:** nada muda. O trade de 0,2% da live (contra a mínima, naked POC, 3:1) é um trade de **nível**, e a
   contagem só deu o contexto ("pode ter terminado aqui"). É exatamente o Uso 2 com o aviso vindo do TPO.
4. **Uso 3 (onda 5 + VAH + funding):** a live mostra o topo de 87,4k pelas peças deles — 5 ondas completas, RSI
   divergente na 5, delta negativo perto da máxima, Coinbase sem comprar — e o funding estava positivo mas não
   "caro". **Ajuste:** a confluência 2 (funding ≥ p80) passa a ser **ou** funding ≥ p80 **ou** OI subindo com CVD
   divergente (longs presos, como eles leram em 85:44–87:44); RSI(14) do 4h com topo mais baixo que o da onda 3 entra
   como qualificador (coluna, não condição). O gatilho continua sendo o desvio da VAH em candle fechado; o "short
   contra a máxima do range" deles fica fora do Uso 3 (é hedge por nível, já coberto pelo desenho do coin-M).

### 5.5 O que não muda
- A régua: critério antes, custo real, três períodos, direção sorteada e retração sorteada; aprovação só acima do p95
  dos controles no holdout.
- A conclusão do §1: tudo que lê só o candle pagou odds justas; a aposta dos três usos é na assimetria e na
  confluência, não na previsão.
- Elliott em 1 min e 5 min: nada. Eles também não contam ali; o 15m deles serve só para "mudança de estrutura e
  reteste" dentro de um setup maior [30:44–30:56].
