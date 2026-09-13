# Ficha: qvboV9frI94

## 1. Identificação
- **Título:** LIVE TRADING - VAL SUSTENTOU O PRECO
- **Data:** listada como 2026-09-04. Na fala, Shaka diz "hoje, quinta-feira, dia 3 de setembro", e o preço citado (~81 mil subindo, máxima nova) bate com 03/09. **A live foi em 03/09/2026 à tarde (termina ~17h36 BRT).**
- **Link:** https://www.youtube.com/watch?v=qvboV9frI94
- **Duração:** ~4h58
- **Apresentador:** Shaka
- **Regime do BTC (regimes_btc.json):**
  - 2026-09-03: alta; preço 81.270; ret60 +27,2%; −34,8% do topo.
  - 2026-09-04 (data listada): alta; 79.661; ret60 +30,5%; −36,1% do topo.
- **Preço durante a live:** saiu de ~78,8 mil para 80,5–81,4 mil entre 14h e 15h UTC (o "Bitcoin acordou"). Depois ficou em 81,0–81,8 mil, com máxima nova ~3:29 de live. A máxima do dia (82.300, 21h UTC) veio logo após o fim.

## 2. Leitura de contexto
- **TPO:** o preço veio buscar a VAL do range, "se sustentou" e fez nova rotação até a parte superior. Merge de ~11 dias define o range atual.
- **Range antes de tendência:** "a maior probabilidade é permanecer no range". Para mudar, precisa sair, testar e formar um range novo, provavelmente em **87–93 mil**.
- **Estrutura de ciclo:**
  - A tendência ainda é de baixa desde outubro/2025. Para virar alta, precisa quebrar ~82 mil e formar volume acima.
  - Desde outubro, três pernadas de impulso: "parece que a tendência mudou", possível fim de ciclo de baixa (sem certeza; alternativa em expanding flat).
- **Elliott:**
  - BTC em **onda 4 indo para a 5ª**; correção de até ~30% ainda cabe numa onda 4.
  - Topo por tempo por volta de **24/09** (até início de outubro), com possível ending diagonal.
  - Depois, queda rápida para 72 mil ou 69 mil (topo do ciclo anterior).
- **Sentimento:** muita gente voltando a comprar atrasada. Ele "torceria" por uma queda forte para comprar no pânico, mas acha improvável.
- **Níveis:** abertura semanal ~82.178; "nível chave" 82 mil (liquidações acima). Mapa de liquidez com massa até 92 mil acima; 49–51 mil e 41 mil abaixo; 158 mil muito acima.

## 3. Ferramentas usadas e COMO
- **TPO (primeiro a ser mostrado):**
  - Leitura das rotações: desvio abaixo da VAL só achou compradores; saída acima só achou vendedores (desequilíbrio); volta ao valor.
  - Área de valor dinâmica ("vai shiftando"). Merge de 11 dias para o range atual.
  - Naked POCs e pivôs semanais marcados.
- **Order flow:**
  - Livro da **Coinbase spot**: excedente vendedor de ~300 BTC no início, 445 BTC mais tarde. Realização de lucro na subida (delta negativo).
  - **Open interest caindo** na alta: short squeeze, "positivo, sem divergência".
  - **Net shorts** subiram de ~92 para ~235 milhões de contratos desde 21/08; **CVD** muito negativo. Muita gente vendida, combustível para squeeze.
  - Ressalva dele: net short/OI **não** é indicador de continuação.
  - **Liquidações** concentradas acima de 82 mil.
  - Volume caindo perto da máxima: possível **leilão fracassado** (failed auction), com preço parado ~1h em 5 min sem liquidações.
  - Stop hunt + venda do spot por quem é stopado no hedge (carry): ajuda a formar topo acima de 82 mil.
- **Elliott:** mapa e tempo (topo ~24/09). Explica que evita operar onda 4 e prefere comprar a onda 2 (retração de 0,5–0,786, invalidação clara na base da onda 1).
- **Fibonacci:** alvo de 0,618 no short de ouro; "golden zone" em SpaceX; justifica o 0,618 como exaustão comportamental.
- **VWAP:** ancorada no início ou no topo do movimento como "preço justo" (SpaceX 147–149; SanDisk "gravitando na VWAP desde o topo").
- **Hierarquia dita no fim:** TPO (o "pai"), depois order flow, depois Elliott, com gestão de risco "que poderia estar em primeiro".

