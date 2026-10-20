# VWAP para avisos de scalp e day trade — o que falhou, o que ainda tem potencial e por onde começar

Autor: especialista-vwap (`.claude/agents/especialista-vwap.md`). Data: 20/10/2026.
Para quem lê: capital pequeno, scalp e day trade, sem robô. O que se quer é um **aviso** com lado, zona de entrada,
stop e alvo. Vocabulário do Tradeiros: VWAP ancorada = "preço justo" do movimento; o preço gravita nela; longe dela
está "esticado"; a volta é o "respiro".

Fontes usadas: `docs/tradeiros/perfil_por_regime.md` (seção 2.1, item VWAP ancorada), `core/vwap.py` (interface:
`VWAPCalculator.vwap(anchor_idx)`, `vwap_bandas()` com ±1/2/3σ ponderados por volume, `vwap_intraday()` com âncora
00:00 UTC, `sinal()` por z-score), `core/scalp_indicadores.py` (setups `vwap_tendencia` e `vwap_reversao`),
memória do scalp por indicadores (11/09/2026) e `docs/especialistas/tpo.md` (régua de medição do projeto).
Tudo abaixo está marcado como **MEDIDO** (número que existe no projeto) ou **HIPÓTESE** (ainda não medido).
Nada aqui promete lucro.

---

## 1. Diagnóstico em 8 linhas

1. **MEDIDO.** Scalp 5m, jan–set/2026, 72.577 candles, custo de ida e volta 0,06%: **retomada na VWAP de sessão** (VWAP inclinada, recuo até ±0,25σ, fechamento de volta, do lado do POC da sessão anterior) deu +0,07% por trade no treino (1,14× o custo) e **−0,05% na validação**. Não aprovada.
2. **MEDIDO.** **Reversão nas bandas ±2σ** da VWAP de sessão (candle estica, fecha de volta, alvo na própria VWAP, fora de regime de tendência): **−0,03% por trade** bruto. Perde antes do custo.
3. **MEDIDO.** Laboratório de 516 combinações em 4h e 1h: no 1h sobrou uma só com VWAP de janela + VWAP de sessão + Fibonacci, +0,1 R por trade; no 4h, das aprovadas só 21% seguraram no holdout. Nada que sustente um aviso.
4. **Por que falhou:** a âncora 00:00 UTC é um relógio, não um fato do mercado. O BTC não abre nem fecha; quem ancora à meia-noite calcula o preço médio de um período que nenhum participante escolheu. A VWAP de sessão é referência de **execução** (o desk compara o preenchimento com ela), não de **decisão**; o preço cruza a VWAP de sessão várias vezes por dia e cada cruzamento é um "sinal" que vale o mesmo que um sorteio.
5. **Por que falhou (2):** em 5m o stop de 0,1 ATR colado no candle fica abaixo de 0,25% do preço e o custo pesa 0,2–0,35 R (MEDIDO no scalp de volatilidade). Qualquer vantagem pequena da VWAP, se existe, é menor que isso.
6. **Por que falhou (3):** "retomada" e "reversão" foram testadas como gatilho **isolado**, com o regime vindo de um detector de 40 candles. O método do Tradeiros usa a VWAP ancorada como **mapa** (onde está o preço justo do movimento) e entra por outro fato (quebra de microestrutura, reação vista).
7. **O que isso muda:** a VWAP de sessão sai do papel de gatilho. O que não foi medido é (a) a **ancorada no pivô** do movimento, que é a do Tradeiros; (b) a VWAP como **alvo** de quem esticou; (c) a VWAP de grau maior como **régua de mão** (lado permitido).
8. **Regra para o aviso:** enquanto nenhuma das três passar na régua (critério escrito antes, dois controles sorteados, três períodos), o mapa diz "VWAP ancorada em X, preço a +1,8σ" como **informação** e não como "compre"/"venda". Sem % inventado.

### Resposta curta ao usuário

