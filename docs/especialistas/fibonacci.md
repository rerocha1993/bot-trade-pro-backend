# Fibonacci para avisos de scalp e day trade — régua de alvo e de escalonamento, não gatilho

Autor: especialista-fibonacci (`.claude/agents/especialista-fibonacci.md`). Data: 20/10/2026.
Para quem lê: capital pequeno, scalp e day trade, sem robô. O que se quer é um **aviso** com lado, zona de entrada,
stop e alvo. Fibonacci entra como o Tradeiros usa: proporção entre pernas, para dizer **onde a correção costuma acabar**
(zona de entrada em fatias) e **onde o impulso costuma se esgotar** (alvo e parciais). Nunca como linha mágica.

Fontes usadas: `docs/tradeiros/perfil_por_regime.md` (2.1 Fibonacci, 2.4 gestão), `core/fibonacci_strategies.py`
(interface: swing = extremo da janela de 100 candles → SL/TP por fase), `core/elliott_pro/pivots.zigzag_atr`
(pivô confirmado quando o preço reverte `fator_atr` ATRs; o último pivô é provisório), memória da calibração de
11/09/2026 e do scalp por indicadores de 11/09/2026. Tudo marcado **MEDIDO** (número que existe) ou **HIPÓTESE**.
Nada aqui promete lucro.

---

## 1. Diagnóstico em 8 linhas

1. **MEDIDO.** O recuo de Fibonacci da sessão como gatilho de scalp em 5 min (11/09/2026, 72.577 candles, treino/validação, critério fixado antes) **não foi aprovado**: bruto zero ou negativo antes do custo de 0,06%. Tocar 0,5–0,786 não é motivo para comprar.
2. **MEDIDO.** No laboratório de 1 h, Fibonacci só sobreviveu em confluência (VWAP janela + VWAP sessão + Fibonacci) e deu **+0,1 R por trade**: fraco, no limite do acaso. Sozinho, nada.
3. **MEDIDO.** Calibração de Elliott (fora da amostra 2024–2026): **88% de acerto com alvo 0,3% e stop 2,5%** e bruto ~0 R. A probabilidade prevista bate com a real, mas o alvo "no Fibonacci mais perto" infla o acerto e mata o R:R. O mercado paga odds justas.
4. **O que isso ensina:** o alvo tem de ser **proporcional ao stop** (≥ 2–3 R), nunca o nível de Fibonacci mais próximo. Se o próximo nível está a menos de 2 R, ele não é alvo: é parcial ou é nada.
5. **Por que Fibonacci é régua, não gatilho:** o nível diz *onde* a proporção entre pernas costuma fechar, não *que* vai fechar. O gatilho tem de ser um fato em candle fechado que o nível não dá: a **quebra de microestrutura** antes do reteste (o que o Tradeiros exige) ou a rejeição vista na zona.
6. **Por que é régua de escalonamento:** 0,5 a 0,786 é uma faixa de 0,286 da perna (0,3–0,9% do preço numa perna de 1–3%). Larga o bastante para 5–9 limitadas com peso crescente para baixo e stop único atrás de 1,0. É aí que fatiar faz diferença: **MEDIDO** que uma escada de ±0,25% é a mesma coisa que entrada única (95–98% preenchida), mas uma faixa de 0,5–0,9% nunca foi medida.
7. **A escolha da perna decide tudo.** `FibonacciStrategies` usa o extremo de 100 candles; isso troca de perna a cada candle novo e não é a perna "do olho" do Tradeiros. Para aviso e para medir, a perna tem de ser objetiva e fechada no passado: **ZigZag ATR** (fator 2,0, ATR 14), só pivôs confirmados.
8. **Nunca medido** (e é o que vale medir): zona 0,5–0,786 com escada e stop em 1,0 **depois de quebra de microestrutura** em 15 m/1 h; parciais em 0,5/0,618 e alvo 1,618 como regra de saída dos outros avisos; o lado contrário (perna que perde 1,0 e prende quem comprou a zona).

### Resposta curta

