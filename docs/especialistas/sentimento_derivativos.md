# Sentimento e derivativos para avisos de scalp e day trade — funding, OI, long/short, liquidações e carry

Autor: especialista-sentimento-derivativos (`.claude/agents/especialista-sentimento-derivativos.md`). Data: 20/10/2026.
Para quem lê: capital pequeno, scalp e day trade, sem robô. O que se quer é um **aviso** com lado, zona de entrada,
stop e alvo. Este documento diz o que o derivativo pode e o que não pode dar para esse aviso.

Fontes: `docs/tradeiros/perfil_por_regime.md` (2.2 e 3.4), `docs/CONSELHO_ESPECIALISTAS.md` (§3, §6),
`data/estudo_niveis_tpo_2_resumo.md` (H5), `data/historico/funding_bybit.json` (inverse 2018-11 a 2026-09, linear
2020-03 a 2026-09, 8 h), `lsr_bybit_1h.json` e `oi_bybit_1h.json` (2020-07 a 2026-10, 1 h), `fear_greed.csv`,
`BTCUSDT_binance_1d.csv`.

Três etiquetas:
- **MEDIDO** — número que já existe no projeto, com protocolo (controle sorteado, três períodos, custo).
- **EXPLORATÓRIO** — percentil ou retorno à frente que eu calculei hoje, em dados diários, **sem custo, sem stop,
  sem controle sorteado e sem corrigir por número de testes**. Serve para calibrar limiar e para matar ideia,
  não para aprovar nada.
- **HIPÓTESE** — o que ainda não foi medido.

Nada aqui promete lucro.

---

## 1. Diagnóstico em 8 linhas

1. **MEDIDO.** Como gatilho ou como filtro de borda em 15 min (estudo 2, H5): long/short contra a mediana de 30 d, OI subindo 6 h e funding "do lado" **não separam** VAL nem VAH de um preço sorteado (1 de 36 positivas, o complemento da hipótese, sem ★). O estudo de 11/09 (VAL segura 74% × 64% com presos) media outra coisa (chegar ao POC antes de perder o extremo, em 3 dias, range válido, 40 trades) e não virou sinal de entrada.
2. **MEDIDO.** Funding do hedge inverse rende 0,1–0,4%/ano porque o short fica pouco tempo aberto. Carry só vira renda se a posição ficar meses.
3. **MEDIDO (distribuição).** Funding linear da Bybit é o "neutro" 0,01%/8h **na mediana e no p75** (p50 = p75 = +0,0100%). Ele só sai do neutro nos extremos: p90 = +0,020%, p95 = +0,050%, p5 = −0,008%, p1 = −0,036% por 8 h. Ou seja: "funding" como variável contínua é quase sempre a mesma constante; só o extremo carrega informação.
4. **EXPLORATÓRIO.** Funding esticado (média de 3 dias ≥ p90, ≈ 30% a.a.) **não antecipa queda**: retorno de 5 dias à frente +0,6% (mediana) contra +0,3% em todos os dias. O que muda é a **amplitude**: 13,4% em 5 dias contra 8,7% (1,5×). Esticado é regime de alta volátil (2020–21 e mar/2024), não topo. **0 dias esticados em 2022, 2025 e 2026.**
5. **EXPLORATÓRIO.** Capitulação por funding (média de 3 d ≤ p5) deu +1,8% em 5 dias com 63% positivos contra +0,3% e 53% (118 dias), mas concentrada em 2020–22; reset rápido de OI (−15% em 7 d) foi +2,7% no treino e **−0,6% / −1,0% na validação e no holdout**. O sinal de fundo existe nos livros e nas lives; nos dados ele é raro e instável.
6. **EXPLORATÓRIO.** Long/short extremo contra a mediana (p90 = +31%, p10 = −26%) não inverte o preço: varejo "muito comprado" foi seguido de +0,8% em 5 dias. Fear & Greed ≤ 20: zero vantagem em 10 dias (+0,9% × +0,5%, 264 dias).
7. **Lição:** o derivativo diz **quem está pagando e quanto o mercado pode andar**, não **para onde**. No aviso ele entra como (a) regime que alarga stop e alvo, (b) veto (não vender fundo de capitulação, não comprar esticado sem nuvem/VWAP) e (c) renda estrutural, que é a única vantagem sem direção.
8. **Capital pequeno:** o carry linear somou 5,1% em 2025 e 1,6% em 2026 (até set). Para US$ 2.000, é US$ 30–100 por ano, abaixo do rendimento de stablecoin. A renda estrutural só volta a valer quando o funding passa do p90 por dias seguidos, o que não acontece desde mar/2024.