| Pergunta | O que foi medido | Como usar no aviso |
|---|---|---|
| VWAP de sessão (00:00 UTC) como gatilho | retomada e reversão em 5m = sorteio ou pior (MEDIDO) | Nunca gatilho. Só como referência de "quem está no lucro hoje" e como **alvo** de respiro (V2) |
| Bandas ±2σ | reversão em 5m −0,03% (MEDIDO) | Medida de "esticado" para **contexto** de V2; não como entrada no toque |
| VWAP ancorada no fundo/topo | NUNCA medida aqui (só janela e sessão) | V1: reteste do preço justo depois de quebra de estrutura |
| VWAP semanal/mensal | não medida como gatilho; só no laboratório de 4h/1h como filtro fraco | V3: régua de mão; só compra acima, só vende abaixo |

---

## 2. As 3 estratégias de VWAP com maior potencial ainda não medidas

Critério de escolha: (a) a âncora é um fato do mercado, escolhido sem olhar o futuro; (b) o gatilho é um candle
fechado de 15 min ou 1 h, não um toque; (c) o stop é estrutural (acima de 0,35% do preço, para o custo pesar menos
que 0,2 R); (d) o alvo é concreto e fica a ≥ 2× o stop ou o aviso não sai; (e) dá para medir com o que existe no
projeto; (f) não repete o que foi reprovado.

Convenção: R = distância da entrada média ao stop. Custo de ida e volta 0,06%. Frequências são estimativas
(HIPÓTESE) até alguém contar no histórico. σ = desvio-padrão ponderado por volume da VWAP em questão
(`vwap_bandas()`), nunca ATR.

### V1 — "Reteste do preço justo" (VWAP ancorada no pivô do movimento)

