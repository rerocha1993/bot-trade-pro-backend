# Order Block para avisos de scalp e day trade — por que o que existe deu zero, o que ainda tem potencial e por onde começar

Autor: especialista-order-block (`.claude/agents/especialista-order-block.md`). Data: 20/10/2026.
Para quem lê: capital pequeno, scalp e day trade, sem robô. O que se quer é um **aviso** com lado, zona de entrada,
stop e alvo. Tudo abaixo está marcado como **MEDIDO** (número que existe no projeto) ou **HIPÓTESE** (o que ainda
não foi medido). Nada aqui promete lucro.

Fontes usadas: `core/order_block.py` (regra do detector), `core/scalp_indicadores.py` (setup "reteste de OB" do
scalp de 11/09/2026), `services/orderblock_institutional_service.py` (faixas do livro), memória do scalp por
indicadores (900 trades, −0,002% por trade), estudos de níveis de TPO de 20/10 (`data/estudo_niveis_tpo_*_resumo.md`)
e `docs/especialistas/tpo.md`. Dados disponíveis: candles Binance de 5 min, 15 min, 1 h e 4 h de ago/2017 a
out/2026; 1 min com eventos; livro de ordens gravado só a partir de **20/10/2026** (um dia).

---

## 1. Diagnóstico em 8 linhas: por que o reteste de OB deu zero em 900 trades

1. **MEDIDO.** Scalp 5 min, jan–set/2026, setup "reteste de order block" (lado pela VWAP, regime não serrilhado, gatilho = volta ao bloco e fecha além dele): **−0,002% por trade em 900 trades**, bruto, antes do custo de 0,06%. Zero. Não é "quase": é a mesma coisa que sortear.
2. **A "estrutura" do detector não é estrutura.** `OrderBlockDetector` chama de rompimento superar a máxima dos **5 candles anteriores** (`lookback=5`). Em 5 min isso acontece dezenas de vezes por dia; é um candle de baixa seguido de três de alta, não um topo de swing rompido. O que o SMC chama de BOS (fechamento acima do último topo de swing confirmado) nunca foi exigido.
3. **O "deslocamento" de 1,5 ATR em 3 candles de 5 min é ruído.** O ATR de 14 candles de 5 min do BTC fica em 0,1–0,2%; 1,5 ATR é 0,15–0,3%, menos que uma oscilação de rotina. Em 1 h a mesma régua vale 0,8–1,5% e já separa impulso de barulho.
4. **Sem FVG, sem varredura, sem "primeira volta".** O detector não pede gap de valor justo à frente, não pede que um topo/fundo igual tenha sido varrido antes, e marca mitigado só quando o preço **fecha além** da zona; logo, um bloco já retocado três vezes continua "ativo". Cada reteste é o primeiro toque de um nível, e o estudo de TPO de 20/10 mediu que o primeiro toque de qualquer nível, em 5 e 15 min, reage **tanto quanto um preço sorteado** (MEDIDO).
5. **Demais blocos = zona sorteada.** Com `lookback=5` e `janela=3`, um dia de 5 min produz dezenas de blocos "ativos" de cada lado a ≤ 3% do preço. Quando há bloco em todo lugar, "preço em order block" é o mesmo que "preço em qualquer lugar".
6. **A zona é menor que o custo.** Bloco de 5 min tem 0,1–0,3% de altura; piso de stop de 0,12%; custo de ida e volta de 0,06%. Para pagar o custo com R:R 1,0 o movimento precisa ser 2× o stop, e isso em 5 min é o ruído do item 3. O tempo gráfico matou a conta antes de o mecanismo entrar.
7. **Nenhum alvo na liquidez.** O setup saía por R:R fixo, não em topos/fundos iguais, naked POC ou FVG oposto. Sem alvo concreto o OB é só "onde entrar", e "onde entrar" sozinho foi reprovado em todos os estudos do projeto (MEDIDO, TPO 1 e 2).
8. **O que um OB qualificado exige (regra sem olhar o futuro):** (a) tempo gráfico de 1 h ou 4 h; (b) último candle contrário antes de um impulso de ≥ 1,5 ATR(14) que **fecha** além do último topo/fundo de swing (pivô com 3 candles de cada lado, confirmado só depois do 3º); (c) FVG dentro do impulso (mínima do candle 3 acima da máxima do candle 1, para alta); (d) de preferência uma varredura de liquidez logo antes (o impulso nasce de um pavio que passou um topo/fundo igual); (e) nunca retocado desde o BOS (checar em 5 min); (f) entrada no 50% da zona, stop além do extremo, alvo em liquidez oposta a ≥ 2 R. OB sem (b) e (c) é só um candle: isso o projeto já mediu.

