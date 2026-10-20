# Presos pelo footprint — como o Tradeiros identifica quem ficou preso

Fonte: live xc2nq9ti8Ns (Shaka, 15/10/2026, "BITCOIN E ALTCOINS CORRIGINDO FORTE"), trecho de order flow em [110:31–112:55],
estrutura em [101:32–105:38]; print da tela enviado pelo usuário (TradingView, BTCUSD.P Bybit 30 min, indicador
"Volume footprint [Manual 150, Compra e venda]", qui 15/10/26 12:30). Ficha: `docs/tradeiros/fichas/xc2nq9ti8Ns.md`.
Marcação: **[R]** = regra dita de forma explícita; **[J]** = julgamento (ele faz, não enuncia); **[O]** = de outra live, citada
para completar. Minutagem [mm:ss] da transcrição automática.

Resumo em uma frase: preso é quem **agrediu a mercado num nível, o preço não andou (absorvido) e a vela fechou do outro lado**;
a entrada é **no reteste desse nível, contra quem está preso**, porque ele vai sair no zero a zero.

---

## 1. O que eles olham no footprint

### 1.1 O gráfico do print
- **Ativo e tempo:** BTCUSD.P da Bybit (perpétuo inverse, o que eles operam), **30 min**. A barra inferior mostra "Delta / Total"
  da vela. VAH, VAL e POC do perfil do dia estão desenhados ao lado das velas (VAH ~82.37k, VAL ~82.17k no print).
- **Dentro de cada vela:** uma linha por faixa de preço; à direita, em azul, o volume **comprador a mercado** naquela linha; à
  esquerda, em vermelho, o volume **vendedor a mercado**. Os números são em USD de contrato (136,69K, 494,6K, 463,17K, 457,37K
  no topo da vela das 12:30; 1,08M e 1,21M vermelhos na vela anterior perto do VAH; 2,52M e 1,36M azuis mais abaixo).
- Não há diagonal 3:1 marcada, nem iceberg: o que ele lê é **tamanho absoluto por linha, de cada lado, e onde a vela fechou**.

### 1.2 Os itens, um a um

| # | O que olha | Paráfrase dele | Min. | Tipo |
|---|---|---|---|---|
| a | **Volume agressor comprador por nível** (tamanho absoluto) | "Os caras tão comprando aqui: 2,33 milhões, 1,44 milhões, 2,52 milhões" — e, no topo da vela atual, "entrou menos: 454 mil, 463 mil. Eu queria mais aqui" | [111:38–112:00] | [R] olha o número; [J] quanto é "muito" |
| b | **Preço "respeitando"** = absorção: agressão grande sem deslocamento | "Os caras tão comprando aqui, só que aí o preço tá respeitando" | [111:47–111:50] | [J] |
| c | **Volume e delta da vela** (estatísticas) | "Vela de 85 milhões de alta; 31 milhões com delta de 1,12; 17 milhões com 2,5 de delta negativo" — "você vê uma forte liquidação para um lado" | [111:00–111:16] | [R] lê; sem corte numérico |
| d | **Fechamento abandona o nível** (o que transforma comprador em preso) | "O preço se afasta, fecha aqui embaixo e deixa aqueles caras ali presos, ou no meio do caminho" | [112:01–112:06] | [R] |
| e | **Onde o nódulo fica dentro da vela** | "De preferência se esse negócio fosse aqui, aqui para baixo" (quer o nódulo comprador no alto da vela, acima de onde fechou) | [112:30–112:36] | [J] |
| f | **Continuação na vela seguinte** | "E aí o preço vai caindo na próxima vela" | [112:36–112:40] | [R] |
| g | **Gatilho fino no 3 min**: liquidação forte ou entrada muito grande e o preço não responde | "No 3 minutos eu vejo uma forte liquidação ou uma entrada muito grande e o preço não respondendo, eu entro ali" | [112:45–112:51] | [R] |
| h | **Tempo gráfico** | "Acompanha as estatísticas no 3 minutos e no 30 minutos"; o TPO e a vela que "precisa fechar vermelha" são de 30 min | [110:52–110:57], [89:28–90:32], [108:28–108:35] | [R] |
| i | **Desequilíbrio diagonal (3:1) e imbalances absorvidos** | Não aparece nesta live. Em 1HGpjDC4dIA: "entre 76.440 e 75.880, 13 imbalances vendedores contra 2 compradores, com compras a limite absorvendo = shorts presos no fundo" | — | [O] |
| j | **Delta por nível no composto** | Não aparece nesta live. Em tOeA: blocos de delta negativo de 7–19 mi abaixo = vendedores presos; blocos azuis de 6–10 mi no topo = compradores presos | — | [O] |
| k | **POC / VAH / VAL** | Usados como **nível de reteste e de plano** (VAL de ontem 82.702 para short; POC 80.814 para compra; "nódulo de volume" segurando o rebote), não como identificação de presos | [83:11–83:16], [91:45–91:54], [84:11–84:18] | [R] |