- **Nome.** Reteste da VWAP ancorada no fundo (ou topo) majoritário depois de quebra de estrutura.
- **Âncora exata (regra sem olhar o futuro).** Para compra: o candle de 1 h cuja mínima é a **menor das últimas 168 h** (7 dias). Esse candidato só vira âncora quando, depois dele, um candle de 1 h **fecha acima do último topo de 1 h** que existia antes do fundo (topo = máxima de 1 h com 6 candles menores de cada lado, já confirmado 6 h depois). É a "quebra de microestrutura" da seção 2.1 do perfil. Do fechamento que confirma em diante, a VWAP é calculada do candle do fundo (`vwap(anchor_idx = índice do fundo)`) e **não muda mais**. A âncora morre quando (i) um candle de 1 h fecha abaixo da mínima do fundo, ou (ii) outro candle faz mínima menor nos 7 dias (nasce uma candidata nova; a antiga é descartada). Espelho para venda (maior máxima de 7 dias, fechamento abaixo do último fundo de 1 h). Sem "fundo majoritário" por olhômetro: é a regra acima ou nada.
- **Tempo gráfico.** 1 h para âncora e estrutura; 15 min para o gatilho e a execução das fatias; 1 min para medir o preenchimento.
- **Contexto.** Movimento em andamento: desde a confirmação, o preço precisa ficar **acima** da VWAP ancorada por pelo menos 24 candles de 15 min (6 h) antes do primeiro toque, e a máxima desde a âncora deve estar a ≥ +2σ da VWAP ancorada (o movimento esticou; agora respira). Fora de fim de semana (regra 17 do perfil) e fora de 30 min antes/depois de CPI/FOMC. Não precisa de detector de regime: a própria quebra de estrutura e o preço do lado certo são o regime.
- **Gatilho em candle fechado.** O **primeiro** candle de 15 min cuja mínima toca a faixa [VWAP − 0,5σ ; VWAP + 0,25σ] e que **fecha acima da VWAP ancorada**, no terço superior da própria amplitude. Só o primeiro reteste de cada âncora conta (o segundo e o terceiro são medidos à parte, como variante B, porque o Tradeiros diz que o 3º/4º toque tende a romper).
- **Zona de entrada (3 fatias limitadas).** De VWAP + 0,10% até VWAP − 0,30%, pesos 20/30/50% de cima para baixo (a fatia maior mais longe). Validade: 8 candles de 15 min (2 h) a partir do gatilho; sem preenchimento da 1ª fatia, o aviso morre.
- **Stop.** O mais distante entre (a) mínima do candle de gatilho − 0,15% e (b) VWAP − 1σ. Teto de 1,2% do preço (acima disso, não avisa: o alvo não paga). Típico 0,5–0,9%.
- **Alvo.** 1 R = tirar o risco (realiza 25–50%, stop no preço médio). Alvo final = **máxima do movimento desde a âncora** (o topo que esticou). Se houver POC de ontem ou naked POC no caminho a ≥ 1,5 R, ele vira o 1º alvo. Se a máxima do movimento estiver a < 2 R da entrada média, **não avisa**.
- **R:R típico (HIPÓTESE).** Em movimento de 7 dias com +2σ a +3σ de extensão e stop de 0,6–0,9%: 2–3,5 R até a máxima do movimento.
- **Frequência esperada (HIPÓTESE).** Mínima/máxima de 7 dias seguida de quebra de estrutura: 1–2 por semana somando os dois lados; primeiro reteste com as condições de contexto: 50–60% delas. **1–2 avisos por semana**, 400–600 eventos em 2020–2026. Amostra suficiente para três períodos.
- **De onde vem a vantagem (HIPÓTESE).** A VWAP ancorada no fundo é o preço médio pago por **quem comprou o movimento inteiro**. Quem está comprado desde o fundo vê o reteste como recarga sem prejuízo; os algoritmos que executam compra institucional usam exatamente essa referência para "estar abaixo da VWAP da campanha". É a tese do perfil (F: xV58eHoPD3Y, qvboV9frI94). O que separa de **retomada na VWAP de sessão** (MEDIDO, reprovada): a âncora é um fato (fundo + quebra), não um relógio; só o primeiro reteste vale; o grau é 15 min/1 h e o stop tem tamanho que o custo não engole.
- **O que a mata.** Movimento que acaba no reteste (o primeiro toque na ancorada costuma ser também onde o lado contrário testa a mão: em dia de tendência contra, o preço atravessa); fundo de 7 dias feito em notícia (a VWAP fica "suja" pelo volume do pânico e a σ vira enorme); mercado lateral de semanas, em que a mínima de 7 dias e a quebra de estrutura aparecem a cada 2 dias e a âncora troca sem parar; fim de semana. E o parente mais próximo já medido não ajuda: a retomada na VWAP de sessão deu −0,05% na validação (MEDIDO).
- **Dados necessários.** Já existem: candles de 1 h, 15 min, 5 min e 1 min da Binance (2017–2026), `VWAPCalculator` com `anchor_idx` e `vwap_bandas()`. Falta a **escolha automática do pivô** (o agente já registrou: não existe), que é só a regra acima aplicada ao 1 h.
- **Como medir.** Critério escrito antes; parâmetros fixos (168 h, 6 candles, 24 candles, 0,5σ/0,25σ, 0,30%, 1σ, 2 R). Dois controles: (1) a **mesma mecânica com âncora sorteada** (um candle qualquer dos 7 dias anteriores à confirmação, VWAP calculada dali), que mede se o fundo importa ou se qualquer média ponderada "segura"; (2) **direção sorteada** no mesmo instante. Terceiro controle opcional: a **média simples** do mesmo pivô, para saber se o volume na ponderação acrescenta algo. Três períodos (treino 2020–23, validação 2024–jun/25, holdout jul/25–set/26), pessimista (favor e contra no mesmo candle de 1 min = contra), mínimo 30 decididos por período. Aprova só o que fica líquido > 0 nos três **e** 2 EP acima dos dois controles em treino e validação; holdout lido uma vez.

### V2 — "Esticado volta ao preço justo" (a VWAP é o ALVO, não o gatilho)

