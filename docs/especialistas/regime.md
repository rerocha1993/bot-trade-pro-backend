# Regime de mercado para avisos de scalp e day trade — quando cada família vale

Autor: especialista-regime (`.claude/agents/especialista-regime.md`). Data: 20/10/2026.
Para quem lê: capital pequeno, scalp e day trade, sem robô. O que se quer é um **aviso** que diga, antes de o dia
começar ou na primeira hora, que tipo de dia é este e, por isso, qual família de estratégia está liberada e qual
está proibida. Regime sozinho não é estratégia: é a condição "só vale quando…" de cada estratégia dos outros
especialistas.

Fontes usadas: `core/regime.py` (interface de `analisar_regime`), `docs/tradeiros/perfil_por_regime.md` (seções
3.1 a 3.5), `data/estudo_niveis_tpo_resumo.md`, `data/estudo_niveis_tpo_2_resumo.md`, `docs/CONSELHO_ESPECIALISTAS.md`
(seção 5), `docs/especialistas/tpo.md` e as memórias do projeto. Tudo abaixo está marcado como **MEDIDO** (número
que existe no projeto) ou **HIPÓTESE** (o que ainda não foi medido). Nada aqui promete lucro.

Convenções: horários em UTC; ATR_d = ATR de 14 dias no diário; IB ("initial balance") = amplitude da primeira
hora de uma sessão; valor de ontem = VAL/POC/VAH do perfil de TPO de D-1 (`core/tpo_sessao.py`); composto = merge
dos 10 dias anteriores (`core/range_tradeiros.contexto`); R = distância da entrada ao stop.

---

## 1. Diagnóstico em 8 linhas

1. **MEDIDO.** `core/regime.py::analisar_regime(ohlcv, janela=40)` olha os últimos 40 candles do tempo gráfico que recebe e tira três números: eficiência de Kaufman (deslocamento líquido / caminho), ATR curto/ATR longo (14 sobre 100) e largura da janela em ATR. Daí rotula `tendencia` (eficiência ≥ 0,35), `serrilhado` (< 0,15), `compressao` (ATR relativo < 0,7 e largura < 5 ATR: só libera rompimento), `expansao` (ATR relativo > 1,2) ou `neutro`, e devolve um único `permite_entrada` para o robô inteiro.
2. **MEDIDO.** No laboratório de 516 combinações (4 h e 1 h) esse filtro não transformou nenhuma combinação em vantagem estável; na linha "Elliott corretivo + regime não-tendência" de `docs/RESULTADOS_BACKTEST.md` o resultado foi 0,78 (−22%). Ele foi desligado do scalp em 11/09 junto com o resto.
3. **Por que não salvou nada (leitura, não medição):** um filtro só muda a *frequência* de uma regra; se a regra paga odds justas em todos os regimes (o que os estudos de TPO mostraram: nível = sorteio), filtrar dá o mesmo zero com menos trades. Filtro não cria vantagem, só revela uma que já existia escondida num subconjunto.
4. A janela de 40 candles é **atrasada por construção**: a eficiência só fica alta depois que a tendência já andou 40 candles, e os rótulos vêm em blocos (dias inteiros `tendencia`, dias inteiros `serrilhado`), então o filtro corta trades em bloco, o que faz a amostra filtrada parecer boa ou ruim por acaso de calendário.
5. Ele não está **ancorado em nada que o Tradeiros usa**: não sabe onde é a área de valor de ontem, se o dia abriu fora dela, que sessão é, se é fim de semana, se há dado às 12:30. É um regime de série temporal, não um regime de leilão.
6. O `permite_entrada` é **igual para todas as famílias**, que é o contrário do que regime deve fazer: `serrilhado` bloqueia tudo, mas o serrilhado é exatamente o dia em que o jogo responsivo de borda deveria valer; `tendencia` libera tudo, inclusive vender a VAH num dia que vai embora.
7. Os limiares (0,15 / 0,35 / 0,7 / 1,2 / 5 ATR) nunca foram comparados com um filtro **sorteado** nem com o **invertido**, então não se sabe se separam alguma coisa; e o detector de explosão de volatilidade (`core/scalp_volatilidade.py`, ≥ 3× a mediana de 7 dias) **funciona como detector** (pega FOMC, CPI, 05/08/2024) mas operar a favor dele ou o preenchimento depois **perdeu antes do custo** nos três períodos (MEDIDO).
8. O que **não** foi medido e é o que este documento propõe: o tipo de dia pela abertura e pela 1ª hora como filtro das bordas e da VWAP; o regime de grau maior (`core/elliott_pro/superciclo.py`, 12/12 fins de ano e 45/49 trimestres, a coisa mais sólida do projeto) como filtro de **lado** do intradiário; e a volatilidade do dia como seletor de R. Fim de semana e sessão já foram cortados no estudo dos níveis de TPO e não salvaram nada (MEDIDO, n de 40–75 por recorte).