## 4. Operações
**Carteira principal (~US$ 92 mil):**

| # | Lado | Entrada | Stop | Alvo | Tamanho/risco | Status | Minuto |
|---|---|---|---|---|---|---|---|
| 1 | Short BTC | Vendas pequenas na parte superior do range (0,06 + 0,06 + 0,03 BTC); total ~18 mil USD (~20% da carteira) | ainda sem stop ("quero ver se há falha de rompimento") | fechar embaixo | ~20% | Executado ao vivo | 0:13–0:14, 0:36, 1:50–1:52 |
| 2 | Short BTC (escada) | +6 mil em 83.848; +6 mil em 84.786; +8 mil em 85.723 (limitadas) | ~87 mil | recuo para testar 80–82 mil | chegaria a ~38% vendido; "máximo 1%" de perda | Ordens planejadas/postadas; **não preenchidas** (máx 82.300) | 1:50–2:00 |
| 3 | Long BTC inverse | Aberto antes na VAL; só 4.120 preenchido | — | realizar perto do stop dos shorts (~579 USD) | — | Parte realizada em ~79 mil (tirou o risco); realizações de 10% e depois 3.200 (~3:30 e ~3:52) | 0:36, 2:00–2:02, 3:30, 3:52 |
| 4 | Short BTC pequeno | "Último preço" ~81,6 mil, antes do stop (em tom de exemplo contra quem comprou em 80,9 mil) | — | — | pequeno | Executado | 3:52–3:53 |

- **Balanço declarado:** mesmo vendendo, a carteira ficaria ~50% comprada em BTC. Nas palavras dele, o short "não é aposta de queda, é proteção do ganho".

**Carteira coin-M nova (~US$ 16.659):**
- Short 8.990 (hedge de ~50% do BTC da conta; perdia ~57 USD) e long 3.370 (parte fechada).
- Ordens para aumentar o short em 81.640 e 82.186. Se formar topo, fecha o long, total ou parcialmente.
- Plano original: vender ~50% entre 72 e 74 mil e até 82 mil. Não compraria tudo em 65 mil numa conta nova.
- Minutos 2:18–2:23.

**Revisão dos trades de altcoins da live de 01/09:**
- **AAVE short:** bateu 1:1. Recomendou tirar 25% (ou 50% para os conservadores); ele fechou metade e levou o stop ao preço médio. Stopado no zero a zero, que chamou de "trade de sucesso" (2:26–2:30).
- **ARB short:** esqueceu de tirar o risco em 1:1 e foi stopado (~−40 USD) (2:30–2:33).
- **LTC e ADA:** preencheram poucas fatias (ADA: risco US$ 74 para ganhar ~400). Fechou tudo e manteve as ordens para reentrar no reteste (2:23–2:26).

**Ouro (XAU perp, OKX, 3×):**
- Short em **venda escalonada post-only** um pouco antes da abertura semanal (preço médio ~4.610).
- Stop acima do topo, risco ~US$ 40–48. Alvo no Fibonacci 0,618; opção de fechar metade e deixar o resto.
- Executado ao vivo (1:32–1:46).

**Pedidos do chat (só opinião):**
- SpaceX: compra na VWAP ancorada / Fibo 131 / VAL 135, alarme no gap + POC 158.
- AVAX: "meio do nada", sem trade.
- ETH: nada até 3.000 ou a VAL 2.864.
- ZEC: compra só em ~570 (VWAP).
- HYPE: caro.

## 5. Regras ditas explicitamente
- Citação: "Eu tenho que comprar no suporte e vender na resistência."
- Não se compra em resistência mesmo com viés de alta, nem se vende em suporte com viés de baixa. Existem regiões sem compra nem venda (o meio).
- A maioria dos rompimentos é falsa; comprar 80,9 mil por medo de ficar de fora está errado mesmo que suba.
- Stop = invalidação; perda máxima de 1% do capital da carteira por trade.
- Tirar o risco em 1:1 (25–50%) e levar o stop ao zero a zero. Zero a zero é trade de sucesso.
- Se a entrada preencheu pouco, fechar e esperar o reteste com as ordens paradas.
- Short no inverse é realização parcial/hedge, não aposta de queda; ir aumentando em escada nas resistências.
- Não shortar no USDT antes do nível para não tomar "stop de bobeira"; no inverse dá para ir vendendo aos poucos.
- Não operar onda 4; preferir a onda 2 (0,5–0,786).
- Seguir as contagens publicadas, não inventar onda 1 em gráfico curto.
- Diversificação e renda de trabalho acima de qualquer trade; não holdar alt sem stop.

