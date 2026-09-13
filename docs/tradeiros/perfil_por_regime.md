# Perfil de operação do Tradeiros (Shaka e Maroja), por regime

Fonte: 25 fichas de lives do YouTube (@tradeiros), de nov/2022 a set/2026. As fichas ficam em `docs/tradeiros/fichas/` (uma por vídeo, 9 seções). Este documento resume como eles operam BTC e o que foi dito ou feito em cada regime, para o Bot Trade Pro seguir o método.

Convenções:
- **[F: id]** é a ficha de origem. Datas são as da live; quando a ficha corrige a data listada, vale a corrigida.
- "O preço depois" vem da seção 8 de cada ficha (Binance 1d; nas lives de set/2026 há só alguns dias de dado).
- **[J]** marca o que depende de julgamento humano difícil de codificar.
- Nas transcrições o nome aparece como Shaka e como Chaka. Aqui fica Shaka.
- O YouTube mostra a análise e parte das operações. As zonas detalhadas iam para a comunidade paga ou para afiliados, várias vezes (D9eBFOl6utg, pXRniMaYcKc, YaPKT6WICE0, 5zfhzGDGsgo). O perfil abaixo é o que aparece em público.

---

## 1. Resumo em 10 linhas

1. Tradeiros: Shaka e Maroja, traders brasileiros de BTC, com comunidade paga e lives quase diárias. Usaram ExoCharts, Bybit e, desde 2025, o livro da Coinbase spot.
2. O ativo é BTC. Altcoins e ações entram como trades pequenos, com risco fixo em dólar.
3. A carteira fica em BTC. O patrimônio é contado em BTC acumulado, e o dólar é secundário.
4. Operam no perpétuo inverse (coin-M), com o BTC como colateral e sem alavancagem.
5. O short no inverse é hedge ("redear"): uma realização parcial feita nas resistências, não uma aposta de queda.
6. O percentual vendido sobe e desce conforme o regime e a posição do preço no range, de ~20% a ~65%. No bear de 2022 chegou a 90–100%.
7. O jogo principal é de bordas: compra no VAL e no suporte, vende na VAH e na resistência, e não opera no meio do range.
8. Cada lado é realizado na borda oposta, e o long e o short convivem na mesma carteira.
9. Hierarquia: TPO/valor primeiro, order flow como contexto, Elliott como mapa. A gestão de risco "poderia vir em primeiro".
10. Gestão de 2026: entrada fracionada com limitadas, risco de 0,5–1% por trade, stop na invalidação, tirar o risco em 1:1 com stop no zero a zero e alvo de 3:1 ou mais, aceitando acertar pouco.

---

## 2. O método em camadas, como está hoje (2025–2026)

Base: BUHBMQA5V_s, xybIvLoZ13s, D1fyBUuDCX0, 5zfhzGDGsgo, b6CT0OLH_2c, tOeA, qvboV9frI94, xV58eHoPD3Y, 1HGpjDC4dIA.

### 2.1 Leitura de valor (onde operar)

- **Perfil composto ("merge")** de ~10–12 dias define o range atual, com VAH, VAL e POC [F: tOeA (10 dias), xV58eHoPD3Y (11–12), qvboV9frI94 (11)]. Exemplos: VAH 80.255 / VAL 76.287 / POC 78.800–79.200 em 01/09/2026, e VAH 79.094 / VAL 76.563 em 04/09/2026. A área de valor "vai se deslocando" com os dias.
- **Valor de prazo longo**: consolidações de semanas ou meses são o "preço justo". O mercado fica lateral ~80% do tempo e alterna equilíbrio e desequilíbrio [F: BUHBMQA5V_s]. Perfis de ranges muito longos definem caro e barato: acima da VAH do range 2020–21 é "premium" [F: NGidqawnffA].
- **TPO do dia (30 min)**: o POC do dia é zona de compra ou venda, o POC de dias anteriores atua como ímã e os perfis por sessão servem para achar os presos [F: 1HGpjDC4dIA, 6Jgm69OajVY].
- **Níveis que atraem o preço**:
  - naked POC diário e mensal;
  - single prints e ineficiências, que funcionam como gap [F: D1fyBUuDCX0];
  - "fundo pobre", que tende a ser revisitado [F: D1fyBUuDCX0, xybIvLoZ13s];
  - HVN como zona reativa [F: BUHBMQA5V_s];
  - vazio abaixo do VAL, onde "o preço pode parar em qualquer lugar" [F: xybIvLoZ13s, 1HGpjDC4dIA].
- **Pivôs**: abertura e fechamento diário, semanal e mensal. O **pivô diário virgem** marca a abertura do dia da reversão, onde ficou gente presa [F: BUHBMQA5V_s]. A abertura semanal 82.178 foi a resistência de set/2026 [F: xV58eHoPD3Y, qvboV9frI94].
- **Fibonacci**:
  - compra no reteste de 0,5–0,786 depois de quebra de microestrutura [F: xybIvLoZ13s, xV58eHoPD3Y];
  - no início de onda 3, aceita 0,382 [F: BUHBMQA5V_s];
  - short em 0,5–0,786 da queda [F: BUHBMQA5V_s];
  - TGP (0,618–0,666) como zona de fundo ou alvo [F: D1fyBUuDCX0, xybIvLoZ13s];
  - realizações em 0,5 e 0,618 [F: 1HGpjDC4dIA];
  - log e linear dão alvos diferentes [F: D1fyBUuDCX0].
- **VWAP ancorada** no fundo majoritário, no início ou no topo do movimento, como "preço justo" [F: xV58eHoPD3Y, qvboV9frI94]. Em 2025–26 aparece pouco no BTC: em tOeA não foi usada.
- **Estrutura**: topos e fundos. A quebra de estrutura (4h ou semanal) muda o tamanho da mão. Em 5m/30m é o gatilho de mudança de característica [F: 5zfhzGDGsgo].

### 2.2 Order flow como contexto (o quê e onde)

É usado **nas bordas**, para avaliar se a borda segura, e não como gatilho isolado.

| Leitura | Como usam | Fichas |
|---|---|---|
| Livro da Coinbase spot ("calço", "nuvens") | Ordens de compra passivas sob o suporte indicam que a borda tende a segurar. "Todo rompimento de alta depois de lateral teve calço, mas nem todo calço segurou." Nuvens vendedoras num pivô virgem = short com stop acima da máxima | tOeA, BUHBMQA5V_s, xV58eHoPD3Y |
| Delta do livro spot × derivativos | Delta de −52 mi no spot contra −486 mi nos derivativos (10x) acendeu alerta de pullback | BUHBMQA5V_s, D1fyBUuDCX0 |
| CVD da Coinbase / spot | No spot querem confluência ("tendência patrocinada"), não divergência. CVD da Coinbase subindo com o preço caindo antecedeu reversões | D1fyBUuDCX0, xybIvLoZ13s, xV58eHoPD3Y |
| CVD de derivativos | Divergência altista **com entrada de contratos** é a "entrada clássica" | D1fyBUuDCX0, xybIvLoZ13s |
| Open interest | Reset de 30–50% = limpeza feita (−37% em abr/25, desejo de ~50% em nov/25). OI caindo numa alta = short squeeze saudável | D1fyBUuDCX0, xybIvLoZ13s, qvboV9frI94 |
| Net longs / net shorts | Onde há presos e combustível para squeeze. Ressalva: não indica continuação | qvboV9frI94, xV58eHoPD3Y, A1gnB7q3DkI |
| Delta por nível no composto | Blocos de delta negativo abaixo = vendedores presos; positivo acima = compradores presos | tOeA |
| Footprint (desequilíbrio 3:1, absorção, iceberg) | Onde o grande player entrou e tende a defender; imbalances vendedores absorvidos por limitadas no fundo = shorts presos | b6CT0OLH_2c, 1HGpjDC4dIA |
| Liquidações e mapa de liquidez | Onde está o combustível; pico já captado perde o valor de alvo | BUHBMQA5V_s, qvboV9frI94 |
| Funding e cash-and-carry | O vendido recebe 10–18% a.a. em BTC na maior parte do tempo. Funding muito negativo marcou fundos (FTX, 57–58k). O institucional compra spot e vende perpétuo | D1fyBUuDCX0, tOeA |
| Leilão fracassado | Preço sobe sem volume e sem liquidações → volta ao valor | xV58eHoPD3Y, qvboV9frI94 |

Nuance entre fichas: em b6CT0OLH_2c, "quem move o preço é a agressão a mercado; o livro é útil, mas não vital". Em xV58eHoPD3Y, "compra sustentada é de ordens a limite; agressão a mercado sem calço devolve o movimento". Uma frase fala do que **move** o preço e a outra do que o **sustenta**, então as duas convivem.