### Resposta curta às perguntas do usuário

| Pergunta | O que foi medido | Como usar no aviso |
|---|---|---|
| Funding | neutro em 75% do tempo; extremo não dá direção; alarga amplitude 1,5× (EXPL.) | **Regime "esticado"**: stop e alvo 1,5× maiores; venda só junto com nuvem + VWAP z ≥ 2 (proposta 1) |
| Open interest | OI subindo 6 h não separa borda (MEDIDO); reset −15%/7 d instável (EXPL.) | **Componente do fundo de capitulação** (proposta 2) e etiqueta no aviso ("OI subindo / caindo"), sem probabilidade |
| Long/short (presos) | não separa VAL/VAH em 1–2% (MEDIDO); extremo não inverte (EXPL.) | Só como **etiqueta** no aviso (presos a favor / contra). Não decide lado |
| Liquidações | nada coletado | Coletar primeiro (seção 3). Pico de liquidação = pavio, serve a **stop** (atrás do pavio) e a **alvo** (mapa de liquidez) |
| Fear & Greed | ≤ 20 sem vantagem em 10 d (EXPL.) | Só compõe o veto de fundo (proposta 2) |
| Carry | 10–18% a.a. nas lives; 5,1% (2025) e 1,6% (2026) nos dados | Renda estrutural condicional (proposta 3); hoje abaixo do custo de troca |

---

## 2. As 3 propostas com maior potencial ainda não medidas

Convenção: horário de cálculo é sempre **candle/pagamento fechado** (funding às 00/08/16 UTC já pago; LSR e OI da
hora fechada; mediana e percentil só com dados anteriores). R = distância da entrada média ao stop. Custo de ida e
volta 0,06% no perp (taker 0,055%, `core/backtest_engine.py`), 0,24–0,31% no par spot + perp.

### P1 — "Esticado" como regime de posicionamento (alimenta o aviso "topo contra nuvem" do especialista de fluxo)

- **Nome.** Regime ESTICADO (comprado) / ESTICADO (vendido) / NEUTRO.
- **Variável exata e regra (HIPÓTESE, limiares EXPLORATÓRIOS).** Três componentes, cada um em percentil da **própria história passada** (janela móvel de 365 dias, calculada à meia-noite UTC com dados até D−1, nunca o percentil de toda a série):
  1. `F3` = média dos últimos 9 pagamentos de funding linear Bybit (3 dias). Esticado comprado se `F3 ≥ p90` (hoje p90 = +0,027%/8h ≈ 30% a.a.; p95 = +0,050% ≈ 55% a.a.). Esticado vendido se `F3 ≤ p10` (hoje −0,001%; na prática "9 pagamentos sem positivo").
  2. `OI7` = OI da Bybit (BTC) ÷ OI de 7 dias atrás − 1. Combustível se `OI7 ≥ p90` (hoje +12,7%).
  3. `LSRd` = LSR de contas ÷ mediana de 30 d − 1. Varejo do lado se `LSRd ≥ p90` (hoje +31%) para comprado, `≤ p10` (−26%) para vendido.
  - **Regime ESTICADO = F3 no extremo E pelo menos um dos outros dois do mesmo lado.** Só F3 = "funding caro", etiqueta sem regime.
  - Multi-exchange ao vivo (`core/dados_derivativos.funding_multi`): se Binance e OKX não confirmarem o extremo (média das três abaixo de p90), rebaixar para "funding caro".