Observação: o "delta por nível" que ele lê na vela é o mesmo dado do item j, só que por vela (30 min) em vez de acumulado
no composto. A ferramenta é uma só: negócios com lado do agressor, somados por faixa de preço.

---

## 2. A regra em palavras deles

### 2.1 Comprador preso [R + J]
1. Numa vela (30 min; ou 3 min para o gatilho fino) aparece **compra a mercado grande em um ou mais níveis** — ordem de
   grandeza no print: milhões de USD por linha, contra centenas de milhares nas linhas vizinhas [111:38–111:47].
2. O **preço não anda** apesar dessa compra ("tá respeitando") — alguém está vendendo a limite contra ela [111:47–111:50].
3. A vela **fecha abaixo** desses níveis; melhor ainda se os níveis estiverem no alto da vela [112:01–112:06, 112:30–112:36].
4. A **vela seguinte cai** [112:36–112:40].
5. Resultado: "deixa um monte de gente comprado" ali em cima, presa [112:27–112:29].

Ele junta isso ao que já sabe pela estrutura: "você vê uma galera comprando ali no topo e depois eles serem stopados aqui
embaixo. Obviamente que eu vou querer" [111:26–111:33]. Ou seja, o preso é quem comprou no topo da perna e vai virar
vendedor (stop ou saída no zero a zero).

### 2.2 Vendedor preso [O + J]
Simétrico; nesta live só pela estrutura: "quem shortou aqui teve que estopar e quem comprou tem a chance de realizar lucro,
recomprar e ir buscar essa galera" [105:21–105:38]. Pelo footprint, a versão explícita é a de 1HGpjDC4dIA: imbalances
vendedores (agressão a mercado no fundo) **absorvidos por ordens a limite**, preço não renova mínima, squeeze.

### 2.3 Presos pela estrutura (sem footprint) [J]
- "A galera shortou, tá no domínio: renovou a mínima três vezes e segurou os topos. Quem comprou aqui teve que stopar"
  [101:32–101:40, 103:22–103:37].
- "Se ele quebra essa estrutura, quem shortou tem que stopar e quem comprou tá no conforto, realizou lucro e vai aumentar
  a mão para continuar stopando o lado contrário" [103:40–103:56].
- O MSB (quebra do topo descendente 81.648) é o momento em que o lado preso troca.

---

## 3. Como usam isso para entrar

| Peça | O que ele diz | Min. | Tipo |
|---|---|---|---|
| Entrada | "Quando ele voltar aqui, eu shorto ali em cima dessa galera" — short **no reteste do nível dos presos**, não na vela em que ficaram presos | [112:40–112:42] | [R] |
| Entrada alternativa | No 3 min, absorção ao vivo ("entrada muito grande e o preço não respondendo"): "eu entro ali", contra a agressão | [112:45–112:51] | [R] |
| Por que funciona | "É normal o preço vir aqui e ser rejeitado, porque o cara que comprou aqui vai querer realizar lucro a cada resistência. Aí o preço recua e você já faz uma graninha" | [58:03–58:16] | [R] |
| Stop | Não dito para o short por footprint. Nos shorts do dia: 63 USD num contrato de 8.000 (~0,8% de preço), acima do topo descendente; para o long do reteste, abaixo do fundo do reteste | [40:02–40:07], [77:56–78:04] | [J] para o footprint |
| Alvo | Não é alvo fixo: "fecho por etapas"; o lucro do short serve para "pagar" o stop do long seguinte; realiza em suporte/resistência | [23:40–23:48], [57:35–58:01] | [R] |
| Tamanho | Trade curto, "uma graninha"; a mão grande é o long plantado | [58:16–58:21] | [J] |
| Licença | O footprint autoriza "fazer uma coisa que não está desenhada" no plano | [110:31–110:43] | [R] |