### 2.3 Elliott como mapa

- **Várias contagens vivas ao mesmo tempo**, cada uma com probabilidade (estrelas em xybIvLoZ13s) e invalidação numérica. O operacional sai da zona e da invalidação comuns: "ajustar a porcentagem de exposição, não o lado inteiro" [F: NGidqawnffA, BUHBMQA5V_s, D1fyBUuDCX0, M6CODUH2Nlo].
- **Graus e tempo**: superciclo, ciclo e primário em gráfico desde 2009. Fibonacci de tempo projeta datas (topo "por volta de 24/09/2026" [F: qvboV9frI94]).
- **Setup preferido: onda 2**. Depois de 5 ondas, a correção para em 0,5–0,618 (até 0,786), com volume e delta caindo. Stop abaixo do fundo [F: 0EDaN9oxWjI, qvboV9frI94]. **Não operam onda 4** [F: qvboV9frI94].
- **Não casar com a contagem**: se o gráfico valida a alternativa, ela vira a primária [F: pXRniMaYcKc, D1fyBUuDCX0].
- **Peso diferente entre os sócios**:
  - o Maroja usa Elliott como mapa principal [F: D1fyBUuDCX0, xybIvLoZ13s, BUHBMQA5V_s];
  - o Shaka, em set/2026, diz que Elliott e SMC valem pouco diante do order flow e põem Elliott "bem depois" [F: 1HGpjDC4dIA];
  - a ordem declarada varia: "TPO, depois Elliott, depois Wyckoff" [F: tOeA] e "TPO, order flow, Elliott" [F: qvboV9frI94].

### 2.4 Gestão de trade

- **Risco por trade** (as fichas divergem, veja 5.3):
  - ≤1% do capital [F: qvboV9frI94, Y1r9iOOT6jw];
  - por tipo: 1% no swing, 0,5–0,7% no day trade, 0,1–0,25% no scalp [F: 5zfhzGDGsgo];
  - 0,5% numa região "relevante, mas não extremamente relevante" [F: tOeA];
  - 0,6% no meio do range e ≥1% nos extremos [F: A1gnB7q3DkI];
  - "risco normal ~2%, mão maior 3%, sem alavancar" [F: 1HGpjDC4dIA].
- **Tamanho** = risco ÷ distância do stop. A alavancagem é consequência, só o mínimo para caber a posição [F: 5zfhzGDGsgo, M6CODUH2Nlo].
- **Alvo** mínimo de 3:1. Com acerto real de 20–33% já é lucrativo; se o acerto subir para ~50%, o alvo cai para ~2,2:1 [F: 5zfhzGDGsgo, BUHBMQA5V_s]. "Lucratividade importa mais que taxa de acerto."
- **Entrada fracionada** com limitadas escalonadas (post-only) na zona:
  - 5 fatias em tOeA, 7 ordens em A1gnB7q3DkI, 9 ordens de 0,5 a 0,786 em xV58eHoPD3Y;
  - camadas crescentes de 5% → 10% → 20% [F: D9eBFOl6utg] ou 10/20/20/30% [F: 6Jgm69OajVY].
- **Stop** = invalidação, sempre a mercado (o limitado é pulado na volatilidade) [F: bo8aNs6kX7E, 8xWRv2SjyR4]. Stop colado + alarme; stopado, reentra só se o preço mostrar força [F: D1fyBUuDCX0].
- **Tirar o risco**: em 1:1 realizar 25–50% e levar o stop ao preço médio. Zero a zero é "trade de sucesso" [F: qvboV9frI94, xV58eHoPD3Y]. Em 1HGpjDC4dIA o Shaka realiza metade em 1:1 (~1,5% com taxas), outra parte em 0,5 e em 0,618, e deixa o resto correr.
- **Entrada mal preenchida**: se só poucas fatias executaram e o preço saiu, fechar e deixar as ordens para o reteste [F: qvboV9frI94, xV58eHoPD3Y].
- **Tamanho pela localização**: pouca mão no meio, mais nos extremos [F: A1gnB7q3DkI]. Mais mão depois de quebra de estrutura, menos comprando fraqueza [F: 1HGpjDC4dIA].
- **Zona passiva × reativa**:
  - passiva: suporte com calço, usa ordens limitadas;
  - reativa: abaixo do suporte, entra só com pavio, presos e quebra de estrutura, comprando o reteste [F: 1HGpjDC4dIA].
- **Paciência**: alarmes nos níveis, ficar de fora também é operar, não scalpar com volume baixo [F: 1HGpjDC4dIA, 8xWRv2SjyR4].

### 2.5 Hedge da carteira (coin-M)

- **Estrutura**:
  - carteira em BTC como colateral no inverse, sem alavancagem;
  - o short "neutraliza exposição, não aposta dólares";
  - o stop do short é "um pedágio pago com o lucro da compra" [F: BUHBMQA5V_s];
  - ser stopado no short devolve a carteira à exposição comprada [F: 5zfhzGDGsgo].
- **Faixas observadas de % vendido**:

| Faixa | Situação | Fichas |
|---|---|---|
| ~20–25% | Correção de ~30% com medo extremo; início da escada numa resistência | xybIvLoZ13s (24%, "a menor em muito tempo"), BUHBMQA5V_s (24,5% depois de comprar a queda), qvboV9frI94 (~20%), NGidqawnffA (Shaka 20–25% na véspera do ETF) |
| ~30–45% | Topo local de range em mercado "descontado" | BUHBMQA5V_s (30→36–38%), xV58eHoPD3Y (Maroja ~41%), 5zfhzGDGsgo (~30% segundo ele), D1fyBUuDCX0 ("~30% redeada numa zona de compra é válido") |
| ~50–65% | Evento esperado, zona premium ou topo perto do ATH | Y1r9iOOT6jw (~50–52%), NGidqawnffA (Maroja 55–60%), 5zfhzGDGsgo (chegou a ~65%), qvboV9frI94 (coin-M nova ~50%), BUHBMQA5V_s (40–60% no 1º toque de topos anteriores; fala ambígua) |
| ~70% contra um long antigo | Consolidação no topo de rompimento | A1gnB7q3DkI (30% → 70% do long) |
| 90–100% | Bear de 2022, depois de perder o range | I_zjWuQqn_s |

- **Escada**: vendas limitadas crescentes nas resistências (VAH, abertura semanal, pivô virgem, 0,5–0,786 da queda, zona de liquidação de shorts). Exemplo: +6k em 83.848, +6k em 84.786 e +8k em 85.723, de ~20% a ~38%, stop ~87k [F: qvboV9frI94].
- **Duas camadas** [F: xybIvLoZ13s]:
  - ativa: vender acima, nas resistências;
  - passiva: stops de venda abaixo do fundo ("botão do pânico");
  - quando vende por cima, retira a camada de baixo.
- **Quando sobe**:
  - resistência ou topo local;
  - mercado esticado perto do ATH ("exposição baixa") [F: xybIvLoZ13s];
  - zona premium do perfil longo [F: NGidqawnffA];
  - clímax de volume [F: dDtPWolYUfQ];
  - evento esperado com "sell the news" [F: NGidqawnffA].
- **Quando desce**:
  - suporte, realizando o short [F: tOeA, 1HGpjDC4dIA];
  - reset de OI, funding negativo e livro comprador, em escada, "sem virar comprado de uma vez" [F: Y1r9iOOT6jw];
  - pânico: realizou metade do short no fundo [F: bo8aNs6kX7E];
  - correção de ~30% com medo extremo [F: xybIvLoZ13s];
  - quebra da estrutura semanal para cima: "pode até fechar o hedge" [F: xV58eHoPD3Y].
- **Limites ditos**:
  - "não chegar a uma queda profunda com só 15% de proteção: precisa de 40–60%" [F: xybIvLoZ13s];
  - "com o preço muito longe da máxima, sempre mais comprado que vendido" [F: BUHBMQA5V_s];
  - "100% vendido na alta, não" [F: qvboV9frI94].
- **O hedge não fica parado**: realiza e reabre em cada micropivô, "colocando BTC no bolso" [F: xybIvLoZ13s].
- **Funding**: renda do short no inverse [F: bo8aNs6kX7E, D1fyBUuDCX0]. "No bear, manter boa parte redeada recebendo funding" [F: D1fyBUuDCX0].
- **Meta**: se o mercado cai 10%, a carteira perde só 3–4% [F: D1fyBUuDCX0]. Mais BTC ao longo do tempo: 0,58 BTC no topo → 0,63 BTC [F: xybIvLoZ13s]; ~0,12 BTC realizado de 70k até o crash sem aporte [F: bo8aNs6kX7E].

---

## 3. Comportamento por regime