- **O que filtra ou dispara.** Não dispara nada. Qualifica o aviso do fluxo: "topo contra nuvem" só sai como **venda** quando o regime é ESTICADO comprado **e** o preço está a < 0,3% de uma parede vendedora persistente **e** VWAP z ≥ 2. Nos demais regimes a parede é informação sem lado.
- **Entrada / stop / alvo (do aviso do fluxo, com a correção do regime).** Entrada: 3 fatias limitadas entre a parede −0,15% e a parede +0,10% (abaixo da nuvem, não dentro). Stop: acima da parede + 0,20%, e **nunca menor que 1,5× o stop padrão** do aviso, porque no regime esticado a amplitude de 5 d é 1,5× a normal (EXPL.). Alvo: 1R tirar o risco; alvo final VWAP da sessão ou POC do dia, exigindo ≥ 2 R ou o aviso não sai.
- **Frequência (EXPL.).** Dias esticados comprados por ano: 27 (2020), 149 (2021), 0 (2022), 9 (2023), 37 (2024), 0 (2025), 0 (2026). Aviso raro: vêm em rajadas de semanas em mercado de alta e somem por anos. Esticado vendido (9 pagamentos ≤ 0): 11 dias em 6,5 anos.
- **De onde vem a vantagem (HIPÓTESE).** Quem paga 30–55% a.a. para ficar comprado é alavancado e tem stop; quando o leilão para contra uma parede, o funding é o custo que obriga a sair. A vantagem é de **assimetria de amplitude** (MFE 3,6% × MAE 3,6% em 5 d, contra 2,3% × 1,7%), não de direção.
- **O que a mata.** (a) Funding extremo = regime de alta: vender só por isso perde (ret 5 d +0,6%, EXPL.); (b) a parede some (spoof); (c) não há histórico do livro ainda, então a parte "nuvem" não é mensurável hoje; (d) com 0 dias esticados desde mar/2024, o aviso pode ficar dois anos mudo; (e) o "neutro" 0,01% concentra a massa, então percentil de janela curta (90 d) degenera: por isso 365 d.
- **Dados.** Já existem: funding linear e inverse, OI e LSR horários, candles. Falta: livro (coletor `scripts/coletor_livro.py` já começou), funding histórico Binance/OKX (gratuito, `fapi/v1/fundingRate`).
- **Como medir.** Antes do livro, dá para medir a metade do regime: para cada aviso de TPO/VWAP já gerado pelo calibrador, etiquetar regime e comparar (i) reação e (ii) amplitude (MFE e MAE em R) por regime contra o **regime sorteado** (mesma frequência, dias embaralhados) e contra **direção sorteada**; três períodos (2020–23, 2024–jun/25, jul/25–set/26); aprova só se a amplitude por regime ficar 2 EP acima do sorteio nos três, e só então se usa o 1,5× no stop. A parte "topo contra nuvem" espera 6–8 semanas de livro.

### P2 — Fundo de capitulação com regra objetiva (aviso de regime + compra do reteste)

- **Nome.** CAPITULAÇÃO (fundo) — veto de venda + compra do reteste.
- **Variável exata e regra (HIPÓTESE; cada componente EXPLORATÓRIO).** À meia-noite UTC, com dados até D−1, o dia D entra em regime CAPITULAÇÃO quando **três de quatro** valem:
  1. `F3 ≤ 0` (9 pagamentos seguidos sem funding positivo; ocorreu 11 dias em 6,5 anos) **ou** `F3 ≤ p5` da janela de 365 d (118 dias na série);
  2. `OI ≤ −30%` da máxima de 90 d **ou** `OI7 ≤ −15%` (reset; 441 e 140 dias na série);
  3. Fear & Greed ≤ 20 no dia anterior;
  4. preço fechou ≥ 20% abaixo da máxima de 60 dias (queda que justifica "capitulação"; sem isso funding negativo é só mercado de lado).
  - O regime dura 10 dias corridos a partir do último dia em que as condições valeram.
