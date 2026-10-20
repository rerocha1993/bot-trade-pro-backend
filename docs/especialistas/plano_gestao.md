# Plano de gestão dos avisos — padrão Tradeiros para capital pequeno

Autor: especialista-gestao-tradeiros (`.claude/agents/especialista-gestao-tradeiros.md`). Data: 20/10/2026.
Fontes: os nove documentos de `docs/especialistas/` (tpo, elliott, fluxo, vwap, volume_profile, order_block,
fibonacci, regime, sentimento_derivativos), `docs/tradeiros/perfil_por_regime.md` (25 lives),
`.claude/agents/perito-btc.md` e `docs/CONSELHO_ESPECIALISTAS.md`.

Para quem lê: banca de 1.000 a 5.000 USDT no linear da Bybit, scalp e day trade, sem robô. O que o usuário
recebe é um **aviso** com lado, zona com as limitadas, stop, 1R e alvo, por indicador, e a probabilidade **só
quando houver medida honesta**. Hoje não há nenhuma: tudo que foi medido no projeto deu odds justas. As notas
abaixo são de **potencial**, não de expectativa de ganho. Nada aqui promete lucro.

Convenções: preço de referência 81.000 USDT (os exemplos usam esse preço; o aviso real usa o do momento).
R = distância do preço médio preenchido ao stop. Custo Bybit: maker 0,02%, taker 0,055%, slippage ~0,02% no
stop; ida e volta ~0,06% quando sai no alvo (limitada), ~0,095% quando sai no stop (a mercado). Nas tabelas o
custo em R é 0,06% ÷ stop; o acerto mínimo que paga a conta é p = (1 + custo) ÷ (R:R + 1), sem parciais.
Fatia mínima na Bybit: 0,001 BTC (~81 USDT). Isso limita a banca de 1.000 a **3 fatias** (20/30/50%); a de
5.000 comporta 5 (10/15/20/25/30%).

---

## 0. Regras fixas, valem para todos os planos

1. **Onde**: só no quartil permitido do composto de 10 dias (p < 0,25 compra, p > 0,75 venda, meio = nada). O
   nível não é gatilho (MEDIDO: 0/180 em 5 min, 3/117 em 15 min); o gatilho é um fato em candle fechado.
2. **Risco por trade**: day trade 0,5–0,7% da banca; scalp e avisos frequentes 0,25–0,4%; swing (4h) 1%. Nunca
   acima de 1%. No meio do range, metade; nos extremos, cheio.
3. **Tamanho** = risco em USDT ÷ distância do stop em %. Alavancagem só o que falta para caber; nos planos
   abaixo nenhum passa de 1× (nocional menor que a banca).
4. **Entrada**: limitadas post-only escalonadas, a fatia maior mais longe. Se preencheu pouco e o preço saiu,
   fecha e deixa as ordens para o reteste (regra 24 do perfil).
5. **Stop** = invalidação estrutural (extremo rejeitado, fundo da perna, início da onda 1), **sempre a mercado**.
   Piso de 0,4% de stop em qualquer aviso: abaixo de 0,25% o custo come tudo (MEDIDO no scalp de volatilidade).
6. **1R**: realiza 25–50% e leva o stop ao preço médio; zero a zero é trade de sucesso. Na banca de 1.000, 50%
   (a fatia mínima não deixa fracionar mais); na de 5.000, 25–33% e parciais em 0,5/0,618 ou no nível.
   Ressalva MEDIDA: "tirar o risco" sozinho cortou ganhadores (−0,04 R no 4h); com as fatias ficou +0,03 R.
   Por isso cada estudo roda com e sem a realização em 1R.
7. **Alvo** ≥ 2R no day trade (≥ 3R no swing); se o próximo nível está a menos de 2R, **o aviso não sai**.
8. **Validade**: cada aviso tem hora de morte para preencher e teto de duração da posição; sem 1R dentro do
   teto, fecha a mercado.
9. **Evento** (CPI/PCE/payroll 12:30, FOMC 18:00/18:30, vencimento Deribit): sem aviso novo de T−30 a T+30;
   posição aberta mantém o stop (não aperta), realiza parcial antes do dado se já está ≥ 0,5R; nunca aumenta mão.
10. **Fim de semana** (sábado 00:00 a segunda 00:00 UTC): sem aviso de scalp/day. Posição de day trade sem 1R
    tirado fecha sexta 20:00 UTC; com o risco tirado, pode ficar com stop no médio.
11. **Sem % medido**: o aviso sai com a frase "sem % medido" e "controle: —". Nunca um número inventado.
12. **Carteira**: em USDT não há hedge coin-M (o hedge deles com stop perdeu BTC em todos os anos, −50,7% desde
    2019). A venda em linear com stop substitui o "redear" para esta banca.

Custo em R por tamanho de stop (saída no alvo / saída no stop): 0,3% → 0,20 / 0,32 R; 0,5% → 0,12 / 0,19 R;
0,7% → 0,09 / 0,14 R; 1,0% → 0,06 / 0,10 R; 2,0% → 0,03 / 0,05 R.

---

## 1. Tabela mestra — todas as estratégias propostas

Freq. = estimativa do próprio especialista (HIPÓTESE). Dados: **P** = pronto no projeto (candle/perfil/derivativo
já existe; pode faltar código), **C** = falta coletar (livro, liquidações, negócios com lado). Nota = a que o
especialista deu (0–10).