---

## 2. As 3 estratégias de OB com maior potencial ainda não medidas

Critério de escolha: (a) OB qualificado, não "qualquer candle contrário"; (b) gatilho em candle fechado; (c) stop
estrutural; (d) alvo em liquidez concreta a ≥ 2× o stop; (e) dá para medir com o que existe, ou diz exatamente o
que falta; (f) não repete o que foi reprovado. Convenção: R = distância da entrada média ao stop. Custo de ida e
volta 0,06%. Frequências são estimativas (HIPÓTESE) até alguém contar no histórico.

### E1 — OB qualificado em 1 h (deslocamento + BOS + FVG), estrutura de 4 h a favor, alvo na liquidez oposta

- **Tempo gráfico.** 4 h para a direção; 1 h para o OB, o BOS, o FVG e o gatilho; 5 min só para executar as fatias e checar se a zona já foi tocada.
- **Definição exata do OB válido (compra; venda espelhada).** Swing = máxima de 1 h com 3 candles menores de cada lado (só existe 3 candles depois). OB = último candle de 1 h de fechamento < abertura antes de um impulso que, em ≤ 3 candles de 1 h: (1) percorre ≥ 1,5 ATR(14, 1 h) da mínima do OB à máxima do impulso; (2) **fecha** acima do último swing high (BOS por fechamento, não por pavio); (3) deixa FVG (mínima do 3º candle do impulso > máxima do 1º); (4) a zona [mínima, abertura] do OB não é tocada entre o OB e o BOS. Altura da zona entre 0,3% e 1,5% (fora disso, pular). O OB vale a partir do fechamento do candle do BOS e expira em 48 candles de 1 h (2 dias) sem reteste.
- **Contexto.** O último evento da estrutura de 4 h é BOS de alta (ou CHoCH de alta depois de fundo). Não comprar OB de 1 h com a estrutura de 4 h em baixa. Dentro do composto de 10 dias do Tradeiros, só compra no quartil inferior ou meio-baixo (o quartil é contexto, não gatilho; MEDIDO que a borda sozinha é sorteio).
- **Gatilho (candle fechado).** Primeiro retorno à zona: um candle de 1 h toca o 50% da zona (ou abaixo) e **fecha acima do topo da zona**. Variante B, medida à parte: limitadas na zona sem esperar o fechamento (preenche no toque).
- **Zona de entrada (3 fatias limitadas).** 20% no topo da zona, 30% no 50%, 50% no 75% em direção à mínima (fatia maior mais longe, como o Tradeiros). Validade: 24 candles de 1 h após o gatilho.
- **Stop.** Mínima do OB − 0,15% (ou − 0,1 ATR de 1 h, o maior). Típico 0,8–1,5% do preço.
- **Alvo (liquidez concreta).** O mais próximo entre: topos iguais de 1 h acima (duas máximas de swing a ≤ 0,15% uma da outra), naked POC acima, FVG de 1 h/4 h não preenchido acima, máxima da semana anterior. Exigência: ≥ 2 R; sem alvo a ≥ 2 R, **sem aviso**. Em 1 R: realizar 25–50% e stop no preço médio.
- **R:R típico (HIPÓTESE).** 2–4 R. Trade dura de horas a 2 dias: é day trade longo, não scalp.
- **Frequência (HIPÓTESE).** 2–5 avisos por semana somando compra e venda; ~9 anos de 1 h dão centenas de eventos por período, amostra boa.
- **De onde vem a vantagem (HIPÓTESE).** No OB ficaram ordens institucionais parcialmente executadas que o impulso provou ter força (BOS); o FVG é o trecho sem negócio que o preço tende a revisitar; no reteste, quem vendeu o rompimento está preso e recompra. É o mecanismo "quem ficou preso, quem precisa recomprar", e em 1 h o movimento é 15–25× o custo.
- **O que a mata.** OB contra a estrutura de 4 h; zona já retocada em 5 min (precisa ser o primeiro retorno); reteste depois de 2 dias (bloco velho); notícia dentro da janela (CPI 12:30, FOMC 18:00 UTC); OB largo (> 1,5%: o alvo não cobre). E o parente mais próximo já medido não ajuda: OB sem qualificação em 5 min = zero (MEDIDO); nível de 1º toque = sorteio (MEDIDO). A família tem histórico ruim; a aposta é que BOS + FVG + tempo maior separam.
- **Dados.** Já existem: 1 h e 4 h da Binance (2017–2026), 5 min para a execução e para checar "já foi tocado". Nada de livro.
- **Como medir.** Critério escrito antes; variantes fixas (A fechamento × B limitadas; 1 h × 4 h) e nenhum parâmetro iterado. Três controles: (1) **OB sem qualificação** (o detector atual, `lookback=5`, sem FVG, sem BOS por fechamento) com a mesma gestão, que mede se a qualificação acrescenta algo; (2) **zona sorteada**: mesma altura, posição sorteada no range das 48 h anteriores, mesma direção de 4 h; (3) **direção sorteada** no mesmo instante. Três períodos (treino 2020–23, validação 2024–jun/25, holdout jul/25–set/26), mínimo 30 decididos por período, pessimista (favor e contra no mesmo candle = contra). Aprova só o que fica líquido > 0 nos 3 períodos **e** 2 EP acima dos três controles em treino e validação; holdout lido uma vez.

