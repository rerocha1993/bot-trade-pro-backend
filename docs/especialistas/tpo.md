# TPO para avisos de scalp e day trade — como usar, o que ainda tem potencial e por onde começar

Autor: especialista-tpo (`.claude/agents/especialista-tpo.md`). Data: 20/10/2026.
Para quem lê: capital pequeno, scalp e day trade, sem robô. O que se quer é um **aviso** com lado, zona de entrada,
stop e alvo, na cabeça do Tradeiros (responsivo: compra borda de baixo, vende borda de cima, nada no meio).

Fontes usadas: `docs/tradeiros/perfil_por_regime.md` (seções 1, 2.1 e 3.3), `data/estudo_niveis_tpo_resumo.md`
(5 min, 36 níveis) e `data/estudo_niveis_tpo_2_resumo.md` (15 min, composto). Tudo abaixo está marcado como
**MEDIDO** (número que existe no projeto) ou **HIPÓTESE** (o que ainda não foi medido). Nada aqui promete lucro.

---

## 1. Diagnóstico em 10 linhas

1. **MEDIDO.** Em 5 min, com alvo de 0,3–0,6% e 4 h de prazo, 36 níveis de TPO (POC/VAH/VAL do dia, das sessões, da semana, do mês, do ano, naked POC, extremos, aberturas) tocados pela **primeira vez** deram **0 de 180** combinações positivas depois do custo, contra 6 níveis sorteados por dia. Nenhum ficou 2 erros padrão acima do sorteio nos três períodos.
2. **MEDIDO.** Em 15 min, com alvo de 1–2% e 2 dias de prazo, as bordas do **composto de 10 dias** (o range do Tradeiros) deram 0 de 16; com desvio × dentro, toque virgem, escada de 5 limitadas e presos (long/short, OI, funding): **3 de 117**, o que o acaso produz, e nenhuma acima do controle.
3. **MEDIDO.** POC, VAH e VAL de qualquer grau reagem **tanto quanto um preço sorteado** (47–53% em 1:1 contra 44–50% do controle; a diferença some com o custo).
4. **MEDIDO.** Máxima e mínima de dia e de sessão são **piores que o sorteio** como ponto de reversão (29–40% de reação em 1:1): o preço que chega de longe atravessa o extremo. Comprar a mínima de ontem ou vender a máxima da Ásia, no primeiro toque, perde para um número aleatório.
5. **MEDIDO.** A escada de 5 limitadas em ±0,25% é a mesma operação que a entrada única (95–98% preenchida). Fatiar não cria vantagem; só muda o preço médio.
6. **MEDIDO.** Presos medidos por long/short da Bybit contra a mediana não separam VAL nem VAH nesta régua. "Presos" só podem entrar como definição **estrutural** (quem comprou acima do POC da manhã e viu o bloco fechar abaixo), não como indicador.
7. **O que isso muda:** o nível **não é gatilho**. Chegar no nível é informação de **onde** o mercado pode reagir, não de **que** vai reagir. O gatilho tem de ser um fato em candle fechado que o nível sozinho não dá: a rejeição vista (cauda), a reentrada no valor (regra dos 80%), a falha de uma sessão.
8. **O nível vira alvo.** A lição consistente dos dois estudos é que o preço **atravessa** níveis: então o POC de ontem, o naked POC e a borda oposta do valor servem para **sair**, não para entrar. Alvo concreto, a ≥ 2× o stop, ou não há aviso.
9. **O extremo vira stop.** A máxima da manhã, o pavio do bloco, o extremo da excursão fora do valor são a invalidação estrutural, o oposto do "stop de bobeira" colado no nível.
10. **Regra para o aviso:** sem % medido, o mapa do dia sai **sem probabilidade** e diz isso. O que vai ter % é só o que passar por critério escrito antes, três períodos e dois controles sorteados (seção 2, "como medir").

### Resposta curta às perguntas do usuário

