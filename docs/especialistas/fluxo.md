# Especialista de fluxo — as "nuvens", três estratégias e o que falta coletar

Data: 20/10/2026. Autor: especialista-fluxo (order flow / microestrutura).
Base: `docs/CONSELHO_ESPECIALISTAS.md` (seção 3), `docs/tradeiros/perfil_por_regime.md` (2.2 e 3.3),
`conselho/coletor_livro.py` e `conselho/livro_historico.py` (coletor ligado hoje às 09:16, ~140 snapshots por exchange até 10:28).

**Aviso antes de tudo: nada deste documento foi medido.** O livro de ordens começou a ser gravado hoje; liquidações e
negócios da Coinbase não são gravados. Toda "probabilidade" citada abaixo é **hipótese para ser testada**, não número
para operar. O conselho só vai mostrar % quando houver o medido, com o controle sorteado ao lado (regra da seção 4 do
conselho). Capital pequeno, scalp/day trade: o custo (taker na Bybit 0,055% × 2 ≈ 0,11% + escorregada ~0,02%) come
um quarto de um stop de 0,5%, então alvo abaixo de 0,8% não paga a conta.

---

## 1. O indicador que o usuário descreveu

O que ele viu — "mede Coinbase e outras grandes, junta os dados e cria nuvens vermelhas (venda) e verdes (compra); a
nuvem vermelha aparece quando o mercado está esticando, com ordens pesadas de venda apregoadas enquanto ainda sobe,
muita gente alavancada comprando a mercado; daqui a pouco deixa todo mundo preso no topo e cai forte" — é o
**heatmap de liquidez do livro de ordens agregado** (ordens *passivas* a limite, somadas entre exchanges, desenhadas
no tempo como manchas de calor). A variante que também desenha "nuvens" é o **mapa de liquidações** (onde as
posições alavancadas *seriam* liquidadas; não são ordens, são estimativas). No vocabulário do Tradeiros: "nuvens" e
"calço" da Coinbase spot. A segunda metade da frase (muita gente alavancada comprando a mercado) não vem do livro,
vem dos **derivativos**: OI subindo, funding caro, long/short de contas alto, agressão compradora no perpétuo.

### 1.1 Ferramentas e que dado cada uma usa

| Ferramenta | O que desenha | Dado de origem | Observação |
|---|---|---|---|
| **Bookmap** | Heatmap do livro no tempo (cor = tamanho da ordem passiva), bolhas de volume negociado, CVD; add-on "multibook" soma várias exchanges | Feed completo do livro (L2 e, onde existe, ordem a ordem) via WebSocket das exchanges conectadas (Binance, Bybit, Coinbase, OKX, Bitmex, Deribit…) | Guarda o livro inteiro, por nível de preço, com atualização sub-segundo. É o mais próximo de "ver a parede sumir" |
| **Coinglass** | "Orderbook Heatmap" (livro), "Liquidation Heatmap" e "Liquidation Map" (nuvens de liquidação), lista de "big orders", bid/ask delta agregado | Livro: profundidade pública das exchanges (Binance, OKX, Bybit, Coinbase, Bitfinex…). Liquidação: **modelo** proprietário a partir de OI, preço e distribuição de alavancagem presumida | A nuvem de liquidação é estimativa, não ordem. API histórica é paga |
| **Hyblock Capital** | "Liquidation Levels" (cumulativo), heatmap do livro, "Liquidity Levels", long/short de varejo | Mesmo esquema: livro público das exchanges + modelo de liquidação por variação de OI e alavancagens típicas (10×/25×/50×/100×) | Também paga para histórico |
| **TensorCharts** | Heatmap do livro em tempo real, negócios por tamanho, imbalance | WebSocket de livro e de negócios (Binance, Coinbase, Bitmex, Bitfinex, Kraken…) | Sem histórico longo acessível |
| **Exocharts** | Footprint, heatmap do livro, CVD, liquidações, tudo **agregado** entre exchanges | WebSocket de negócios, livro e liquidações (Binance, Bybit, OKX, Bitmex, Coinbase, Deribit…) | É o que mais se parece com "junta Coinbase e as grandes" num gráfico só |
| Material Indicators (FireCharts), aggr.trade | Heatmap do livro da Binance com cores por tamanho; agregador de negócios open source | Livro e negócios públicos da Binance (e outras) | Citado por completude; a leitura é a mesma |

Resumo: **todas** usam dados públicos das exchanges (livro e negócios por WebSocket). O que é proprietário é
(a) o histórico guardado por anos e (b) o modelo de liquidação. Nenhuma delas tem acesso a ordens que o público não vê.

### 1.2 O que dá para reproduzir com dado público gratuito