### E2 — Varredura de liquidez + volta (sweep de topo/fundo igual, CHoCH em 15 min, entrada no OB que fez a volta)

- **Tempo gráfico.** 4 h para a direção; 1 h para o nível de liquidez e a varredura; 15 min para o CHoCH, o OB e o gatilho; 5 min para executar.
- **Definição exata (venda depois de sweep de topo; compra espelhada).** Liquidez = topos iguais de 1 h (≥ 2 máximas de swing a ≤ 0,2% entre si, separadas por ≥ 12 candles) **ou** máxima do dia anterior **ou** máxima da semana anterior. Varredura válida = candle de 1 h cuja máxima passa o nível em ≥ 0,05% e ≤ 0,8% e que **fecha abaixo** do nível (ou o candle seguinte fecha abaixo). Excursão > 0,8% é rompimento, não varredura: pular. Volta confirmada = CHoCH em 15 min: fechamento de 15 min abaixo do último fundo de swing de 15 min (3 candles de cada lado) formado na subida até o nível, em ≤ 8 candles de 15 min após a varredura. OB = último candle de alta de 15 min antes do impulso que fez o CHoCH, com deslocamento ≥ 1 ATR(14, 15 min) e FVG; zona = [abertura, máxima].
- **Contexto.** Só varredura **contra** a direção permitida de 4 h, ou no extremo do range de 4 h (sweep de topo com 4 h em baixa ou lateral; sweep de fundo com 4 h em alta ou lateral). Em tendência de 4 h a favor do rompimento, a varredura vira continuação (HIPÓTESE, mas é o que mata o setup).
- **Gatilho (candle fechado).** O fechamento do candle de 15 min que faz o CHoCH. A partir dele, o aviso sai com a zona do OB de 15 min. Variante B, medida à parte: entrada a mercado no fechamento do CHoCH (sem esperar reteste).
- **Zona de entrada (3 fatias limitadas).** 20% na base da zona do OB, 30% no 50%, 50% no 75% em direção ao extremo. Validade: 16 candles de 15 min (4 h); se não retestar, o aviso morre.
- **Stop.** Máxima da varredura + 0,10%. Típico 0,5–1,0%.
- **Alvo (liquidez concreta).** Lado oposto: fundos iguais de 1 h, mínima do dia anterior, naked POC abaixo, VAL do composto, FVG de 1 h não preenchido. Exigência ≥ 2 R; em 1 R tirar o risco e stop no médio.
- **R:R típico (HIPÓTESE).** 2–3 R, trade de 2–12 h: cabe no day trade do usuário.
- **Frequência (HIPÓTESE).** 3–6 eventos por semana (máxima/mínima do dia anterior existem todo dia; topos iguais, menos); com o filtro de 4 h e o CHoCH, 1–3 avisos por semana.
- **De onde vem a vantagem (HIPÓTESE).** Acima de topos iguais há stops de vendidos e ordens de compra de rompimento. A varredura executa as duas; quem comprou o rompimento fica preso quando o preço fecha de volta, e o CHoCH é a prova de que a volta tem força. É o único setup aqui cujo combustível (presos) está na definição. O estudo de TPO ajuda por um lado estranho: ele mediu que máximas e mínimas de dia e sessão **atravessam** no primeiro toque (29–40% de reação; MEDIDO), ou seja, a varredura é o normal. O que não foi medido é se, **depois** da varredura com fechamento de volta, o retorno paga.
- **O que a mata.** Varredura que é rompimento (4 h a favor); CHoCH que chega tarde (o preço já fez 1 R quando o aviso sai, por isso a entrada é no reteste, não a mercado); nível de liquidez muito próximo do preço corrente (< 0,3%: tudo vira varredura); notícia; fim de semana (o Tradeiros não scalpa, volume baixo). Três parâmetros (excursão máxima, janela do CHoCH, tolerância dos topos iguais) são três convites a sobreajuste: fixar antes.
- **Dados.** Já existem: 1 h, 15 min, 5 min e 1 min com eventos (2017–2026). Nada de livro.
- **Como medir.** Critério escrito antes, variantes fixas (topos iguais × PDH/PDL × PWH/PWL; A reteste × B mercado). Controles: (1) **toque simples do mesmo nível sem varredura** (o que o estudo de TPO já mediu como pior que o sorteio; serve de controle natural); (2) **varredura sem CHoCH** (entrada no fechamento de volta), que mede se o CHoCH separa; (3) **zona sorteada** e **direção sorteada**. Mesmos três períodos, mínimo 30 decididos por período, pessimista, aprovação idêntica à E1.