| # | Especialista | Nome | TF | Gatilho (1 linha) | Stop típico | Alvo (R) | Freq. | Custo (R) | Acerto mín. | Dados | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TPO | E1 Abriu fora do valor de ontem e voltou (80%) | 30 min | 2 blocos de 30 min fecham dentro do valor de D-1 após abrir fora (00:00 ou 13:30 UTC) | 0,5–1,0% | 2–3 (VAL/VAH de ontem) | 1–3/sem | 0,08 | 31% | P | 6 |
| 2 | TPO | E2 Cauda no bloco de 30 min na borda | 30 min | Bloco toca borda vindo de ≥0,5% e fecha com cauda ≥0,30% e ≥60% da amplitude, no terço certo | 0,4–0,7% | 2–3 (POC/naked POC) | 3–6/sem | 0,11 | 32% | P | 5,5 |
| 3 | TPO | E3 A América contra a manhã | 30 min | Manhã em forma P/b; bloco da América (13:30–16:00) fecha através do POC da manhã; entrada no reteste | 0,5–0,9% | 2–3 | 1–2/sem | 0,09 | 31% | P | 5 |
| 4 | Elliott | U1 Setup de onda 2 (4h; 1h para day trade) | 4h / 1h | Cenário onda_2 vivo, onda 1 maior que 3x o ZigZag, candle entra em 0,5–0,618 sem fechar abaixo de 0,786; limitadas na zona | 4h 1,5–3%; 1h 0,8–1,5% | 3,7 (estrutural) / 7 (curto) | 4h 1–3/mês; 1h 3–8/mês | 0,03 / 0,06 | 22% / 13% | P | 6 |
| 5 | Elliott | U2 Elliott como veto e direção dos avisos de TPO/fluxo | 1h/4h/1d | Não gera entrada: veta (superciclo, 4h prob_bear ≥60%), dá inteiro/metade e alvo máximo | — | — | corta 30–40% dos avisos | — | — | P | 3 scalp / 5 day |
| 6 | Elliott | U3 Onda 5 esticada + VAH do composto + funding caro (venda) | 4h | Candle 4h fecha de volta abaixo da VAH após desvio, com funding ≥p80, OI subindo 24h, fase onda_5/correcao_a | 1–2% | 2,5–4 (POC; fundo da onda 4) | 1–3/mês em alta madura; 0 em queda | 0,04 | 25% | P | 5 |
| 7 | Fluxo | A Esticado contra nuvem (topo preso) | 1 min | VWAP z ≥2 + 2 de {OI 6h, funding, LSR, CVD perp}; parede pesada persistente a ≤0,3%; 1 min fecha abaixo da abertura com CVD caindo | 0,35–0,55% | 1,5–2,5 (VWAP; POC) | 1–3/sem | 0,13 | 38% | C (liquidações, negócios Coinbase/Bybit, OI 5 min, livro perp) | 6 |
| 8 | Fluxo | B Calço na borda (nuvem compradora sob o VAL) | 1 min | Parede ≥3x e ≥30 BTC a 0–0,5% abaixo do VAL, persistente 10 min antes da chegada; absorção no 1 min | 0,5–0,8% | 2–4 (POC; VAH) | ≤1/sem | 0,09 | 27% | C (idem; 6–9 meses) | 4 |
| 9 | Fluxo | C Cascata de liquidações + absorção (reversão do pavio) | 1 min | Liquidações 5 min ≥p97 + queda ≥1,5%/15 min + OI −2% + exaustão + absorção; reclaim do 1 min | 0,4–0,7% | 1,5–2,5 (metade do pavio; VWAP) | 1–3/sem | 0,11 | 37% | C (liquidações; retroteste Binance possível) | 5 |
| 9b | Fluxo | D Nódulo abandonado (presos pelo footprint; live xc2nq9ti8Ns) | 5 min / 30 min | Nódulo agressor num nível (vol ≥3× mediana da barra, ≥p90 de 48 barras, terço do extremo), barra fecha do outro lado (absorvido), 2 barras seguintes se afastam ≥0,3%/0,5% (abandonado); entrada no 1º reteste do nível, 1 min fecha contra com delta ≤0 | 0,3–0,6% | 1 (deles) / 1,5–2,5 (fechamento pós-abandono) | 5 min 2–5/dia; 30 min 1–3/dia | 0,13 | 57% (1R) / 38% (2R) | P (30 dias de negócios com lado + fetcher Bybit desde 2020; reforços C) | 5 |
| 10 | VWAP | V1 Reteste do preço justo (ancorada no pivô de 7 dias + quebra) | 1h / 15 min | 1º reteste da VWAP ancorada: 15 min toca [−0,5σ; +0,25σ] e fecha acima, no terço superior | 0,5–0,9% (teto 1,2%) | 2–3,5 (máxima do movimento) | 1–2/sem | 0,09 | 29% | P (falta âncora automática) | 6 |
| 11 | VWAP | V2 Esticado volta ao preço justo (VWAP é o alvo) | 15 min | ≥2 fechamentos acima de +2σ, OI +1% em 4h, funding > mediana 30d, sessão sem drive; 1º candle fecha abaixo de +2σ | 0,4–0,8% (teto 1,0%) | 2–3 (+1σ; VWAP) | 2–4/sem | 0,10 | 31% | P | 5,5 |
| 12 | VWAP | V3 Mudança de mão na VWAP semanal (régua de lado) | 1h | 48 h de um lado; 2 fechamentos de 1h do outro lado, o 2º além do 1º; reteste | 0,7–1,2% (teto 1,5%) | 2–3 (−1σ; −2σ) | 0,5–1/sem | 0,06 | 30% | P | 5 |
| 13 | VP | V1 Corredor de vazio (LVN caminho, HVN alvo) | 15 min | 4 fechamentos no HVN, depois 1 fechamento dentro do vazio a ≥0,10% da borda; entrada no reteste da borda | 0,4–0,8% | 2–3 (meio do vazio; HVN oposto) | 2–4/sem | 0,10 | 31% | P (falta código HVN/LVN como zona) | 6 |
| 14 | VP | V2 Reteste do bloco de presos (delta por nível) | 15 min | Bloco de delta ≤−25% em ≥3 bins; preço 2h acima; 15 min toca o bloco e fecha acima do topo | 0,4–0,8% | 2–3 (3–4 em bloco estreito) | 1–3/sem | 0,10 | 31% | C (histórico de negócios com lado; piloto nos 30 dias) | 6,5 |
| 15 | VP | V3 Volta ao POC do impulso (perfil ancorado) | 30 min / 1h | Impulso ≥2,5% e ≥12h com POC entre 0,382–0,786; recuo toca o POC e bloco de 30 min fecha acima | 0,6–1,2% | 2–3 (VAH ancorada; máxima) | 1–2/sem | 0,07 | 31% | P (falta VP ancorado) | 5 |
| 16 | OB | E1 OB qualificado em 1h (deslocamento + BOS + FVG) | 1h (4h direção) | Primeiro retorno à zona do OB: 1h toca o 50% e fecha acima do topo; 4h com BOS a favor | 0,8–1,5% | 2–4 (liquidez oposta) | 2–5/sem | 0,05 | 26% | P (falta motor swing/BOS/FVG) | 6 |
| 17 | OB | E2 Varredura de liquidez + volta (sweep + CHoCH 15 min) | 15 min / 1h | Candle 1h passa topo/fundo igual ou PDH/PDL em 0,05–0,8% e fecha de volta; CHoCH 15 min em ≤8 candles; entrada no OB 15 min | 0,5–1,0% | 2–3 (liquidez oposta) | 1–3/sem | 0,08 | 31% | P (mesmo motor de E1) | 7 |
| 18 | OB | E3 Paredes do livro como zona passiva | 5 min | Faixa ≥3% do livro em ≥2 exchanges, persistente 30 min; 5 min fecha de volta sem a parede sumir | 0,25–0,4% | 2 (parede oposta) | 1–3/dia | 0,18 | 39% | C (≥90–180 dias de livro + negócios) | 4 |
| 19 | Fibonacci | E1 Escada 0,5–0,786 depois de quebra de microestrutura | 15 min (1h variante) | 15 min fecha acima do último pivô de alta do ZigZag 5 min; 5 limitadas 0,50 a 0,786 na perna do ZigZag 15 min | 0,4–1,2% (≈0,33 L + 0,10%) | 1,7 (reteste 1,0) / 3,3 (1,618) | 1–2/dia em tendência; 0 em dia morto | 0,10 | 41% / 26% | P | 6 |
| 20 | Fibonacci | E2 Régua de alvos e parciais (0,5 / 0,618 / 1,618) | o do aviso | Não gera entrada; dá 1R, parciais ≥1,5R e alvo final ≥2R para todos os avisos | — | ≥2 por construção | a dos avisos | — | — | P | 7 |
| 21 | Fibonacci | E3 Perna morta (quem comprou 0,5–0,786 ficou preso) | 15 min | Zona 0,5–0,786 tocada e 15 min fecha abaixo de 1,0; venda no reteste 0,70–0,886 | 0,2–0,6% (≈0,2 L) | 2,3 (−0,272) / 4 (−0,618) | 0–1/dia | 0,15 | 29% | P | 5 |
| 22 | Fibonacci | Fibonacci de tempo; log × linear | semanal+ | Fora da escala de day trade | — | — | — | — | — | — | 2 |
| 23 | Regime | F1 Tipo de dia pela 1ª hora (R/V liberam bordas; A/D proíbem) | 1h → dia | Filtro declarado às 01:00 e 14:30 UTC: P (dentro/fora do valor de D-1), IB/ATR_d por tercil, eficiência da 1ª hora | — | — | corta ~50% dos toques | — | — | P (rig do estudo 2) | 7 |
| 24 | Regime | F2 Volatilidade como seletor de R (stop em ATR) | 15 min | Filtro: R = k × ATR(100) com k em {2, 3, 4}; proíbe tipo X | — | — | igual | — | — | P | 5 |
| 25 | Regime | F3 Superciclo como filtro de lado do intradiário | 1d → dia | Filtro: estado do superciclo em D-1 decide se só compra, só vende ou nada | — | — | corta ~metade | — | — | P | 6 |
| 26 | Regime | Dia de evento com reclassificação pós-dado; compressão (C) → rompimento com bloco fechado | 30 min | Filtros; dependem de tabela estática de eventos | — | — | ~15% dos dias úteis / ~10% | — | — | P (falta tabela de eventos) | 4 / 3 |
| 27 | Regime | Pós-expansão (X) → reversão; sessão; fim de semana; Kaufman/ATR de core/regime.py | — | MEDIDOS negativos ou sem separação; ficam só como prudência | — | — | — | — | — | — | 2 / 2 / 2 / 1 |
| 28 | Derivativos | P1 Esticado como regime de posicionamento | 8h / 1h | Não dispara: F3 ≥p90 (365 d) + OI7 ≥p90 ou LSRd ≥p90; alarga stop e alvo ×1,5 e qualifica o "topo contra nuvem" | ×1,5 do aviso-base | o do aviso | 0 dias esticados desde mar/2024 | — | — | P (metade); C (nuvem) | 6 |
| 29 | Derivativos | P2 Capitulação (veto de venda + compra do reclaim em 4h) | 1d / 4h | 3 de 4: F3 ≤p5, OI reset, F&G ≤20, preço −20% da máx. 60 d; gatilho = 4h fecha acima da máx. do candle da mínima | 3–5% | ≥2 (POC do composto) | 2–6/ano | 0,015 | 29% | P (liquidações faltam) | 4 |
| 30 | Derivativos | P3 Carry condicional (spot + perp vendido) | 8h | Liga com F3 ≥p90, desliga <p50 ou 30 dias; sem stop de preço | margem | funding | 0 janelas desde mar/2024; US$ 16–51/ano por 1.000 | 0,31%/ciclo | — | P (falta base spot×perp) | 3 |

