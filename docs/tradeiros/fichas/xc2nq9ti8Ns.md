# Ficha — xc2nq9ti8Ns

## 1. Identificação
- **Título:** BITCOIN E ALTCOINS CORRIGINDO FORTE — ANÁLISE AO VIVO DO BTC
- **Data:** 2026-10-15 (quinta-feira; live começou 11:07 de Brasília, print do footprint às 12:30)
- **Link:** https://www.youtube.com/watch?v=xc2nq9ti8Ns
- **Duração:** ~2h54 (análise 0:07–0:44, 0:54–1:05, 1:21–1:53; o resto é chat, inverse/USDT, contadores). Só o Shaka (Maroja regularizando uma empresa). Encerrou às 2:48 por pressão alta (153/105) — ficou esperando a "volta" para comprar e não viu o fim.
- **Regime BTC no dia:** correção forte dentro de alta — fundo 57k (jul/26), máxima anterior 82k, topo 87k, preço em ~80–82k; tendência local de baixa desde 21/09 (topos e fundos descendentes); o preço tocou o 0,618 da perna 74k→87k abaixo de 80k de madrugada e voltou.

## 2. Leitura de contexto
- "Zona de compra" entre o fundo de 74k e o topo de 87k: quem comprou em cima tem stop aqui, "não precisa ser gênio" [07:48–08:24]. Quer aumentar long em todas as carteiras, mas mantém shorts de hedge que fecha por etapas na queda [23:22–24:02].
- Duas hipóteses abertas: (a) topo em 87k e correção de tudo desde 57k, com "respiros"; (b) correção para renovar máximas (90, 94, 100, 112, 126k) sem perder estrutura. Prefere (b), mas "tem pernada, segunda, terceira: grande probabilidade de ser o topo já" [19:48–22:11]. Conclusão operacional: short de proteção e long plantado, separados [22:34–25:31].
- Macro: CPI acima da previsão, guerra; "o gráfico vem antes; notícia péssima num suporte, ele supera" [34:09–35:30].
- Estrutura de curto prazo: fundo descendente, topo descendente, fundo descendente; "a maior probabilidade é mais um fundo descendente, mas eu acredito que vai quebrar; você tradea isso shortando o topo descendente" [38:12–38:38]. Topo descendente em 81.648 [40:32]. Rompeu às 0:54 ("Rompendo, mané... rompeu") = mudança de estrutura de mercado (MSB) [54:24–54:36].
- Quem está no controle: "a galera shortou, renovou a mínima três vezes, segurou os topos; quem comprou teve que stopar. Se quebra a estrutura, quem shortou tem que stopar e quem comprou realizou lucro e vai aumentar a mão para continuar stopando o lado contrário" [101:32–103:56]. "Dessa vez quem shortou teve que estopar e quem comprou pode realizar, recomprar e ir buscar essa galera" [105:21–105:38].

## 3. Ferramentas e como usaram
- **Fibonacci:** o fundo de madrugada segurou exatamente no 0,618 ("meia de Fibo") da perna 74k→87k; ele nem tinha visto, as ordens estavam 1% abaixo do fundo e abaixo de 80k por ser psicológico [63:05–64:16]. Golden pocket (0,618–0,666) como "segunda chamada" que não explica [32:03–33:01]. Alvos do rebote: 0,618 da queda e TGP; depois da quebra, comprar a partir de 0,5 do novo topo [55:50–56:16]; "a maioria das vezes forma fundo em 0,382/0,236 ou segura no ponto de partida" [77:26–77:52].
- **TPO (30 min):** POC de ontem = zona do short da véspera (23:30) [37:29–37:45]; VAL de ontem 82.702 como zona de short no rebote [83:11–83:16, 108:52–109:00]; POC 80.814 como entrada na volta [91:45–91:54]; "nódulo de volume" segurando o rebote e "depois não tem nada" até o 0,618 [84:11–84:18].
- **Footprint / order flow (BTCUSD.P Bybit, 30 min, com estatísticas de 3 min):** é a parte que importa desta ficha, detalhada em `docs/tradeiros/presos_footprint.md`. Resumo: vela de 85 mi de alta, outra de 31 mi com delta +1,12 mi, outra de 17 mi com delta −2,5 mi [111:03–111:16]; "galera comprando no topo e depois stopada embaixo" = o que ele quer shortar [111:26–111:35]; níveis com 2,33 / 1,44 / 2,52 mi de compra a mercado "e o preço respeitando" (não anda = absorvido) vs. 454k / 463k no topo da vela atual ("eu queria mais") [111:38–112:00]; "o preço se afasta, fecha embaixo e deixa aqueles caras presos; quando voltar, shorto em cima dessa galera" [112:01–112:42]; no 3 min, "forte liquidação ou entrada muito grande com o preço não respondendo, entro ali" [112:45–112:51].
- **Estrutura de mercado (Dow):** topos/fundos descendentes para saber quem manda; MSB como gatilho de compra "com muito poder de fogo, inclusive swing" [64:50–65:02].
- **Derivativos:** funding positivo (0,007, "quase zero a zero"; 0,001 é o normal); explica quem paga quem e 10–14% a.a. no BTC [137:02–139:43]. Carteira no inverse (coin-margin): long = BTC em cima de BTC, ganha duas vezes; stop real de um long inverse é maior que o nominal (61 vira ~160–170) [132:34–133:10].
- **Backtest:** "backtest num bear valida qualquer setup de short; mudança de característica do mercado invalida; eu não faço backtest, eu sou backtest" [151:00–155:20].