### E3 — "Order blocks institucionais" do livro como zona passiva (parede que absorve), gatilho em 5 min

- **Tempo gráfico.** Livro em tempo real (snapshot a 30 s, Coinbase + Binance + Bybit); 5 min para o gatilho; 1 h/4 h para a direção.
- **Definição exata da zona válida (sem olhar o futuro).** Faixa de 0,05% com ≥ 3% do volume agregado do lado (a regra de `detectar_blocos`), presente em ≥ 2 exchanges, a ≤ 1,5% do preço, **persistente por ≥ 30 min** (60 snapshots seguidos com ≥ 80% do tamanho; a persistência é o filtro anti-spoof) e alinhada com a estrutura: bid abaixo do preço com 4 h em alta, ou coincidindo (≤ 0,2%) com OB de candle de 1 h, VAL/VAH do composto ou naked POC. Fora desse alinhamento a parede é só número.
- **Contexto.** Direção de 4 h a favor; quartil do composto permitido (compra embaixo, venda em cima). A faixa é **zona**, nunca gatilho (o 1º toque de nível é sorteio, MEDIDO).
- **Gatilho (candle fechado).** O preço chega a ≤ 0,1% da faixa, a faixa **não some** (≥ 80% do volume enquanto o preço está encostado) e um candle de 5 min fecha de volta além da faixa (absorção vista: a agressão vendedora bateu e o preço não atravessou). Regra de morte: parede puxada antes do preenchimento = aviso cancelado na hora.
- **Zona de entrada.** 2 fatias limitadas: borda da faixa + 0,05% e borda + 0,15%.
- **Stop.** Borda oposta da faixa − 0,15%. Típico 0,25–0,4%.
- **Alvo.** Parede passiva oposta (ask wall para compra) ou nível de 1 h mais próximo; ≥ 2 R, ou seja, 0,5–0,8% em scalp. Em 1 R tirar o risco.
- **R:R típico (HIPÓTESE).** 2 R; trade de 20 min a 2 h. É o único dos três que é scalp de verdade, e por isso o custo (0,06% contra alvo de 0,5%) pesa 12%.
- **Frequência (HIPÓTESE).** Paredes de 3% são comuns; a persistência de 30 min e o alinhamento derrubam para 1–3 por dia.
- **De onde vem a vantagem (HIPÓTESE).** Ordem passiva grande e real executa: absorve a agressão e o preço não passa; quem vendeu nela fica preso e a volta é a cobertura. É o "calço" do Tradeiros, com a diferença de ter uma régua (persistência e absorção) em vez do olho.
- **O que a mata.** Spoof (parede puxada a 0,05% do preço é rotina em BTC; sem a regra de morte o setup vira o pior dos três); parede de market maker que anda junto com o preço (ordem dinâmica, nunca é alcançada); parede atravessada em notícia; snapshot de 30 s (a parede some e volta entre dois snapshots); custo em scalp.
- **Dados: é aqui que a estratégia para.** O livro só está sendo gravado desde **20/10/2026** (um dia, `dados/livro/<exchange>/2026-10-20.jsonl.gz`, coletor em `scripts/coletor_livro.py` a 30 s). Não existe histórico para medir nada. Precisa: (1) coletor ligado sem buraco por **≥ 90 dias** (180 é o mínimo para três períodos), nas 3 exchanges, profundidade de ≥ 2% dos dois lados; (2) **negócios agregados por minuto** (agressão compradora × vendedora) no mesmo período, para distinguir "absorveu" de "ninguém bateu"; sem isso o gatilho de absorção não é verificável; (3) candles de 1 min do mesmo período (já existem). Até lá, E3 é zona de confluência para E1 e E2 no aviso ("há parede de X BTC em Y"), sem probabilidade.
- **Como medir (quando houver 90 dias).** Controles: (1) **faixa sorteada** da mesma largura, à mesma distância do preço, mesma direção; (2) **faixa com volume mas sem persistência** (o grupo "spoof"), que mede se a persistência separa; (3) direção sorteada. Com 90 dias só dá treino (60) e validação (30); o holdout fica para os 90 dias seguintes. Resultado preliminar fica marcado como preliminar.