---

## 2. Tipo de dia: classificação objetiva sem olhar o futuro

### 2.1 O que se sabe e quando

| Momento | O que já está fechado e pode entrar na regra |
|---|---|
| 00:00 (abertura do dia) | perfil de D-1 (POC, VAH, VAL, máx, mín, fechamento), amplitude de D-1 em ATR_d, composto de 10 dias (VAL/POC/VAH e em que quartil o fechamento de D-1 está), dia da semana, agenda de eventos do dia (publicada com meses de antecedência), funding e OI das 00:00, estado do superciclo |
| 01:00 (1ª hora da Ásia) | IB do dia (máx − mín de 00:00–01:00), fechamento da 1ª hora em relação ao valor de ontem, eficiência da 1ª hora |
| 08:00 | perfil da Ásia fechado |
| 13:30 (abertura da América) | perfil Ásia + Europa fechado, posição do preço de 13:30 em relação ao valor de ontem **e** ao valor de hoje até aqui |
| 14:30 (1ª hora da América) | IB da América, fechamento da 1ª hora da América |

Em BTC não existe gap às 00:00: o "open" do dia é o fechamento de D-1. Então "abriu fora do valor" às 00:00 quer
dizer **D-1 fechou fora da própria área de valor**, que é o que o Tradeiros chama de "fechou fora, mas ainda não
aceitou". A abertura que tem gap de verdade é a das 13:30, quando os EUA chegam a um preço que a Ásia e a Europa
construíram sem eles.

### 2.2 Os quatro números de entrada (todos conhecidos na hora de usar)

| Número | Definição | Como ler |
|---|---|---|
| **Posição da abertura** (P) | fechamento de D-1 (às 00:00) ou preço de 13:30 (na América) em relação ao VAL/VAH de D-1 | DENTRO, FORA-ACIMA, FORA-ABAIXO |
| **Amplitude da 1ª hora** (IB/ATR_d) | (máx − mín) da 1ª hora dividido pelo ATR_d de ontem | pequeno / normal / grande, pelo **tercil dos últimos 60 dias** da mesma sessão (sem número fixo: evita afinar limiar) |
| **Eficiência da 1ª hora** (E1) | \|fechamento − abertura\| / (máx − mín) da 1ª hora | ≥ 0,6 = a hora foi numa direção só (open-drive); ≤ 0,3 = rodou |
| **Amplitude de D-1** (A1 = range de D-1 / ATR_d) | quanto ontem andou | ≤ 0,6 = ontem comprimiu; ≥ 1,8 = ontem explodiu |

Mais dois contextos fixos do dia: **quartil do composto** em que o preço está (de baixo, meio, de cima; fora do
composto) e **bandeiras** de fim de semana e de evento (seção 4).

### 2.3 Tabela de tipos de dia (regra calculável às 01:00, revista às 14:30)

Frequências são **HIPÓTESE** (estimativa para BTC 2020–2026; ninguém contou ainda). A expectativa de
comportamento vem do método do Tradeiros (seção 3.3 do perfil) e da literatura de Market Profile; é hipótese até
ser medida com o rito da seção 3.