- **O que filtra ou dispara.** (a) **Veto**: nenhum aviso de venda sai em regime CAPITULAÇÃO (o Tradeiros: "fundo de ciclo ninguém vende"); (b) **compra do reteste**, abaixo.
- **Entrada / stop / alvo.**
  - Gatilho (candle de 4 h fechado): o primeiro fechamento de 4 h **acima da máxima** do candle de 4 h que fez a mínima do regime ("reclaim" do pavio). Nada de comprar a queda.
  - Entrada: 3 fatias limitadas no reteste, entre o fechamento do gatilho e a metade do candle de reclaim (zona de 0,5–1,0%), pesos 30/30/40 de cima para baixo; validade 6 candles de 4 h (24 h); sem reteste, o aviso morre.
  - Stop: mínima do regime − 1,0% (típico 3–5% do preço: é swing, não scalp; com risco de 0,5% do capital o tamanho é 10–15% do capital).
  - Alvo: 1R tirar o risco e stop no médio; alvo final POC do composto de 10 dias ou VAH de ontem, o que vier primeiro, exigindo ≥ 2 R. Alvo de tempo: 10 dias; sem alvo, sair no fechamento.
- **Frequência (EXPL.).** Três de quatro condições: estimativa de 2–6 episódios por ano em mercado de queda e zero em alta (combinação `F3 ≤ 0 e OI7 ≤ −10%`: 22 dias no treino, 1 na validação, 7 no holdout). Amostra total em 6 anos: 20–40 episódios. **Nunca vai ter n suficiente para o critério de 30 por período**; o veredito terá de ser por amplitude (MFE/MAE) e contra o sorteio, com a ressalva escrita.
- **De onde vem a vantagem (HIPÓTESE).** Quando o vendido paga para ficar vendido, o OI já saiu e o medo é público, quem podia vender já vendeu; o reclaim do pavio é o primeiro sinal de que o leilão abaixo falhou. É o que as fichas chamam de "sinais clássicos de fundo" (FTX, 57–58k), e o reteste é a postura declarada em jan/2023.
- **O que a mata.** (a) Instabilidade já vista: reset de OI deu +2,7% no treino e −0,6% / −1,0% depois (EXPL.); (b) F&G ≤ 20 sem vantagem; (c) 2026 teve 3 dias de 9 pagamentos negativos e o preço foi a 57,8k depois: a capitulação pode ser a do meio da queda; (d) stop de 3–5% com capital pequeno é um trade por mês, não scalp; (e) OI da Bybit em BTC cai também quando o preço sobe (mesmo dólar, menos BTC): usar OI em USD ou normalizar.
- **Dados.** Já existem: funding, OI, LSR, F&G, candles 1 d / 4 h. Falta: liquidações (para distinguir capitulação com cascata de capitulação sem; seção 3) e OI de Binance/OKX (a Bybit é uma fatia).
- **Como medir.** Regra escrita antes, incluindo o "três de quatro"; nenhum limiar iterado. Controles: (1) **direção sorteada** no mesmo gatilho de reclaim, (2) **reclaim sem regime** (mesmo gatilho de 4 h em dias sorteados de queda ≥ 20%). Três períodos, pessimista, custo 0,06%. Como n será pequeno, reportar intervalo de confiança e declarar "sem leitura" quando < 15 episódios no período, em vez de aprovar.

### P3 — Renda estrutural: carry condicional (spot + perp vendido) e o hedge que rende