| Pergunta | O que foi medido | Como usar no aviso |
|---|---|---|
| Comprar 0,5–0,786 | gatilho de 5 min reprovado (MEDIDO) | Só **depois** de quebra de microestrutura, em fatias, stop atrás de 1,0 (E1, HIPÓTESE) |
| Golden pocket / TGP 0,618–0,666 | nada isolado | Fatia de maior peso dentro da escada, não entrada única |
| 0,382 | nada | Só com Elliott dizendo "início de onda 3"; fora disso, não entra |
| Alvo em 1,0 / 1,272 / 1,618 | alvo perto mata o R:R (MEDIDO) | Alvo = o primeiro nível a ≥ 2 R; os anteriores viram parciais (E2) |
| Parciais 0,5 e 0,618 | nunca medido | Regra de saída comum a todos os especialistas (E2) |
| Fibonacci de tempo, log × linear | nunca medido | Fora do scalp/day trade (ver 2.4) |

---

## 2. As 3 estratégias/usos com maior potencial ainda não medidos

Convenção: L = tamanho da perna (fundo → topo). R = distância da entrada **média preenchida** ao stop. Custo de ida e
volta 0,06%. Frequências são estimativas (HIPÓTESE) até alguém contar no histórico. Tudo em candle fechado; nada olha
o futuro; o último pivô do ZigZag (provisório) nunca define a perna de entrada.

### E1 — Compra em fatias de 0,5 a 0,786 depois de quebra de microestrutura

- **Nome.** Reteste escalonado do Tradeiros ("compra no reteste 0,5–0,786 depois de quebra de microestrutura"). Espelhado para venda em 0,5–0,786 da queda.
- **Regra objetiva da perna (sem olhar o futuro).** ZigZag ATR no 15 min (fator 2,0, ATR 14). O fundo da perna é o **último pivô de baixa confirmado**. O topo é a máxima feita **depois da quebra** (abaixo), congelada no candle do gatilho; se o preço fizer máxima nova antes da primeira fatia preencher, a perna é refeita e as ordens recolocadas (uma vez; na segunda, o aviso morre).
- **Tempo gráfico.** Perna e gatilho em 15 min; execução das fatias em 1 min. Variante medida à parte: 1 h.
- **Contexto exigido.** Preço no terço de baixo do composto de 10 dias, ou Elliott (15 m/1 h) permitindo compra (não é onda 4 nem correção recém-iniciada). Não avisa em dia de evento (CPI, FOMC) nem fim de semana.
- **Gatilho (candle fechado).** Quebra de microestrutura: um candle de 15 min **fecha acima do último pivô de alta do ZigZag de 5 min** (fator 1,0) feito depois do fundo. Sem a quebra não há perna válida para retrair; esse é o fato que o Fibonacci sozinho não tem.
- **Zona de entrada (5 limitadas, post-only).** Frações da perna medidas do topo para baixo: **0,50 / 0,572 / 0,643 / 0,714 / 0,786**, pesos **10 / 15 / 20 / 25 / 30%** (mais mão mais fundo, como as 9 ordens de xV58eHoPD3Y). Validade: 8 candles de 15 min (2 h) a partir do gatilho; se nenhuma fatia preencher, o aviso morre. Se preencheu só 1–2 fatias e o preço saiu, fechar no reteste do topo (regra do Tradeiros para entrada mal preenchida).
- **Stop.** Abaixo de **1,0 da perna** (o pivô de baixa) − 0,10%, a mercado. Típico 0,4–0,6 L.
- **Alvo e parciais.** Tirar o risco em 1 R (realiza 25–50%, stop no preço médio; 1 R cai perto de 0,236–0,382 da perna). Parcial de 25% no reteste do topo (1,0). Alvo final na **extensão 1,618** (topo + 0,618 L). Se Elliott entregar invalidação e alvo, eles prevalecem.
- **R:R (HIPÓTESE).** Com média preenchida em ~0,67 L e stop em 1,0 + 0,10%: até 1,0 ≈ 1,7 R; até 1,618 ≈ 3,3 R. Filtro: só avisa se L ≥ 0,8% (abaixo disso 1 R não paga o custo).
- **Frequência (HIPÓTESE).** Em 15 min, 2–5 pernas confirmadas por dia; com quebra e reteste de 0,5 preenchido, 1–2 avisos por dia em dia de tendência, zero em dia morto. Em 6,7 anos, milhares de eventos: amostra boa.
- **De onde vem a vantagem (HIPÓTESE).** A quebra de microestrutura mostra comprador agressivo; o reteste 0,5–0,786 é onde quem perdeu a quebra recompra e onde fica o stop de quem vendeu o topo. O escalonamento converte a incerteza de "onde acaba a correção" em preço médio, em vez de em acerto.
- **O que a mata.** Perna escolhida errada (ZigZag sensível demais vira ruído; lento demais perde a perna). Correção que passa de 0,786 e fecha abaixo de 1,0 (o caso de E3). Dia de tendência de baixa, onde cada reteste é venda. E o parente mais próximo foi reprovado: recuo de Fibonacci da sessão em 5 min sem quebra (MEDIDO, 11/09). Esta regra é outra (perna por ZigZag, quebra exigida, escada larga, 15 m/1 h), mas a família tem histórico ruim.
- **Como medir.** Critério escrito antes: fator do ZigZag, pesos e frações fixos, zero iteração. Controles: (1) mesma gestão com a **faixa sorteada** (mesma largura da zona, posicionada ao acaso entre 0,1 e 0,9 da perna), que mede se 0,5–0,786 vale algo; (2) **direção sorteada** no mesmo gatilho; (3) entrada única em 0,618 com o mesmo stop, que mede se a escada acrescenta. Preenchimento pessimista (fatia só preenche se a mínima do minuto ficar abaixo do preço; favor e contra no mesmo candle = contra). Três períodos (treino 2020–23, validação 2024–jun/25, holdout jul/25–set/26), mínimo 30 decididos por período. Aprova só o que fica líquido > 0 nos 3 e 2 EP acima dos controles em treino e validação; o holdout é lido uma vez.