- **Nome.** Respiro contra a sardinha: venda responsiva de quem esticou a mercado com OI subindo, alvo na VWAP ancorada.
- **Âncora exata.** A mesma de V1 (fundo/topo de 7 dias confirmado por quebra de estrutura). Enquanto não houver âncora confirmada, usa-se a VWAP ancorada na **abertura semanal** (segunda 00:00 UTC), que é um fato do calendário usado pelo próprio Tradeiros como nível (abertura semanal 82.178 foi a resistência de set/2026, seção 2.1). A regra de qual âncora vale é fixa: V1 se existir, senão semanal.
- **Tempo gráfico.** 15 min para gatilho; 1 h para OI/funding; 1 min para execução.
- **Contexto.** Preço **esticado**: fechamento de 15 min ≥ +2σ da VWAP ancorada (venda) **e** OI da Bybit (1 h) subiu ≥ 1% nas últimas 4 h **e** funding da última janela acima da mediana de 30 dias. É a definição de "esticado" já escrita em `docs/CONSELHO_ESPECIALISTAS.md` (VWAP z ≥ 2, OI subindo, funding alto): comprador alavancado chegando a mercado no topo. Dia de **equilíbrio**, não open-drive: a VWAP de sessão (00:00 UTC) tem inclinação |VWAP_agora − VWAP_4h atrás| < 0,5σ de sessão. Se a sessão está em drive, a regra do agente é clara: não operar reversão.
- **Gatilho em candle fechado.** Depois de ≥ 2 candles de 15 min com fechamento acima de +2σ, o primeiro candle que **fecha abaixo de +2σ** com máxima acima da máxima anterior (fez o topo e voltou: rejeição vista, não antecipada). Espelho para compra em −2σ com OI subindo e funding abaixo da mediana (short esticado).
- **Zona de entrada (3 fatias limitadas).** De +2σ − 0,10% até +2σ + 0,25%, pesos 20/30/50% de baixo para cima. Validade: 6 candles de 15 min (1,5 h).
- **Stop.** Máxima da excursão acima de +2σ + 0,15%. Teto de 1,0% do preço. Típico 0,4–0,8%.
- **Alvo.** A própria **VWAP ancorada** (preço justo). 1 R = tirar o risco e stop no preço médio; se +1σ estiver a ≥ 1 R, +1σ é o 1º alvo e a VWAP o final. Se a VWAP estiver a < 2 R da entrada média, **não avisa** (acontece quando σ é pequena; então o esticado não vale o custo).
- **R:R típico (HIPÓTESE).** Entrada em +2σ, alvo em 0σ, stop a 0,4–0,6σ acima: 3–5 R no papel; na prática, com o preenchimento parcial das fatias, 2–3 R.
- **Frequência esperada (HIPÓTESE).** |z| ≥ 2 na ancorada com OI subindo e dia sem drive: **2–4 por semana** nos dois lados, 700–1.200 eventos em 2020–2026 (o OI da Bybit em 1 h existe desde 2020, 54 mil horas).
- **De onde vem a vantagem (HIPÓTESE).** A reversão nas bandas sozinha paga odds justas (MEDIDO). O que ainda não foi medido é se o **OI subindo com funding alto** separa o esticado que volta (comprador alavancado que vai ser liquidado ou forçado a sair) do esticado que continua (comprador spot em drive). A VWAP aqui só diz **até onde** o respiro vai; o gatilho vem da estrutura (topo feito e perdido) e dos derivativos. O perfil do Tradeiros usa a mesma leitura: "esticado" + presos = jogo responsivo (seções 2.2 e 3.3).
- **O que a mata.** Open-drive que o filtro de inclinação não pega (notícia no meio do dia); OI subindo por hedge institucional e não por sardinha (o dado não distingue); funding "alto" em bull market prolongado (a mediana de 30 dias sobe junto e o filtro vira ruído); σ pequena em dia morto (alvo < 2 R, sem aviso, o que é certo); short squeeze em cima do stop (o stop de 0,15% acima da máxima é estreito para BTC em evento). E o parente mais próximo já medido não ajuda: a reversão nas bandas de sessão em 5m deu −0,03% bruto (MEDIDO).
- **Dados necessários.** Já existem: candles 15 min e 1 min, `oi_bybit_1h.json` (2020–2026), `funding_bybit.json`, `lsr_bybit_1h.json`, `VWAPCalculator`. Falta só a âncora automática (V1).
- **Como medir.** Critério escrito antes; parâmetros fixos (2σ, 2 candles, 1% de OI em 4 h, mediana de 30 dias, 0,5σ de inclinação). **Dois controles obrigatórios**: (1) o **mesmo gatilho sem o filtro de OI/funding**, que responde à única pergunta nova desta estratégia (os derivativos acrescentam algo à banda?); (2) **direção sorteada**. Comparar ainda com a linha já medida (reversão em 5m, −0,03%), que é o ponto de partida. Três períodos, pessimista, mínimo 30 decididos. Aprovação como em V1.