- **Nome.** CARRY CONDICIONAL por regime de funding; variante HEDGE-QUE-RENDE para quem já guarda BTC.
- **Variável exata e regra (MEDIDO na distribuição, HIPÓTESE na regra).** `F3` (média de 9 pagamentos, linear). Liga quando `F3 ≥ p90` (hoje +0,027%/8h ≈ 30% a.a.); desliga quando `F3 < p50` (volta ao neutro 0,01%) **ou** depois de 30 dias. Histerese obrigatória: o teste sem histerese (ligar/desligar a cada pagamento ≥ 0,02%) deu 150 trocas em 6,5 anos e custo de 46% contra 53% recebidos (EXPL.): a troca come o carry.
- **O que faz.** Compra spot e vende o mesmo tamanho em perp linear (USDT) ou, para quem guarda BTC, vende inverse (coin-M) contra o BTC em carteira (o hedge do Tradeiros, que já é um carry).
- **Entrada / stop / alvo.** Entrada: as duas pernas a limite, no mesmo minuto, tamanho igual em BTC. Stop: não há stop de preço (posição neutra); há **stop de margem**: perp com 2× de alavancagem (margem = 50% do nocional), liquidação a +90%, e o spot cobre. Alvo: o funding recebido; saída quando `F3 < p50` ou 30 dias.
- **Conta de custo (capital US$ 2.000, 50% spot + 50% margem; MEDIDO nas taxas, EXPL. no funding).**
  - Ida e volta: spot 0,10% + 0,10%, perp 0,055% + 0,055% = **0,31%** a taker (0,24% com maker nas quatro pernas) sobre US$ 1.000 de nocional = US$ 2,40–3,10 por ciclo.
  - Carry bruto se ficasse ligado o ano inteiro (soma dos pagamentos linear): 2020 14,2%, 2021 38,3%, 2022 3,0%, 2023 8,9%, 2024 12,0%, 2025 5,1%, 2026 1,6% (até 11/09). Sobre US$ 1.000 de nocional: **US$ 51 em 2025, US$ 16 em 2026**.
  - Condicional (≥ p90 com histerese): tempo ligado ≈ 8–10% do ano; ganho nas janelas ≈ 0,8–1,5% do nocional por janela de 30 d (US$ 8–15), menos US$ 3 de custo. Desde mar/2024: **zero janelas**.
  - Referência: stablecoin em produto de rendimento da própria corretora paga na faixa de 3–6% a.a. sem troca de pernas (verificar no dia; não é número do projeto).
- **Frequência.** Janelas ≥ p90: 17 episódios no inverse (2019–24) e 14 no linear (2020–24), de 2 a 25 dias cada. Nenhuma em 2025–26.
- **De onde vem a vantagem (MEDIDO na história).** O comprado alavancado paga: funding positivo em 84% dos pagamentos (linear) e 81% (inverse) desde 2020; média 12,8% a.a. no linear. Vantagem sem direção. O que não é garantido é a **magnitude**: 2022, 2025 e 2026 pagaram menos que stablecoin.
- **O que a mata.** (a) Capital pequeno: o número absoluto não paga a atenção (US$ 16–51/ano); (b) troca de pernas sem histerese; (c) risco de execução das duas pernas em momentos diferentes (um minuto de descasamento num dia de 5% é mais que um mês de carry); (d) funding negativo por dias dentro da janela (2021-05: p5 = −0,016%/8h) vira custo; (e) no inverse, a margem está em BTC e o P&L do short em BTC varia com o preço (convexidade), o que o `backtest_hedge_tradeiros.py` já contabiliza.
- **Dados.** Já existem: funding linear e inverse completos; taxas em `core/backtest_engine.py`. Falta: base spot × perp (seção 3) para somar o prêmio de entrada/saída ao carry (entrar quando o perp está acima do spot e sair quando converge é a segunda metade do cash-and-carry e hoje ninguém mede).
- **Como medir.** Simulação pagamento a pagamento (8 h), regra escrita antes (p90 de 365 d, histerese p50, 30 d), custo 0,31% por ciclo, três períodos. Controle: **janelas sorteadas** com a mesma duração e número por ano. Reportar em US$ para o capital do usuário, não só em %. Aprova se líquido > rendimento de stablecoin nos três períodos; a leitura de hoje é que **não aprova em 2025–26**, e o documento deve dizer isso.

---