| Pergunta | O que foi medido | Como usar no aviso |
|---|---|---|
| POC diário (de ontem, da semana, do mês, do ano) | 1º toque = sorteio em 5 e 15 min (MEDIDO) | **Alvo e ímã**: "tirar o risco" ou alvo final da entrada feita por outro motivo. Mensal e anual só dizem caro/barato (contexto), e só entram no mapa se estiverem a ≤ 5% do preço |
| POC/VAH/VAL do composto de 10 dias | bordas = sorteio no 1º toque (MEDIDO) | **Onde é permitido operar** (quartil de baixo: só compra; de cima: só venda; meio: nada). Não é gatilho |
| Máxima/mínima da Ásia, Europa, América | pior que sorteio como reversão (MEDIDO) | **Stop/invalidação** e referência de quem ficou preso. Nunca "vender a máxima da Ásia" no toque |
| Naked POC, single print | 1º toque = sorteio (MEDIDO) | **Alvo** da rotação, por estarem no caminho e "puxarem" o preço (HIPÓTESE sobre o alvo; a parte do gatilho já foi reprovada) |
| Onde entrar | — | No **reteste depois do fato** (bloco de 30 min fechado mostrando rejeição ou reentrada), com 3 fatias limitadas numa zona de 0,2–0,3%, stop atrás do extremo rejeitado, alvo no nível do mapa a ≥ 2 R |

---

## 2. As 3 estratégias de TPO com maior potencial ainda não medidas

Critério de escolha: (a) o nível entra como contexto ou alvo, nunca como gatilho de primeiro toque; (b) gatilho em
bloco de 30 min fechado (não olha o futuro); (c) stop estrutural; (d) alvo concreto a ≥ 2× o stop; (e) dá para
medir com os dados que já existem (5 min e 1 min da Binance, perfis de `core/tpo_sessao.py`, composto de
`core/range_tradeiros.py`); (f) não é repetição do que foi reprovado.

Convenção de R: R = distância da entrada média ao stop. Custo de ida e volta 0,06%. Frequências são estimativas
(HIPÓTESE) até alguém contar no histórico.

### E1 — "Abriu fora do valor de ontem e voltou" (regra dos 80%)

- **Contexto em que vale (HIPÓTESE).** O dia (00:00 UTC) ou a sessão americana (13:30 UTC) abre **fora** da área de valor de ontem: acima da VAH ou abaixo do VAL do perfil diário de D-1. O preço continua dentro do composto de 10 dias (o range não foi rompido). Ontem não foi dia de tendência que saiu do composto (se a área de valor de ontem é uma fatia fina no extremo do composto, o "valor" ainda não é aceito; pular).
- **Gatilho exato (candle fechado).** Dois blocos de 30 min consecutivos fecham **dentro** da área de valor de ontem (fechamento ≤ VAH e ≥ VAL para quem abriu acima). O gatilho é o fechamento do 2º bloco. Para o dia, o mais cedo é 01:00 UTC; para a América, 14:30 UTC. Variante B, medida à parte: um bloco só.
- **Zona de entrada (3 fatias limitadas).** Venda (abriu acima): entre VAH − 0,10% e VAH + 0,15%, pesos 20/30/50% de baixo para cima (a fatia maior mais longe, como o Tradeiros). Compra espelhada no VAL. Validade: 4 blocos (2 h) a partir do gatilho; se não retestar, o aviso morre. Variante C, medida à parte: entrada a mercado no fechamento do 2º bloco.
- **Stop.** Extremo da excursão fora do valor (máxima feita desde a abertura, para venda) + 0,10%. Típico 0,5–1,0% do preço.
- **Alvo concreto.** 1º alvo = POC de ontem (tirar o risco: realizar 25–50% e stop no preço médio); alvo final = **VAL de ontem** (regra dos 80%: quem reentra no valor tende a atravessá-lo inteiro). Se o composto tiver naked POC no caminho, ele vira o 1º alvo.
- **R:R típico (HIPÓTESE).** Largura da área de valor diária do BTC ÷ stop. Com área de 1,5–2,5% e stop de 0,6–0,9%: 2–3 R até o VAL; ~1 R até o POC. Filtro obrigatório: só avisa se a largura (VAH − VAL) ≥ 2× o stop.
- **Frequência esperada (HIPÓTESE).** Abrir fora do valor acontece numa parcela grande dos dias (o BTC não para de negociar, então "abrir fora" é "estar fora à meia-noite"); com a reentrada de 2 blocos, 1–3 avisos por semana contando dia e América. Em 6,7 anos: várias centenas de eventos, amostra boa.
- **De onde vem a vantagem (HIPÓTESE).** Quem comprou a abertura acima do valor apostando em continuação pôs o stop dentro do valor de ontem. A reentrada aciona esses stops e o leilão volta a procurar o outro lado do valor. É a leitura de Dalton e o que o Tradeiros chama de "desvio": sai do valor e volta.
- **O que a mata.** Dia de tendência que reentra e sai de novo (falsa reentrada); área de valor de ontem estreita (< 0,8%: o alvo não paga o custo); notícia dentro da janela (CPI 12:30, FOMC 18:00 UTC); fim de semana (volume baixo, o Tradeiros não scalpa). E o parente mais próximo já medido não ajuda: a **abertura do dia como nível** deu sorteio (MEDIDO, estudo 1) e o "desvio confirmado" nas bordas do composto em 15 min teve 71/26/20 toques e reagiu em 25% no holdout (MEDIDO, estudo 2, H2a). Esta regra é outra (valor **diário**, confirmação de **2 blocos**, alvo na **borda oposta**), mas a família tem histórico ruim.
- **Dados necessários.** Já existem: candles de 5 min (e 1 min para a execução das fatias), perfis diários e blocos de 30 min de `core/tpo_sessao.py`, composto de 10 dias.
- **Como medir.** Critério escrito antes: as 4 variantes (dia × América; reteste × fechamento) ficam fixas e nenhum parâmetro é iterado. Dois controles: (1) a **mesma regra com a área de valor deslocada** ao acaso (mesma largura, posição sorteada dentro do range dos 5 dias anteriores), que mede se o valor de ontem acrescenta algo à mecânica "voltou e retestou"; (2) **direção sorteada** no mesmo instante. Três períodos (treino 2020–23, validação 2024–jun/25, holdout jul/25–set/26), mínimo 30 decididos por período, pessimista (favor e contra no mesmo candle = contra). Aprova só o que fica líquido > 0 nos 3 períodos **e** 2 EP acima dos dois controles em treino e validação; o holdout é lido uma vez.

