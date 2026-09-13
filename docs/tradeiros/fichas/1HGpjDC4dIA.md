# Ficha — 1HGpjDC4dIA

## 1. Identificação
- **Título:** BITCOIN HOJE: o mercado no caos, nós no plano! Trading AO VIVO
- **Data:** live na sexta-feira 2026-09-11 (o Chaka diz "dia 11"); publicada em 2026-09-12. Dia do CPI às 9:30 de Brasília; FOMC na quarta seguinte.
- **Link:** https://www.youtube.com/watch?v=1HGpjDC4dIA
- **Duração:** ~4h05. Só o Chaka. BTC ~0:40–2:30; altcoins/ações ~2:50–3:55; o resto é chat e sermão contra operar dado econômico.
- **Regime BTC:** o histórico só vai até 2026-09-05; usando o último dia: "alta" pelo rótulo (ret60 +31,1%), preço 79.832, −36,0% do topo. Na live, o Chaka fala em ~54% de queda do topo de 126k (preço ~77k).

## 2. Leitura de contexto
- Range de ~3 semanas: comprando 76–75k e vendendo 80–82k (entradas citadas: short 79.986 e long 76.799). O preço tocou ~82k (semanal/mensal) sem quebrar a estrutura de baixa (topos descendentes): compradores sem força.
- No dia: o CPI levou o preço até pouco acima de 75.450 (zona de compra passiva), voltou forte até ~79k (VAH do range) e retornou ao POC do dia (~77,3k). Rotação completa VAL→VAH→VAL num dia.
- Formou um fundo ascendente e quebrou microestruturas (15m/4h), mas não o topo que sustenta a queda. Cenários: onda 2 para uma 5ª, ou ABC com topo em 82k e nova perna de baixa (0,618 da faixa até 90–91k ≈ 71k; long squeeze até 63k). Compara com a lateralização de fev/2023.
- Macro ignorada para o trade: não sabia o resultado do CPI.

## 3. Ferramentas e como usaram
- **TPO (30 min):** VAH e VAL do range; POC do dia (~77,3k) = compra; POC da sexta anterior 80.826 = zona de short (possível "front run" antes); abaixo de 75k há vazio porque ali houve só liquidação: próximo POC 71.651 e suporte 71.700. Regra: nunca shortar no VAL ou abaixo dele, a não ser que perca, construa volume embaixo e reteste por baixo.
- **Footprint/order flow:** delta do livro de +340 BTC nos fundos virou −400 BTC em ~1h ao chegar em 79k. Compra no spot americano (Coinbase) contra venda do varejo alavancado. Entre 76.440 e 75.880 houve 13 imbalances vendedores contra 2 compradores, com compras a limite absorvendo → shorts presos no fundo, squeeze e 8,4 mi liquidados. Depois: OI caindo (saídas no zero a zero), volume baixo → provável range local no fim de semana. Longs entraram no rompimento de 77.340 e no topinho de 78k e estavam sendo liquidados.
- **CME:** "caixas" de gap em 72.750 e 68.260 (alarmes para o domingo).
- **Elliott:** só para cenários (onda 2 x ABC; OCO como 1-5 + ABC; flat corrido). Declara a hierarquia: gestão de risco primeiro, depois TPO e footprint; Elliott bem depois — e diz que Elliott e SMC valem muito pouco diante do order flow.
- **Fibonacci:** saídas em 0,5 e 0,618 da queda; 0,618 como suporte provável de uma correção futura (71k).
- **Estrutura:** comprar mais depois da quebra de estrutura, mesmo mais caro, do que comprar mais barato sem quebra.