## 3. O que falta coletar (itens objetivos)

| # | Dado | Fonte gratuita | Como | Para quê |
|---|---|---|---|---|
| C1 | **Liquidações em tempo real** (lado, preço, quantidade) | Binance `wss://fstream.binance.com/ws/!forceOrder@arr` (sem chave); Bybit WS v5 tópico `allLiquidation.BTCUSDT` | Gravar cada evento em `data/historico/liquidacoes_<exchange>.csv.gz` (ts, lado, preço, qty); agregar por minuto; mesmo processo do `coletor_livro.py` | P2 (capitulação com cascata), stop atrás do pavio de liquidação, alvo no mapa de liquidez. Histórico não é gratuito (Coinglass exige plano); começa do zero hoje |
| C2 | **Base spot × perp** (prêmio) | Binance `fapi/v1/premiumIndexKlines` (histórico, 1 m–1 d, gratuito) e `fapi/v1/premiumIndex` ao vivo; Bybit `v5/market/premium-index-price-kline` | Baixar histórico completo em 1 h e 5 m (`scripts/baixar_derivativos.py`, mesma paginação) | P3 (entrar com prêmio, sair na convergência); "leilão fracassado" (preço sobe sem prêmio); regime esticado intraday (prêmio em percentil) |
| C3 | **Prêmio da Coinbase** (Coinbase spot − Binance spot) | Coinbase Exchange `GET /products/BTC-USD/candles` (1 m, gratuito, paginado em 300) | Baixar 1 m e 5 m desde 2020; diferença contra BTCUSDT Binance 5 m já baixado | Etiqueta "institucional comprando spot" das lives; filtro de P2 (fundo com prêmio Coinbase positivo) |
| C4 | **Funding e OI de Binance e OKX** (histórico) | Binance `fapi/v1/fundingRate` (desde 2019) e `futures/data/openInterestHist` (só 30 dias); OKX `api/v5/public/funding-rate-history` | Baixar o funding inteiro; OI acumular daqui para frente | P1 (confirmar extremo em 3 exchanges) e tirar a Bybit de ser a única fonte |
| C5 | **OI em USD** (além de BTC) | derivado: OI_BTC × preço de fechamento da hora | Calcular, não coletar | P2: separar reset de posições de queda do preço |
| C6 | **Vencimento de opções** (Deribit) | `public/get_book_summary_by_currency` (ao vivo), `public/get_volatility_index_data` (DVOL, histórico) | Gravar diário; marcar a última sexta do mês às 08:00 UTC | Etiqueta de "dia de evento" no aviso; sem probabilidade até medir |
| C7 | **Liquidações agregadas 24 h** (Coinglass) | já previsto em `core/dados_derivativos.liquidacoes`, exige `COINGLASS_API_KEY` | Só preencher a chave gratuita | Painel; não substitui C1 (sem histórico) |

Ordem: C1 e C2 primeiro (são as duas coisas que nenhum estudo pôde medir), C4 junto porque é um script de
um dia, C3 e C5 depois, C6 e C7 quando houver aviso que os use.

---

## 4. Ranking, por onde começar e risco principal

| Proposta | Nota 0–10 | Por quê | O que já pode ser medido hoje |
|---|---:|---|---|
| **P1 Esticado como regime** | **6** | Dado existe inteiro; encaixa no desenho do conselho (qualifica, não dispara); amplitude 1,5× é um efeito grande e testável; mas é regime raro (0 dias desde mar/2024) e **não dá lado** | Metade do regime (funding + OI + LSR) sobre os avisos de TPO/VWAP do calibrador, contra regime sorteado |
| P2 Capitulação | 4 | O sinal mais citado nas lives e o maior retorno à frente no exploratório, mas instável entre períodos, n de 20–40 episódios em 6 anos, stop de 3–5%: é swing de um trade por mês, não scalp | A regra "três de quatro" + reclaim de 4 h, com a ressalva de amostra; serve mais como **veto** de venda do que como entrada |
| P3 Carry condicional | 3 | Única vantagem sem direção e com história longa, mas em 2025–26 paga US$ 16–51 por US$ 1.000 e menos que stablecoin; sem janela ≥ p90 há 2,5 anos | Simulação completa em um dia; o resultado esperado é "não liga agora, liga quando F3 ≥ p90 voltar" |