| Tipo | Regra (01:00 / 14:30) | Freq. esperada | O que se espera do resto do dia |
|---|---|---|---|
| **R — Rotação dentro do valor** | P = DENTRO e IB/ATR_d no tercil baixo ou médio e E1 ≤ 0,6 | ~45–55% | preço rodando entre VAL e VAH de ontem; bordas reagem; o meio não tem risco-retorno |
| **V — Abriu fora e voltou** (regra dos 80%) | P = FORA e o fechamento da 1ª hora voltou para dentro do valor de ontem | ~10–15% | rotação até o POC de ontem e, com aceitação, até a borda oposta; é o melhor dia para a borda que foi reconquistada |
| **A — Abriu fora com aceitação** | P = FORA e a 1ª hora inteira ficou fora (mín > VAH ou máx < VAL) e IB/ATR_d no tercil médio ou alto | ~10–15% | dia de tendência potencial: o valor de ontem vira alvo de quem está contra, não borda; reversão proibida |
| **D — Open-drive** | IB/ATR_d no tercil alto **e** E1 ≥ 0,6, independente de P | ~5–10% | dia de tendência: só a favor; VWAP é piso/teto, não ímã; stop estrutural é o extremo da 1ª hora |
| **C — Compressão** | A1 ≤ 0,6 e IB/ATR_d no tercil baixo e preço dentro do composto | ~10% | dia de espera: nada até sair do composto ou da área de valor com fechamento de bloco; vale só armar, não entrar |
| **X — Pós-expansão** | A1 ≥ 1,8 **ou** o detector de explosão disparou nas últimas 24 h | ~5–8% | digestão: stop em % fixo fica pequeno demais; a favor da explosão perdeu (MEDIDO); o preenchimento também perdeu (MEDIDO); dia para R maior ou para não operar |
| **E — Evento** | agenda com FOMC/CPI/payroll/PCE/vencimento trimestral da Deribit/decisão de ETF | ~15% dos dias úteis | plano antes; sem aviso novo de T−30 a T+30 min; depois reclassificar pela primeira meia hora pós-dado (seção 4) |
| **F — Fim de semana** | sábado 00:00 a segunda 00:00 | 2/7 | sem scalp (regra 17 do Tradeiros); ver seção 4 |

Precedência quando mais de um bate: F > E > X > D > A > V > C > R. O dia pode mudar de tipo às 14:30 (a América
decide): um R da Ásia vira A ou D se a América abre fora e aceita. O aviso deve dizer "tipo R até 13:30; revisto
às 14:30".

Dois cuidados para a regra não olhar o futuro: (i) os tercis são dos 60 dias **anteriores**; (ii) o tipo só é
declarado no fechamento da 1ª hora, nunca com ela em andamento. E um cuidado para não se enganar: o tipo diz o
que se *espera*; a medição da seção 3 é que vai dizer se a expectativa separa alguma coisa do sorteio.

### 2.4 Por família: vale em / proibido em / o que muda

Tudo nesta subseção é **HIPÓTESE** salvo onde marcado. A coluna "o que muda" diz o que se espera ver na medição
(frequência e acerto), que é o que o filtro invertido e o sorteado vão testar.

**Bordas do TPO (valor de ontem) e do composto de 10 dias**

| | Regra |
|---|---|
| Vale em | **R** (bordas de ontem) e **V** (a borda reconquistada, com alvo no POC de ontem); no composto, só no quartil de baixo (compra) e de cima (venda), nos dias R, V e C-que-saiu-com-bloco-fechado |
| Proibido em | **A** e **D** (o valor de ontem vira alvo, não borda; quem vende a VAH num dia A é o preso); **X** (stop pequeno demais); **F**; **E** de T−30 a T+30 |
| O que muda | MEDIDO sem filtro: 1º toque = sorteio (0/180 em 5 min, 3/117 em 15 min). Hipótese: restringindo a R+V cai a frequência para ~1/2 dos toques e a reação em 1:1 deve subir acima do controle **do mesmo tipo de dia**; se não subir, o tipo de dia não separa nada e o nível continua sendo alvo, não gatilho |

**VWAP (do dia e de sessão)**

| | Regra |
|---|---|
| Vale em | **D** e **A** como piso/teto **a favor** (comprar o reteste da VWAP num dia D de alta; nunca vender nela); **R** como ímã para "tirar o risco" e alvo do meio |
| Proibido em | **R** e **C** como gatilho de reversão na banda (a banda num dia rodado é um preço qualquer); **X** (a VWAP do dia da explosão está longe demais; usar a de sessão); **F** |
| O que muda | Hipótese: em D/A, a continuação depois do reteste da VWAP com fechamento de bloco a favor deve ser melhor que o sorteio; em R, a banda da VWAP deve ficar igual ao sorteio (como os níveis de TPO). Frequência: poucas (D+A ≈ 15–25% dos dias, 1–2 retestes por dia) |