| Dado | Fonte gratuita | Alcance real | Status aqui |
|---|---|---|---|
| Livro **Coinbase** spot (BTC-USD) | REST level 2 (livro inteiro, ~20 mil níveis por lado); WebSocket `level2` público; existe até level 3 (ordem a ordem, com ID) | Inteiro: parede a 1–5% do mid é visível | **Gravado desde hoje**, a cada 30 s, faixas de 0,1% até ±5% |
| Livro **Binance** spot | REST `depth` limite 5000 (≈1% por lado a 81k); WebSocket `depth@100ms` de diferenças, que mantém um livro local **completo** se partir de um snapshot | REST: ~1%. WS diff: inteiro | Gravado por REST (só 9 faixas cheias). O WS de diferenças não é usado |
| Livro **Binance** perpétuo USDT-M | REST `depth` limite 1000; WS diff completo | Igual ao spot | **Não coletado**. É onde mora a alavancagem |
| Livro **Bybit** linear | REST v5 limite 500; WS `orderbook.500` | ~0,06–0,1% por lado (só a faixa 0) | Gravado; serve só para topo do livro |
| **Liquidações Bybit** | WS v5 `allLiquidation.BTCUSDT` (todas as liquidações, linear) e `allLiquidation.BTCUSD` (inverse) | Completo, com ms | **Não coletado** |
| **Liquidações Binance** futuros | WS `btcusdt@forceOrder` | **Amostrado: no máximo 1 ordem por segundo por símbolo**; em cascata subconta | **Não coletado**; piso, não total |
| Liquidações históricas Binance | Arquivos diários públicos de `data.binance.vision` (pasta `liquidationSnapshot` dos futuros USDT-M) e `metrics` (OI e long/short de 5 em 5 min) | Anos, mas com a mesma amostragem | **Não baixado**; verificar cobertura antes de contar com isso |
| Negócios **Coinbase** spot (para CVD spot) | WS `market_trades`/`matches` público (preço, qtd, lado agressor); REST `trades` só pagina para trás devagar | Ao vivo: completo. Retroativo: lento, sem garantia | **Não coletado** |
| Negócios Binance (spot e perp) | WS `aggTrade`; histórico diário completo em `data.binance.vision` desde 2017 (spot) / 2019 (perp) | Completo, retroativo | Não baixado; dá CVD spot × perp da Binance **para trás** |
| Negócios Bybit perp | WS `publicTrade.BTCUSDT` | Completo ao vivo | 30 dias gravados (ago–set/2026, `dados/trades_bybit`), coletor desligado |
| OI, long/short, funding | Bybit REST (OI de 5 min só os últimos ~200 pontos; LSR e funding históricos); Binance `openInterestHist` 5 min (30 dias) | Hora em hora desde 2020 aqui | Falta OI de 5 min contínuo |
| Mapa de liquidação (estimado) | Ninguém dá de graça | — | Dá para **aproximar** com OI de 5 min + escada de alavancagens (10/25/50/100×) a partir de cada candle; é hipótese sobre hipótese |

**O que não dá:** histórico do livro antes de hoje (Tardis/Kaiko vendem; o Tardis libera o primeiro dia de cada mês de
graça, insuficiente para medir); o modelo de liquidação da Coinglass/Hyblock; e "ver a parede sumir" com snapshot de
30 s — spoof é puxado em menos de 1 s, então o teste de spoof pede cadência de 1–5 s na zona próxima do preço.

---

## 2. As três estratégias de fluxo de maior potencial

Formato do agente: contexto, leitura com números, gatilho, entrada, stop, alvo, R:R, frequência, quem perde, o que mata,
dados e histórico, como medir. Separado em **[H] hipótese** e **[M] medido**. Os números de corte são **ponto de partida**;
todos devem ser fixados por escrito *antes* da medição, e só podem mudar com nova medição em período novo.

Parâmetros comuns (a 81k, 0,1% = 81 USD):

- **Parede**: faixa de 0,1% no livro da Coinbase com quantidade ≥ 3× a mediana das últimas 24 h da faixa à mesma distância
  (é o que `paredes()` já marca) **e** ≥ 30 BTC (~2,4 M USD; piso absoluto para a mediana baixa de madrugada não virar
  parede). "Pesada" = ≥ 5× e ≥ 60 BTC. Confirmada quando a Binance (spot e, quando coletado, perp) também tem a faixa
  ≥ 2× a mediana, se a parede estiver dentro do 1% que a Binance alcança.
- **Persistente**: a mesma parede (em **preço**, tolerância ±0,1%, não em índice de faixa, porque o índice anda com o mid)
  presente em ≥ 10 snapshots consecutivos (5 min) e com quantidade atual ≥ 70% do máximo dos últimos 5 min.
- **Teste de spoof** (só com cadência rápida, item 3.2): nos 60 s em que o preço chega a 0,3% da parede, a quantidade
  cai mais de 50% sem negócio executado contra ela → **spoof**, aviso cancelado. Parede que "anda" na frente do preço
  (sobe quando o preço sobe, mantendo a distância) → layering, não conta.
- **VWAP da sessão**: ancorada em 00:00 UTC, por 1 min, com desvio-padrão do preço em torno dela (z).
- **CVD perp**: soma (compra a mercado − venda a mercado) dos negócios da Bybit linear; z calculado contra as janelas
  de 15 min das últimas 24 h. **CVD spot**: idem com os negócios da Coinbase.
- **Custo** por operação: 0,13% ida e volta (taker + escorregada). Risco por aviso para capital pequeno: 0,5% do capital.

### 2.1 Estratégia A — "Esticado contra nuvem" (a do usuário)

**Nome:** topo preso contra nuvem vendedora (short responsivo). Simétrico para fundo preso contra nuvem compradora.