Leitura da tabela: **nenhuma linha tem número medido a favor**. As 22 estratégias com entrada própria se
dividem em 15 com dado pronto (podem ser medidas nas próximas semanas) e 7 que esperam coleta (livro,
liquidações, negócios com lado; a D do fluxo é a única de fluxo medível hoje). As 9 restantes são filtros ou réguas que só valem em cima de um aviso.

---

## 2. As 6 de maior potencial — plano de trade completo no padrão Tradeiros

Critério de escolha: vantagem estrutural plausível (fato novo, não o nível sozinho) × frequência que cabe em
day trade × R:R líquido do custo × viabilidade com 1.000–5.000 USDT (stop ≥ 0,4%, fatias acima do mínimo, sem
alavancagem) × facilidade de medir com o dado que existe. Ficaram de fora por falta de dado as estratégias A, B e C do fluxo, o
VP2 (delta) e o OB3 (paredes), que são as mais parecidas com o que o Tradeiros faz ao vivo, mas que não podem
ser medidas antes de 2027. Elas entram na seção 4 como "coleta já".

As escolhidas: **TPO E1**, **OB E2**, **Fibonacci E1**, **TPO E2**, **Fluxo D** (presos pelo footprint, entrou
depois da live xc2nq9ti8Ns: é o único ingrediente de dentro do candle com dado já disponível) e **Elliott U1**
(redesenhado pela live TZND78d0dVY). A VWAP V2 saiu das seis e fica como plano reserva no apêndice.

Tamanhos calculados com o stop típico de cada uma; o aviso real recalcula com o stop do dia. Nocional = risco ÷
stop; BTC = nocional ÷ 81.000.

### 2.1 TPO E1 — "Abriu fora do valor de ontem e voltou" (regra dos 80%)

| Item | Plano |
|---|---|
| Contexto | Dia (00:00) ou América (13:30 UTC) abre fora da área de valor de D-1; composto de 10 dias inteiro; valor de ontem não é fatia fina no extremo do composto; largura VAH−VAL ≥ 2× o stop (senão não avisa). Tipo de dia do regime = **V** (é o mesmo evento). |
| Gatilho | Fechamento do 2º bloco de 30 min consecutivo dentro do valor de ontem (mais cedo: 01:00 ou 14:30 UTC). |
| Zona (venda, abriu acima) | 3 limitadas post-only: VAH − 0,10% (20%), VAH + 0,02% (30%), VAH + 0,15% (50%). Médio ≈ VAH + 0,06%. Compra espelhada no VAL. Banca de 5.000: 5 fatias 10/15/20/25/30% na mesma faixa. |
| Risco | 0,5% da banca (day trade). Nos extremos do composto (p < 0,15 ou > 0,85), 0,7%. |
| Stop | Máxima da excursão fora do valor + 0,10%, a mercado. Típico 0,7% (0,5–1,0%). |
| Tamanho (stop 0,7%) | Banca 1.000: risco 5 USDT → nocional 714 USDT = **0,0088 BTC** (fatias 143/214/357 USDT). Banca 5.000: 25 USDT → 3.571 USDT = **0,044 BTC**. Alavancagem: nenhuma (0,7× da banca). Com stop de 1,0%: 500 / 2.500 USDT. |
| 1R | Preço médio − 0,7%. Realiza 50% (banca 1.000) ou 33% (5.000), stop no médio. O POC de ontem costuma cair em 1–1,8R: é o lugar natural de tirar o risco. |
| Alvo e parciais | Alvo final = VAL de ontem (2–3R). Naked POC no caminho vira 1º alvo. Banca 5.000: parcial de 25% no POC, resto no VAL. Sem nível a ≥ 2R, não avisa. |
| Validade | 4 blocos (2 h) para preencher; posição com teto de 24 h; sem 1R em 24 h, fecha a mercado. |
| Sessão | Variante América (14:30 UTC) é a principal; variante 00:00 UTC medida à parte. Sem aviso de sábado a segunda 00:00. |
| Evento | Dado às 12:30/14:00 dentro da janela de 2 h: o aviso não sai. Posição aberta antes do FOMC (18:00): parcial se ≥ 0,5R, stop fica. |
| Custo | 0,06 / 0,7 = **0,09 R** no alvo (0,14 R no stop). Acerto mínimo com 2,5R: **31%** (2R: 37%; 3R: 27%). |
| Frequência | 1–3 avisos/semana. ~100/ano × 0,09 R = ~9 R/ano de custo = 4,5% da banca por ano se o acerto for o do sorteio. |
| O que o faz perder primeiro | Dia de tendência que reentra e sai de novo (falsa reentrada); área de valor estreita (< 0,8%); e o parente H2a (desvio confirmado no composto) reagiu em 25% no holdout. |

Modelo de Telegram (6 linhas):

```
TPO E1 | VENDA | sem % medido | 20/10 14:30 UTC
Abriu acima do valor de ontem, 2 blocos de 30 min fecharam dentro (VAH 81.420 · POC 80.600 · VAL 80.200)
Zona: 81.340 (20%) · 81.440 (30%) · 81.540 (50%) limitadas post-only | vale até 16:30 UTC
Stop: 81.950 a mercado (máx. da excursão +0,10%) = 0,59% | risco 0,5% → 0,0104 BTC (banca 1.000) · 0,052 BTC (5.000)
1R: 80.990 → realiza 50%, stop no médio | alvo 1: POC 80.600 (1,8R) | alvo final: VAL 80.200 (2,6R)
Tipo de dia: V | evento: nenhum | controle: — (a família "saiu e voltou" deu sorteio em 15 min)
```

### 2.2 OB E2 — "Varredura de liquidez + volta" (sweep de topo/fundo igual, CHoCH em 15 min)

| Item | Plano |
|---|---|
| Contexto | Liquidez = topos iguais de 1h (≥ 2 swings a ≤ 0,2%), máxima de ontem ou da semana passada. Só varredura **contra** a direção de 4h ou no extremo do range de 4h; dentro do quartil permitido do composto. |
| Gatilho | Candle de 1h passa o nível em 0,05–0,8% e fecha de volta (ou o seguinte fecha); CHoCH em 15 min (fechamento abaixo do último fundo de swing de 15 min) em ≤ 8 candles. O aviso nasce no fechamento do CHoCH. |
| Zona (venda) | OB de 15 min = último candle de alta antes do impulso do CHoCH, zona [abertura, máxima]. 3 limitadas: abertura (20%), 50% da zona (30%), 75% em direção à máxima (50%). Médio ≈ 55% da zona. |
| Risco | 0,5% da banca. Se a liquidez varrida for a máxima da semana passada, 0,7%. |
| Stop | Máxima da varredura + 0,10%, a mercado. Típico 0,75% (0,5–1,0%). |
| Tamanho (stop 0,75%) | Banca 1.000: 5 USDT → 667 USDT = **0,0082 BTC** (133/200/333). Banca 5.000: 25 USDT → 3.333 USDT = **0,041 BTC**. Sem alavancagem. |
| 1R | Médio − 0,75%. Realiza 50% / 33%, stop no médio. |
| Alvo e parciais | Liquidez oposta ≥ 2R: fundos iguais de 1h, mínima de ontem, naked POC, VAL do composto, FVG de 1h não preenchido. O mais próximo a ≥ 2R é o alvo final; se houver dois, parcial de 25% no primeiro. |
| Validade | 16 candles de 15 min (4 h) para preencher; posição de 2–12 h; teto 24 h. |
| Sessão | Qualquer dia útil; Europa e América concentram as varreduras de PDH/PDL. Sem fim de semana. |
| Evento | Varredura feita pelo dado (T±30) não conta: é pavio de notícia, não liquidez tomada. |
| Custo | 0,06 / 0,75 = **0,08 R** (0,13 R no stop). Acerto mínimo com 2,5R: **31%**. |
| Frequência | 1–3/semana. ~100/ano × 0,08 R = ~8 R/ano = 4% da banca a 0,5% de risco. |
| O que o faz perder primeiro | Varredura que é rompimento (4h a favor): o preço fecha acima e segue. Três parâmetros (0,8%, 8 candles, 0,2%) são três convites a sobreajuste; o CHoCH que chega tarde faz a entrada a mercado ser 1R pior que a do reteste. |

Modelo de Telegram:

```
OB E2 | VENDA | sem % medido | 20/10 09:45 UTC
Varreu a máxima de ontem 82.100 (máx. 82.410, +0,38%) e fechou de volta; CHoCH 15 min em 81.780
Zona (OB 15 min 81.900–82.150): 81.900 (20%) · 82.025 (30%) · 82.090 (50%) | vale até 13:45 UTC
Stop: 82.490 a mercado (máx. da varredura +0,10%) = 0,56% | risco 0,5% → 0,0110 BTC (1.000) · 0,055 BTC (5.000)
1R: 81.575 → realiza 50%, stop no médio | alvo: fundos iguais 1h 80.950 (2,4R) | naked POC 80.600 (3,1R)
4h: lateral (permite) | evento: CPI 12:30 → sem aviso novo 12:00–13:00; parcial antes se ≥0,5R | controle: —
```

### 2.3 Fibonacci E1 — "Escada 0,5–0,786 depois de quebra de microestrutura"

| Item | Plano |
|---|---|
| Contexto | Preço no terço de baixo do composto (compra) ou Elliott 15m/1h permitindo (não é onda 4 nem correção recém-iniciada). Perna L = do último pivô de baixa confirmado do ZigZag ATR 15 min (fator 2,0) até a máxima depois da quebra, congelada no gatilho. Só avisa se L ≥ 0,8%. |
| Gatilho | Candle de 15 min fecha acima do último pivô de alta do ZigZag de 5 min (fator 1,0) feito depois do fundo: a quebra de microestrutura. |
| Zona | Banca 5.000: 5 limitadas em 0,50 / 0,572 / 0,643 / 0,714 / 0,786 da perna, pesos 10/15/20/25/30%. Banca 1.000: 3 limitadas em 0,50 / 0,643 / 0,786, pesos 20/30/50%. Médio ≈ 0,67 L. Se o preço fizer máxima nova antes da 1ª fatia, refaz a perna uma vez; na segunda, morre. |
| Risco | 0,5% da banca sobre a escada inteira. Se preencheu só 1–2 fatias, o risco real é proporcional. |
| Stop | 1,0 da perna (o pivô de baixa) − 0,10%, a mercado. Do médio: ≈ 0,33 L + 0,10%; com L de 1,5–2,5%, **0,6–0,9%** (0,4–1,2%). |
| Tamanho (stop 0,6%) | Banca 1.000: 5 USDT → 833 USDT = **0,0103 BTC** (3 fatias 167/250/417). Banca 5.000: 25 USDT → 4.167 USDT = **0,051 BTC** (5 fatias 417/625/833/1.042/1.250). Sem alavancagem. |
| 1R | ≈ 0,34 L acima do médio (perto de 0,382–0,236 da perna). Realiza 50% / 33%, stop no médio. |
| Alvo e parciais | Parcial de 25% no reteste do topo (1,0 da perna, ≈ 1,7R). Alvo final na extensão 1,618 (≈ 3,3R). Se Elliott entrega invalidação e alvo, prevalecem. Resto com stop atrás do último pivô de baixa do ZigZag 15 min. |
| Validade | 8 candles de 15 min (2 h) para preencher; se preencheu pouco e o preço saiu, fecha no reteste do topo. Posição: teto 24 h. |
| Sessão | Dias úteis; funciona em dia de tendência (tipos A/D do regime); em dia R/C a perna é um ponto do range: o aviso não deve sair. |
| Evento | Sem aviso em dia de CPI/FOMC entre T−30 e T+30; a perna feita pelo dado não vale (volume de pânico). |
| Custo | 0,06 / 0,6 = **0,10 R** (0,16 R no stop). Acerto mínimo: **41%** se só até 1,0 (1,7R); **26%** até 1,618 (3,3R). |
| Frequência | 1–2/dia em dia de tendência, 0 em dia morto. ~250/ano × 0,10 R = ~25 R/ano = **12,5% da banca** em custo a 0,5% de risco: é a mais cara de operar sem vantagem. |
| O que o faz perder primeiro | Dia de queda em que cada reteste é venda (regra 16: mínima renovada sem máxima renovada → não compra); perna escolhida pelo ZigZag que ninguém opera; escada que preenche inteira só quando o preço vai furar 1,0 (o pior médio no pior dia). O parente sem quebra em 5 min reprovou (MEDIDO). |

Modelo de Telegram:

```
FIBO E1 | COMPRA | sem % medido | 20/10 15:15 UTC
Quebra de microestrutura 15 min (fechou acima do pivô 5 min 81.300); perna 79.900 → 81.650 (L 2,2%)
Escada: 80.775 (0,50 · 20%) · 80.525 (0,643 · 30%) · 80.275 (0,786 · 50%) | vale até 17:15 UTC
Stop: 79.820 a mercado (1,0 da perna −0,10%) = 0,78% do médio | risco 0,5% → 0,0079 BTC (1.000) · 0,040 BTC (5.000)
1R: 81.080 → realiza 50%, stop no médio | parcial 25% no topo 81.650 (1,9R) | alvo 1,618: 82.730 (3,6R)
Composto: terço de baixo | Elliott 1h: não é onda 4 | tipo de dia: A | evento: nenhum | controle: —
```

### 2.4 TPO E2 — "Cauda no bloco de 30 min na borda" (rejeição vista)

| Item | Plano |
|---|---|
| Contexto | Preço chega de longe (≥ 0,5% nas últimas 4 h) numa borda do mapa: VAL/VAH do composto, VAL/VAH de ontem, naked POC. O nível tem de estar no quartil de fora do composto. Range com 3–4 toques na mesma borda: cautela (não é filtro, MEDIDO que não há gradiente). |
| Gatilho | O bloco de 30 min que toca o nível fecha com cauda ≥ 0,30% do preço e ≥ 60% da amplitude, fechamento do lado certo do nível e no terço certo do bloco. |
| Zona (compra) | Do fechamento do bloco até fechamento − 50% da cauda; 3 limitadas: fechamento (20%), meio (30%), fechamento − 50% da cauda (50%). |
| Risco | **0,4% da banca** (é o aviso mais frequente; o custo por trade é maior). Nos extremos do composto, 0,5%. |
| Stop | Extremo da cauda − 0,10%, a mercado. Típico 0,55% (0,4–0,7%). Abaixo de 0,4% de stop, não avisa. |
| Tamanho (stop 0,55%) | Banca 1.000: 4 USDT → 727 USDT = **0,0090 BTC** (145/218/364). Banca 5.000: 20 USDT → 3.636 USDT = **0,045 BTC**. Sem alavancagem. |
| 1R | Médio + 0,55%. Realiza 50% / 33%, stop no médio. |
| Alvo e parciais | Nível do mapa mais próximo no sentido da rejeição a ≥ 2R: POC do dia em formação, POC de ontem, naked POC. Sem nível a 2R, não avisa. Banca 5.000: parcial 25% no primeiro nível ≥ 1,5R. |
| Validade | 4 blocos (2 h) para preencher; posição com teto de 8 h ou até 20:00 UTC, o que vier primeiro. |
| Sessão | Dias úteis, Europa e América. A cauda da madrugada (volume baixo) não conta. Sem fim de semana. |
| Evento | Cauda feita pelo dado não é gatilho (T±30). |
| Custo | 0,06 / 0,55 = **0,11 R** (0,17 R no stop). Acerto mínimo com 2,5R: **32%**. |
| Frequência | 3–6/semana. ~200/ano × 0,11 R = ~22 R/ano = **8,8% da banca** a 0,4% de risco. |
| O que o faz perder primeiro | Dia de tendência em que cada cauda é engolida no bloco seguinte ("pavio e vai"): três stops seguidos na mesma borda. Se o controle (a) mostrar que a cauda sem nível reage igual, o TPO sai de gatilho e isto vira só mapa. |

Modelo de Telegram:

```
TPO E2 | COMPRA | sem % medido | 20/10 10:30 UTC
Bloco 10:00–10:30 tocou o VAL do composto 79.950 vindo de longe: cauda 0,47% (mín. 79.650), fechou 80.030 no terço superior
Zona: 80.030 (20%) · 79.935 (30%) · 79.840 (50%) | vale até 12:30 UTC
Stop: 79.570 a mercado (extremo da cauda −0,10%) = 0,42% | risco 0,4% → 0,0118 BTC (1.000) · 0,059 BTC (5.000)
1R: 80.245 → realiza 50%, stop no médio | alvo: POC de ontem 80.900 (3,0R) | naked POC 81.150 (3,7R)
Composto p = 0,05 (só compra) | tipo de dia: R | evento: nenhum | controle: —
```

### 2.5 Fluxo D — "Nódulo abandonado" (presos pelo footprint; reteste contra quem ficou preso)