Regime segundo `compilado.json` (preço, ret60, distância do topo). As 4 lives de set/2026 recebem o rótulo "alta" (ret60 de +16% a +31%), mas o conteúdo é de range, e por isso estão em LATERAL. qVDSKTKdk6s tem rótulo "queda" e conteúdo de range: aparece em QUEDA com essa ressalva.

### 3.1 ALTA (inclui rompimento de máxima)

| Item | Comportamento |
|---|---|
| Postura | Long estrutural mantido (às vezes com stop subindo), hedge **vendido na força**: topo de explosão, clímax, consolidação no topo, premium. Hedge típico de ~50–60% em topos locais e eventos (NGidqawnffA, Y1r9iOOT6jw); até ~70% contra um long antigo (A1gnB7q3DkI); "maior parte vendida no topo" com >90% do capital em BTC (D9eBFOl6utg) |
| Onde compram | Reteste da zona rompida **com aceitação** (fechamentos acima, não pavio); POC/VAL do range deixado para trás; naked POC abaixo; zonas de liquidação de longs; onda 2 em 0,5–0,618 |
| Onde vendem | Clímax de volume com liquidações; consolidação logo abaixo/acima da máxima; acima da VAH de um range longo; confluências de POC + golden pocket + liquidações de short ("short pedágio", ~1% de risco, ~5 R) |
| No meio | Mão mínima (0,6% de risco num long de meio de range em A1gnB7q3DkI); nada de scalp no meio |
| Tamanho | Diminui quanto mais sobe ("com o preço subindo muito, o risco-retorno piora → diminuir compras", D9eBFOl6utg); compras em camadas 5% → 10% → 20% abaixo |
| Evitam | Comprar a explosão/rompimento (FOMO); shortar com força ou fechar o long estrutural; long alavancado pagando funding caro; confiar só em book ou só em CVD |

Exemplos:
- **14/01/2023 — dDtPWolYUfQ** (virada de jan/23):
  - viraram o viés para comprador pela aceitação de volta no range de 149 dias e pelo flip de POC;
  - mesmo assim venderam hedge no clímax de ~21,3k e planejaram comprar em 18,9–18k;
  - depois: o preço foi a 23,8k (25/01) e 26,4k em 60 dias. O hedge perderia ~11% se mantido, as compras de 18,9–18k não executaram e o long de 16,5k mantido funcionou.
- **05/05/2023 — pXRniMaYcKc**:
  - Elliott macro com onda 3, sem vender a posição; esperavam varrer liquidez abaixo antes de romper 32–33k;
  - depois: −12,5% em 7 dias (25,8k). O rompimento de 32–33k levou ~5,5 meses; a contagem altista seguiu consistente por 12 meses.
- **10/01/2024 — NGidqawnffA** (ETF):
  - hedge de 55–60% (Maroja) e escada até 48,9k; esperavam "sell the news";
  - depois: máxima de 48.969 dentro da zona, −21% até 38,6k (23/01) e +80% até 70k em 60 dias. Quem recomprou em 41–38k pegou a alta; quem manteve o hedge perdeu a perna seguinte.
- **15/03/2024 — D9eBFOl6utg** (dia seguinte à máxima de 73.777):
  - maior parte vendida no topo; compras em camadas em 70k, 69k e 66–66,6k;
  - depois: a máxima não foi superada em 30 dias. As compras de 69k e 66,6k executaram e chegaram a −8% a −12% no fundo de 60,8k (seriam stopadas com stop logo abaixo de 66k). Vender as voltas abaixo de 67.170 funcionaria até 20/03.
- **19/04/2024 — Y1r9iOOT6jw** (halving):
  - hedge de ~50% nos dois sócios, com vieses opostos e execução igual; short "pedágio" em 66,5–68,3k;
  - depois: a máxima de 67.232 ficou dentro da zona, queda de ~16% até 56,6k (01/05); o hedge amorteceu a queda.
- **25/04/2024 — M6CODUH2Nlo**:
  - Shaka ~70% comprado (comprou o fundo) e vendendo o repique; Maroja vendendo na TGP 0,5–0,666;
  - depois: o repique acabou no próprio dia, 56,6k em 01/05 e o stop do long de 64–66k acionado; a compra planejada em 59–60k rendeu ~+20% até 21/05.
- **06/12/2024 — A1gnB7q3DkI** (rompimento de 100k):
  - realizaram os longs curtos, subiram o hedge para ~70% do long antigo (7 ordens, médio 101.793) e compraram pouco no meio;
  - depois: 94,2k em 09/12, abaixo do alvo médio do short antes do stop; o long do meio foi stopado; rompeu 104k em 15/12 (108,4k) e caiu a 92,2k em 20/12, no naked POC marcado.

### 3.2 QUEDA (inclui crash e pânico)

São dois comportamentos diferentes, conforme a leitura da estrutura maior:
- **Bear declarado** (2022, depois de perder o range de 149 dias): hedge de 90–100%, compra só com reaceitação do range ou estrutura de alta (fundo e topo mais altos) [F: I_zjWuQqn_s].
- **Correção dentro da alta** (2023–2025): hedge reduzido, compras em camadas no pânico e mais mão só depois de quebra de estrutura [F: 0EDaN9oxWjI, bo8aNs6kX7E, D1fyBUuDCX0, xybIvLoZ13s].

| Item | Comportamento |
|---|---|
| Postura | Bear: 90–100% vendido. Correção com medo extremo: hedge baixo (~24%) com re-hedge passivo (stops de venda abaixo do fundo). "No bear, boa parte redeada recebendo funding" |
| Onde compram | Captura de liquidez abaixo de fundo pobre com reação; TGP 0,618–0,666; naked POC mensal e pivô mensal; zona de liquidação; reação forte no pânico; **pullback depois de romper o topo que sustenta a estrutura de baixa ("compra obrigatória", D1fyBUuDCX0)** |
| Onde vendem | Voltas e retestes de níveis perdidos (VAL, VWAP anual, single print); com a estrutura ainda feia, re-shortar as voltas; distribuição do que comprou no fundo nas resistências do repique |
| No meio | Não recomprar no meio da queda sem estrutura; não shortar no meio do repique sem quebra |
| Tamanho | Compras pequenas contra o fundo, com camadas abaixo; mão cheia só depois de 5 ondas + onda 2 ou de quebra de estrutura; risco de 1% perto do fundo paga muitos R (24 R no exemplo de 8xWRv2SjyR4) |
| Evitam | Short alavancado no suporte "no desespero"; aportar dinheiro novo no pânico; comprar o vazio abaixo do VAL; operar a notícia; montar operações novas ao vivo no dia de volatilidade |

Exemplos:
- **21/11/2022 — I_zjWuQqn_s** (duas semanas depois da FTX):
  - 90–100% vendido em 4 carteiras, pensando em realizar; chamou o fundo que se formava de "fraco";
  - depois: a mínima de 15.476 foi o fundo do ciclo; lateral de 15,6–17,4k por duas semanas e +44% em janeiro.
- **23/12/2022 — qVDSKTKdk6s** (rótulo queda, conteúdo de range):
  - range de ~15,5–18,4k, presos dos dois lados, "fim de semana não vale operar"; long do fundo com o risco tirado; shorts planejados em 17,1–17,5k e 18,9–19,5k;
  - depois: 14 dias travado em 16,3–17,0k; em 08–13/01 a alta atravessou as duas zonas de short; o long do fundo ganharia muito.
- **04/09/2023 — 0EDaN9oxWjI**:
  - ~100% exposto em BTC com shorts nas resistências; long pequeno e plano de compra na captura de ~24.750;
  - depois: fundo de 24.901 em 11/09 (a ordem de 24.750 não executaria na Binance); o long colado provavelmente foi stopado; +44% em 60 dias.
- **05/08/2024 — bo8aNs6kX7E** (crash até 49k):
  - hedge feito em 68–70k; compra no pânico da madrugada; metade do short realizada no fundo; re-short menor no repique;
  - depois: 49k não voltou. O short planejado em 57,2–60k foi atropelado até 62,7k antes de voltar a 56k.
- **06/08/2024 — 8xWRv2SjyR4**:
  - distribui o que comprou no fundo; venda em 58k e "com mais força" em 61–62k; compra no reteste de 54k;
  - depois: squeeze até 62.745 em 08/08, dentro da zona de 61–62k; a venda de 58k com stop curto seria stopada e a de 61–62k capturou a queda a 56k.
- **07/04/2025 — D1fyBUuDCX0** (tarifas):
  - camadas de compra abaixo de 77,2k e em 74–69/70k; hedge realizado no single print; compra obrigatória se romper 88.740;
  - depois: 74.508 foi o fundo; as ordens de 77,2–74,6k executaram; re-shortar as voltas perderia a partir de 10/04; rompeu 88.740 em 22/04 e fez 112k em 60 dias.