### E2 — Régua de alvos e parciais (0,5 / 0,618 / 1,618) para os avisos dos outros especialistas

- **Nome.** Régua de saída comum. Não gera entrada; recebe um aviso (lado, entrada média, stop) de TPO, fluxo, Elliott ou E1 e devolve tirar-risco, parciais e alvo.
- **Regra objetiva da perna.** ZigZag ATR (fator 2,0, ATR 14) **no tempo gráfico do aviso**. Perna de referência: (a) para aviso **responsivo** (compra numa queda, venda numa alta), a perna é o movimento contrário que está sendo comprado, do último pivô confirmado ao extremo atual; (b) para aviso **de continuação** (depois de quebra), a perna é o impulso que foi retraído.
- **Tempo gráfico.** O do aviso (15 min ou 1 h). Em 5 min as pernas são pequenas demais para os níveis ficarem a 2 R.
- **Contexto exigido.** Um aviso válido de outro especialista com stop estrutural. Sem stop não há R, e sem R a régua não funciona.
- **Gatilho.** Não tem; é o do aviso de origem.
- **Zona de entrada.** A do aviso de origem.
- **Stop.** O do aviso de origem (invalidação). A régua nunca encurta o stop para "caber" o alvo.
- **Alvo e parciais (a regra).** 1) Em **1 R**: realiza 25–50% e leva o stop ao preço médio (não é Fibonacci; é a regra do Tradeiros). 2) Aviso responsivo: parcial de 25% em **0,5** e 25% em **0,618** da perna contrária, **só se estiverem a ≥ 1,5 R**; abaixo disso a parcial é pulada (não realizar perto). 3) Aviso de continuação: parcial em **1,0** (reteste do extremo), alvo final em **1,618** da perna. 4) **Alvo final obrigatório ≥ 2 R.** Se nenhum nível de Fibonacci antes de 2,618 (ou antes da invalidação de Elliott, ou do VAH/VAL oposto) está a ≥ 2 R, **o aviso não sai**. 5) O resto (25%) vai com stop móvel atrás do último pivô de baixa do ZigZag no tempo do aviso.
- **R:R.** Por construção ≥ 2 R no alvo final; parciais em 1 R e 1,5–2 R. A esperança por trade passa a depender só do acerto, que é o que se mede.
- **Frequência.** A dos avisos de origem.
- **De onde vem a vantagem (HIPÓTESE).** Não é vantagem de entrada: é **não devolver o R:R**. A lição da calibração (88% com 0,3% de alvo = zero) diz que a saída perto é o que zera trades com entrada boa. Realizar em proporção da perna, e só longe, deixa a assimetria viva; o stop no médio em 1 R tira a cauda da perda.
- **O que a mata.** Entrada sem vantagem: nenhuma gestão cria esperança onde o lado é moeda (MEDIDO: a mesma lógica em Elliott, assimetria e indicadores deu odds justas). Mercado lateral apertado, onde 1,618 nunca chega e a posição vira 1 R realizado + stop no médio = zero menos custo. Perna errada, que põe 0,5/0,618 em lugar nenhum.
- **Dados necessários.** Já existem (candles de 5 min e 1 min, ZigZag ATR, avisos de E1 e do E1 do TPO quando forem gerados).
- **Como medir.** A variável é a **regra de saída**, não a entrada: nas mesmas entradas (E1, o E1 do TPO e um conjunto de entradas com **direção sorteada** como controle), comparar (a) alvo fixo 2 R sem parciais, (b) esta régua, (c) só 1 R e stop no médio, (d) a régua com **níveis deslocados ao acaso** à mesma distância média (mede se a proporção de Fibonacci importa ou só a distância). Critério antes: a régua só é adotada se bater (a) e (d) em treino e validação nos avisos reais **e** não bater nada nas entradas sorteadas (se ganha no sorteio, é tendência do período, não a régua). Três períodos, 30 decididos por período.