Definição que vale (live xc2nq9ti8Ns, `docs/tradeiros/presos_footprint.md`): **preso é quem agrediu a mercado num nível,
o preço não andou (absorvido) e a vela fechou do outro lado**. Não é long/short de contas nem funding (os dois já medidos e
não separam); é delta por nível **dentro** da vela. Os testes de "presos" do projeto mediram outra coisa: o conceito real
nunca passou pela régua. É a única estratégia de fluxo medível hoje (negócios públicos da Bybit com lado desde 2020).

| Item | Plano |
|---|---|
| Contexto | Negócios da Bybit com lado do agressor, níveis de 20 USD, barra de 5 min (mede primeiro) e 30 min (a do print). Melhor depois de uma perna (nódulo no topo do rebote ou no fundo da queda), Europa e América. Nível coincidindo com VAL/VAH/POC de ontem ou do composto (±0,2%) = "poder de fogo"; fora de nível = "uma graninha" (mão menor). |
| Gatilho | Nódulo comprador na barra B (vol_buy do nível ≥ 3× a mediana da barra, ≥ p90 das últimas 48 barras, terço superior, delta > 0) **e** absorvido (B fecha ≤ L − 0,05%) **e** abandonado (as 2 barras seguintes fecham ≥ 0,3% [5 min] / ≥ 0,5% [30 min] abaixo de L sem negociar acima da máxima de B). Reteste = primeira volta a L ± 0,05%, ≥ 2 barras depois e até 24 h, chegando por baixo; versão medida: o 1º 1 min na zona fecha abaixo da abertura com delta ≤ 0. Espelho para vendedores presos. |
| Zona (venda) | Banca 1.000: 1 limitada em L. Banca 5.000: 2 limitadas, L − 0,05% (40%) e L + 0,05% (60%). Nunca na barra em que ficaram presos: só no reteste. |
| Risco | **0,25% da banca** (scalp; é o aviso mais frequente de todos). Nível de TPO a ±0,2%: 0,4%. |
| Stop | Máxima de B + 0,10%, a mercado. Típico 0,45% (0,3–0,6%); abaixo de 0,4% o aviso não sai (regra 5). |
| Tamanho (stop 0,45%) | Banca 1.000: 2,5 USDT → 556 USDT = **0,0069 BTC**. Banca 5.000: 12,5 USDT → 2.778 USDT = **0,034 BTC**. Em nível de TPO (0,4%): 889 / 4.444 USDT. Sem alavancagem. |
| 1R | Médio − 0,45%. Realiza 50%, stop no médio (é o que eles fazem: "faz uma graninha"). |
| Alvo e parciais | Alvo = fechamento mais baixo entre o abandono e o reteste, **exigido ≥ 2R** ou o aviso não sai. A versão deles (alvo 1 = 1R e pronto) precisa de 57% de acerto líquido: não paga com esta banca; fica como variante medida. Com mapa de liquidação, o aglomerado de longs abaixo vira alvo 2. |
| Validade | 2 h depois do reteste; sem resolução, fecha a mercado. |
| Sessão | Europa e América. Madrugada e fim de semana fora (mediana baixa infla o 3×; piso absoluto de 500 mil USD por nível). |
| Evento | ±30 min de macro: veto. Reteste com compra nova (CVD spot subindo, OI subindo, parede compradora embaixo) é continuação, não volta: quando esses dados existirem, vetam. |
| Custo | 0,06 / 0,45 = **0,13 R** (0,21 R no stop). Acerto mínimo com 2R: **38%**; com 1R (versão deles): 57%. |
| Frequência | 5 min: 2–5/dia depois dos filtros; 30 min: 1–3/dia; com 2R e sessão, 1–2/dia. ~300/ano × 0,13 R = ~39 R/ano = **10% da banca** a 0,25% de risco: depois da Fibonacci E1, a mais cara de operar sem vantagem. |
| O que o faz perder primeiro | Nódulo que é hedge (não defende nível nem sai no zero a zero); reteste patrocinado (continuação, stop inteiro); o motor de fluxo com absorção ao vivo deu bruto zero nos mesmos 30 dias; custo de scalp em stop de 0,3–0,45%. |

Modelo de Telegram:

```
FLUXO D | VENDA | sem % medido | 20/10 11:40 UTC (30 min)
Nódulo comprador 2,4 M USD em 81.260 (barra 10:30, terço superior), fechou 81.180 e as 2 barras seguintes fecharam ≤ 80.800: compradores presos
Zona: 81.230 (40%) · 81.300 (60%) | reteste chegando por baixo; 1 min fechou abaixo da abertura com delta ≤ 0 | vale até 13:40 UTC
Stop: 81.690 a mercado (máx. da barra +0,10%) = 0,51% | risco 0,25% → 0,0061 BTC (1.000) · 0,030 BTC (5.000)
1R: 80.855 → realiza 50%, stop no médio | alvo: fechamento mais baixo pós-abandono 80.450 (2,0R) | nível: VAH de ontem 81.300 (±0,2% → mão de 0,4%)
Reforços sem dado ainda (parede Coinbase acima? CVD spot no reteste?) | evento: nenhum | controle: —
```

### 2.6 Elliott U1 — "Setup de onda 2" em camadas (1h para day trade; 4h e 1d para swing)

Redesenhado pela live TZND78d0dVY (`docs/tradeiros/contagem_metodo.md`, `docs/especialistas/elliott.md` §5): a entrada é
em **camadas de Fibonacci com stop por camada** (o próximo Fibonacci abaixo), nunca na invalidação final; o **alvo 1 é o
topo da onda 1**; e existe a variante **1-B** (a C fecha, o preço ganha o topo anterior e entra-se no reteste).

| Item | Plano |
|---|---|
| Contexto | Superciclo não em correcao_inicial (compra); grau acima do setup com prob_bear < 60%. **Prova da onda 1**: ≥ 5 pivôs no ZigZag de 1,5× dentro da perna (5 subondas) e fechamento acima do último topo do grau acima (mudança de estrutura). **Estrutura da onda 2**: no tempo gráfico abaixo do setup (15 min para o 1h; 1h para o 4h), a correção já tem A e B confirmadas (cenário correcao_c vivo, ou correcao_b com B < 1,0 × A) e a zona 0,5–0,618 da onda 1 coincide com 1,0–1,618 × A projetado do fim da B. Sem A-B, sem aviso (a regra original, só a retração, roda como variante). Volume caindo na onda 2 entra como coluna, não condição. Nunca onda 4. |
| Gatilho | As limitadas ficam armadas quando a B se confirma; preenchem no toque. Não se espera candle (é o gatilho de swing deles: "ordens escalonadas já postadas nas zonas"). |
| Zona (4 camadas) | 0,382 (20%), 0,5 (30%), 0,618 (30%), 0,666–0,786 (20%) da onda 1. Cada camada carrega a contagem que a justifica: as de cima são da primária, as de baixo da alternativa mais funda. Na banca de 1.000 as quatro cabem acima da fatia mínima. |
| Risco | 1h: 0,7% total; 4h/1d: 1% total; repartido pelos pesos (20/30/30/20). A camada 0,786 só entra se o grau maior ainda permitir (não entra em correcao_inicial). |
| Stop por camada | Próximo Fibonacci abaixo da camada − 0,25 × ATR(14) do setup, a mercado: 0,382 → abaixo de 0,5; 0,5 → abaixo de 0,618; 0,618 → abaixo de 0,786; 0,786 → abaixo da origem. Em 1h com onda 1 de 3–4%: **0,5–1,0% por camada**. A invalidação final (origem da onda 1) só mata a contagem. Variante "estrutural" (tudo na origem) fica como controle; o curto 0,786 sai. |
| Tamanho (1h, onda 1 de 4%, stops 0,57/0,58/0,77/0,97%) | Banca 1.000: 7 USDT = 1,4/2,1/2,1/1,4 USDT por camada → 246/362/273/144 USDT = **1.025 USDT ≈ 0,0127 BTC** (≈ 1× da banca: a única que encosta; se não couber, corta a camada 0,382). Banca 5.000: 5.125 USDT ≈ **0,063 BTC**. 4h com onda 1 de 8%: stops dobram, nocional cai à metade (≈ 700 / 3.500 USDT com risco 1%). |
| 1R | Por camada (o stop dela). Realiza 25–50%, stop no médio da camada. Roda com e sem (12 variantes fixas: 3 formatos de stop × 2 alvos × tirar-risco ligado/desligado). |
| Alvo e parciais | **Alvo 1 = topo da onda 1** (fim da onda 1): da camada 0,5 ≈ 3,5R, da 0,618 ≈ 3R; realiza 25–50% ali e stop no médio. Alvo 2 = fundo da onda 2 + 1,618 × onda 1 (em log quando a perna for > ~40% ou grau ≥ primário; os dois números no aviso). |
| Camada perdida | **Não vende.** Segundo aviso: "camada X perdida: realizar no repique até o nível perdido e reavaliar" (eles compram o repique e vendem o pullback; a camada seguinte continua armada). Fica anotado, fora da medição do U1. |
| Validade | Até fechar abaixo da origem (morreu) ou acima do topo da onda 1 sem preencher (a onda 3 saiu sem a gente: **não perseguir**). Posição: dias (1h) a semanas (4h); no 1d, 1–3 por ano, só como aviso de swing com veto, sem prova estatística. |
| Sessão / fim de semana | Indiferente. Atravessa fim de semana com stop por camada; com o risco tirado antes de sexta 20:00 UTC, mantém; sem 1R, reduz à metade. Volume baixo de fim de semana "justifica uma onda B": não comprar o meio. |
| Evento | Não arma camada nova T±30. Posição atravessa o dado com o stop da camada (não aperta); realiza parcial antes se ≥ 1R. |
| Custo | 1h: 0,06 / 0,7 ≈ **0,08 R** por camada; 4h: 0,04 R. Acerto mínimo com 3,5R: **24%**; só até o alvo 1 pela camada 0,618 (3R): 27%. |
| Frequência | 1h: 3–8/mês (~60/ano × 0,08 R ≈ 5 R/ano = 3,5% da banca a 0,7%). 4h: 1–3/mês. A exigência de A-B-C corta parte disso; a mais barata de operar e a mais lenta de medir. |
| Variante 1-B (a mão grande deles) | A C fecha em 5 ondas com C ≥ 1,0 × A **e** o setup fecha acima do último topo da correção (mudança de estrutura); limitadas em 0,5–0,786 da perna de rompimento (é a Fibonacci E1 no grau do setup); stop abaixo do fundo da C; alvo 1 = topo da onda 1, alvo 2 = 1,618 × onda 1 do fundo da C. Menos entradas, entrada pior, stop mais curto: medir lado a lado com as camadas. |
| O que o faz perder primeiro | "Onda 1" que era onda C; A que era a onda 2 inteira (compra a A achando que é a C); em 1h/15 min o ZigZag reclassifica e a onda 1 some (45% de troca de fase em 1 min, MEDIDO); "80–90% das vezes que passa de 0,786 não é onda 2" é número de memória deles, não medido (medição em `data/cenarios/` antes de confiar); a calibração já mostrou que a contagem lida só no candle paga odds justas. |