- **19/11/2025 — xybIvLoZ13s** (−29% do topo, medo extremo):
  - hedge em 24% (o menor), long no reteste 0,5–0,786 com stop de ~1,5–1,7%, re-hedge passivo abaixo do fundo e compra em 84–82k;
  - depois: o long foi stopado no dia seguinte; os stops de re-hedge ganharam na queda; 80,6k em 21/11 (1,7% abaixo da zona); a compra em 84–82k estava no lucro em 7–14 dias;
  - no prazo longo, a invalidação de 74k caiu em 03/02/2026 e o preço foi a 57,8k em 01/07/2026: o cenário de topo de ciclo, que tratavam como o menos provável, se confirmou.

### 3.3 LATERAL / RANGE

É o regime mais frequente nas lives recentes e onde o método aparece mais completo.

| Item | Comportamento |
|---|---|
| Postura | Carteira líquida comprada de ~50–70%, hedge de ~20–45%; long e short convivem no mesmo range, cada um realizado na borda oposta |
| Onde compram | VAL do merge; naked POC; POC do dia; zona passiva com calço (Coinbase); desvio abaixo da VAL que volta ao valor; falha de rompimento do fundo com reclaim |
| Onde vendem | VAH; POC acima (ex.: 78,8–79,2k); abertura semanal ou pivô virgem; falha de rompimento do topo (só depois de ver a reação); topo com leilão fracassado |
| No meio | Nada: "não existe risco-retorno"; só parciais e ajuste de hedge |
| Tamanho | Pequeno e fracionado (0,5% em tOeA; mão pequena no teste da VAH com limitada em xV58eHoPD3Y); mais mão só com quebra de estrutura |
| Evitam | Vender no meio; comprar o topo do range com volume baixo; shortar no VAL ou abaixo sem aceitação e reteste; short no USDT antes do nível ("stop de bobeira"); ordem pendurada para short de rompimento; operar o dado econômico |

Desvio × aceitação:
- a maioria dos rompimentos é falsa [F: qvboV9frI94];
- rompimento vale com volume construído além do nível e reteste [F: tOeA, 1HGpjDC4dIA];
- se o preço entra de volta no valor, atravessa até a outra borda: quem entrou na borda deve stopar logo [F: xV58eHoPD3Y].

Exemplos:
- **07/11/2022 — ZYvYA4BlZ08** (véspera da FTX):
  - short no teste do rompimento ≥21,4k, long no suporte do mini range e as duas pontas com stop na entrada;
  - depois: o short capturaria até ~27% na queda da FTX; o long saiu no zero a zero em 08/11.
- **07/12/2022 — qOq7sPDo13o**:
  - shorts antigos sem risco e long scalp pequeno como proteção;
  - depois: aperto até 18.388 (+6% contra os shorts de 17,1–17,3k) antes de voltar a 16.256.
- **28/07/2023 — YaPKT6WICE0**:
  - cenário preferido: varrer o fundo, subir à confluência VAL + Fibonacci + banda de VWAP e cair;
  - depois: 28,6k (01/08), ~30k (02 e 08/08) e 25,2k em 17/08, na sequência descrita.
- **10/07/2024 — 6Jgm69OajVY**:
  - long protegido por short na mesma carteira; swing em 57–55k (10/20/20/30%), stop abaixo de 53.499 e alvo de 89k;
  - depois: fundo de 56,5k dentro da zona, +22% até 22/07; sem realização, o stop foi acionado no crash de 05/08; o aumento do short em 58,2k seria stopado em 14–15/07.
- **25/06/2025 — 5zfhzGDGsgo** (perto do ATH de 112k):
  - escada de short de 107–109k (carteira até ~65% vendida) e long no fundo da guerra (98–99k);
  - depois: o short realizou ~1% em 106,5k e foi stopado em 5 dias; 112k rompido 14 dias depois e 124k em 60 dias; o long do fundo funcionou.
- **10/10/2025 — b6CT0OLH_2c** (a live acabou antes do colapso):
  - fechou o short restante e comprou em ~116,9k, na "última entrada do player" pelo footprint da Coinbase;
  - depois: pavio até 102k no mesmo dia (−12,7% contra o long) e 116,9k não voltou em 14 dias; o resultado depende de um stop não citado.
- **20/04/2026 — BUHBMQA5V_s**:
  - hedge de 24,5% → 36% em 76–77k e compra em 73–70k; operou as duas contagens (fundo feito e onda B);
  - depois: o re-hedge foi stopado em 2 dias (~2% sobre 36%); o alvo da onda B (82,85k) veio em 06/05; em seguida 59,1k em 05/06 (onda C) e as compras de 73–70k seriam stopadas.
- **01/09/2026 — tOeA**:
  - merge de 10 dias, compra em fatias na VAL (risco de 0,5%) e short pequeno aumentado em 78,2k;
  - depois: a VAL (76,3k) segurou e o preço subiu 7,9% até 82,3k; o short de 78,2k ficou +5,2% contra; poucas fatias preencheram.
- **03/09/2026 — qvboV9frI94**:
  - short ~20% no topo do range, escada até ~38% em 83,8–85,7k; realizou o long da VAL;
  - depois: a máxima de 82,3k deixou a escada sem preencher; 78,7k em 04/09 e 75,9k em 11/09 (Bybit).
- **04/09/2026 — xV58eHoPD3Y**:
  - realizou 25% do short do topo; Maroja com hedge de 41% e 9 fatias de compra de 0,5 a 0,786;
  - depois: só +1 dia de dado; pelo relato de 11/09, o range seguiu sem romper 82,85k.
- **11/09/2026 — 1HGpjDC4dIA** (CPI):
  - rotação VAL→VAH→POC no dia; compra em fatias pelo footprint e tirou o risco em 1:1; re-short em escada até 80,8k;
  - depois: sem dado.

### 3.4 TOPO DE CICLO e FUNDO DE CICLO

**Topo de ciclo.** Nenhuma das 25 lives é do dia de um topo de ciclo declarado por eles. O que as fichas mostram:
- **Método de medir o ciclo**: tempo e profundidade das correções, correções encolhendo, fibo de tempo [F: pXRniMaYcKc]. Em ago/2024 a expectativa era que a onda 3 primária não terminasse antes de out/2025, "mais comum 2027–2030" [F: 8xWRv2SjyR4].
- **Perto do ATH (regras gerais)**:
  - exposição baixa com o mercado esticado perto do ATH [F: xybIvLoZ13s];
  - vender pesado na força e comprar só em camadas abaixo [F: D9eBFOl6utg];
  - hedge até ~65% logo abaixo do ATH [F: 5zfhzGDGsgo];
  - realizar "todo topinho" em zona premium [F: NGidqawnffA].
- **O topo de 126,2k (06/10/2025)**:
  - 4 dias depois, a carteira seguia "muito comprada" e a expectativa era de continuação [F: b6CT0OLH_2c];
  - em 19/11/2025, "topo do ciclo em 126k" era a contagem menos provável (4 estrelas) [F: xybIvLoZ13s];
  - o preço chegou a 57,8k em 01/07/2026. Registro neutro: nas lives disponíveis, o topo de ciclo não foi tratado como cenário primário em tempo real; o hedge em escada e a invalidação de 74k eram as proteções previstas.
- **Depois do topo** [F: BUHBMQA5V_s]:
  - "descontado = líquido comprado": 60–75% exposto, hedge de 25–40% que sobe nas altas;
  - venda agressiva só na resistência majoritária (85–90k);
  - sinais clássicos de fundo que ainda faltavam: divergência semanal e funding extremo como na FTX.

**Fundo de ciclo.**
- **Nov/2022**: quase todo vendido, mas "pensando em realizar, não em aumentar". Planejava compra só com reaceitação ou estrutura de alta; o fundo "fraco" foi o fundo [F: I_zjWuQqn_s].
- **Jan/2023, a virada** [F: dDtPWolYUfQ]:
  - aceitação de volta no range anterior com candles de 4h (não só pavio);
  - flip de POC;
  - fibo de tempo 1:1 do ciclo;
  - medo, capitulação e liquidação.
  - Declaram a mudança de regime em voz alta, mas não compram a explosão: esperam o reteste.
- **Sinais de fundo citados em várias fichas**:
  - funding muito negativo por muito tempo (FTX, 57–58k) [F: D1fyBUuDCX0, tOeA];
  - reset de OI [F: Y1r9iOOT6jw, bo8aNs6kX7E, D1fyBUuDCX0];
  - livro comprador com calço na Coinbase [F: tOeA, xybIvLoZ13s];
  - consenso público baixista [F: 0EDaN9oxWjI, BUHBMQA5V_s, xybIvLoZ13s];
  - "fundos majoritários saem nos piores momentos" [F: D1fyBUuDCX0].
  - Wyckoff só em fundos grandes (2022 e "talvez o atual") [F: tOeA].