### V3 — "Mudança de mão na VWAP semanal" (a VWAP é a régua de regime; o lado permitido vem dela)

- **Nome.** Aceitação do outro lado da VWAP semanal: day trade só na direção da mão nova.
- **Âncora exata.** Segunda-feira 00:00 UTC (fato de calendário, sem escolha). A VWAP semanal e as bandas ±1σ/±2σ são recalculadas a cada candle de 1 h desde a âncora. Também é lida a VWAP da semana **anterior** (congelada no domingo 23:59 UTC) como nível.
- **Tempo gráfico.** 1 h para o regime e o gatilho; 15 min para a entrada; 1 min para execução.
- **Contexto.** O preço ficou de **um só lado** da VWAP semanal por ≥ 48 h (48 fechamentos de 1 h consecutivos acima, por exemplo): quem comprou a semana está no lucro e a mão é compradora. Fora de fim de semana e de janela de notícia.
- **Gatilho em candle fechado.** Dois fechamentos de 1 h **consecutivos abaixo** da VWAP semanal (perda = mudança de mão), o segundo deles abaixo também da mínima do primeiro (aceitação, não pavio). O aviso nasce no fechamento do 2º candle. Daí em diante o **lado permitido** é só venda até que dois fechamentos de 1 h voltem acima (retomada, que é o gatilho espelho).
- **Zona de entrada (3 fatias limitadas).** No reteste: de VWAP semanal − 0,10% até VWAP semanal + 0,25%, pesos 20/30/50% de baixo para cima. Validade: 12 candles de 1 h. Variante B, medida à parte: entrada a mercado no fechamento do 2º candle (sem esperar reteste).
- **Stop.** Máxima dos últimos 6 candles de 1 h antes do gatilho + 0,15% (o último topo de quem ainda estava comprado). Teto de 1,5% do preço. Típico 0,7–1,2%.
- **Alvo.** −1σ semanal = tirar o risco (1 R mínimo exigido; se −1σ estiver a < 1 R, o aviso espera o reteste mais alto ou morre); alvo final = **−2σ semanal** ou a VWAP da semana anterior, o que estiver mais perto, desde que a ≥ 2 R. Em dia de tendência, trailing por candle de 1 h depois de 2 R.
- **R:R típico (HIPÓTESE).** 2–3 R até −2σ em semana de amplitude normal (σ semanal do BTC entre 1,5% e 3%).
- **Frequência esperada (HIPÓTESE).** Perda ou retomada da VWAP semanal com 48 h de um lado antes: **0,5–1 por semana**, 180–350 eventos em 2020–2026. Amostra menor; os três períodos ficam no limite de 30 decididos cada.
- **De onde vem a vantagem (HIPÓTESE).** A VWAP semanal é o preço médio da semana para todo o mercado; perdê-la depois de 2 dias acima põe no prejuízo quem comprou a semana inteira, e esse comprador defende o preço médio (compra o reteste) até desistir. A aceitação (2 fechamentos, o 2º abaixo do 1º) é o fato de que desistiu. É a regra "perda da VWAP = mudança de mão" do agente, levada para o grau em que a VWAP tem dono (a semana), não para a sessão de 00:00 em que ninguém está preso por convicção. Não é gatilho de toque: a VWAP aqui define **quem pode operar** (lado) e o gatilho é a aceitação.
- **O que a mata.** Semana lateral em que a VWAP é cruzada todo dia (o filtro de 48 h reduz, não elimina); segunda-feira, em que a VWAP tem poucas horas e σ é instável (regra: sem aviso antes de 48 h de semana); mudança de mão em notícia (a aceitação de 2 candles vem tarde e o reteste não acontece); fim de semana (volume baixo cruza a VWAP sem convicção, mas o aviso não sai); amostra pequena. Parente mais próximo medido: o laboratório de 4h/1h com VWAP de janela e de sessão como filtro, fraco (+0,1 R) (MEDIDO), e a "abertura semanal como nível" no estudo de TPO, que deu sorteio no toque (MEDIDO); aqui ela é só âncora, não nível de entrada.
- **Dados necessários.** Já existem: candles 1 h, 15 min e 1 min, `VWAPCalculator` com `anchor_idx` na segunda 00:00 UTC. Nada a coletar.
- **Como medir.** Critério escrito antes; parâmetros fixos (48 h, 2 candles, 6 candles, 0,15%, 2 R). Dois controles: (1) **VWAP semanal com âncora deslocada** ao acaso (um dia da semana sorteado), mesma mecânica, que mede se a segunda-feira importa; (2) **direção sorteada**. Três períodos, pessimista, mínimo 30 decididos (se o holdout não chegar a 30, o resultado fica "inconclusivo", não "aprovado"). Aprovação como em V1.