O scalp deles na mesma live (contra a mínima local, alvo no naked POC seguinte, 3:1 obrigatório, 0,2% de risco) **não
é aviso de Elliott**: é um trade de nível com a contagem como contexto, o Uso 2 com o aviso vindo do TPO. Para esta
banca: 0,2% = 2 USDT (1.000) / 10 USDT (5.000); com stop de 0,25% o nocional é 800 / 4.000 USDT (0,0099 / 0,049 BTC), o
custo é **0,24 R** e o acerto mínimo com 3R é 31%. Abaixo do piso de 0,4% de stop da regra 5: só sai se a mínima local
permitir stop ≥ 0,4% e o naked POC estiver a ≥ 1,2%.

Modelo de Telegram:

```
ELLIOTT U1 | COMPRA em camadas | sem % medido | 20/10 12:00 UTC (setup 1h; A-B-C no 15 min)
Onda 1 78.400 → 81.600 (4,1%, 5 subondas, ganhou o topo 80.900); A e B feitas, C projetada 1,0–1,618×A = 79.900–79.400; superciclo impulso_alta; 4h prob_bear 35%
Camadas: 80.380 (0,382 · 20% · stop 79.920) · 80.000 (0,5 · 30% · stop 79.540) · 79.620 (0,618 · 30% · stop 79.005) · 79.085 (0,786 · 20% · stop 78.320)
Risco 0,7% total → 0,0127 BTC (banca 1.000) · 0,063 BTC (5.000) | cada camada com o próprio stop a mercado | a contagem morre em 78.400
1R por camada → realiza 25–50%, stop no médio da camada | alvo 1: topo da onda 1 81.600 (3,5R da camada 0,5) | alvo 2: 1,618 ≈ 84.580 (log: 84.900)
Camada perdida = não vende: realizar no repique até o nível perdido | não é onda 4 | evento: nenhum | controle: —
```

---

## 3. Ranking final das 6 e por onde começar

| # | Estratégia | Vantagem estrutural | Freq. | R:R líquido | Capital pequeno | Medir | **Nota (0–10)** |
|---|---|---|---|---|---|---|---|
| 1 | **TPO E1 — abriu fora e voltou** | fato de 2 blocos; alvo é o nível (lição dos estudos); mesmo evento do tipo de dia V | 1–3/sem | 2,5R − 0,09 | stop 0,7%, sem alavancagem | rig do estudo 2 pronto; definição fechada; controle de área deslocada | **6,0** |
| 2 | **OB E2 — varredura + volta** | presos na definição; controle natural já medido (extremo atravessa) | 1–3/sem | 2,5R − 0,08 | stop 0,75% | precisa motor swing/BOS/FVG/CHoCH; 3 parâmetros livres | **6,0** |
| 3 | **Fibonacci E1 — escada após quebra** | o trade declarado do Tradeiros; escada larga nunca medida | 1–2/dia | 1,7R/3,3R − 0,10 | stop 0,6–0,9%; banca 1.000 só 3 fatias | ZigZag pronto; milhares de eventos; mas o custo anual é o maior | **5,5** |
| 4 | **Fluxo D — nódulo abandonado** | o único ingrediente nunca medido (delta por nível dentro da vela: o "preso" de verdade, não o long/short); dois vendedores no mesmo nível | 1–3/dia (com filtro de 2R, 1–2) | 2R − 0,13 (deles: 1R) | stop 0,45%: custo pesa; 1–2 fatias | 30 dias prontos + fetcher desde 2020; controles a/b/c; o motor de fluxo deu zero nos mesmos dias | **5,5** |
| 5 | **TPO E2 — cauda no bloco** | regra 6 do Tradeiros ("só depois de ver a reação") | 3–6/sem | 2,5R − 0,11 | stop 0,55%: custo pesa | rig pronto; parâmetros 0,30%/60% são escolhas | **5,5** |
| 6 | **Elliott U1 — onda 2 em camadas** | assimetria por camada (alvo 1 = topo da onda 1 a 3–3,5R; stop por camada curto); "Elliott é a lei" do usuário | 1h 3–8/mês; 4h 1–3/mês | 3,5R − 0,08 | stop 0,5–1,0% por camada; a única que encosta em 1× da banca | cenários desde 2021; 12 variantes fixas; exige A-B-C no grau abaixo; amostra pequena; calibração já deu odds justas | **5,0** |
| 7 | VWAP V2 — esticado volta ao justo (reserva, apêndice) | dado fora do candle já coletado (OI/funding) | 2–4/sem | 2,5R − 0,10 | stop 0,6% | parente −0,03% medido; funding quase sempre neutro | 5,0 |

Desempate entre 1 e 2: a TPO E1 mede-se esta semana sobre o rig que já existe e tem menos parâmetros; a OB E2
tem o mecanismo mais claro mas exige um motor novo e três números que ainda podem ser "afinados até passar".
Nenhuma passa de 6 porque **cinco das seis leem só o candle**, e tudo que leu o candle neste projeto empatou com o
sorteio. A D lê dentro da vela (quem agrediu em cada preço) e por isso entra apesar do R:R fraco e do custo de scalp:
é a única das seis cujo ingrediente nunca passou pela régua. A diferença, se existir, está no fato acrescentado ao
nível, e isso ninguém mediu.

**Começar a receber como aviso: TPO E1.** Motivos: (1) é o aviso com **menos lugar para perder dinheiro**
enquanto não há medida: 1–3 por semana, stop estrutural de 0,5–1,0% (custo 0,06–0,12 R), alvo que é o próprio
nível, sem fim de semana, sem evento, só no quartil permitido; (2) é o mesmo evento do tipo de dia **V** do
regime, então uma rodada mede os dois; (3) a definição não tem botão de ajuste (2 blocos dentro, ponto); (4) o
custo anual de operar sem vantagem é o menor entre as frequentes (~4,5% da banca a 0,5% de risco), contra 12,5%
da Fibonacci E1, 10% da Fluxo D e 8,8% da TPO E2; (5) ensina o ONDE do método (composto, valor de ontem, POC como ímã) antes
de qualquer gatilho mais fino. A OB E2 entra em seguida, assim que o motor de swings estiver construído, e a
Fibonacci E1 e a Fluxo D só depois de medidas, porque são as que mais trades geram e as que mais custam se o acerto
for o do sorteio (a D tem o ingrediente mais novo, mas também o stop mais curto; o passo 2 da ordem de medição decide).