**Order block (bloco de ordens / última vela contrária antes do impulso)**

| | Regra |
|---|---|
| Vale em | **A** e **V** (o bloco que iniciou a saída do valor é o reteste "com aceitação" que o Tradeiros compra: fechamentos acima, não pavio); **D** no primeiro reteste a favor |
| Proibido em | **R** e **C** (dentro do valor, o bloco é um nível no meio: "não existe risco-retorno"); **X** (blocos da explosão já foram atravessados) |
| O que muda | Hipótese: a frequência cai muito (só blocos que nascem fora do valor ou na saída dele); o acerto no reteste deve ser maior que o do mesmo bloco em dia R. Sem isso, OB é mais um nível que paga odds justas |

**Fibonacci / onda 2 (0,5–0,618 da perna; golden pocket 0,618–0,666)**

| | Regra |
|---|---|
| Vale em | **A** e **D** depois da primeira perna (a onda 2 só existe se houve impulso: dia que saiu do valor), com lado permitido pelo superciclo (seção 3, F3); **V** quando a perna de volta ao valor recua 0,5–0,618 |
| Proibido em | **R** e **C** (não há perna para retrair: a retração de um range é um ponto do range); **X** (retração de pavio de evento) |
| O que muda | MEDIDO: "regra do grupo de contagens" perdeu em 4 h e 1 h, com probabilidade calibrada e odds justas. Hipótese nova: restringir a onda 2 a dias A/D com o lado do superciclo deve tirar os dias de range, onde a retração não é retração; esperar frequência de 2–4 por semana |

**Fluxo / nuvens do livro (calço, absorção, parede, CVD, delta)**

| | Regra |
|---|---|
| Vale em | **R** e **V** nas bordas (o calço na Coinbase é o que qualifica a borda: "zona passiva com calço"); **X** no fundo do pânico (absorção depois de cascata de liquidações, com funding extremo) |
| Proibido em | **D** e **A** como argumento para ir contra (parede contra tendência some); **C** (livro fino, spoof barato); **F** (livro raso, mais pavio) |
| O que muda | MEDIDO: motor de fluxo em 30 dias reais deu bruto zero; o livro só começou a ser gravado em 20/10 (`dados/livro/`), então nada do livro pode ser medido antes de semanas. Hipótese: a nuvem só diferencia em R/V; em D/A ela é atropelada |

**Derivativos (funding, OI, long/short, liquidações)**

| | Regra |
|---|---|
| Vale em | **X** (reset de OI + funding extremo depois de cascata = sinal de fundo/topo local que o Tradeiros cita em várias fichas); **A/D** para dizer quem está preso (OI subindo contra o movimento) e virar alvo de liquidação; contexto de **lado** em qualquer tipo |
| Proibido em | como gatilho isolado em **R** e **C** (MEDIDO: long/short da Bybit contra a mediana não separa VAL nem VAH); em **E** de T−30 a T+30 (o funding e o OI do dado são ruído) |
| O que muda | Hipótese: derivativos só têm valor quando a volatilidade já aconteceu (X) ou quando qualificam uma borda (presos estruturais); frequência baixa (X ≈ 5–8% dos dias) |

Resumo em uma linha por tipo, para o aviso do dia:

- **R:** bordas de ontem + nuvem; VWAP como alvo; nada de OB, Fibonacci ou derivativos como gatilho.
- **V:** a borda reconquistada; alvo POC de ontem; OB da saída; derivativos dizem quem ficou preso fora.
- **A / D:** só a favor: VWAP e OB no reteste, onda 2 com lado do superciclo; bordas de ontem são alvo.
- **C:** armar e esperar o bloco fechado fora; nada para entrar.
- **X:** R maior ou nada; derivativos e absorção para fundo/topo local; nunca a favor da explosão (MEDIDO).
- **E / F:** seção 4.

---

## 3. Os 3 filtros de regime com maior potencial ainda não medidos

Rito comum de medição (vale para F1, F2 e F3), o mesmo dos estudos de TPO:

- candles de 15 min da Binance 2020-01..2026-09 (`data/historico/BTCUSDT_binance_15m.csv`), três períodos fixos
  (treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09), custo 0,06% ida e volta, stop
  antes do alvo no mesmo candle (pessimista), critério escrito **antes** de rodar, nenhum parâmetro iterado;
- a estratégia-base é uma que já está medida sem filtro (bordas do composto e VAL/VAH de ontem do estudo 2), para
  que o efeito do filtro seja a única coisa nova;
- três controles obrigatórios: (a) a mesma estratégia **sem** filtro (já existe); (b) **filtro invertido** (opera só
  nos dias em que o filtro proíbe); (c) **filtro sorteado**: os rótulos de tipo de dia embaralhados entre os dias,
  mantendo a mesma proporção, 20 sorteios;
- aprovação: líquido > 0 nos 3 períodos com ≥ 30 decididos por período **e** o filtrado acima de 95% dos sorteados
  no holdout **e** o invertido pior que o sem-filtro nos 3 períodos. Faltando qualquer um, o filtro não separa.

### F1 — Tipo de dia pela 1ª hora como filtro das bordas (R/V liberam, A/D proíbem)

- **Hipótese.** O jogo responsivo de borda (comprar VAL, vender VAH, de ontem e do composto) só paga em dias R e V; em
  A e D o mesmo toque é o preso. Sem o filtro, os dois grupos se cancelam e o resultado é o sorteio (MEDIDO).
- **Regra do filtro (01:00 e 14:30).** P e IB/ATR_d por tercil dos 60 dias anteriores, E1, conforme 2.3. Entrada
  permitida das 01:00 às 13:30 pelo tipo da Ásia; das 14:30 em diante pelo tipo da América.
- **O que se espera.** Frequência cai para ~50–60% dos toques; reação em 1:1 em R/V acima do controle sorteado do
  mesmo dia; em A/D abaixo. Se R/V ficar no sorteio, o tipo de dia pela 1ª hora não tem informação para bordas.
- **Como medir.** Rito comum, estratégia-base = H1 do estudo 2 (VAL compra, VAH venda, R = 1%, 1:1 e 2:1). Quebrar
  por tipo de dia e por sessão em que o tipo foi declarado. Segunda rodada, só se a primeira aprovar: mesma coisa
  nos níveis de ontem em 5 min (estudo 1), para ver se o filtro salva o scalp ou só o day trade.
- **Nota: 7/10.** É o filtro que o método do Tradeiros pressupõe sem dizer, é barato (o rig do estudo 2 já existe) e,
  mesmo reprovado, vira um aviso útil ("hoje é dia A: bordas proibidas") que não promete %.

### F2 — Volatilidade do dia como seletor de R (stop em ATR, não em %)

- **Hipótese.** Os estudos usaram R fixo (0,3/0,6% em 5 min; 1/2% em 15 min). Em dia de ATR baixo, 1% é grande demais
  (o alvo não vem, sai por tempo); em dia X, 1% é pequeno demais (o pavio come). Um R = k × ATR de 15 min dos últimos
  100 candles (k fixo, 3 valores escritos antes: 2, 3, 4) deve igualar o risco entre regimes e tirar os dias X da
  conta de quem opera borda.
- **Regra do filtro.** Nenhuma seleção de dias: o regime entra só no tamanho do R. Variante com seleção: proibir o
  tipo X (A1 ≥ 1,8 ou detector disparou nas 24 h).
- **O que se espera.** Mesma frequência; a distribuição de resultado por trade deve ficar menos dependente do período
  (hoje treino 2020–2021 e holdout 2025–2026 têm ATR muito diferentes). Se melhorar só por reduzir o custo em R, não
  é vantagem: comparar o custo médio em R antes e depois.
- **Como medir.** Rito comum, estratégia-base = H1 do estudo 2, três k, controle sorteado de nível (já existe) com o
  mesmo R em ATR. Invertido aqui é "R fixo em %" (o que já foi medido). Sorteado: k sorteado por dia entre os três.
- **Nota: 5/10.** Dificilmente cria vantagem (muda a régua, não a informação), mas corrige um defeito de medição que
  pode estar escondendo um sinal pequeno e é pré-requisito para qualquer aviso com stop "em ATR".

### F3 — Superciclo (grau maior) como filtro de LADO do intradiário