## 6. O que evitaram e por quê
- Comprar BTC a 80,9 mil (esticado, FOMO, sem suporte).
- Short no USDT antes de 82 mil (stop de bobeira).
- Stop imediato no short da parte de cima: queria ver se havia falha de rompimento.
- 100% vendido na alta (resposta a seguidor): risco de perder a valorização se o preço for direto a 108 mil.
- Alts esticadas (ZEC, HYPE), ETH e AVAX no meio.
- Wyckoff, SMC e médias como ferramentas principais: muitos cenários e regras fracas.

## 7. Viés declarado e invalidação
- **Tático:** range. Topo local provável acima de 82 mil (stop hunt + realização), com volta para testar 80–82 mil. Vende em escada até ~85 mil.
- **Estrutural:** 5ª onda até 87–93 mil com topo ~24/09 a início de outubro. Depois queda forte para 72 mil / 69 mil.
- **Pessoal:** preferiria uma queda forte agora (para recomprar no pânico), mas acha improvável.
- **Invalidação:**
  - Shorts: stop acima de ~87 mil; aceitação acima dela significa ir para outro range (87–93 mil).
  - Leitura de alta: não passar de 82 mil e perder o range abre queda (ABC/expanding flat; liquidez em 49–51 mil e 41 mil).
  - Invalidação estrutural de alta: quebrar 82 mil e formar volume acima.

## 8. O que o preço fez depois (BTCUSDT Binance; o histórico vai até 2026-09-05)
- **Referência:** fim da live ~20h36 UTC de 03/09, preço ~81,5–81,8 mil.
- **Mesmo dia após a live:** máxima **82.300** às 21h UTC (tocou a abertura semanal ~82,2 mil e rejeitou); fechamento 81.270.
- **+1 dia (04/09):** máx 81.428 / mín 78.660 / fech 79.661.
- **+2 dias (05/09, último dado):** máx 80.200 / mín 79.442 / fech 79.832.
- **+3, +7 e +14 dias pela Binance:** sem dado.
- **Complemento, fonte diferente (Bybit BTCUSD inverse 1h, até 13/09 12h UTC):**
  - +3 dias (06/09): fechamento 80.300.
  - +7 dias (10/09): fechamento 76.495.
  - 04–13/09: máx 81.392 / mín 75.908 (11/09); último 76.708.
  - +14 dias sem dado.
- **Leitura factual:**
  - A escada de short em 83,8–85,7 mil **não foi atingida** (máxima 82,3 mil).
  - As ordens da coin-M em 81.640 e 82.186 ficaram ao alcance (82,3 mil).
  - O cenário tático (stop hunt/topo perto de 82 mil + volta para testar 80 mil ou menos) se confirmou: queda a 78,7 mil em 04/09 e a 75,9 mil em 11/09 (Bybit).
  - O "leilão fracassado" perto da máxima também bateu com o que veio depois.
  - A 5ª onda para 87–93 mil não aconteceu até 13/09 (sem dado para o fim de setembro).
  - A realização do long em 79–81,6 mil ficou acima dos preços dos dias seguintes.

## 9. Três traços de PERFIL
1. **Vende a resistência mesmo esperando alta:** o viés estrutural de 5ª onda não muda a execução. Short em escada nas resistências como hedge (20%, até ~38%), realização do long na borda superior, recompra só no suporte.
2. **Gestão ativa e padronizada:** tirar o risco em 1:1 com 25–50% e stop no zero a zero; fechar entradas mal preenchidas e esperar o reteste; limite de 1% por trade; prestação de contas pública dos stops.
3. **Decisão por valor e fluxo, Elliott como mapa:** TPO/merge dizem onde operar; OI, net shorts, CVD, livro da Coinbase e volume dizem se a borda segura (squeeze, leilão fracassado). Elliott dá direção, tempo (24/09) e invalidação. Anti-FOMO explícito.