**O que faria o usuário perder dinheiro primeiro (em ordem):**

1. **Operar um aviso "sem % medido" como se tivesse %.** Hoje o acerto esperado de qualquer um é o do sorteio;
   o único número certo é o custo. Duas operações por dia a 0,10 R custam ~25 R por ano = 12,5% da banca a 0,5%
   de risco. É isso que acontece primeiro, devagar, sem nenhum stop grande.
2. **Dia de tendência contra o aviso responsivo**: três caudas engolidas (E2) ou três retestes vendidos (Fibo E1)
   na mesma manhã, 3 stops de 0,4–0,5% = 1,2–1,5% da banca antes do almoço. Por isso o tipo de dia A/D proíbe
   bordas e o aviso tem de calar.
3. **Stop limitado em vez de a mercado, ou stop apertado em evento** (o pavio de 19/11/2025 passou por cima do
   stop curto). Stop é a mercado e não se mexe T±30.
4. **Perseguir**: comprar a onda 3 que saiu sem preencher (U1), entrar a mercado no CHoCH em vez de esperar o
   reteste (OB E2), entrar na cauda que ainda não fechou (E2).
5. **Segurar 1 fatia preenchida depois que o preço saiu** esperando "voltar". Regra 24: fecha, deixa as ordens.
6. **Alavancar para caber tamanho maior do que o risco permite.** Na banca de 1.000, a fatia mínima de 0,001 BTC
   obriga a 3 fatias; forçar 5 fatias com alavancagem dobra o risco sem o usuário perceber.
7. **Confundir regime com direção**: vender porque o funding está alto ou porque o varejo está comprado
   (MEDIDO: não inverte o preço). Derivativo dá amplitude e veto, não lado.
8. **Fim de semana e madrugada**: pavio maior, reação menor, mediana do livro inflada. O aviso não sai; se o
   usuário operar "por conta", é a conta dele.

---

## 4. Ordem de medição

Princípio: o mesmo código que gera o aviso ao vivo é o que roda no histórico; critério escrito antes; variantes
fixadas; nenhum parâmetro iterado; o que reprovar vira linha na lista "medido e reprovado" do agente.

**Critério de aprovação comum (vale para todas):**
- custo real (maker na entrada e no alvo, taker + 0,02% no stop, funding quando atravessa 00/08/16h UTC);
- leitura pessimista: favor e contra no mesmo candle = contra; fatia só preenche se o minuto atravessou o preço;
- três períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09, com ≥ 30
  decididos por período (abaixo disso, "inconclusivo", nunca "aprovado");
- **líquido > 0 nos 3 períodos**;
- **2 erros padrão acima do controle sorteado** (direção sorteada, 20 sorteios) **e** acima do controle
  específico da estratégia (nível/área/zona/âncora/perna deslocada ao acaso) em treino e validação;
- **holdout olhado uma vez**, depois de fixado o conjunto; compra e venda separadas; ano a ano (2021–2026 foi de
  alta: uma regra comprada pode parecer boa só pela tendência);
- com N variantes, olhar o conjunto das aprovadas no holdout, não o pódio (~N/4 passam em dois períodos por acaso).

**Ordem (dado pronto primeiro; cada passo reaproveita o anterior):**

| Passo | O que roda | Por que nesta ordem | Esforço |
|---|---|---|---|
| 1 | **TPO E1** (4 variantes: dia × América; reteste × fechamento) + **Regime F1** (tipo de dia pela 1ª hora, controles invertido e sorteado) + **Regime F2** (R em ATR, k em {2,3,4}) sobre o rig do estudo 2 | rig existe; E1 e tipo V são o mesmo evento; F1 responde se bordas valem em R/V; F2 corrige a régua de todas as outras | 1–2 dias |
| 2 | **Fluxo D** nos 30 dias de negócios (5 min primeiro, 30 min confirma; três períodos de 10 dias; controles a/b/c: nível sorteado da mesma barra, nódulo não abandonado, direção sorteada) e, em paralelo, baixar 60–90 dias de 2020–2026 com regimes diferentes (alta, range, queda) pelo fetcher da Bybit, **reduzindo na hora** a delta por nível de 20 USD e barra de 1 min e descartando o bruto | é a única estratégia de fluxo medível hoje e o único ingrediente que nunca passou pela régua; se reprovar nos 30 dias, não se gasta coleta com a versão completa; se passar, vira o "presos" que A e B precisam | 2 dias (+ download) |
| 3 | **TPO E2** (cauda) com controle "mesma cauda sem nível" + **TPO E3** (América contra a manhã) | mesmo rig de blocos de 30 min; o controle de E2 decide de uma vez se o nível acrescenta algo a um fato | 1 dia |
| 4 | **Fibonacci E1 + E2 juntas** em 15 min e 1h (faixa sorteada, direção sorteada, entrada única em 0,618; régua contra alvo fixo 2R e níveis deslocados) + **Fibonacci E3** | ZigZag ATR existe; E2 (régua) só tem de onde sair com E1; a régua, se passar, vira a saída de todos os avisos | 1–2 dias |
| 5 | **OB E2** (varredura + volta) e **OB E1** (OB qualificado 1h) com o motor de swing/BOS/FVG/CHoCH construído uma vez | motor novo; três controles; E2 contém E1 | 2–3 dias |
| 6 | **Elliott**: antes de tudo, rodar o superciclo no 1d até 16/10/2026 e registrar o estado (se der correcao_em_curso, o veto bate de frente com a compra que eles fazem e isso se decide antes de usar o veto como aviso); medir em `data/cenarios/` a hipótese "passou 0,786 → ≥ 70% perde a origem"; **U2** (juntar colunas de 1h/4h/superciclo aos CSVs dos estudos de TPO, poda a 2 cenários, veto só com força; data sorteada como controle); **U1** (replay com camadas e stop por camada, 12 variantes, onda 1 sorteada, A-B-C exigida × só retração, 1-B lado a lado); **U3** (quando o superciclo voltar a impulso_maduro) + **Regime F3** | U2 é uma tarde sobre o que existe; U1 decide o lugar de Elliott no conselho; F3 roda dentro dos dias R/V de F1 | 3–4 dias |
| 7 | **VWAP V1** (âncora automática no pivô de 7 dias) → **V2** (esticado, controle "sem OI/funding") → **V3** (semanal) + **Derivativos P1** (etiquetar os avisos gerados até aqui com o regime e medir MFE/MAE por regime contra regime sorteado) | V2 reaproveita a âncora de V1; P1 responde a pergunta mais barata do projeto (os derivativos já coletados acrescentam algo?) | 2 dias |
| 8 | **VP V1** (corredor de vazio; código de HVN/LVN como zona; validar a aproximação de 1 min contra os 30 dias de negócios) → **VP V3** (POC ancorado, com VWAP ancorada como 3º controle) → **VP V2** (delta por nível no composto, com a mesma redução de negócios do passo 2) | código novo; o controle de vazio deslocado também responde pelo VP V2; a redução do passo 2 serve às duas | 2 dias |
| 9 | **Fluxo C** retroteste no histórico público da Binance (liquidationSnapshot, metrics), se a cobertura existir; **Derivativos P2** como veto de venda (sem %) desde já; **P3** simulado e deixado desligado com regra de religar | único fluxo com liquidação que pode ser medido antes de 90 dias de coleta; P2 é veto de custo zero | 1–2 dias (+ download) |
| 10 | **Coleta ligada hoje, sem buraco**: negócios Bybit (linear e inverse) gravados já reduzidos; liquidações Bybit/Binance; negócios Coinbase agregados por minuto; OI 5 min; livro perp Binance; cadência rápida ±1% na Coinbase; rastreador de paredes em preço; base spot×perp; tabela estática de eventos; log de qualidade | cada dia sem coleta é um dia a menos de histórico; A, B, C, OB E3 e os reforços da D dependem disso | contínuo |
| 11 | Em ~45 dias: **parede genérica** (≥ 3× persistente segura o 1º toque mais que o sorteio?). Em ~90 dias: **Fluxo A** (12–40 eventos: sinal forte ou nada) e a **D completa** (calço, CVD spot, liquidações no reteste). Em 6–9 meses: **Fluxo B** e **OB E3** | é a parte que mais se parece com o Tradeiros ao vivo e a única com informação fora do candle; não há atalho | abr/2027 para a primeira leitura confiável de A |