- **2026**: as fichas divergem na data do fundo majoritário. Em abril, "fundo em ~60k (fev/2026)" [F: BUHBMQA5V_s]; o preço fez 59,1k em 05/06 e 57,8k em 01/07; em setembro, "fundo majoritário em 57–58k (julho)" [F: xV58eHoPD3Y, tOeA]. Critério de confirmação dito em set/2026: romper 82,8k (estrutura semanal) e formar volume em 84–85k, "com ressalva de bull trap".
- **Postura no fundo**:
  - compra em camadas no pânico com stop abaixo;
  - hedge baixo, mas não zero;
  - mais mão depois de quebra de estrutura;
  - compra da onda 2 (0,5–0,618) [F: 0EDaN9oxWjI, qvboV9frI94].

### 3.5 DIAS DE EVENTO

Regra comum (15 fichas): **a notícia não é gatilho**. O plano é feito antes; o horário do dado só marca a volatilidade, a hora de realizar ou de mexer em stops. Se o dado leva o preço a uma borda, operam contra a reação do consenso [F: 1HGpjDC4dIA, xV58eHoPD3Y]. Não abrem live para discurso do Fed [F: 1HGpjDC4dIA].

| Evento | Live | O que fizeram | O que o preço fez |
|---|---|---|---|
| Briga CZ x FTX, véspera do colapso | 07/11/2022 ZYvYA4BlZ08 | Descartaram a notícia; short no teste do rompimento, long no suporte com stop na entrada | −27% em 3 dias a partir de 21,4k |
| Pós-FTX | 21/11/2022 I_zjWuQqn_s | 90–100% vendido, caça ao stop de um short grande na Deribit (16.280), pensando em realizar | Fundo do ciclo no próprio dia |
| Dados dos EUA + Natal | 23/12/2022 qVDSKTKdk6s | Não operar o fim de semana de Natal; travamento previsto | 14 dias em 16,3–17,0k |
| Aprovação dos ETFs | 10/01/2024 NGidqawnffA | Operaram antes, durante e depois; hedge de 20–60%, mão direcional pequena, "sell the news" | −21% até 23/01, depois +80% |
| Halving (e ataque Israel–Irã) | 19/04/2024 Y1r9iOOT6jw | "Não muda nada na operação"; hedge ~50%, short pedágio pequeno | −16% até 01/05 a partir da zona |
| Crash de ago/2024 | 05–06/08/2024 bo8aNs6kX7E, 8xWRv2SjyR4 | Seguir o plano; comprar o pânico com o dinheiro do hedge; realizar metade do short; sem aporte; distribuir no repique | 49k não voltou; repique até 62,7k |
| Tarifaço EUA x China | 07/04/2025 D1fyBUuDCX0 | Ignoraram a notícia: "o preço foi à zona que esperávamos"; camadas de compra | Fundo no dia; +50% em 60 dias |
| Ataque EUA x Irã | 25/06/2025 5zfhzGDGsgo (fim de semana anterior) | Compra "independente das notícias" em 98–99k | Voltou a 107–108k em 3 dias |
| Liquidações de 10/10/2025 | 10/10/2025 b6CT0OLH_2c | Fecharam o short restante e compraram o repique (a live acabou antes do colapso). Depois o Shaka disse que "toda a Tradeiros desceu shortada" (não verificável na transcrição) | Pavio até 102k no mesmo dia |
| FOMC + Nvidia | 19/11/2025 xybIvLoZ13s | Evento como fonte de volatilidade; ordens postas antes | −12% até 80,6k em 2 dias |
| Payroll | 04/09/2026 xV58eHoPD3Y | Realizou lucro às 9:30, antes do dado; na queda só compraram | Range manteve |
| CPI | 11/09/2026 1HGpjDC4dIA | Não sabia o resultado; ordens na zona passiva (75,45k tocado); vendas na VAH | Rotação VAL→VAH→POC no dia |

---

## 4. Evolução 2022 → 2026

| Ferramenta / tema | 2022–2023 | 2024 | 2025–2026 |
|---|---|---|---|
| TPO / Volume Profile | TPO do dia no ExoCharts; "POC da região"; em 2023, perfil de ranges longos (149 dias) com POC, VAL e VAH; VPVR chamado de amador | TPO de 30 min por dia e **mesclado no fim de semana**; naked POC, single prints, cauda compradora; perfil do range 2020–21 para caro e barato | **Merge de ~10–12 dias** para o range; valor de semanas como preço justo; HVN, fundo pobre, vazio; delta por nível no composto; VP de faixa livre |
| Order flow | Footprint, trades por segundo e liquidações da Bybit; caça ao stop tick a tick, perto de gatilho; **OI e long/short desprezados** (ZYvYA4BlZ08); CVD spot × futuro por corretora; Binance "atrasada" | OI, funding, prêmio do perpétuo, heatmap e book (Trading Lite) em topos e fundos; delta spot × perpétuo | **Livro e CVD da Coinbase spot** como referência; calço; delta do livro spot × derivativos; OI e net longs/shorts; mapa de liquidações; desequilíbrio 3:1 e absorção; cash-and-carry. **Contexto, não gatilho** |
| Elliott | Útil para swing (2022); em 2023 vira mapa macro principal, com primária e alternativa e fibo de tempo | Várias contagens operadas ao mesmo tempo, vieses opostos com a mesma execução; graus desde 2009 | Estrelas de probabilidade (Maroja); topo por tempo; não operar onda 4; Shaka em set/2026: "vale pouco diante do order flow" |
| Fibonacci | Retração como "dor" (0,382/0,5/0,618); TGP para short; extensões diárias | Golden pocket; 0,5–0,786 para recompra depois do repique | Reteste 0,5–0,786 depois de quebra de microestrutura; 0,382 no início de onda 3; alvos de realização |
| VWAP | Banda da VWAP (2023); VWAP ancorada em 1º de janeiro | VWAP anual e mensal como nível-chave (ago/2024) | VWAP ancorada no fundo majoritário ou no topo como preço justo; uso menor no BTC |
| Macro e intermercado | S&P, DXY e gap da CME como confluência | DXY e S&P (VAH do S&P) como pano de fundo; gap da CME como ímã | DXY só para semanas; agenda só para a hora da volatilidade; "juros e BTC sem relação desde 2022" |
| Risco por trade | Mão em dólar; exemplo de 1% com 2:1 mínimo; stop curtíssimo (0,36%, 8:1); 22% de acerto divulgado | ≤1%; 0,5% com stop largo e tamanho ajustado; 1–5% conforme o operador (8xWRv2SjyR4) | 1% swing / 0,5–0,7% day / 0,1–0,25% scalp; 0,5–1% (Shaka em 1HGpjDC4dIA: ~2%, até 3%) |
| Alvo e acerto | 2:1 mínimo (2022); "stop pequeno para ganhar muito mais" | R ≥ 3; compra no fundo paga 24 R | 3:1 mínimo; acerto aceito de 20–40% |
| Entrada | Ordens escalonadas (só a 1ª executou); criticam escalonar com stop largo e realizar cedo | Camadas 5/10/20% e 10/20/20/30%; 7 ordens | 5–9 fatias post-only na zona; fechar se preencheu pouco |
| Tirar o risco | Parcial + stop na entrada (ZYvYA4BlZ08); risco tirado no long do fundo | "No scalp, tirar o risco perto de 1:1 e subir as ordens" | **1:1 realizando 25–50%, stop no preço médio; zero a zero = sucesso** |
| Alavancagem | Scalp USD-margined a 5x (2022) | "Alavancagem é insanidade"; sem alavancagem | Só o mínimo para caber o tamanho; coin-M sem risco de liquidação |
| Hedge | Pares long × short em dólar; 90–100% vendido no bear; 2023: "~100% exposto em BTC coin-M e shorta resistências" | **% explícito**: 20–25% a 55–60%; escada; realizar metade no pânico; "nunca comprar no coin-M, só vender" (bo8aNs6kX7E) | 20–65%; duas camadas (stops abaixo + vendas acima); **long e short no mesmo inverse** (tOeA, qvboV9frI94, 1HGpjDC4dIA); funding como renda |
| Tom | Muito marketing, ataque a concorrentes | Mais didática de gestão | Prestação de contas pública dos stops e dos zero a zero |

---

## 5. Regras operacionais

Formato: **SE** condição **ENTÃO** ação. O range é o merge de ~10 dias, com VAL, POC e VAH. `p` é a posição do preço no range (0 = VAL/fundo, 1 = VAH/topo).