## 4. Operações
Tudo na conta coin-M (inverse), sem risco de liquidação, convivendo short (hedge) e long.
| # | Lado | Entrada | Stop | Alvo | Tamanho/obs. | Status | Min. |
|---|---|---|---|---|---|---|---|
| 1 | Short (hedge do range) | 78,75–80k (antes da live) | acima do topo | alvos abaixo (72, 68, 63k) | 12.350 USD | aberta | 0:41, 1:29 |
| 2 | Long (zona passiva) | já tinha 6.840; + 1.790 em 77.315 e + 1.790 em 76.980 | 75.929 | resistências acima | fracionado; chegou a 10.120 USD | EXECUTADA ao vivo (ordens preenchidas) | 0:41–0:42, 1:28–1:29 |
| 3 | Realização do short | ordem limitada no preço | — | — | 20% (2.590), ~USD 70 de lucro, quase o valor do stop do long | EXECUTADA ao vivo | 1:31–1:32 |
| 4 | Re-short | 3.000 em 78.500 e 6.000 um pouco antes do POC 80.826 | stop reduzindo 7.000 acima do topo ~82,8k (mantém 2.000) | queda até 72/68/63k | escada de venda | ordens POSTADAS | 2:17–2:19 |
| 5 | Long adicional (leitura de footprint) | 7.000 com ordens escalonadas no preço (~77,3k) | parcial abaixo do fundinho local, perda ~USD 22 | tira o risco em 1:1 (~1,5% com taxas) realizando 3.500; 3.500 em 0,5 e 3.500 na zona de 0,618; o resto corre | long total 17.000 | EXECUTADA ao vivo | 2:21–2:27 |
| 6 | Long reativo | abaixo de 75k só com pavio, presos e quebra de estrutura; compra o reteste | abaixo do pavio | — | mão maior = risco de 3% em vez de 2%, sem alavancar | cenário | 1:39–1:45 |
| 7 | Short de continuação | se perder a zona, construir volume abaixo e retestar por baixo | acima | — | — | cenário | 1:35 |
- Também: ETH long com risco já tirado (stop no fundo ascendente); BCH long (risco ~USD 30, alvo ~USD 180); LINK long com stop curto (risco ~USD 41–50 contra 400–500); alarmes em IBM (reteste de rompimento), XRP (TGP ~1,20) e SOL. Ficar de fora também é operar.
- Ele próprio diz que o certo seria tirar o risco na primeira resistência; ele tira mais acima.

## 5. Regras ditas
- Seguir o plano feito antes (agenda de segunda-feira): comprar suportes, vender resistências; dado econômico só marca a hora da volatilidade.
- Quando o consenso reage à notícia numa borda, operar contra: dado "bom" numa resistência → vende; dado "ruim" num suporte → compra.
- Zona passiva (suporte com ordens limitadas) x zona reativa (abaixo do suporte, só com reação, pavio e quebra de estrutura).
- Nunca shortar no VAL ou abaixo dele sem aceitação e reteste por baixo.
- Mais mão depois da quebra de estrutura; menos mão comprando fraqueza.
- Tirar o risco no 1:1 e subir o stop; realizar em 0,5/0,618; hedge coin-M realizado conforme o preço anda (short realiza na queda, long na alta).
- Risco normal ~2% por trade; nunca aumentar alavancagem.
- Esperar o preço vir ao nível (alarmes); ficar sem operar faz parte.

## 6. O que evitaram e por quê
- Operar o CPI/FOMC ou abrir live para o discurso do Fed.
- Colocar ordens de capital sério em 73–70k (abaixo do suporte não há calço; o preço pode parar em qualquer lugar).
- Shortar o ETH (mantém estrutura de alta) e entrar em XRP/SOL fora dos níveis.
- Linha de tendência "geométrica", figuras, e resumos de IA como forma de estudo.

## 7. Viés e invalidação
- **Viés:** neutro-operacional dentro do range; comprador na zona 77–75k no curto prazo, mas reconhece que a tendência maior segue de baixa enquanto não romper os topos (~82k).
- **Muda a leitura:** perder 75k com volume e retestar por baixo → vende e busca 71,7k/68k/63k; romper a estrutura acima de ~82k → compra mais agressiva nos retestes; 90–93k seria zona para vender.

## 8. O que o preço fez depois
- **Sem dado:** o CSV termina em 2026-09-05, antes desta live. Não é possível medir 1, 3, 7 ou 14 dias depois.
- Só o relato do próprio dia (não é CSV): o CPI levou o preço a ~75,45k, abaixo do stop de 75.929 citado mais tarde, e o Chaka conta que um dos longs da manhã foi stopado e o outro ficou; o preço voltou a ~79k, onde a zona de venda segurou, e retornou a ~77k. No fim da live não havia resolução do range: nenhum dos cenários de rompimento (acima de ~82k ou abaixo de 75k com reteste) tinha sido acionado.

## 9. Traços de perfil
1. Operar o range com as duas mãos ao mesmo tempo (short de hedge e long) em coin-M, realizando cada lado na borda oposta.
2. Execução por footprint e presos: entra onde o varejo agrediu contra ordens a limite, com stop curtíssimo, fracionado, e tira o risco no 1:1.
3. Disciplina de plano e aversão a operar notícia; paciência com alarmes e mão maior só depois de quebra de estrutura.