### E2 — "Cauda no bloco de 30 min na borda" (rejeição vista, não antecipada)

- **Contexto em que vale (HIPÓTESE).** O preço chega **de longe** (fechamento a ≥ 0,5% do nível nas últimas 4 h, a mesma definição dos dois estudos) numa borda do mapa: VAL/VAH do composto, VAL/VAH de ontem ou naked POC. O nível tem de estar no quartil de fora do composto (regra Tradeiros: nada no meio). Se o preço já rompeu o composto com aceitação, a borda não vale.
- **Gatilho exato (candle fechado).** O bloco de 30 min que toca o nível fecha com **cauda** ≥ 0,30% do preço e ≥ 60% da amplitude do bloco, com o fechamento de volta do lado "certo" do nível (compra: mínima abaixo do VAL, fechamento acima do VAL e no terço superior do bloco). É a regra 6 do perfil do Tradeiros: "só depois de ver a reação, sem ordem pendurada".
- **Zona de entrada (3 fatias limitadas).** Entre o fechamento do bloco e a metade da cauda (compra: de close − 50% da cauda até o nível), pesos 20/30/50% de cima para baixo. Validade: 4 blocos (2 h).
- **Stop.** Extremo da cauda − 0,10% (compra). É a invalidação estrutural: o preço que o mercado acabou de rejeitar.
- **Alvo concreto.** O nível do mapa mais próximo no sentido da rejeição a ≥ 2× o stop: POC do dia em formação, POC de ontem ou naked POC. Se não houver nível a ≥ 2 R, **não avisa**. 1 R = tirar o risco.
- **R:R típico (HIPÓTESE).** Stop 0,4–0,7% (metade da cauda + folga), alvo 1,0–1,5%: 2–3 R.
- **Frequência esperada (HIPÓTESE).** 3–6 avisos por semana (há muitas bordas e o BTC faz caudas de 0,3% com frequência). É a estratégia mais compatível com scalp e day trade.
- **De onde vem a vantagem (HIPÓTESE).** Quem vendeu o rompimento do VAL dentro do pavio e viu o bloco fechar de volta está preso; o stop dele fica acima do nível. A diferença para o que foi medido: no estudo 1 o toque era aceito **antes** de saber se o preço atravessaria ou rejeitaria, e o resultado (extremos piores que o sorteio) diz que ele costuma atravessar. A cauda é o fato que separa "atravessou" de "rejeitou". Se isso separa de verdade, é o que vai aparecer no controle (a).
- **O que a mata.** Dia de tendência em que cada cauda é engolida no bloco seguinte ("pavio e vai"); cauda feita por notícia; fim de semana; nível no meio do composto; alvo perto demais. Caudas no composto de 10 dias quando o range já tem 3–4 toques na mesma borda (o Tradeiros diz que o 3º/4º tende a romper; MEDIDO no estudo 2, H3: não apareceu gradiente de enfraquecimento, então é só cautela, não filtro).
- **Dados necessários.** Já existem: candles de 5 min agrupados em blocos de 30 min, perfis, composto, naked POCs.
- **Como medir.** Critério escrito antes, parâmetros fixos (0,30%, 60%, terço superior). **Dois controles obrigatórios**: (a) a **mesma cauda em preço sem nível** (bloco com a mesma cauda em qualquer lugar do range), que mede se a borda acrescenta algo à cauda; (b) cauda no nível com **direção sorteada**. Comparar ainda com a linha já medida do 1º toque simples (sorteio) para saber se a cauda sozinha já é o que importa. Três períodos, pessimista, mínimo 30 decididos. Aprovação como em E1.