**O que o aviso mostra enquanto não há medida:** a etiqueta **"sem % medido"** e **"controle: —"** na primeira e
na última linha; lado, zona com as limitadas e pesos, stop a mercado, 1R com o que realiza, alvo com o R:R,
validade, tamanho sugerido para a banca cadastrada; a linha de contexto (quartil do composto, tipo de dia, veto de
Elliott, etiquetas de derivativos, presos pelo footprint quando houver); e a ressalva curta do parente mais próximo
já medido ("família X deu sorteio"). Cada aviso enviado é **fechado e contado** (alvo, stop ou tempo) na tela
`/avisos`: o acerto real ao vivo aparece com o n ao lado, marcado "pouca amostra" abaixo de 30 e "preliminar" abaixo
de 100, e nunca substitui a régua dos três períodos. Quando uma estratégia passar, o % entra com n, período e o % do
controle sorteado ao lado.

---

## 5. Como combinar — TPO > fluxo > Elliott aplicado aos avisos

1. **TPO dá o ONDE**: composto de 10 dias define o quartil permitido (p < 0,25 só compra, p > 0,75 só venda,
   meio nada); valor de ontem, naked POC e single prints são **alvos**; máximas e mínimas de dia/sessão são
   **stops**. Nenhum nível é gatilho (MEDIDO). "O TPO dá o lugar, o footprint dá a licença."
2. **Regime dá o QUANDO**: tipo de dia às 01:00 e 14:30 UTC (R/V liberam bordas e caudas; A/D só a favor, com
   VWAP, OB e onda 2; C arma e não entra; X R maior ou nada; E e F calam o aviso). O superciclo dá o lado da
   carteira e veta o lado contrário.
3. **Fluxo dá o SE SEGURA e QUEM ESTÁ PRESO**: preso é o agressor que entrou num nível e viu a vela fechar do outro
   lado (footprint, estratégia D), nunca o long/short; calço/parede persistente (quando houver histórico) diz se a
   borda é passiva (limitadas) ou reativa (só depois de pavio + presos + quebra, comprando o reteste); OI e funding
   são etiqueta. Fluxo a favor = aviso inteiro; neutro = metade; contra = o aviso não sai.
4. **Elliott dá o LADO permitido, o VETO, as CAMADAS e o TETO do alvo**: correcao_inicial veta compra;
   fundo_terminal/novo_impulso/zona_onda_2 vetam venda; 4h com prob_bear ≥ 60% **e força** (range > 1,5 ATR ou volume
   > 1,5× mediana) veta compra, sem força = "em disputa" = metade; só os 2 cenários de maior probabilidade com
   movimento distinto contam; a camada de Fibonacci perdida é "perde probabilidade", a origem é a morte; o 1º alvo
   de Elliott limita o alvo e, a menos de 1,5× o stop, veta por falta de espaço. Aviso próprio só na onda 2; onda 4 nunca.
5. **Fibonacci dá a RÉGUA de saída**: 1R tira o risco; parciais em 0,5/0,618 só se a ≥ 1,5R; alvo final ≥ 2R ou
   o aviso não nasce; o que sobra corre atrás do último pivô. O scalp deles mira o naked POC seguinte com 3:1.
6. **Derivativos dão o TAMANHO do stop e do alvo**: regime ESTICADO ×1,5; CAPITULAÇÃO veta venda; nunca dão lado.
7. **O gatilho é sempre um fato fechado** (reentrada de 2 blocos, cauda, CHoCH, quebra de microestrutura, nódulo
   abandonado, B confirmada), e a entrada é no reteste com limitadas, nunca a mercado no fechamento.
8. **Ordem dos vetos**: F/E → meio do composto → superciclo → Elliott 4h contra com força → fluxo contra → alvo < 2R.
   Qualquer um cala o aviso; o aviso diz qual calou.
9. **Um aviso por zona por vez**, risco somado do dia ≤ 1,5% da banca, sem aumentar mão em evento, sem scalp no
   fim de semana, sem trade para recuperar o dia. Troca de contagem não é troca de posição: ajusta exposição, não o lado.
10. **Tudo sai "sem % medido" até passar na régua**; quando passar, o % vem com n, período e o controle sorteado
    ao lado, para o usuário ver com os próprios olhos se o aviso bate o acaso.

---

## 6. O que este documento não promete

Nenhuma das 31 linhas da tabela tem número a favor. As notas são a opinião de um gestor de risco sobre **onde
vale gastar tempo de medição**, não sobre onde vale gastar dinheiro. O único número certo nos seis planos é o
custo; o resto é hipótese até os três períodos e os dois controles dizerem o contrário. Se as seis reprovarem, o
que sobra é o que os estudos já apontaram: TPO como mapa de alvos e stops, Elliott como mapa de direção e veto,
fluxo como contexto, e o usuário de fora do mercado, que também é operar.

---

## Apêndice A — plano reserva

### A.1 VWAP V2 (plano reserva, 7º no ranking) — "Esticado volta ao preço justo" (VWAP ancorada é o alvo; OI e funding qualificam)

| Item | Plano |
|---|---|
| Contexto | VWAP ancorada no fundo/topo de 7 dias confirmado por quebra de estrutura (regra de V1); sem âncora, a da abertura semanal. Fechamento de 15 min ≥ +2σ **e** OI da Bybit +1% em 4 h **e** funding da última janela acima da mediana de 30 dias **e** VWAP de sessão sem drive (inclinação < 0,5σ em 4 h). Espelho para compra em −2σ. |
| Gatilho | Depois de ≥ 2 candles de 15 min fechando acima de +2σ, o primeiro que fecha abaixo de +2σ com máxima acima da anterior (topo feito e perdido). |
| Zona (venda) | 3 limitadas: +2σ − 0,10% (20%), +2σ + 0,07% (30%), +2σ + 0,25% (50%). |
| Risco | 0,4% da banca (frequente e com parente medido negativo). Se o regime P1 dos derivativos for ESTICADO, stop e alvo ×1,5 e risco 0,5%. |
| Stop | Máxima da excursão acima de +2σ + 0,15%, a mercado. Teto 1,0%; típico 0,6% (0,4–0,8%). |
| Tamanho (stop 0,6%) | Banca 1.000: 4 USDT → 667 USDT = **0,0082 BTC**. Banca 5.000: 20 USDT → 3.333 USDT = **0,041 BTC**. Sem alavancagem. |
| 1R | Médio − 0,6%. Realiza 50% / 33%, stop no médio. Se +1σ está a ≥ 1R, é o 1º alvo. |
| Alvo e parciais | Alvo final = a própria VWAP ancorada (≥ 2R ou não avisa). Parcial de 25% em +1σ (banca 5.000). |
| Validade | 6 candles de 15 min (1,5 h) para preencher; posição com teto de 12 h. |
| Sessão | Dias úteis; melhor América. Sem fim de semana (σ pequena, alvo < 2R: o próprio filtro cala o aviso). |
| Evento | Funding e OI em torno do dado são ruído: sem aviso T−30 a T+30. |
| Custo | 0,06 / 0,6 = **0,10 R** (0,16 R no stop). Acerto mínimo com 2,5R: **31%**. |
| Frequência | 2–4/semana. ~150/ano × 0,10 R = ~15 R/ano = 6% da banca a 0,4%. |
| O que o faz perder primeiro | Open-drive de notícia que o filtro de inclinação não pega; short squeeze por cima do stop de 0,15%; funding "acima da mediana" é quase sempre 0,01% (MEDIDO: p50 = p75), então o filtro pode ser vazio. A reversão em banda sem derivativos deu −0,03% (MEDIDO). |

Modelo de Telegram:

```
VWAP V2 | VENDA | sem % medido | 20/10 16:15 UTC
Ancorada no fundo 77.900 (14/10) = 80.350 · +1σ 81.175 · +2σ 82.000; 2 candles 15 min acima, o último fez máx. 82.500 e fechou 81.930
Zona: 81.920 (20%) · 82.060 (30%) · 82.200 (50%) | OI +1,4% em 4 h · funding 0,018% (> mediana) · sessão sem drive | vale até 17:45 UTC
Stop: 82.625 a mercado (máx. +0,15%) = 0,64% | risco 0,4% → 0,0077 BTC (1.000) · 0,039 BTC (5.000)
1R: 81.580 → realiza 50%, stop no médio | alvo 1: +1σ 81.175 (1,8R) | alvo final: VWAP 80.350 (3,4R)
Regime P1: neutro (funding caro, não esticado) | evento: FOMC 18:00 → parcial antes, stop fica | controle: —
```