---

## 3. Ranking, por onde começar e risco principal

| # | Estratégia | Nota 0–10 | Por quê | Estado |
|---|---|---|---|---|
| 1 | **E2 — varredura + volta** | **7** | Mecanismo mais concreto (presos na definição), cabe no day trade do usuário, dados prontos, controle natural já medido (toque simples = pior que o acaso) | HIPÓTESE, medível hoje |
| 2 | E1 — OB qualificado 1 h | 6 | Regra mais simples, 9 anos de 1 h, custo irrelevante; mas é a família que já deu zero, agora com qualificação, e o trade é mais longo que o usuário quer | HIPÓTESE, medível hoje |
| 3 | E3 — paredes do livro | 4 | O mecanismo é o do Tradeiros, mas não há histórico de livro nem de agressão; spoof é o padrão em BTC. Nota é do potencial, não do que se sabe | HIPÓTESE, **não medível** antes de ~jan/2027 |

**Para começar: E2.** Ela contém o OB qualificado da E1 (deslocamento + FVG + estrutura) e acrescenta o único
fato que o detector atual nunca viu: a varredura com fechamento de volta. Se E2 reprovar, E1 se mede em seguida
com o mesmo motor de swings/BOS/FVG (construído uma vez). Enquanto E2 e E1 são medidas, o coletor do livro fica
ligado sem buraco para que E3 exista em três meses.

**Risco principal da E2:** a varredura que é rompimento. Em tendência de 4 h, o preço passa o topo igual, fecha
acima e segue; o filtro de 4 h e o CHoCH existem para isso, mas são parâmetros, e três parâmetros fixados "até
passar" dão um backtest bonito e um holdout zero (foi o que o motor otimista fez com o robô 9, MEDIDO). Por isso:
regra escrita antes, nenhuma iteração, três controles, holdout lido uma vez.

**O que vai no aviso, até a medição existir:** lado e zona (OB de 15 min depois da varredura), stop (máxima da
varredura + 0,10%), alvo (liquidez oposta a ≥ 2 R), e a frase "sem probabilidade medida". Parede do livro, quando
houver, entra como confluência descrita, não como número.