### E3 — "A América contra a manhã" (presos da Ásia/Europa)

- **Contexto em que vale (HIPÓTESE).** O perfil da manhã (merge Ásia + Europa, 00:00–13:30 UTC) **estendeu** numa direção: POC da manhã no terço superior do range da manhã (forma P) e preço acima da VAH de ontem. Espelho para baixo (forma b, abaixo do VAL de ontem). O composto de 10 dias segue inteiro (a manhã não aceitou preço fora dele).
- **Gatilho exato (candle fechado).** Um bloco de 30 min da América, entre 13:30 e 16:00 UTC, fecha **abaixo do POC da manhã** (venda). A sessão de mais volume não aceita o valor que a sessão de menos volume construiu; os comprados da manhã ficam presos. Espelho para compra.
- **Zona de entrada (3 fatias limitadas).** Reteste do POC da manhã por baixo: de POC − 0,05% a POC + 0,20%, pesos 20/30/50% de baixo para cima. Validade: até 18:00 UTC.
- **Stop.** Máxima da manhã + 0,10% (a América aceitou os preços altos: invalidação).
- **Alvo concreto.** O nível do mapa mais próximo abaixo a ≥ 2× o stop: mínima da Ásia, VAH/POC/VAL de ontem ou naked POC. 1 R = tirar o risco. Se não houver nível a 2 R, não avisa.
- **R:R típico (HIPÓTESE).** Stop 0,5–0,9% (do POC da manhã à máxima da manhã), alvo 1,2–2,0%: 2–3 R.
- **Frequência esperada (HIPÓTESE).** 1–2 avisos por semana (precisa manhã com extensão clara **e** falha da América).
- **De onde vem a vantagem (HIPÓTESE).** "Os presos de uma sessão são o combustível da outra" e "abertura e fechamento americanos pesam mais" (perfil do Tradeiros). Aqui o preso é estrutural: quem comprou a manhã acima do POC e viu a América fechar abaixo. Não depende do long/short da Bybit, que **não separa** (MEDIDO, estudo 2, H5).
- **O que a mata.** Open-drive americano que continua a manhã (o bloco fecha abaixo do POC e volta em seguida); dado econômico às 12:30 ou 14:00 UTC; POC da manhã no meio do composto (sem lugar para ir); manhã sem forma (D, POC no meio do range da manhã: não qualifica). Parentes medidos que não ajudam: POC da Ásia e da Europa de hoje no 1º toque em 5 min = sorteio; extremos de sessão como reversão = pior que o sorteio; "comprar o rompimento" do extremo (continuação) = 0 de 183 (MEDIDO, estudo 1). Esta regra difere por exigir **fechamento de bloco da América através do POC da manhã**, reteste e alvo longe (1–2%), mas é a que mais se parece com o que já falhou.
- **Dados necessários.** Já existem: candles de 5 min, perfis por sessão (`core/tpo_sessao.sessoes`), merge Ásia + Europa, perfis de ontem, naked POCs. Long/short e OI de 1 h só como etiqueta secundária, sem peso no gatilho.
- **Como medir.** Critério escrito antes; forma P e forma b medidas separadamente (o viés de alta de 2020–23 aparece no controle e contamina a venda, MEDIDO no estudo 2). Dois controles: (1) a mesma regra com o POC da manhã trocado por um **nível sorteado dentro do range da manhã**; (2) direção sorteada às 13:30. Três períodos, pessimista, mínimo 30 decididos. Aprovação como em E1.