### 5.1 Regras explícitas (ditas por eles)

**Onde operar**
1. SE `p` está no meio do range (perto do POC ou do 0,5) ENTÃO não abrir posição nova; só realizar parciais ou ajustar o hedge. [F: ZYvYA4BlZ08, tOeA, qvboV9frI94]
2. SE o preço está no suporte/VAL ENTÃO compra é permitida e venda nova é proibida; SE está na resistência/VAH ENTÃO o inverso, **independente do viés**. [F: qvboV9frI94, Y1r9iOOT6jw, M6CODUH2Nlo, BUHBMQA5V_s]
3. Tamanho por quartil (sugestão de A1gnB7q3DkI): compra com interesse médio em `p` de 0,25–0,5 e alto em 0–0,25; venda em espelho. Invalidação nos extremos. Risco no meio de ~0,6% e nos extremos de ≥1%.
4. SE o preço está no VAL ou abaixo dele ENTÃO não vender, a não ser que ocorram as três coisas: perder o VAL, construir volume abaixo e retestar por baixo. [F: 1HGpjDC4dIA]
5. SE o preço rompe uma borda ENTÃO tratar como desvio até haver **aceitação** (fechamentos além do nível com volume construído, não pavio) e **reteste**. [F: dDtPWolYUfQ, D9eBFOl6utg, qvboV9frI94, tOeA]
6. SE houve falha de rompimento (pavio além da borda e fechamento de volta) ENTÃO operar na direção da volta com stop além do pavio, **só depois de ver a reação**, sem ordem pendurada. [F: BUHBMQA5V_s, xybIvLoZ13s, xV58eHoPD3Y] [J: "reação"]
7. SE o preço perde o VAL e volta ao valor ENTÃO vender o reteste do VAL por baixo. [F: tOeA]
8. SE entrou na borda e o preço volta para dentro do valor contra a posição ENTÃO stopar logo: o preço tende a atravessar até a outra borda. [F: xV58eHoPD3Y]
9. SE o preço já subiu (esticado, longe do valor) ENTÃO não comprar; esperar a volta à zona anterior com energia compradora. [F: b6CT0OLH_2c, dDtPWolYUfQ, qvboV9frI94] [J: "energia compradora"]
10. SE a zona tem calço (limitadas visíveis) ENTÃO é zona passiva, com ordens limitadas. SE está abaixo do suporte, sem calço, ENTÃO é zona reativa: entrar só depois de pavio, presos e quebra de estrutura, comprando o reteste. [F: 1HGpjDC4dIA] [J: calço exige livro L2 da Coinbase]
11. SE houve quebra de estrutura a favor ENTÃO aumentar a mão (mesmo mais caro). SE a compra é contra a estrutura ENTÃO mão menor. [F: 1HGpjDC4dIA, xV58eHoPD3Y]
12. SE o preço rompe o topo que sustenta a estrutura de baixa ENTÃO comprar o pullback ("obrigatório"); com quebra da estrutura semanal, pode fechar o hedge. [F: D1fyBUuDCX0, xV58eHoPD3Y]
13. SE houve repique forte desde o fundo ENTÃO realizar parte e recomprar a volta em 0,5–0,786. [F: bo8aNs6kX7E, xybIvLoZ13s]
14. SE há 5 ondas completas e correção em 0,5–0,618 (até 0,786) sem perder o fundo, com volume e delta caindo ENTÃO comprar a onda 2 com stop abaixo do fundo. SE a leitura é onda 4 ENTÃO não operar. [F: 0EDaN9oxWjI, qvboV9frI94] [J: contagem]
15. SE há várias contagens vivas ENTÃO operar a zona e a invalidação comuns e ajustar a % de exposição, não o lado inteiro. [F: NGidqawnffA, BUHBMQA5V_s, D1fyBUuDCX0] [J: contagem]
16. SE o preço renovou a mínima sem renovar a máxima ENTÃO não comprar (ou comprar muito pouco) até um fundo com liquidação, volume e queda de OI. [F: NGidqawnffA]
17. SE o volume está muito baixo (fim de semana, feriado) ENTÃO não scalpar; cuidado redobrado sem mudar o setup. [F: 8xWRv2SjyR4, qVDSKTKdk6s, YaPKT6WICE0]

**Gestão**
18. Risco por trade: swing 1%, day 0,5–0,7%, scalp 0,1–0,25%; teto de 1% [F: 5zfhzGDGsgo, qvboV9frI94]. Tamanho = risco ÷ distância do stop; alavancagem só consequência. [F: 5zfhzGDGsgo, M6CODUH2Nlo]
19. SE o alvo até a próxima borda ou nível for menor que 3 R ENTÃO não entrar. SE o acerto medido estiver em ~50% ENTÃO o alvo mínimo cai para ~2,2 R. [F: 5zfhzGDGsgo, BUHBMQA5V_s, 8xWRv2SjyR4] Recusar trade com risco igual ao alvo. [F: YaPKT6WICE0]
20. Entrada em fatias com limitadas post-only escalonadas na zona (5–9 ordens), com camadas maiores mais longe. [F: tOeA, xV58eHoPD3Y, A1gnB7q3DkI, D9eBFOl6utg, 6Jgm69OajVY]
21. Stop = invalidação da estrutura ou contagem, enviado **a mercado**. [F: bo8aNs6kX7E, 8xWRv2SjyR4]
22. SE o preço andou 1 R a favor do preço médio ENTÃO realizar 25–50% e mover o stop para o preço médio. Saída no zero a zero conta como sucesso. [F: qvboV9frI94, xV58eHoPD3Y]
23. Realizações seguintes em 0,5 e 0,618 do movimento ou na borda oposta; o resto corre. [F: 1HGpjDC4dIA, tOeA]
24. SE poucas fatias preencheram e o preço saiu da zona ENTÃO fechar o que preencheu e manter as ordens para o reteste. [F: qvboV9frI94, xV58eHoPD3Y]
25. SE foi stopado só por pavio e depois houve quebra de estrutura a favor ENTÃO recomprar e soltar o hedge. [F: xybIvLoZ13s]
26. Não usar um trade para salvar outro; não operar para recuperar a perda do dia. [F: bo8aNs6kX7E, tOeA]

**Hedge (coin-M)**
27. O short no inverse usa o BTC como colateral, sem alavancagem, e é realização parcial. O stop do short fica acima do topo e é aceito como pedágio. [F: BUHBMQA5V_s, 5zfhzGDGsgo, I_zjWuQqn_s]
28. SE o preço chega a uma resistência (VAH, abertura semanal, pivô virgem, 0,5–0,786 da queda) ENTÃO subir o hedge em escada com limitadas crescentes. SE chega ao suporte ENTÃO realizar parte do short. [F: qvboV9frI94, BUHBMQA5V_s, 1HGpjDC4dIA, xV58eHoPD3Y]
29. Hedge em duas camadas: stops de venda abaixo do fundo (passivo) e vendas acima (ativo). Ao executar a venda de cima, cancelar os stops de baixo. [F: xybIvLoZ13s]
30. SE o hedge está abaixo de ~15% e o cenário admite queda profunda ENTÃO elevar para 40–60%. [F: xybIvLoZ13s]
31. SE o preço está muito abaixo da máxima ("descontado") ENTÃO manter a carteira líquida comprada (hedge < 50%). SE está esticado perto do ATH ENTÃO exposição baixa (hedge alto). Em correção de ~30% com medo extremo, exposição alta. [F: BUHBMQA5V_s, xybIvLoZ13s]
32. SE está comprado e o preço chega à resistência ENTÃO aumentar o short (vender uma fração, ex.: de 30% para 70% do long) em vez de fechar o long. [F: 6Jgm69OajVY, A1gnB7q3DkI, dDtPWolYUfQ]
33. SE long e short estão abertos ao mesmo tempo ENTÃO o long é maior, e o short com lucro tirado serve de colchão. [F: qVDSKTKdk6s]
34. O hedge não fica parado: realizar e reabrir a cada micropivô. [F: xybIvLoZ13s] SE houve crash com capitulação ENTÃO realizar ~metade do short no fundo e comprar a reação, sem aporte novo. [F: bo8aNs6kX7E]
35. Não vender no USDT antes do nível ("stop de bobeira"); no inverse pode ir vendendo aos poucos. [F: qvboV9frI94]