**Começar por P1**, na forma que já é mensurável: etiquetar cada aviso que o calibrador gera com o regime
(ESTICADO comprado / vendido / NEUTRO, mais as etiquetas "funding caro", "OI subindo", "presos a favor/contra") e
medir **amplitude** (MFE e MAE em R) por regime contra regime sorteado, em três períodos. Se a amplitude 1,5×
sobreviver, o aviso passa a alargar stop e alvo nesse regime e o "topo contra nuvem" fica pronto para receber o
livro quando o coletor tiver 6–8 semanas. P2 entra como veto de venda sem probabilidade desde já (custo zero,
regra objetiva), e a compra do reteste espera as liquidações (C1). P3 fica escrito e desligado, com a regra de
religar.

**Risco principal:** confundir regime com direção. Todo número exploratório deste documento diz que funding
caro, varejo comprado e medo extremo **não** inverteram o preço; o que o derivativo entrega é amplitude, custo de
carregar e veto. Se o aviso de P1 sair como "venda porque o funding está alto", ele repete o erro que o estudo 2
já mediu (presos, OI e funding como filtro de lado: 1 de 36). O segundo risco é o n: P2 e P3 nunca terão as 30
decisões por período; qualquer % mostrado para eles tem de vir com o intervalo e a palavra "sem leitura".

---

## Apêndice — percentis calculados hoje (EXPLORATÓRIO, série inteira; para o aviso usar janela de 365 d)

Funding por pagamento de 8 h (linear, 2020-03 a 2026-09, n = 7.083): p1 −0,036%, p5 −0,008%, p10 −0,003%,
p25 +0,003%, **p50 = p75 = +0,010%**, p90 +0,020%, p95 +0,050%, p99 +0,168%. Positivo em 84%. Média 12,8% a.a.
Inverse (2018-11 a 2026-09, n = 8.570): p5 −0,016%, p50 +0,010%, p95 +0,050%; positivo em 81%.
Média de 3 dias (9 pagamentos): p5 −0,004%, p10 −0,001%, p90 +0,026%, p95 +0,051%.
Sequências de funding ≤ 0 no linear: 28 de ≥ 2 dias, 10 de ≥ 3 dias, 2 de ≥ 5 dias, máxima 20 pagamentos.

Long/short de contas Bybit (1 h, 2020-07 a 2026-10): p5 0,90, p50 1,44, p95 2,59; mediana por ano 1,11 (2020),
1,50 (2021), 1,21 (2022), 1,24 (2023), 1,92 (2024), 1,98 (2025), 1,44 (2026). Desvio contra a mediana de 30 d:
p10 −27%, p90 +31%. O nível absoluto muda de ano para ano; só o desvio contra a própria mediana é comparável.

OI Bybit (BTC): desvio contra a mediana de 30 d p10 −10%, p90 +15%; variação de 7 d p5 −18%, p95 +18%; de 30 d
p5 −25%, p95 +40%. OI a ≥ 30% abaixo da máxima de 90 d em **19% das horas**: o "reset de 30–50%" das lives é
comum, não raro, quando medido assim; precisa de OI em USD e de janela maior para virar sinal.

Retorno à frente (fechamento diário, sem custo, sem stop): todos os dias +0,34% em 5 d (53% positivos, n = 2.358);
F3 ≥ p95 +0,29% (51%, n = 118), amplitude MFE +3,6% / MAE −3,6%; F3 ≤ p5 +1,78% (63%, n = 118); OI −15% em 7 d
+2,65% treino / −0,63% validação / −0,97% holdout; LSR ≥ p90 +0,79%; F&G ≤ 20 em 10 d +0,86% contra +0,52%.