---

## 3. Mapa do dia (modelo dos avisos de 00:00, 08:00 e 13:30 UTC)

Regras do mapa: sai **sem %** até alguma estratégia passar na régua (o aviso diz "nível sozinho = sorteio");
cada nível vem com o **papel** dele (operar / alvo / stop / contexto); nível a mais de 5% do preço fica de fora;
o preço atual e a posição `p` no composto (0 = VAL, 1 = VAH) abrem a mensagem. Níveis que só servem para
alvo ou stop nunca viram "entre aqui".

### 00:00 UTC — abre o dia e a Ásia

| Ordem | Nível | Papel | Por quê |
|---|---|---|---|
| 1 | VAL, POC e VAH do **composto de 10 dias** e a posição `p` do preço | Onde é **permitido** operar: p < 0,25 só compra, p > 0,75 só venda, meio = nada | É o range do Tradeiros (seção 2.1 do perfil). Sem isso, qualquer gatilho das 3 estratégias está no lugar errado. Largura média 6,8% (MEDIDO) |
| 2 | VAH, POC e VAL de **ontem** e se o preço está dentro ou fora | Monta E1 (abriu fora? precisa de 2 blocos dentro) e dá o 1º alvo (POC de ontem) | A regra dos 80% é o setup mais limpo que ainda não foi medido |
| 3 | **Naked POCs** a ≤ 3% e **single prints** de ontem/anteontem | **Alvo** da rotação | O preço atravessa níveis (MEDIDO); o que atravessa chega no próximo ímã. Nunca como entrada |
| 4 | **Máxima e mínima de ontem** | **Stop/invalidação** e referência de presos | Reversão no toque é pior que o sorteio (MEDIDO); como invalidação é o extremo que o mercado já rejeitou |
| 5 | Abertura semanal (segunda) e, se dentro de 5%, VAL/VAH/POC da **semana passada** | Contexto do grau acima; alvo secundário | A abertura semanal foi a resistência de set/2026 no perfil do Tradeiros; como gatilho deu sorteio (MEDIDO) |
| 6 | POC/VAH/VAL do **mês** e do **ano**, só se ≤ 5% | Caro × barato; veto de lado | Perfis longos dizem "premium" ou "desconto"; não dão entrada (MEDIDO) |
| 7 | Agenda: fim de semana? dado às 12:30/14:00/18:00 UTC? | Janelas em que o aviso **não** sai | Regra 17 do perfil (sem scalp com volume baixo) e 3.5 (a notícia não é gatilho) |

### 08:00 UTC — fecha a Ásia, abre a Europa

Repete 1–3 do mapa das 00:00 (atualizados) e acrescenta, nesta ordem:

| Ordem | Nível | Papel | Por quê |
|---|---|---|---|
| a | **Máxima, mínima e POC da Ásia** | Mínima/máxima = stop e referência de presos; POC = 1º alvo de quem opera na Europa | Extremos de sessão no toque = pior que o sorteio (MEDIDO); POC de sessão = sorteio no toque (MEDIDO); como alvo é o uso que resta |
| b | Posição do fechamento da Ásia em relação ao valor de ontem (dentro / acima / abaixo) e forma da Ásia (P, b, D) | Qualifica E1 (se a Ásia abriu fora e já reentrou, o gatilho pode estar perto) e prepara E3 | A forma diz quem está preso |
| c | Se houve **cauda de 30 min** numa borda nas últimas 2 h, com nível, extremo e fechamento | Gatilho de E2 ainda válido (validade de 4 blocos) | É o único fato "já aconteceu" que o mapa pode relatar sem olhar o futuro |

### 13:30 UTC — fecha a Europa, abre a América

Repete 1–3 das 00:00 e a–c das 08:00 (com a Europa somada) e acrescenta:

| Ordem | Nível | Papel | Por quê |
|---|---|---|---|
| i | **POC, VAH, VAL, máxima e mínima da manhã** (merge Ásia + Europa) e a **forma** (P / b / D) | Monta E3: o POC da manhã é o nível do gatilho; a máxima/mínima da manhã é o stop | A América é a sessão de mais volume e a que decide se a manhã vale |
| ii | Preço da América em relação ao valor de ontem (fora → E1 na variante 13:30 fica armada) | Setup | A abertura americana pesa mais que a de 00:00 na leitura do Tradeiros |
| iii | Próximo alvo abaixo e acima a ≥ 2 R do stop candidato, em cada direção | O aviso só nasce se existir alvo a 2 R | Critério de R:R mínimo (regra 19 do perfil: < 3 R não entra; aqui 2 R por ser day trade) |
| iv | Dado econômico de hoje (hora) | Janela em que o aviso não sai ou fecha parciais | Regra 3.5 do perfil |

O que o mapa **não** diz: "compre o VAL", "venda a máxima da Ásia", "o POC vai segurar". Nenhuma dessas frases tem
número que a sustente (MEDIDO).

---

## 4. Ranking e escolha

| # | Estratégia | Potencial (0–10) | Por quê a nota | Risco principal |
|---|---|---|---|---|
| 1 | **E1 — abriu fora do valor e voltou (80%)** | **6** | Gatilho sem parâmetro livre (2 blocos dentro), alvo que é o próprio nível (lição dos estudos), controle limpo (área deslocada), amostra de centenas de eventos, cabe no day trade | O parente mais próximo (desvio confirmado no composto, H2a) deu 25% no holdout; a área de valor diária pode ser estreita para o custo; a abertura de 00:00 UTC é arbitrária em cripto (por isso a variante 13:30 é obrigatória) |
| 2 | **E2 — cauda no bloco de 30 min na borda** | **5,5** | Mais frequente (3–6/semana), é a regra 6 do Tradeiros "só depois de ver a reação", stop estrutural natural; o controle (a) responde à pergunta certa: o nível acrescenta algo à cauda? | Parâmetros (0,30%, 60%) são escolhas; se a cauda sozinha já explica tudo, o TPO vira só filtro de localização; dias de tendência engolem caudas em série |
| 3 | **E3 — a América contra a manhã** | **5** | Usa a assimetria de volume entre sessões e a ideia dos presos de forma estrutural (sem long/short, que não separa); alvo longe e claro | É a que mais se parece com o que já falhou (POC de sessão no toque = sorteio; continuação de extremo 0/183); 1–2 por semana dá amostra menor; forma P/b precisa de definição que não existe no código ainda |

Nenhuma passa de 6 porque o ingrediente de base (o nível) foi medido como sorteio duas vezes no mesmo dia. O
potencial está no **fato** acrescentado ao nível, e isso ninguém mediu ainda.

**Escolha para começar: E1.** Motivos: (1) é a definição mais fechada, com menos lugar para "ajuste" depois de ver o
resultado; (2) o alvo é o nível, que é exatamente a forma de uso que os dois estudos apontam; (3) o controle de
área deslocada diz, sem ambiguidade, se o valor de ontem importa; (4) a amostra é grande o bastante para três
períodos com ≥ 30 decididos em cada um nas 4 variantes. **Risco principal:** a família "saiu e voltou" tem o
histórico do H2a (sorteio, com n pequeno) e, se a área de valor diária do BTC for estreita demais, o alvo de 80% não
paga o custo. Por isso o filtro "largura ≥ 2× stop" entra no critério **antes** de rodar, e não depois.

Se E1 reprovar, E2 é a segunda, porque o controle (a) ensina algo mesmo em reprovação: se a cauda sem nível
reage igual à cauda no nível, o TPO sai de gatilho para sempre e fica só como mapa de alvos e stops, que é o
que a seção 3 já entrega.

### O que este documento não promete

- Nenhuma das três tem número. "Potencial" é a avaliação de um especialista sobre o que ainda falta medir, não
  uma expectativa de ganho.
- A régua que vale é a dos dois estudos: critério escrito antes, custo real, três períodos, pessimista e
  controles sorteados. O que passar vira aviso com % e n ao lado; o que não passar vira linha na lista de
  "medido e reprovado" do agente, para não ser repetido.