**Evento e disciplina**
36. SE há dado macro agendado ENTÃO não abrir posição pelo dado; realizar ou ajustar stops antes do horário e deixar as ordens nas bordas. SE o dado leva o preço a uma borda ENTÃO operar contra a reação (dado "bom" na resistência → vende; "ruim" no suporte → compra). [F: 1HGpjDC4dIA, xV58eHoPD3Y]
37. SE aparecem nuvens vendedoras no livro num pivô virgem ENTÃO short com stop acima da máxima. [F: BUHBMQA5V_s] [J: exige livro]
38. Numa entrada com stop barato perto de um nível, entrar pequeno e somar se quebrar a estrutura, sem esperar "alinhamento". [F: 5zfhzGDGsgo] Numa boa zona, comprar contra o fundo atual e deixar ordens abaixo. [F: D1fyBUuDCX0]

### 5.2 Padrões recorrentes observados (contagem em 25 fichas)

| # | Padrão (condição → ação) | Fichas |
|---|---|---|
| P1 | Carteira com long e short de hedge convivendo; cada lado realizado no extremo oposto | 24 (todas menos YaPKT6WICE0) |
| P2 | Resistência → vender em escada como hedge; suporte → recomprar | 16 (NGidqawnffA, D9eBFOl6utg, Y1r9iOOT6jw, 6Jgm69OajVY, bo8aNs6kX7E, 8xWRv2SjyR4, A1gnB7q3DkI, D1fyBUuDCX0, 5zfhzGDGsgo, b6CT0OLH_2c, xybIvLoZ13s, BUHBMQA5V_s, 1HGpjDC4dIA, xV58eHoPD3Y, qvboV9frI94, tOeA) |
| P3 | Notícia ou evento → não é gatilho; seguir o plano | 15 |
| P4 | Contagens múltiplas com invalidação numérica explícita | 15 |
| P5 | Entrada fracionada com limitadas escalonadas | 14 |
| P6 | Preço esticado ou rompimento com euforia → não comprar; esperar reteste | 13 |
| P7 | Consenso ou sentimento extremo → posição contrária (medo = compra, euforia = venda) [J] | 12 |
| P8 | Quebra de estrutura (ou aceitação no range anterior) → aumentar a mão ou mudar o viés | 11 |
| P9 | Aceitação × pavio: pavio não confirma rompimento | 9 |
| P10 | Meio do range → sem posição nova ou com mão mínima | 8 (ZYvYA4BlZ08, qVDSKTKdk6s, bo8aNs6kX7E, 8xWRv2SjyR4, A1gnB7q3DkI, xV58eHoPD3Y, qvboV9frI94, tOeA) |
| P11 | Reset de OI, liquidações ou limpeza de alavancagem → sinal de fundo local e redução do hedge | 8 (Y1r9iOOT6jw, M6CODUH2Nlo, bo8aNs6kX7E, A1gnB7q3DkI, D1fyBUuDCX0, xybIvLoZ13s, xV58eHoPD3Y, 1HGpjDC4dIA) |
| P12 | Queda com pânico → realizar parte do hedge no fundo e comprar em camadas | 8 (I_zjWuQqn_s, NGidqawnffA, Y1r9iOOT6jw, bo8aNs6kX7E, D1fyBUuDCX0, xybIvLoZ13s, 1HGpjDC4dIA, xV58eHoPD3Y) |
| P13 | Funding como contexto (caro = excesso de longs; negativo prolongado = fundo) ou renda do short | 7 (D9eBFOl6utg, Y1r9iOOT6jw, bo8aNs6kX7E, 8xWRv2SjyR4, D1fyBUuDCX0, xybIvLoZ13s, tOeA) |
| P14 | Presos (delta por nível, net longs, longs no topo, shorts no fundo) marcam a borda que deve segurar ou o combustível do squeeze [J parcial] | 9 (ZYvYA4BlZ08, qVDSKTKdk6s, dDtPWolYUfQ, A1gnB7q3DkI, D1fyBUuDCX0, BUHBMQA5V_s, 1HGpjDC4dIA, xV58eHoPD3Y, tOeA) |

Registro neutro dos resultados (seção 8 das fichas), útil para calibrar as regras:
- **Stops curtos em zonas atingidas foram comuns**: planos com a leitura de direção certa foram stopados antes do movimento em pelo menos 7 casos:
  - short de 57,2–60k (bo8aNs6kX7E) e de 58k (8xWRv2SjyR4);
  - short de 58,2k (6Jgm69OajVY);
  - long do meio (A1gnB7q3DkI);
  - re-hedge de 76–77k (BUHBMQA5V_s);
  - long do reteste (xybIvLoZ13s);
  - short de 107,5k (5zfhzGDGsgo).
  - A camada mais distante da escada foi a que funcionou em 8xWRv2SjyR4 (61–62k).
- **Ordens mais distantes muitas vezes não executam**: ZYvYA4BlZ08, qVDSKTKdk6s, dDtPWolYUfQ, 0EDaN9oxWjI, bo8aNs6kX7E, D1fyBUuDCX0, qvboV9frI94.
- **Hedge mantido em rompimentos verdadeiros custou a perna seguinte**: dDtPWolYUfQ, NGidqawnffA, 5zfhzGDGsgo.
- **Compras no pânico com camadas terminaram perto do fundo**: bo8aNs6kX7E, D1fyBUuDCX0, xybIvLoZ13s (zona 84–82k), 6Jgm69OajVY, M6CODUH2Nlo (59–60k), 5zfhzGDGsgo (98–99k), tOeA (VAL).

### 5.3 Onde as fichas divergem

- **Risco por trade**: ≤1% (qvboV9frI94, Y1r9iOOT6jw) × "normal ~2%, até 3%" (1HGpjDC4dIA) × "1–5% conforme o operador" (8xWRv2SjyR4).
- **Stop curto × stop largo**: 2022–23 com stop curtíssimo e alvo longo (qVDSKTKdk6s, pXRniMaYcKc, YaPKT6WICE0) × "o stop pode ser largo, o tamanho se ajusta" (M6CODUH2Nlo, ICP com stop de 17%).
- **Toques na borda**: "o terceiro toque aumenta a chance de segurar" (xV58eHoPD3Y) × "cada novo toque aumenta a chance de desvio ou rompimento; 4º toque" (tOeA).
- **Esperar reação ou não**: esperar reação na zona, sem Fibonacci seca (ZYvYA4BlZ08, YaPKT6WICE0, regras 6 e 9) × entrar pequeno sem esperar confirmação quando o stop é barato (5zfhzGDGsgo, D1fyBUuDCX0).
- **Long no inverse**: "nunca comprar no coin-M, só vender" (bo8aNs6kX7E, 2024) × long e short no mesmo inverse (tOeA, qvboV9frI94, 1HGpjDC4dIA, 2026).
- **Livro de ordens**: "não é gatilho" (b6CT0OLH_2c) × "nuvens vendedoras no pivô virgem = short sem pensar" (BUHBMQA5V_s).
- **Peso de Elliott**: o Maroja o usa como mapa principal; o Shaka (1HGpjDC4dIA) diz que vale pouco diante do order flow.
- **OI e long/short**: desprezados em 2022 (ZYvYA4BlZ08), contexto central em 2025–26.

### 5.4 Difícil de codificar (julgamento humano)

- "Reação na zona", "energia compradora", "fundo fraco", absorção [J].
- Contagem de Elliott e escolha entre contagens; estrelas de probabilidade [J].
- Calço e nuvens no livro da Coinbase: exige livro L2 histórico, que o projeto não tem [J de dado].
- Divergência de CVD "com entrada de contratos" e leilão fracassado: codificáveis com dados de trades, mas com limiares não ditos.
- Sentimento e consenso de influenciadores [J]. O Fear & Greed é um proxy parcial.
- "Premium × desconto" do perfil de prazo longo: codificável, mas a janela varia (range de 149 dias, range 2020–21, semanas).

---

## 6. Onde o projeto atual diverge do perfil

Estado do projeto (13/09/2026):
- **Robô 9**: votação de indicadores + 5 fatias no linear 4h, em demo. Depois da correção do motor, fica ≈ 0 R e é indistinguível de sorte no holdout.
- **Robô 10**: jogo do range em 30m, no simulador. A jogada de borda com gestão Tradeiros deu −3,9 / −5,1 / +7,5 R (treino / validação / holdout), com ~15 trades por ano.
- **Robô 8**: grade de hedge no inverse. −3,4% em BTC desde 2019 com funding, vendido só 5–6% em média. A escada de 35% com recompra no POC/VAL e stop no rompimento perdeu BTC em todos os anos (−50,7% desde 2019; sem stop, −17,8%).
- **Scalp de fluxo**: sem vantagem.

As divergências abaixo explicam por que esses testes medem outra coisa que não o perfil.