Sequência completa que ele descreve (e que a ficha 1HGpjDC4dIA repete): pavio ou nódulo com presos, depois quebra de
estrutura, depois reteste, depois entrada com stop curto e fracionada, depois tira o risco em 1R.

---

## 4. Como combinam com o livro (calço) e com o TPO

- **TPO dá o lugar, o footprint dá a licença.** Nesta live os níveis de plano são todos de TPO/Fibo: VAL de ontem 82.702
  e POC de ontem para short, POC 80.814 e 0,5–0,618 do novo topo para compra, "nódulo de volume" segurando o rebote
  [83:11, 91:45, 84:11]. O footprint entra como exceção: "posso fazer algo que não está aqui desenhado, baseado em order
  flow" [110:31–110:43]. Em outras palavras: presos num nível de TPO = o melhor caso; presos fora de nível = trade menor.
- **Livro (calço) não foi aberto nesta live.** A regra geral deles (perfil_por_regime.md, item 10, de 1HGpjDC4dIA): zona
  com calço (limitadas visíveis na Coinbase) é zona **passiva**, pode comprar na borda; zona sem calço é **reativa**: só
  entra depois de pavio, presos e quebra de estrutura, comprando o reteste. Os presos do footprint são a parte "reativa"
  do critério; o calço diz se o nível vai segurar no toque; o TPO diz se o nível importa.
- **Hierarquia dita por eles** (1HGpjDC4dIA): gestão de risco, depois TPO e footprint, Elliott bem depois.
- **Derivativos** entram como contexto, não como gatilho: funding "quase zero a zero" hoje, sem leitura de presos por
  funding [137:02–139:43]; o "quem está no controle" vem da estrutura (topos/fundos), não do long/short ratio.

---

## 5. Como reproduzir com os dados do projeto

### 5.1 O que um footprint precisa
Negócios com **lado do agressor** (quem bateu a mercado), agregados por **(barra, nível de preço)**:
`vol_buy`, `vol_sell`, `n_buy`, `n_sell`; derivados: `delta = vol_buy − vol_sell` por nível, volume e delta da barra, POC da
barra (nível de maior volume), VAH/VAL do perfil do dia. Nada de OHLCV: é tudo informação **dentro** do candle. Linhas de
preço: no print são ~15–20 USD por linha em 30 min; para 5 min, 10–20 USD (0,012–0,025% a 81k) é o que ainda enxerga nódulo.

### 5.2 O que existe aqui
| Dado | Onde | Cobertura | Serve para |
|---|---|---|---|
| Negócios reais da Bybit, BTCUSDT linear, com `side` do agressor | `dados/trades_bybit/BTCUSDT<dia>.csv.gz` | 30 dias, 10/08–08/09/2026; 41–60 MB/dia comprimido, 1,8 GB no total | Footprint retroativo em qualquer TF |
| Download de qualquer dia desde 2020 | `core/bybit_trades_fetcher.py` (public.bybit.com/trading/BTCUSDT/); `ler_arquivo` já devolve price, qty, side, ts em ms | Qualquer dia; ~45–60 MB/dia | Estender a medição a outros regimes. Verificar se a pasta `trading/BTCUSD/` (inverse, o do print) existe com o mesmo formato |
| Livro de ordens Coinbase / Binance / Bybit, a cada 30 s | `dados/livro/<exchange>/<dia>.jsonl.gz` (`conselho/coletor_livro.py`) | Desde 20/10/2026 | Calço no reteste (só daqui para a frente) |
| Candles 5m/15m/1h/4h/1d Binance | `data/historico` | Desde 2017 | Estrutura, VAH/VAL/POC de TPO, controle |
| OI, LSR, funding Bybit (1 h) | `data/historico/*.json` | Desde 2020 | Contexto; já medido que não separa borda do sorteio |
| Liquidações | — | **Nenhuma** | Gatilho g ("forte liquidação") fica sem dado |
| Negócios da Coinbase (CVD spot) | — | **Nenhum** | "Quem sustenta" no reteste fica sem dado |

Tamanho: o bruto da Bybit é ~60 MB/dia comprimido (100–300 mil negócios/dia); reduzido a delta por nível e barra (5 min x
~60 níveis x 4 contadores) dá ~100–300 KB/dia. O caminho é **baixar, reduzir, descartar o bruto**.