### E3 — Perna morta: quem comprou 0,5–0,786 ficou preso

- **Nome.** Falha do reteste (o contrário de E1). Escolhido no lugar de Fibonacci de tempo e de log × linear porque é o único dos três que cabe em day trade e se mede com os dados que existem (ver 2.4).
- **Regra objetiva da perna.** A mesma de E1 (ZigZag ATR 15 min, fundo = último pivô de baixa confirmado, topo = máxima depois da quebra). E3 só existe onde E1 existiu: a perna já teve quebra de microestrutura e o preço entrou em 0,5–0,786.
- **Tempo gráfico.** 15 min para perna e gatilho; 1 min para as fatias.
- **Contexto exigido.** Preço no meio ou no terço de cima do composto de 10 dias (abaixo do VAL o Tradeiros não vende), ou Elliott permitindo venda. Não avisa em dia de evento.
- **Gatilho (candle fechado).** O preço tocou a zona 0,5–0,786 **e** um candle de 15 min **fecha abaixo de 1,0 da perna** (o pivô de baixa). A perna morreu; quem comprou a zona com stop em 1,0 saiu a mercado ou está preso.
- **Zona de entrada (3 limitadas).** Venda no reteste, de baixo para cima, em **0,886 / 0,786 / 0,70** da perna (a antiga zona de compra, agora resistência), pesos 30 / 40 / 30%. Validade: 8 candles de 15 min; sem reteste, morre.
- **Stop.** Acima de **0,618** da perna + 0,10% (se o preço recupera o golden pocket, não há preso), a mercado.
- **Alvo e parciais.** Tirar o risco em 1 R. Parcial de 25% em **−0,272** (projeção 1,272 da queda, abaixo do fundo). Alvo final em **−0,618** (projeção 1,618). Se houver naked POC ou VAL abaixo e mais perto, ele vira a parcial e −0,618 segue como alvo.
- **R:R (HIPÓTESE).** Entrada média ~0,79 L, stop em 0,618 + 0,10%: ≈ 0,2 L de risco. Até −0,272: ≈ 2,3 R; até −0,618: ≈ 4 R. Filtro: L ≥ 0,8%.
- **Frequência (HIPÓTESE).** Uma fração das pernas de E1 (as que falham): 0–1 por dia, mais em dia de queda. Amostra provável de centenas de eventos em 6,7 anos.
- **De onde vem a vantagem (HIPÓTESE).** Presos definidos **estruturalmente** (quem comprou a zona viu a perna fechar abaixo do fundo), não por indicador. O reteste da zona é onde eles saem no zero a zero, e onde não ficam os stops de quem vendeu o rompimento. É a leitura "fundo pobre / preso" do Tradeiros aplicada à própria zona de Fibonacci.
- **O que a mata.** Varrida: fecha abaixo de 1,0 por um candle e volta (fundo falso, que em Elliott é o fim da onda 2 ou da C). Distinguir exige o candle fechado, e isso custa entrada pior. A família "presos" por long/short da Bybit **não separou nada** (MEDIDO, estudo 2 de TPO); a definição estrutural é outra, mas não há número a favor dela.
- **Como medir.** Mesmo protocolo de E1. Controles: faixa de venda sorteada dentro da perna; direção sorteada no mesmo gatilho; e, específico, **mesmo gatilho sem exigir que a zona tenha sido tocada** (mede se "houve comprador preso" acrescenta algo a "perdeu o fundo").