- **Hipótese.** `core/elliott_pro/superciclo.py` acertou 12/12 fins de ano e 45/49 trimestres sem olhar o futuro
  (MEDIDO) e nunca foi usado como filtro de lado no intradiário. A borda de baixo (VAL) só se compra quando o grau maior
  permite comprar (`fundo_terminal`, `novo_impulso`, `zona_onda_2`, `impulso_alta`); a borda de cima (VAH) só se vende
  em `impulso_maduro`, `correcao_inicial`, `correcao_em_curso`; nos estados `hold`/`memoria`/`recuo_profundo`, nada.
  É a versão medível dos vetos "fundo de ciclo ninguém vende; correção recém-iniciada ninguém compra".
- **Regra do filtro (00:00).** Estado do superciclo no fechamento de D-1 (`ContextoSuperciclo.estado()`), que só usa
  dados até ali.
- **O que se espera.** Frequência cai para ~metade (só um lado por vez); o lado permitido deve ficar acima do controle
  sorteado e o lado proibido abaixo. Se os dois ficarem iguais, o grau maior não desce até o intradiário (plausível:
  o ciclo acerta o trimestre, não a hora).
- **Como medir.** Rito comum, estratégia-base = H1 do estudo 2. Invertido = opera só o lado proibido. Sorteado =
  lado permitido sorteado por dia (20 sorteios). Cuidado com a autocorrelação: o estado dura meses, então os três
  períodos têm poucos estados cada; exigir que cada período contenha pelo menos dois estados diferentes ou declarar
  que o teste é inconclusivo.
- **Nota: 6/10.** Base mais sólida do projeto e coerente com "Elliott é a lei"; o risco é o grau maior não ter
  resolução para o day trade, e a amostra efetiva ser pequena (poucos estados por período).

---

## 4. Regra de fim de semana e de dia de evento

### 4.1 Fim de semana (sábado 00:00 a segunda 00:00)

- **MEDIDO.** O Tradeiros não scalpa com volume muito baixo (regra 17 em 5.1 do perfil: fim de semana, feriado) e
  disse "fim de semana não vale operar" (23/12/2022). No estudo dos níveis de TPO em 5 min, o recorte fim de semana ×
  dias úteis **não salvou nenhum tipo** de nível (n de 40–75 por recorte, erro padrão de 6–8 pontos): o nível continua
  sorteio nos dois.
- **HIPÓTESE.** Fim de semana tem menos liquidez e mais pavio, então o stop em % apanha mais; o que não é dito é que
  também tem menos ATR, então o R em ATR (F2) seria menor. Não há medição de VWAP, OB ou fluxo no fim de semana.
- **Regra para o aviso:** sem aviso de scalp de sábado 00:00 a segunda 00:00. Ordens de day trade/swing já armadas
  numa borda do composto podem ficar, com a nota "fim de semana: pavio provável, stop estrutural e não de bobeira". O
  domingo à noite (22:00 em diante) conta como Ásia de segunda para efeito de tipo de dia, mas o tipo da segunda só é
  declarado às 01:00. Rótulo F tem precedência sobre todos.
- **Se alguém quiser medir:** a estratégia-base de F1 quebrada em dia útil × fim de semana, com os mesmos controles.
  Expectativa honesta: não separa (o estudo de TPO já apontou isso).

### 4.2 Dia de evento (tipo E)

- **MEDIDO.** "A notícia não é gatilho" em 15 fichas: o plano é feito antes; o horário só marca volatilidade e a hora
  de realizar/mexer em stop. Se o dado leva o preço a uma borda, operam contra a reação do consenso (CPI 11/09/2026,
  payroll 04/09/2026). O detector de explosão pega os eventos (FOMC, CPI, 05/08/2024), mas operar a favor dele ou o
  preenchimento perdeu antes do custo nos três períodos.
- **Agenda calculável sem olhar o futuro:** FOMC (decisão 18:00, coletiva 18:30), CPI/PCE/payroll (12:30), vencimento
  trimestral da Deribit (última sexta do trimestre, 08:00), datas de ETF e halving. Tudo publicado com meses de
  antecedência; para backtest é preciso uma **tabela estática** no projeto (`core/macro_event_checker.py` raspa o
  investing.com ao vivo e não serve para histórico). Até existir a tabela, o tipo E não pode ser medido.