## 4. Operações
| # | Lado | Entrada | Stop | Alvo | Tamanho/obs. | Status | Min. |
|---|---|---|---|---|---|---|---|
| 1 | Long (inverse) | ordens limitadas 1% abaixo do fundo e abaixo de 80k, de madrugada; segurou no 0,618 | abaixo do fundo | 85k em 1–2 semanas (swing); position só acima de 85k | carteira 91.483 USD; risco 103 USD, quer chegar a 900 (1%) | EXECUTADA | 08:50–09:17, 18:10–19:13, 63:05–63:34, 98:11–98:51 |
| 2 | Short (hedge antigo) | 84k, segunda/terceira reabertura em retestes de resistência | — | fecha por etapas na queda, "a qualquer momento" | pagando 350 contra 100 de risco | posição aberta; no Smart Traders (USDT) fechado 100% | 23:22–24:02, 173:40 |
| 3 | Short novo | ~81.379, no topo descendente 81.648 ("vou caçar") | 63 USD (~81.750) | pagar o stop do long seguinte | 8.000 USD de contrato; "o lucro extra paga a próxima entrada" | STOPADA na quebra (−60) | 38:38–41:17, 57:25–58:01, 95:47–96:00 |
| 4 | Long (reteste pós-MSB) | 0,5–0,618 do novo topo; ou "pausa, volta" com rangezinho e stop no novo long | abaixo do fundo do reteste | 85k | aumentar a mão "sem apostar o toba" | cenário; esperou até 2:53 e não veio | 55:50–56:43, 76:15–78:25 |
| 5 | Short no rebote | VAL de ontem 82.702 / 0,618 da queda / TGP, depois de 30 min fechar vermelho e voltar; ou se perder 81.621 | acima da máxima | recompra embaixo | "shortaria de novo junto com vocês" | cenário | 82:50–83:16, 89:28–90:32, 108:22–110:04 |
| 6 | Long por zona de risco | agressivos: 0,5% de risco com 10–20% da mão na volta ao POC 80.814; sistemáticos: 0,618; conservadores: falha de rompimento / ponto de partida | "tudo stopado hoje se perder o fundo" | — | "eu treido os três" | cenário | 91:45–95:37 |
| 7 | Short por footprint | em cima do nível onde a galera comprou e ficou presa, no reteste | acima da vela dos presos | queda seguinte | "coisa que não está desenhada, baseada em order flow" | cenário/regra | 110:31–112:55 |
- Resultado na live: carteira foi de 91.000 para 92.574 USD (long inverse + BTC subindo "duas vezes") [73:44–74:43, 97:02–97:28].

## 5. Regras ditas
- Short na resistência mesmo bullish: "quem comprou vai realizar a cada resistência; o preço recua, você faz uma graninha e a invalidação fica" [58:03–58:21]. O lucro do short paga o stop do long seguinte [57:35–58:01].
- Stop é ferramenta: "stopo para entrar mais pesado numa entrada melhor; se não reverteu, não chegou no ponto importante" [67:19–68:48]. Sem DCA solto; DCA só dentro do range com narrativa e stop [85:42–85:50, 106:47–107:24].
- MSB em 30 min "com calma": na maioria das vezes forma fundo em 0,382/0,236 ou no ponto de partida; entra no reteste [77:26–78:25].
- Order flow autoriza entrada fora do plano: volume mudando, estatísticas de 3 e 30 min, presos no topo, liquidação forte com preço não respondendo [110:31–112:55].
- Posição grande só com capital que "vem de outros carnavais"; iniciante compra spot [27:12–29:58].

## 6. O que evitaram e por quê
- Comprar o rompimento sem a volta: "não adianta botar ordem agora; quando começar a quebrar e voltar, traço o topo e entro a partir de 0,5" [56:01–56:16].
- Apostar tudo no MSB: "já aconteceu de quebrar e cair mesmo assim" [77:02–77:26].
- Entrar na zona "só Fibonacci" sem pavio ou nível: prefere o VAL de ontem [109:07–109:33].
- Manter short parado: fecha por etapas e reabre em retestes.

## 7. Viés e invalidação
- **Viés:** comprador (acumulação para "sair muito comprado"), com hedge ativo; curto prazo: MSB feito, espera reteste para aumentar.
- **Muda a leitura:** perder o fundo da madrugada (abaixo de 80k) = stopa tudo o que entrou hoje; perder 74k = correção de tudo desde 57k.

## 8. O que o preço fez depois (Binance 1d)
- Pendente (candles disponíveis até 19/10/2026; +1d, +3d, +7d a preencher; +14d só após 29/10).

## 9. Traços de perfil
1. Hedge e long separados: short no topo descendente para "pagar" o stop do long do reteste; o stop é parte do plano, não derrota.
2. Gatilho = MSB em 30 min + reteste 0,5–0,618 em nível de TPO (POC/VAL de ontem), três zonas de risco (agressivo, sistemático, conservador).
3. Footprint como licença para entrar fora do desenho: procura agressão compradora grande em nível que o preço "respeita" e depois abandona, e shorta o reteste em cima dos presos.