**Contexto:** qualquer regime, **exceto** tendência patrocinada (CVD spot da Coinbase subindo junto com o preço nos
últimos 60 min, z ≥ +1). Melhor na sessão América (13:30–20:00 UTC) ou na Europa depois de uma Ásia que construiu
para cima. Vale mais quando a parede está num nível que o TPO já conhece (VAH do composto, pivô virgem, abertura
semanal), mas o nível não é exigido — pelo estudo 2 de 20/10 o nível sozinho não bate o sorteio; a parede é a hipótese.

**Leitura do "esticado"** (precisa de 3 das 5, a primeira obrigatória):

1. z da VWAP da sessão ≥ +2,0 (preço a dois desvios acima do valor do dia). [H]
2. OI da Bybit (e Binance, quando houver) subiu ≥ +1,5% nas últimas 6 h com o preço subindo — alavancagem nova
   entrando no topo, não short squeeze (OI caindo na alta é saudável e **veta**). [H]
3. Funding previsto ≥ +0,01%/8 h **ou** acima do percentil 80 dos últimos 30 dias. [H]
4. Long/short de contas (Bybit) acima da mediana de 30 dias + 1 desvio: sardinha comprada. [H; como filtro de borda
   em 15 min não separou do sorteio — por isso é 1 de 5 e não condição única]
5. Agressão: CVD perp dos últimos 15 min com z ≥ +2 **e** delta spot da Coinbase no mesmo período menor que 1/5 do
   delta perp (a desproporção 1:5 a 1:10 que o Tradeiros usa como alerta de pullback). [H]

**Leitura da "nuvem":** parede vendedora **pesada e persistente** na Coinbase entre 0,2% e 1,5% acima do preço,
confirmada pela Binance quando dentro do 1%; sem spoof no teste de aproximação. Se houver mais de uma, a mais
próxima.

**Gatilho:** preço chega a ≤ 0,3% da parede com o esticado ativo e a parede intacta (≥ 70% do máximo). Duas formas:

- *Responsiva (mão humana):* limitada a 0,05% abaixo da parede.
- *Confirmada (a que será medida):* primeiro candle de 1 min que toca a zona e **fecha abaixo da sua própria
  abertura** com CVD perp dos últimos 3 min caindo (a agressão compradora secou na parede — "absorveu").

**Zona de entrada:** entre parede −0,3% e parede −0,05%. Uma fatia só (capital pequeno; escada não cabe).

**Stop:** parede +0,25% (acima da faixa inteira + margem de pavio). Risco típico 0,35–0,55%.

**Alvo 1:** VWAP da sessão (z → 0). Com z ≥ 2 e σ intradiário de 0,4–0,7%, isso dá 0,8–1,5%. Sai metade, stop para a
entrada ("tira o risco" em 1R). **Alvo 2:** POC do dia ou o maior aglomerado de liquidações de long abaixo (quando o
mapa existir) — "onde os alavancados morrem é o alvo".

**R:R nominal:** 1,5 a 2,5 : 1 no alvo 1. **Frequência estimada:** 1–3 por semana (z ≥ 2 acontece em ~10% das horas;
com parede pesada persistente e sem spoof, bem menos). [H]

**De onde vem a vantagem (quem perde):** quem comprou a mercado, alavancado, no topo, contra uma oferta passiva maior
que a agressão. Quando o preço para, essa turma só tem uma saída: vender. Stop e liquidação viram agressão vendedora
e o movimento de volta é "patrocinado" por quem está preso. O passivo da Coinbase (spot) é quem sustenta o teto.

**O que mata:**

- **Spoof**: a parede some no toque. Com snapshot de 30 s não dá para distinguir; precisa da cadência rápida (3.2).
- **Parede de hedge**, não de venda direcional: institucional vendendo spot contra long de perp (ou o contrário) não
  defende nível; some quando o hedge é desfeito. Sinal: a parede aparece e some junto com variações grandes de OI.
- **Parede comida**: CVD spot da Coinbase subindo forte no toque = compra real a limite atrás da agressão; a parede é
  consumida e o preço acelera (short squeeze). Veto: z do CVD spot 30 min ≥ +2 na chegada.
- **Notícia**: ±30 min de dado macro (CPI, FOMC, payroll) e manchete de ETF/hack: veto por lista.
- **Madrugada/fim de semana**: mediana baixa infla razões; por isso o piso absoluto em BTC.
- **O que a torna o "motor otimista" de novo**: usar o livro *depois* de saber que o preço caiu. O mesmo código que
  avisa ao vivo é o que roda no histórico; a parede só vale no snapshot anterior ao gatilho.

**Dados e histórico necessários:** livro Coinbase (tem), Binance spot (1%) e **perp** (falta), negócios Bybit perp
(religar) e **Coinbase** (falta), OI de 5 min (falta), funding e LSR (tem), 1 min (tem). Eventos: 1–3/semana →
**30 dias: 4–12 eventos (nada se conclui); 90 dias: 12–40 (sinal forte ou nada); 6 meses: 25–80 (primeira leitura
que merece %)**. Para separar 60% de 50% com confiança razoável precisa de ~150 eventos; isso é mais de um ano.
Sendo honesto: a primeira medição "confiável" desta estratégia é em **abril/2027**, se a coleta não cair.