---

## 3. Ranking e escolha

| # | Estratégia | Potencial (0–10) | Por quê a nota | Risco principal |
|---|---|---|---|---|
| 1 | **V1 — reteste do preço justo (ancorada no pivô)** | **6** | É a VWAP do Tradeiros e nunca foi medida; âncora é um fato (fundo + quebra), não um relógio; só o primeiro reteste conta; stop grande o bastante para o custo pesar < 0,2 R; controle limpo (âncora sorteada) responde à pergunta certa; 400–600 eventos | A família "recuo até a VWAP e fechamento de volta" já perdeu em 5m na sessão (MEDIDO); a regra de pivô (7 dias, 6 candles) é uma escolha, e em lateral a âncora troca sem parar; primeiro toque na ancorada é onde a mão contrária também testa |
| 2 | **V2 — esticado volta ao preço justo (VWAP como alvo)** | **5,5** | A VWAP sai do gatilho e vira só alvo, que é a lição dos estudos de TPO (o nível é para sair); a pergunta nova (OI + funding separam a sardinha?) é respondível com o controle "sem OI"; frequência boa (2–4/semana); dados prontos | A reversão nas bandas já deu −0,03% (MEDIDO); OI não distingue hedge de sardinha; em bull longo o filtro de funding vira ruído; stop estreito em evento |
| 3 | **V3 — mudança de mão na VWAP semanal (régua de lado)** | **5** | Ideia distinta das reprovadas (aceitação, não toque; grau em que a VWAP tem dono); sem parâmetro de âncora (calendário); serve de filtro de lado para V1 e V2 mesmo que não vire aviso sozinha | Amostra pequena (180–350 eventos, holdout no limite); segunda-feira com σ instável; parente mais próximo (VWAP como filtro no 1h) foi fraco (MEDIDO) |

Nenhuma passa de 6 porque a VWAP, nas duas formas já medidas, pagou odds justas. O potencial está em mudar o
**papel** da VWAP (de gatilho para mapa, alvo e régua) e a **âncora** (de relógio para fato), e isso ninguém mediu.

**Escolha para começar: V1.** Motivos: (1) é a ferramenta exata que o Tradeiros usa e a única das três que o
projeto declarou "nunca testada"; (2) a regra de âncora é fechada e verificável sem olhar o futuro, então não há
"ajuste depois de ver o resultado"; (3) o controle de âncora sorteada diz, sem ambiguidade, se o pivô importa ou se
qualquer média ponderada "segura" (se o controle empatar, V1 morre e V2/V3 herdam a lição); (4) a amostra permite
três períodos com ≥ 30 decididos. **Risco principal:** é da mesma família da retomada de sessão, que passou no treino
(+0,07%) e caiu na validação (−0,05%); se o resultado do treino vier positivo e pequeno (< 2× o custo), é para
desconfiar, não para comemorar. V2 vem em seguida, porque reaproveita a âncora de V1 e o controle "sem OI" responde à
pergunta mais barata do projeto hoje (os derivativos já coletados acrescentam algo?). V3 fica como filtro de lado das
outras duas até ter amostra própria.

### O que este documento não promete

Nenhuma das três tem número. "Potencial 6" é a opinião de um especialista sobre quanto vale medir, não probabilidade
de acerto. Um aviso com % só sai depois de critério escrito antes, dois controles sorteados e três períodos, como
em `docs/especialistas/tpo.md`. Se o controle de âncora sorteada empatar com V1, a conclusão é a mesma dos estudos
de TPO: a VWAP diz **onde**, não **que**.