### 2.4 Por que não Fibonacci de tempo nem log × linear (por enquanto)

- **Log × linear.** Em pernas de day trade (1–3%) a diferença entre nível log e linear é de centésimos de por cento, menor que o custo. Só importa acima de ~30% de movimento (semanal/mensal), que é mapa de Elliott, não aviso de scalp. HIPÓTESE sem efeito mensurável nesta escala.
- **Fibonacci de tempo.** Projeta data de topo/fundo por proporção entre durações de pernas (o Tradeiros projetou "topo por volta de 24/09/2026"). Em day trade a amostra por perna é pequena, a tolerância (±1 candle) engole a precisão e não há regra objetiva do Tradeiros para a razão usada. Vale, se um dia, como **validade** de aviso (não entrar depois de 1,618 do tempo da perna anterior), e só depois de E1 e E2 terem número.

---

## 3. Ranking, por onde começar e risco principal

| Ordem | Uso | Nota 0–10 | Por quê |
|---|---|---|---|
| 1 | **E2 — régua de alvos e parciais** | **7** | Não aposta num gatilho; aplica-se a todo aviso (TPO, fluxo, Elliott, E1), ataca o erro medido (alvo perto mata o R:R) e se mede com os dados que existem. Potencial de **não perder** o que a entrada deu, não de criar vantagem. |
| 2 | **E1 — compra escalonada depois de quebra** | **6** | É o aviso do Tradeiros, nunca medido na forma certa (quebra + perna objetiva + escada larga + 15 m/1 h). Parente de 5 min sem quebra reprovado, e a escada em faixa estreita já deu "igual à entrada única". |
| 3 | **E3 — perna morta** | **5** | Hipótese plausível (presos estruturais), mas depende de E1 existir e a família "presos" por indicador não separou nada. |
| — | Fibonacci de tempo, log × linear | 2 | Fora da escala de day trade; sem regra objetiva. |

**Por onde começar:** medir **E1 e E2 juntas**, em 15 min e 1 h. E2 sozinha não tem de onde sair; E1 sozinha repetiria o erro da calibração se o alvo for o nível mais perto. O estudo entrega duas respostas separadas: (i) o gatilho de E1 fica acima da faixa sorteada e da direção sorteada? (ii) a régua de E2 fica acima do alvo fixo de 2 R e dos níveis deslocados nas entradas reais, e **não** nas sorteadas? Se (i) falhar e (ii) passar, E2 vira a régua dos avisos de TPO e de fluxo e Fibonacci sai do gatilho de vez. Se as duas falharem, Fibonacci fica no projeto só como alvo de Elliott, que é onde já está.

**Risco principal:** a **perna**. ZigZag ATR com fator 2,0 em 15 min pode não ser a perna que o Tradeiros vê "do olho"; se o fator for ajustado até passar, é sobreajuste, e se ficar fixo pode medir uma perna que ninguém opera. Por isso fator e tempo gráfico ficam escritos antes (2,0 e 14; 15 min e 1 h, só esses dois) e o controle de faixa sorteada existe: se a zona 0,5–0,786 não bater uma faixa aleatória **na mesma perna**, a proporção de Fibonacci não vale nada e o problema não é a perna. Segundo risco, já conhecido: nenhuma régua de saída cria esperança em entrada que é moeda (MEDIDO três vezes neste projeto); E2 só tem valor em cima de aviso que já tenha número.