### 5.3 Regra objetiva candidata (fixar por escrito antes de rodar)
Dois tempos gráficos, medidos separadamente: **5 min** (aproxima o "3 min" do gatilho fino) e **30 min** (o do print).
Níveis de **20 USD**. Todos os cortes abaixo são ponto de partida; só mudam com nova medição em período novo.

1. **Nódulo comprador** numa barra B: nível L com `vol_buy(L) ≥ 3x mediana de vol_buy` dos níveis negociados de B **e**
   `vol_buy(L) ≥ percentil 90` de `vol_buy` por nível das últimas 48 barras do mesmo TF **e** L no **terço superior** do
   range de B **e** `delta(L) > 0`.
2. **Absorvido** ("o preço respeitando"): a barra B fecha **abaixo** de L (`fech(B) ≤ L − 0,05%`). Sem isso não é preso, é
   rompimento com compra.
3. **Abandonado** ("fecha embaixo e deixa os caras presos; a próxima vela cai"): dentro das **2 barras seguintes** o
   fechamento fica `≥ 0,3%` (5 min) ou `≥ 0,5%` (30 min) abaixo de L, e nenhuma delas negocia acima da máxima de B.
4. **Reteste**: primeira volta do preço a `L ± 0,05%`, **pelo menos 2 barras depois** do abandono e até 24 h; o preço chega
   por baixo.
5. **Operação medida**: short limitado em L; **stop** = máxima de B + 0,1% (risco típico 0,3–0,6%); **alvo 1** = 1R;
   **alvo 2** = fechamento mais baixo entre o abandono e o reteste. Custo 0,13% ida e volta. Expira em 2 h.
6. **Vendedor preso**: espelho (nódulo vendedor no terço inferior, barra fecha acima, abandono para cima, long no reteste).

Reforços **não obrigatórios**, contados para calibrar (só valem de 20/10 em diante): parede vendedora na Coinbase entre L e
L + 0,5% (calço do short); CVD spot da Coinbase caindo no reteste (quando for coletado); L dentro de ±0,2% de VAL/VAH/POC
de ontem ou do composto.

### 5.4 Como medir
- **Critério antes:** taxa de alvo 1 antes do stop; bruto líquido de custo; excursão máxima a favor e contra em 2 h; tempo
  até resolução. Número mínimo: 40 eventos por TF.
- **Controles sorteados, com a mesma mecânica de stop/alvo:**
  (a) reteste de um **nível sorteado da mesma barra B** sem nódulo (o nódulo acrescenta algo ao reteste de uma máxima?);
  (b) nódulo igual que **não foi abandonado** (barra fechou acima de L): presos x não presos;
  (c) **direção sorteada** no mesmo reteste.
- **Três períodos** nos 30 dias que existem: 10–19/08, 20–29/08, 30/08–08/09 de 2026; depois, mais 30–60 dias baixados
  pelo fetcher de meses com regime diferente (um de alta, um de range, um de queda).
- **Eventos esperados:** 30 min = 1.440 barras em 30 dias; com nódulo + absorção + abandono + reteste em 3–6% das barras,
  40–90 eventos. 5 min = 8.640 barras, 250–500 eventos. O 5 min mede primeiro; o 30 min confirma.
- **Aprovação:** alvo 1 ≥ controle (a) + 10 pontos **e** bruto líquido > 0 **nos três períodos** e nas duas direções.
  Reprovado em qualquer um = reprovado.
- **Ressalva honesta:** o motor de fluxo do scalp (absorção/retomada em níveis, barra por volume) deu bruto zero nesses
  mesmos 30 dias. O que esta regra tem de diferente é o **abandono** (fechamento do outro lado, 2 barras) e o **reteste
  atrasado** (não entra na absorção ao vivo). Se isso também não bater o sorteio, a leitura de presos pelo footprint cai
  para este projeto e não se insiste com outro corte.

### 5.5 O que coletar a partir de hoje para a versão completa
1. Religar o coletor de negócios da Bybit (linear e, se possível, inverse) e gravar **reduzido**: delta por nível de 20 USD
   e barra de 1 min (reagrega para 3/5/30 min).
2. Negócios da Coinbase (WS `market_trades`), agregados por 1 min: dá o CVD spot do reteste.
3. Liquidações da Bybit (WS `allLiquidation`): é o dado do gatilho g ("forte liquidação") e do "comprou no topo e foi
   stopado embaixo".
4. Manter o livro (já ligado): calço no reteste.