- **Regra para o aviso:**
  1. Às 00:00: "dia de evento às HH:MM"; avisos da manhã valem só até T−30 min e devem dizer "realizar ou tirar o risco
     antes do dado" (o que o Tradeiros fez em 04/09/2026).
  2. De T−30 a T+30: nenhum aviso novo; stops ficam onde estão (não apertar: o pavio do dado passa por cima do stop
     curto, como em 19/11/2025).
  3. Depois de T+30: reclassificar o dia pela primeira meia hora pós-dado, como se fosse a 1ª hora: bloco de 30 min
     fechou **de volta** dentro do valor depois de encostar numa borda → tipo V (reação contra o consenso: a borda
     reconquistada com alvo no POC); bloco fechou **fora** com amplitude no tercil alto → tipo A/D (só a favor, e
     mesmo assim com a ressalva de que a favor da explosão perdeu quando medido); nada disso → segue o tipo da manhã.
  4. Fim de semana que antecede evento geopolítico não muda o tipo: é F.
- **HIPÓTESE a medir (depois da tabela de eventos):** a estratégia-base de F1 só nos dias E, dividida em "antes do
  dado", "T±30" e "depois do dado com reclassificação", contra o sorteio de dias não-E com as mesmas horas. Expectativa:
  "antes" e "T±30" ficam no sorteio ou pior; "depois com V" é a única fatia com chance.

---

## 5. Ranking e escolha

| # | Filtro de regime | Estado | Nota | Por quê |
|---|---|---|---|---|
| 1 | **F1 — tipo de dia pela 1ª hora (R/V × A/D) para bordas** | HIPÓTESE | **7** | é o pressuposto escondido do jogo responsivo; rig pronto; vira aviso útil mesmo se reprovar |
| 2 | F3 — superciclo como filtro de lado | HIPÓTESE | 6 | base mais sólida do projeto; risco de não ter resolução intradiária e amostra por estado pequena |
| 3 | F2 — R em ATR (volatilidade como seletor de R) | HIPÓTESE | 5 | corrige a régua, não cria informação; pré-requisito de qualquer stop "em ATR" |
| 4 | Dia de evento com reclassificação pós-dado (4.2) | HIPÓTESE | 4 | coerente com as fichas; precisa de tabela estática de eventos antes de medir |
| 5 | Compressão (tipo C) → só rompimento com bloco fechado | HIPÓTESE, vizinho de MEDIDO | 3 | a continuação nos extremos deu 0/183 em 5 min; a versão por bloco fechado e saída do composto não foi medida, mas o vizinho reprovou |
| 6 | Pós-expansão (tipo X) → reversão à média | MEDIDO (negativo) | 2 | o preenchimento depois da explosão perdeu nos três períodos, mesmo em 1 min |
| 7 | Sessão (Ásia/Europa/América) como filtro | MEDIDO (negativo) para níveis de TPO | 2 | recortes de n 40–75 sem nada acima do controle; para VWAP/OB não medido, sem razão para esperar diferente |
| 8 | Fim de semana × dias úteis | MEDIDO (negativo) para níveis de TPO | 2 | mesmo resultado; a regra "não scalpar" fica por prudência, não por vantagem |
| 9 | Kaufman/ATR de `core/regime.py` como está | MEDIDO (negativo) | 1 | 516 combinações sem vantagem estável; atrasado, não ancorado no valor, um `permite_entrada` para tudo |

**Escolha: F1.** Ordem recomendada: F1 primeiro (um dia de trabalho sobre o rig do estudo 2), e só se F1 passar ou
mostrar separação clara entre R/V e A/D, rodar F3 em cima dele (lado do superciclo dentro dos dias R/V). F2 pode
rodar junto com F1 como variante de régua, sem custo extra, desde que os três k estejam escritos antes.

O que o usuário ganha mesmo no pior caso: um aviso diário às 01:00 e às 14:30 com o **tipo de dia** e a lista de
famílias liberadas/proibidas, sem %, até a medição dizer que fatia tem número. Se F1, F2 e F3 reprovarem, a
conclusão honesta é que, no BTC em 15 min, o regime do dia não separa o nível do sorteio, e o único regime que
sobra com número é o de grau maior, que decide o lado da carteira e o hedge, não o scalp.