| # | Perfil Tradeiros | Projeto hoje | O que mudar para ficar fiel |
|---|---|---|---|
| 1 | Resultado medido em **BTC acumulado da carteira** e em quanto se perde quando o BTC cai ("cai 10%, perco 3–4%") | Resultado em R por trade, em USDT, por robô isolado | Métrica principal: BTC final ÷ BTC inicial contra HODL, drawdown em BTC e em USD contra o BTC puro, por ano e por regime |
| 2 | **Uma carteira** com long estrutural e hedge variável (20–65%, extremos de 90–100%), long e short juntos, cada lado realizado na borda oposta | Robôs separados: 9 e 10 abrem trades independentes de compra ou venda; 8 só vende e fica 5–6% vendido em média | Simular a carteira inteira: exposição líquida alvo por regime (regras 30–31), com long e short no mesmo inverse |
| 3 | **Hedge variável por regime e localização**: sobe na resistência e perto do ATH, desce na correção com medo, no reset de OI e no pânico; duas camadas (stops de venda abaixo + vendas acima) | Escada fixa de 35% com stop no rompimento; grade sem noção de regime | Hedge com % por estado (descontado × esticado; bear × correção), camada passiva abaixo do fundo e realização a cada micropivô (regras 28–34) |
| 4 | Stop do hedge é **pedágio**: ser stopado devolve a exposição comprada, e o custo é pago pelo lucro do long | O stop no rompimento foi tratado como perda da estratégia de hedge isolada | Contabilizar o stop do short junto com o long que ele protege; medir a carteira, não o short |
| 5 | **Stop curto na invalidação e alvo ≥3 R**, aceitando acerto de 20–40%; o tamanho sai do stop | Robô 9: stop 1,5 ATR e alvo 3 ATR (2:1) no 4h, sem ligação com nível | Stop além do nível ou do pavio que invalida; alvo na borda oposta ou nível; filtro "só entra se ≥3 R até o alvo" (regra 19) |
| 6 | **Tirar o risco em 1:1 realizando 25–50% e stop no preço médio**; fechar se preencheu pouco | Gestão testada manteve o stop original depois da realização (regra do usuário) e não fecha entrada mal preenchida | Testar as duas versões lado a lado: stop original (usuário) × stop no preço médio (perfil 2026) e "fecha se < N fatias" (regras 22 e 24) |
| 7 | Sinal **responsivo** de valor: comprar VAL, vender VAH, nada no meio; rompimento só com aceitação e reteste | Robô 9 vota VWAP/TPO/VP/OB com sinal de rompimento (acima da VAH = compra), TPO de janela | O robô 9 não representa o método. Para o perfil, usar o motor do robô 10 (merge) como fonte de sinal (regras 1–8) |
| 8 | **Tamanho pela localização e pela estrutura**: 0,6% no meio, ≥1% nos extremos, mais mão depois de quebra de estrutura; zona passiva × reativa | Risco fixo por trade | Risco dependente de `p` no range e do estado da estrutura (regras 3, 10 e 11) |
| 9 | O jogo de borda é **uma parte** da carteira; o grosso do resultado nas fichas vem de comprar pânico em camadas, distribuir no repique e hedgear topos | Robô 10 testa a borda sozinha, com ~15 trades por ano | Testar a combinação carteira + hedge + bordas, não a borda isolada; incluir as jogadas de pânico (regras 12, 13 e 34) |
| 10 | Order flow de **contexto** nas bordas: calço da Coinbase, OI, net longs, funding, presos, leilão fracassado | Robô 10 tem filtro de presos (long/short de contas); scalp de fluxo usado como gatilho de tick | Manter fluxo como filtro de borda; somar reset de OI e funding como moduladores do hedge; o calço exige livro L2, que falta como dado |
| 11 | Multiprazo: valor de semanas (caro × descontado), merge de 10 dias e TPO do dia e da sessão | Robô 10 usa merge adaptativo; robô 9 usa janela | Camada de "prazo longo" (premium/desconto e distância do ATH) para decidir a % de hedge |
| 12 | Evento: ordens postas antes, realizar na hora do dado, operar contra a reação na borda | Sem tratamento de agenda nos robôs 9 e 10 | Flag de agenda (CPI, payroll, FOMC) para realizar ou ajustar antes do horário (regra 36) |

Cuidados ao testar essas mudanças (método do projeto):
- critério escrito antes;
- três períodos;
- custo real, incluindo o funding que o short recebe;
- régua de acaso com direção sorteada nos mesmos candles;
- resultado separado por ano e por regime, porque a carteira em BTC depende muito do ciclo (2022 × 2023–24 × 2025–26).

---

## 7. Lives usadas

| # | Data da live | Título curto | Link | Regime (compilado) |
|---|---|---|---|---|
| 1 | 2022-11-07 (listada 08/11) | Bitcoin para onde vai? Previsão para semana | https://www.youtube.com/watch?v=ZYvYA4BlZ08 | lateral (véspera da FTX) |
| 2 | 2022-11-21 | Bitcoin fraco ou pegadinha? | https://www.youtube.com/watch?v=I_zjWuQqn_s | queda (fundo de 2022) |
| 3 | 2022-12-07 | Bitcoin em dia confuso | https://www.youtube.com/watch?v=qOq7sPDo13o | lateral |
| 4 | 2022-12-23 (listada 24/12) | Whales Bar 009 — TPO, Order Flow | https://www.youtube.com/watch?v=qVDSKTKdk6s | queda (conteúdo de range) |
| 5 | 2023-01-14 | Whales Bar 011 — Sábado da Virada | https://www.youtube.com/watch?v=dDtPWolYUfQ | alta |
| 6 | 2023-05-05 | Análise do longo prazo — TPO, Elliott, ExoCharts | https://www.youtube.com/watch?v=pXRniMaYcKc | alta |
| 7 | 2023-07-28 (vídeo 29/07) | Novidades — análise ao vivo | https://www.youtube.com/watch?v=YaPKT6WICE0 | lateral |
| 8 | 2023-09-04 (vídeo 05/09) | Bitcoin alerta máximo! | https://www.youtube.com/watch?v=0EDaN9oxWjI | queda |
| 9 | 2024-01-10 | Será que o ETF vai flopar o BTC? | https://www.youtube.com/watch?v=NGidqawnffA | alta (ETF) |
| 10 | 2024-03-15 | Bitcoin em dia de queda | https://www.youtube.com/watch?v=D9eBFOl6utg | alta (topo de mar/24) |
| 11 | 2024-04-19 | Halving do Bitcoin | https://www.youtube.com/watch?v=Y1r9iOOT6jw | alta (halving) |
| 12 | 2024-04-25 | Estou comprando Bitcoin agora, porém... | https://www.youtube.com/watch?v=M6CODUH2Nlo | alta |
| 13 | 2024-07-10 | Ursos ligam alerta no Bitcoin | https://www.youtube.com/watch?v=6Jgm69OajVY | lateral |
| 14 | 2024-08-05 | RIP Bitcoin | https://www.youtube.com/watch?v=bo8aNs6kX7E | queda (crash) |
| 15 | 2024-08-06 | Atualização macro e meus alvos | https://www.youtube.com/watch?v=8xWRv2SjyR4 | queda |
| 16 | 2024-12-06 | Bitcoin liquidou a sardinhada | https://www.youtube.com/watch?v=A1gnB7q3DkI | alta (rompimento de 100k) |
| 17 | 2025-04-07 | Bitcoin destrói mercado em nova mínima | https://www.youtube.com/watch?v=D1fyBUuDCX0 | queda (tarifas) |
| 18 | 2025-06-25 | Onde vou comprar Bitcoin? | https://www.youtube.com/watch?v=5zfhzGDGsgo | lateral |
| 19 | 2025-10-10 | Será que o Bitcoin vai de Odete? | https://www.youtube.com/watch?v=b6CT0OLH_2c | lateral (liquidações de 10/10) |
| 20 | 2025-11-19 | Bitcoin em modo bear market? | https://www.youtube.com/watch?v=xybIvLoZ13s | queda |
| 21 | 2026-04-20 | Bitcoin no momento da grande decisão | https://www.youtube.com/watch?v=BUHBMQA5V_s | lateral (pós-topo de ciclo) |
| 22 | 2026-09-01 | Live trading — acumulação ou distribuição | link não disponível (id tOeA) | rótulo alta; conteúdo de range |
| 23 | 2026-09-03 (listada 04/09) | Live trading — VAL sustentou o preço | https://www.youtube.com/watch?v=qvboV9frI94 | rótulo alta; conteúdo de range |
| 24 | 2026-09-04 | A queda vem aí? — order flow ao vivo | https://www.youtube.com/watch?v=xV58eHoPD3Y | rótulo alta; conteúdo de range (payroll) |
| 25 | 2026-09-11 (publicada 12/09) | O mercado no caos, nós no plano | https://www.youtube.com/watch?v=1HGpjDC4dIA | rótulo alta; conteúdo de range (CPI) |