**Como medir:** (1) critério escrito antes: taxa de alvo 1 antes do stop e bruto líquido de custo, com ≥ 40 eventos;
(2) três controles sorteados com a **mesma regra**: (a) mesmo esticado, parede "sorteada" numa distância aleatória
entre 0,2% e 1,5% (a parede acrescenta algo ao esticado?); (b) mesma parede, em hora sorteada sem esticado (o esticado
acrescenta algo à parede?); (c) direção sorteada; (3) três períodos (meses) e só aprova se ganhar do controle nos três.
Aprovação: alvo 1 ≥ controle + 10 pontos e bruto líquido > 0 nos três períodos.

### 2.2 Estratégia B — "Calço na borda"

**Nome:** nuvem compradora sob o VAL do composto (a borda que segura). Simétrico: nuvem vendedora sobre a VAH.

**Contexto:** **LATERAL/RANGE** com composto de 10–12 dias válido (é onde o Tradeiros opera de forma mais completa,
seção 3.3 do perfil). Preço vindo de cima para o VAL. Serve também para naked POC e POC do dia, mas a medição começa
pelo VAL do composto. Nunca "no meio": sem borda não há aviso.

**Leitura:** parede compradora na Coinbase **entre 0,0% e 0,5% abaixo do VAL** (calço = sob o suporte, não em cima:
"ordens de compra passivas sob o suporte"), ≥ 3× mediana e ≥ 30 BTC, **persistente há ≥ 20 snapshots (10 min) antes de
o preço chegar a 0,5% do VAL** (parede que aparece só quando o preço chega é suspeita), e intacta no toque. Reforços
(não obrigatórios, contados para calibrar): CVD spot da Coinbase plano ou subindo enquanto o preço cai (spot não
vende = "sustento"); CVD perp caindo (vendedores a mercado chegando = quem vai ficar preso); LSR abaixo da mediana de
30 dias (shorts acumulando). [H para a parede; M parcial para presos: VAL segura 74% com presos × 64% sem, só 40
trades, e em 15 min não separou do sorteio]

**Gatilho:** preço dentro da zona (VAL até a parede) e **absorção** no 1 min: volume ≥ 2× a média de 20 candles com
fechamento no terço superior do candle. Sem absorção, não entra — "nem todo calço segurou".

**Zona de entrada:** VAL −0,1% até o preço da parede. Uma fatia; se couberem duas, metade no VAL e metade na parede.

**Stop:** parede −0,25%. Risco típico 0,5–0,8%. Regra do Tradeiros embutida: se o preço fecha dois candles de 5 min
abaixo da parede (aceitação abaixo), sai antes do stop — "quem entrou na borda deve stopar logo".

**Alvo 1:** POC do composto (tirar o risco em 1R no caminho). **Alvo 2:** VAH. Com composto de 3–6% de largura, VAL→POC
dá 1,5–2,5%.

**R:R nominal:** 2 a 4 : 1. **Frequência:** toques no VAL em range ~2/semana; com calço persistente talvez 1/semana ou
menos. [H]

**De onde vem a vantagem (quem perde):** quem vende o rompimento do fundo sem aceitação e reteste ("short no USDT
antes do nível", "stop de bobeira") — justamente o que o Tradeiros evita fazer. O passivo da Coinbase compra deles;
quando o preço volta para dentro do valor, esses shorts são o combustível até o POC.

**O que mata:** calço puxado no toque (spoof); rompimento verdadeiro com volume construído além do nível (quebra de
estrutura: a maioria dos rompimentos é falsa, mas o que vale leva o stop inteiro); notícia; composto mal desenhado
(VAL errado = parede no lugar errado); parede que é hedge e some com a volatilidade; range que vira tendência (o
evento de 10/10/2025: compra na "última entrada do player" e pavio de −12,7% no mesmo dia).

**Dados e histórico:** livro Coinbase (tem), composto (o portal Tradeiros já calcula), negócios Coinbase e Bybit
(faltam), 1 min (tem). **É a mais lenta de medir**: 90 dias → 5–15 eventos; precisa de **6–9 meses** só para a primeira
leitura. Por isso o caminho é medir primeiro a pergunta genérica, que tem centenas de eventos em 30 dias:
**"uma parede ≥ 3× persistente segura o primeiro toque? por quanto tempo? quanto o preço vai contra antes de ceder?"**
em qualquer nível, em qualquer hora. Se a parede genérica não segurar mais que o sorteio, B e A caem juntas e não
se gasta um semestre.

**Como medir:** critério antes (alvo 1 antes do stop; bruto líquido); controles: (a) mesmo VAL sem parede (é o que já
se mediu: ~64%); (b) parede igual num preço sorteado fora de borda; (c) direção sorteada; três períodos.

### 2.3 Estratégia C — "Cascata de liquidações + absorção" (minha escolha livre)

**Nome:** fim da cascata de long (long de reversão do pavio). Simétrico: cascata de short no topo → short.

Escolhi esta, e não "CVD spot divergente no VAL" nem "leilão fracassado", por três motivos: tem mais eventos (mede mais
rápido), o dado que exige (liquidações + negócios) é o mesmo que A precisa, e a vantagem tem um mecanismo claro:
**vendedor forçado não olha preço**. "Cascata = pavio; depois da cascata, reação."

**Contexto:** qualquer regime; melhor em range e em alta (cascata em queda de ciclo pode ser a primeira perna). Sessão
qualquer; a América e as 00:00/08:00/16:00 UTC (funding) concentram.

**Leitura:**

1. **Cascata**: liquidações de long (Bybit `allLiquidation`, linear + inverse; Binance como piso) somadas em 5 min
   ≥ percentil 97 das janelas de 5 min dos últimos 30 dias (ordem de grandeza hoje: dezenas de milhões de USD somando
   as exchanges; o corte é por percentil, não por valor fixo) **e** queda de preço ≥ 1,5% em 15 min. [H]
2. **Limpeza**: OI caiu ≥ 2% em 15 min (posições fechadas, não abertas). [H]
3. **Exaustão**: o minuto de pico de liquidações passou e os 2 minutos seguintes têm < 20% do pico cada. [H]
4. **Absorção**: candle de 1 min com volume ≥ 3× a média de 20, delta perp fortemente negativo (z ≤ −2) **mas**
   fechamento no terço superior do próprio range; e, do lado do sustento, CVD spot da Coinbase **não** caindo no mesmo
   minuto (o spot não vendeu: é pavio, não distribuição) **ou** parede compradora surgindo na Coinbase a ≤ 0,5% abaixo
   (≥ 2× mediana). [H]

**Gatilho:** depois da exaustão (3) e da absorção (4), o primeiro 1 min que **fecha acima da máxima do minuto
anterior** (reclaim). Sem reclaim em 10 min, o aviso expira.

**Zona de entrada:** do fechamento do reclaim até 0,3% acima da mínima do pavio. A mercado ou limitada no fechamento.

**Stop:** mínima do pavio −0,2%. Risco típico 0,4–0,7%.

**Alvo 1:** metade do pavio (ponto médio entre o início da cascata e a mínima); com pavio de 1,5–3%, dá 0,75–1,5%.
Tira o risco em 1R. **Alvo 2:** VWAP da sessão ou o preço de onde a cascata começou. "Pico já captado perde o valor de
alvo": se o preço já recuperou metade antes do gatilho, não entra.

**R:R nominal:** 1,5 a 2,5 : 1. **Frequência:** cascatas ≥ p97 com queda ≥ 1,5%: 1–3 por semana em 2025–26. [H]

**De onde vem a vantagem (quem perde):** o long liquidado já perdeu; vendeu a qualquer preço. Quando o último sai, não
sobra vendedor, e quem absorveu (passivo, market maker, spot) marca para cima. O segundo perdedor é o short que
correu atrás da cascata e virou combustível do squeeze.

**O que mata:** cascata que é o início de uma perna (notícia: hack, saída de ETF, macro) — a segunda perna leva o stop
inteiro; entrar na primeira reação antes da exaustão (pegar faca); exchange degradada durante a cascata (dado
atrasado, WebSocket cai justamente na hora: gravar `latencia_ms` e marcar buracos); Binance subcontando (1 ordem/s);
fim de semana com pouca liquidez (pavio maior, reação menor). **E o maior:** a versão só com candle (queda + reclaim)
é o "scalp de volatilidade" que já perdeu em 13/09; a hipótese é que a **informação fora do candle** (liquidação,
OI, spot) separa pavio de perna. Se não separar, C morre como as outras.

**Dados e histórico:** liquidações (falta; Bybit ao vivo desde o dia em que ligar; Binance histórico público para
trás, se a pasta `liquidationSnapshot` tiver a cobertura), negócios Bybit perp (religar) e Coinbase (falta), OI de
5 min (falta ao vivo; `metrics` da Binance para trás), 1 min (tem), livro (tem). **É a mais rápida de medir**: a parte
de preço + liquidação + OI pode ser **retrotestada agora** com o histórico público da Binance (meses ou anos, com a
amostragem como ressalva), e ao vivo 90 dias dão 12–40 eventos. Primeira leitura: **~45 dias** se o histórico da
Binance servir; **~90 dias** só com a coleta nova; confiável em 6 meses.

**Como medir:** critério antes; controles: (a) mesma queda ≥ 1,5%/15 min e mesmo reclaim **sem** pico de liquidação (a
liquidação acrescenta algo?); (b) mesma regra sem a condição de absorção/spot; (c) direção sorteada; três períodos;
reprovar se o bruto líquido não ganhar do controle nos três.

---

## 3. O que o coletor grava hoje e o que falta coletar desde já

### 3.1 O que já está gravado (`conselho/coletor_livro.py`, ligado em 20/10/2026 09:16)

- Por exchange (Coinbase BTC-USD spot, Binance BTCUSDT spot, Bybit BTCUSDT linear), a cada 30 s, em
  `dados/livro/<exchange>/<dia>.jsonl.gz`: `ts` (segundos), `mid`, `melhor_bid`, `melhor_ask`, 50 faixas de 0,1% por
  lado em BTC (`bids`, `asks`), `total_bids/asks`, `fora_bids/asks` (além de ±5%), `niveis_bids/asks`, `latencia_ms`.
- Alcance real medido: Coinbase cheia (50 faixas; ~20,7 mil níveis por lado; ~680 BTC de bid e ~450 de ask dentro de 5%
  às 10:28); Binance 9 faixas (~1%); Bybit 1 faixa (~0,1%).
- Leitura: `livro_historico.paredes()` marca faixa ≥ 3× a mediana de 24 h da mesma faixa, mínimo 10 snapshots. A
  comparação é por **índice de faixa** (distância relativa ao mid), não por preço.

### 3.2 O que falta, em ordem de urgência (cada dia sem coleta é um dia a menos de histórico)

1. **Liquidações Bybit** por WebSocket v5 `allLiquidation.BTCUSDT` e `allLiquidation.BTCUSD`: gravar `ts` em ms, lado,
   preço, quantidade, exchange, símbolo. Serve A (alvo), C (gatilho) e o mapa de liquidação futuro.
2. **Liquidações Binance** futuros `btcusdt@forceOrder`: gravar igual, com a marca "amostrado (≤ 1/s)". Usar como piso.
3. **Negócios da Coinbase** (WS `market_trades`): gravar agregado por 1 min — volume comprador, volume vendedor, número
   de negócios, VWAP do minuto, maior negócio — e não negócio a negócio (100–300 mil por dia; o agregado basta para
   CVD spot). Serve A (veto de tendência patrocinada, desproporção spot × perp), B (sustento) e C (pavio × distribuição).
4. **Negócios da Bybit linear** (WS `publicTrade.BTCUSDT`): religar o coletor que gravou ago–set e mantê-lo ligado;
   agregar por 1 min do mesmo jeito, guardando também o delta por faixa de preço de 0,1% (para "delta por nível").
5. **OI a cada 5 min** (Bybit `open-interest` 5min; Binance `openInterestHist` 5m) e **funding previsto** com a hora do
   próximo funding, a cada 5 min. A série de hora em hora não enxerga 6 h com resolução suficiente para o esticado.
6. **Livro do perpétuo da Binance** (USDT-M), a mesma agregação em faixas: a alavancagem mora ali, e a parede que
   segura o comprado alavancado pode estar no perp, não no spot. REST limite 1000 (~0,2%) ou WS de diferenças
   (inteiro).
7. **Profundidade maior na Binance spot**: manter livro local pelo WS `depth@100ms` a partir do snapshot REST, para as
   50 faixas ficarem cheias como na Coinbase. Sem isso, "confirmação pela Binance" só existe dentro de 1%.
8. **Cadência rápida perto do preço**: na Coinbase (WS `level2`), gravar as faixas de ±1% a cada 1–5 s **além** do snapshot
   de 30 s. É o único jeito de fazer o teste de spoof (parede puxada em < 1 s no toque). Volume de dados: ~20 faixas ×
   17 mil snapshots/dia, aceitável comprimido.
9. **Rastreador de paredes em preço**: um registro por parede (preço, exchange, primeiro visto, último visto, máximo
   em BTC, quantidade no toque, se foi consumida ou puxada, quanto negociou contra ela). É isso que vira "persistente"
   e "spoof" nas estratégias; `paredes()` por índice de faixa não basta porque a parede muda de faixa quando o mid anda.
10. **Download retroativo da Binance** (`data.binance.vision`): `aggTrades` spot e perp (CVD para trás),
    `liquidationSnapshot` e `metrics` (OI/LSR de 5 min). Verificar primeiro quais pastas existem e desde quando; é o
    único histórico gratuito que permite retrotestar C antes de 90 dias.
11. **Calendário de eventos** (CPI, FOMC, payroll, vencimentos da Deribit) como lista manual, para o veto de ±30 min.
12. **Qualidade da coleta**: marcar buracos (snapshot faltando, latência > 5 s, WS reconectado) num log por dia; a
    medição exclui janelas com buraco, e ao vivo o aviso não sai sem dado dos últimos 2 min.

Sem os itens 1, 3 e 4, as três estratégias só têm a metade "livro"; sem o 8 e o 9, a palavra "spoof" não tem dado.

---

## 4. Ranking, escolha e risco

| # | Estratégia | Potencial (0–10) | Por quê | Eventos em 90 dias | Primeira medição confiável |
|---|---|---|---|---|---|
| 1 | **A — Esticado contra nuvem** | **6** | Mecanismo mais claro de quem perde (alavancado preso contra passivo); é a leitura que o Tradeiros usa; mas o dado mais frágil (spoof, hedge, parede do spot e não do perp) e poucos eventos | 12–40 | 6 meses (abril/2027) |
| 2 | **C — Cascata + absorção** | **5** | Vendedor forçado é vantagem conhecida e disputada; mede mais rápido e tem histórico público para retroteste; a versão só-candle já reprovou, então o ganho depende inteiramente do dado novo | 12–40 (+ retroteste) | 45–90 dias |
| 3 | **B — Calço na borda** | **4** | Construída sobre uma borda que sozinha não bateu o sorteio em 15 min; a única medição parcial a favor (presos no VAL, 74% × 64%) tem só 40 trades; eventos raros | 5–15 | 6–9 meses |

As notas são de **potencial não medido**: dizem onde eu apostaria o tempo de coleta, não onde apostaria dinheiro.
Nenhuma passou de 6 porque tudo que foi medido neste projeto até hoje em candle ficou em odds justas, e o livro ainda
não provou que é diferente.

**Escolha para começar:** ligar **toda** a coleta da seção 3.2 nesta semana (itens 1–5 e 9 primeiro; 6–8 depois), porque
as três partilham os mesmos dados, e medir **nesta ordem**:

1. Em ~45 dias (início de dezembro/2026): a pergunta genérica da parede — "parede ≥ 3× persistente segura o primeiro
   toque mais que o sorteio?" — com centenas de toques. É o alicerce de A e B; se cair, as duas caem sem gastar o
   semestre.
2. Ao mesmo tempo, o retroteste de C no histórico público da Binance (se a cobertura existir), com os controles.
3. Em ~90 dias (janeiro/2027): A com 12–40 eventos — sinal forte ou nada. Só com ≥ 40 eventos e três períodos o
   conselho mostra %; antes disso o aviso de A sai **sem %**, com lado, entrada, stop e alvo, marcado "não medido",
   para o humano acompanhar e para o acerto real ser contado.
4. B só depois de A e da parede genérica, com 6–9 meses.

**Risco principal:** o spoof e a parede de hedge. A parede que o heatmap mostra é a que mais chama a atenção justamente
porque é grande, e as grandes são as mais puxadas. Se o teste genérico mostrar que a parede de 3× **não** segura mais que
o sorteio, o conceito inteiro das "nuvens" cai para este projeto, por mais bonito que fique na tela da Coinglass. O
segundo risco é operacional: a coleta cair (servidor, WebSocket, disco) e o histórico ficar com buracos que invalidam
a mediana de 24 h e a persistência.

**O que o aviso vai conter, quando existir:** lado, zona de entrada, stop, alvo 1 e 2, R:R, e a probabilidade **medida**
(taxa de alvo 1 antes do stop, nos três períodos) **ao lado do controle sorteado** — nunca um número sem o controle.
Até a medição: sem %.

---

## 5. Presos pelo footprint (live xc2nq9ti8Ns)

Acrescentado em 20/10/2026 a partir da live de 15/10/2026 (Shaka), trecho [110:31–112:55] e print do footprint de 30 min
do BTCUSD.P da Bybit. Detalhe da leitura deles e da regra candidata em `docs/tradeiros/presos_footprint.md`; ficha em
`docs/tradeiros/fichas/xc2nq9ti8Ns.md`. Tudo aqui é **[H] hipótese**; o único "medido" é negativo (motor de fluxo bruto
zero nos mesmos 30 dias, com outra regra).

O que eles chamam de preso, em uma linha: **quem agrediu a mercado num nível, o preço não andou (absorvido) e a vela fechou
do outro lado; a entrada é no reteste desse nível, contra quem ficou preso, porque ele sai no zero a zero.** Não é o
long/short de contas nem o funding (já medidos aqui, não separam do sorteio): é delta por nível dentro da vela.

### 5.1 Estratégia D — "Nódulo abandonado" (short no reteste em cima dos presos)

**Nome:** short responsivo no reteste do nível onde compradores a mercado ficaram presos. Simétrico: long no reteste do
nível onde vendedores a mercado ficaram presos.

**Contexto:** qualquer regime; melhor depois de uma perna (o nódulo no topo de um rebote ou no fundo de uma queda), nas
sessões Europa e América. Vale mais quando o nível coincide com VAL/VAH/POC de ontem ou do composto (±0,2%) — eles entram
ali com "poder de fogo"; fora de nível é "uma graninha". O nível de TPO não é exigido, é contado.

**Leitura exata do fluxo** (perp Bybit; barra de 5 min para medir primeiro, 30 min para confirmar; níveis de 20 USD):

1. **Nódulo comprador** na barra B: nível L com `vol_buy(L) ≥ 3x mediana` de `vol_buy` dos níveis negociados de B **e**
   `≥ p90` de `vol_buy` por nível das últimas 48 barras **e** L no terço superior do range de B **e** `delta(L) > 0`. Na
   live: linhas de 1,4–2,5 mi USD contra centenas de milhares nas vizinhas. [H]
2. **Absorvido** ("o preço respeitando"): B fecha abaixo de L (`fech(B) ≤ L − 0,05%`). [H]
3. **Abandonado** ("fecha embaixo, a próxima vela cai"): nas 2 barras seguintes o fechamento fica ≥ 0,3% (5 min) / ≥ 0,5%
   (30 min) abaixo de L, sem negociar acima da máxima de B. [H]
4. Reforços só contados (não exigidos; dados de 20/10 em diante): parede vendedora na Coinbase entre L e L + 0,5%, ≥ 3x a
   mediana e persistente ≥ 10 snapshots (calço do short); CVD spot da Coinbase com z ≤ 0 nos 15 min do reteste (spot não
   está comprando a volta); liquidações de short somadas nos 15 min do reteste abaixo do p50 (não é squeeze). [H]

**Gatilho:** primeira volta do preço a `L ± 0,05%`, pelo menos 2 barras depois do abandono e até 24 h, chegando por baixo.
Versão confirmada (a que será medida): o primeiro 1 min na zona que fecha abaixo da própria abertura com delta perp do
minuto ≤ 0 (a compra da volta secou em cima dos presos).

**Zona de entrada:** L − 0,1% até L + 0,05%. Uma fatia (capital pequeno).

**Stop:** máxima de B + 0,1%. Risco típico 0,3–0,6%.

**Alvo 1:** 1R (tira o risco; é o que eles fazem). **Alvo 2:** o fechamento mais baixo entre o abandono e o reteste; quando
houver mapa de liquidação, o aglomerado de longs abaixo. Expira em 2 h sem resolução.

**R:R nominal:** 1 : 1 no alvo 1, 1,5–2,5 : 1 no alvo 2. O alvo 1 só paga a conta se a taxa passar de ~57% líquido de custo.

**Frequência estimada:** 5 min: 8–15 eventos/dia nos dois lados antes dos filtros, 2–5/dia depois; 30 min: 1–3/dia. [H]

**De onde vem a vantagem (quem está preso):** quem comprou a mercado no alto da vela, contra limitadas que não deixaram o
preço andar, e viu a vela fechar embaixo. No reteste ele vende para sair no zero a zero ("o cara que comprou vai querer
realizar a cada resistência" [58:06]); quem vendeu a limite na vela B defende o mesmo preço. Dois vendedores no mesmo nível
contra uma volta sem patrocínio.

**O que mata:** (1) o reteste vem com **compra nova** (CVD spot subindo, OI subindo, parede compradora aparecendo embaixo):
então não é volta, é continuação e o stop vai inteiro — por isso o reforço 4 e o gatilho confirmado; (2) nódulo que é
**hedge** (institucional comprando perp contra venda de spot): não defende nível e não "sai no zero a zero"; (3) notícia
(veto ±30 min de macro); (4) madrugada e fim de semana (mediana baixa infla o 3x: manter piso absoluto em USD por nível,
ponto de partida 500 mil); (5) a armadilha do motor otimista: o nódulo só vale com a barra B fechada e o abandono
confirmado **antes** do reteste; nunca olhar o que o preço fez depois para escolher L; (6) o mesmo risco das outras três:
a parte "só candle" (máxima retestada) já é odds justas aqui; se o nódulo não acrescentar nada ao controle (a), D morre.

**Dados necessários e histórico:** negócios da Bybit com lado do agressor (30 dias existem; o fetcher baixa qualquer dia
desde 2020), candles 1/5/30 min (tem). Para os reforços: livro (desde 20/10), negócios da Coinbase e liquidações (faltam).
**É a única das quatro que pode ser medida hoje**, com os 30 dias de ago–set/2026, e estendida a outros regimes baixando
mais dias (um mês de alta, um de range, um de queda).

**Como medir:** critério escrito antes (taxa de alvo 1 antes do stop, bruto líquido, excursão a favor/contra em 2 h,
≥ 40 eventos por TF e por lado); controles sorteados com a mesma mecânica: (a) reteste de nível sorteado da mesma barra
sem nódulo, (b) nódulo igual não abandonado (barra fechou acima de L), (c) direção sorteada; três períodos (10–19/08,
20–29/08, 30/08–08/09) e depois três meses de regimes diferentes; aprova só se alvo 1 ≥ controle (a) + 10 pontos e bruto
líquido > 0 nos três períodos e nos dois lados.

### 5.2 Nota de potencial

| # | Estratégia | Potencial (0–10) | Por quê | Primeira medição |
|---|---|---|---|---|
| D | **Nódulo abandonado (presos pelo footprint)** | **5** | Mecanismo claro (dois vendedores no mesmo nível), informação de dentro do candle que nunca foi medida aqui com esta regra, e **dado já disponível** (30 dias + fetcher); contra: o motor de fluxo com absorção ao vivo deu zero nos mesmos dias, e a versão sem livro/spot/liquidação não enxerga se a volta tem patrocínio | **Agora**, com os 30 dias; completa (reforços) em ~90 dias |

Fica atrás de A (6) porque A tem o mecanismo mais limpo de quem perde, e na frente de B (4) porque pode ser medida sem
esperar meio ano. Se D reprovar nos 30 dias, não gastar coleta com a versão completa; se passar, ela vira o gatilho das
estratégias A e B (o "presos" que o calço e o esticado precisam).

### 5.3 O que falta coletar ou reduzir

- **Negócios da Bybit**: o bruto é ~45–60 MB/dia comprimido (1,8 GB nos 30 dias). Ao baixar com `core/bybit_trades_fetcher.py`,
  **reduzir na hora** a delta por nível (20 USD) e barra (1 min), com `vol_buy`, `vol_sell`, `n_buy`, `n_sell`, e descartar
  o bruto: ~100–300 KB/dia. Religar a coleta ao vivo já no formato reduzido; incluir o inverse (BTCUSD) se a pasta pública
  existir, porque é o contrato do print.
- **Negócios da Coinbase** (WS `market_trades`) agregados por 1 min: o reforço de "volta sem patrocínio" e o veto de
  tendência patrocinada.
- **Liquidações da Bybit** (`allLiquidation`): o "comprou no topo e foi stopado embaixo" e o gatilho fino de 3 min que ele
  descreve ("forte liquidação com o preço não respondendo").
- **Livro** (já ligado): rastreador de paredes em preço para o calço do short no reteste (item 9 da seção 3.2).
- **Perfil do dia e composto** (VAH/VAL/POC) já calculados pelo portal: gravar junto com cada evento para contar o reforço
  "nível de TPO".
