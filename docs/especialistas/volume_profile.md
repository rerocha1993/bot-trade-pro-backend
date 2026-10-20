# Volume Profile para avisos de scalp e day trade — o que o VP diz que o TPO não diz, e por onde medir

Autor: especialista-volume-profile (`.claude/agents/especialista-volume-profile.md`). Data: 20/10/2026.
Para quem lê: capital pequeno, scalp e day trade, sem robô. O que se quer é um **aviso** com lado, zona de entrada,
stop e alvo. O TPO (tempo por preço) é coberto por `docs/especialistas/tpo.md`; este documento trata só do que é
**volume por preço**: HVN/LVN como estrutura, delta por nível (presos) e perfil ancorado no movimento.

Fontes: `docs/tradeiros/perfil_por_regime.md` (2.1 e 2.2, "delta por nível no composto", "HVN como zona reativa",
"vazio abaixo da VAL"), `core/volume_profile_pro.py` (interface), `data/estudo_niveis_tpo_resumo.md`,
`data/estudo_niveis_tpo_2_resumo.md`, memórias dos estudos de scalp (11/09 e 13/09/2026) e os 30 dias de negócios
da Bybit em `dados/trades_bybit/` (10/08 a 08/09/2026, com lado do agressor, ~1,2 milhão de negócios por dia).
Tudo abaixo é **MEDIDO** (número que existe no projeto) ou **HIPÓTESE** (ainda não medido). Nada promete lucro.

---

## 1. Diagnóstico em 8 linhas: TPO × VP

1. **TPO conta tempo; VP conta volume.** Um preço que ficou 3 blocos de 30 min num domingo vale 3 TPOs, igual a 3 blocos de terça às 14:30 UTC com 20× o volume. O VP pesa o segundo e descarta o primeiro. Em BTC, que negocia 24 h com volume muito desigual entre sessões, essa é a diferença que importa.
2. **MEDIDO (TPO).** POC/VAH/VAL por tempo, de qualquer grau, no primeiro toque = preço sorteado (0 de 180 em 5 min; 0 de 16 no composto em 15 min). Extremos piores que o sorteio. Escada de 5 limitadas = entrada única. Long/short da Bybit como "presos" não separa (1 de 36, sem ★).
3. **MEDIDO (VP).** A única coisa de VP já testada foi a **regra dos 80% pelo VP** no scalp 5m (11/09/2026): bruto ~0, reprovada; e o VP como voto no laboratório de votação, sem vantagem no holdout. Nos dois casos o VP entrou como **linha** (VAH/VAL por volume) e com sinal de **rompimento** (`price_signal`: acima da VAH = compra), o oposto do jogo responsivo do Tradeiros.
4. **Nunca medido com VP:** HVN e LVN como **zona** com largura (o código atual devolve os 3 bins de maior e menor volume, 3 linhas, não zonas); delta por nível (não existe no código; só há 30 dias de dado com lado); perfil **ancorado** no fundo ou topo de um movimento (o módulo só faz janela fixa de candles); e POC/VA por **volume** medidos separadamente do TPO.
5. **O que o VP pode dizer e o TPO não:** (a) **onde não há negócio** (LVN): no vazio o preço não tem referência e "pode parar em qualquer lugar", logo não é lugar de entrada nem de stop; (b) **onde o grande player negociou** (HVN largo = comprometimento, não só permanência); (c) **quem agrediu em cada preço** (delta por nível): o TPO não sabe se o volume do nível foi compra ou venda a mercado, e é exatamente aí que o Tradeiros procura os presos; (d) **o preço justo de um movimento** (POC ancorado), que o perfil por calendário não enxerga.
6. **Aproximação do VP atual.** `VolumeProfilePRO` distribui o volume do candle uniformemente entre máxima e mínima. Com candles de 1 min da Binance (existem desde nov/2019; amplitude típica de 0,03–0,1%, do tamanho de um bin de 0,1%) a aproximação fica perto do real. **HIPÓTESE a confirmar com os 30 dias de negócios reais**: POC e bordas do VP de 1 min caem no mesmo bin de 0,1% do VP feito negócio a negócio na maioria dos dias. Se confirmar, o histórico de 2020–2026 serve para medir V1 e V3 sem coletar nada.
7. **Lição dos estudos que vale para o VP:** o nível sozinho não é gatilho e o preço atravessa níveis. Logo, no VP, a entrada tem de nascer de um **fato** (fechamento que aceita o vazio, reteste de um bloco de presos, volta ao POC do impulso) e o alvo tem de ser **estrutura concreta** (o próximo HVN, o POC ancorado), a ≥ 2× o stop.
8. **Ordem de valor esperada (HIPÓTESE):** o ingrediente mais novo é o **delta por nível**, porque acrescenta informação que nenhum estudo até hoje teve (lado do agressor). A estrutura HVN/LVN é o que dá para medir **amanhã** com o dado que existe. O perfil ancorado é o mais parecido com o que já reprovou (volta a um nível) e fica por último.

### Resposta curta: o que o VP entrega no aviso

| Objeto de VP | Estado | Papel no aviso |
|---|---|---|
| VAH/VAL/POC por volume (composto 10 dias) | linha ≈ TPO, família reprovada (MEDIDO para TPO; regra dos 80% pelo VP reprovada em 5m) | Só localização: quartil de baixo compra, de cima vende, meio nada. Não é gatilho |
| HVN largo (zona) | HIPÓTESE | Alvo da travessia; stop atrás dele; zona onde o preço "para e gira" |
| LVN / vazio | HIPÓTESE | Corredor: o preço que aceita o vazio tende a atravessá-lo; proíbe entrada e stop no meio dele |
| Bloco de delta (presos) | HIPÓTESE, sem dado histórico | Suporte/resistência "com dono": quem está preso defende ou corre; reteste é o gatilho |
| POC ancorado no impulso | HIPÓTESE | Preço justo do movimento; a volta a ele com o movimento ainda válido é a zona de compra da onda 2 |

---

## 2. As 3 estratégias de VP com maior potencial ainda não medidas

Critério de escolha: (a) o objeto é de **volume**, não de tempo, e não é só uma linha; (b) gatilho em candle fechado
(15 min ou bloco de 30 min), sem olhar o futuro; (c) stop estrutural, nunca no meio de um vazio; (d) alvo concreto a
≥ 2× o stop; (e) diz o que falta coletar; (f) não repete o que reprovou (rompimento de VAH/VAL, regra dos 80% em 5m,
1º toque de linha).

Convenções: bins de **0,1% do preço** (como `core/tpo_sessao.py`), VP construído com candles de **1 min**
(aproximação) ou com negócios (real). R = distância do preço médio ao stop. Custo de ida e volta 0,06%.
Frequências são estimativas (HIPÓTESE) até alguém contar no histórico.

### V1 — "Corredor de vazio" (LVN como caminho, HVN como alvo)

- **Perfil usado.** Composto por volume dos **10 dias anteriores** (00:00 UTC de D, candles de 1 min, bins de 0,1%). Dele saem as zonas: **HVN** = sequência de bins contíguos com volume ≥ 50% do bin do POC, largura ≥ 0,3%; **LVN (vazio)** = sequência contígua com volume ≤ 15% do bin do POC, largura ≥ 0,5%, situada **entre dois HVN** (vazio nas pontas do perfil não conta: é só o fim do range). Perfil e zonas fixos para o dia inteiro.
- **Contexto em que vale (HIPÓTESE).** O preço passou as últimas 2 h (8 candles de 15 min) **dentro** de um HVN que faz fronteira com um vazio, sem ter atravessado esse vazio nas últimas 24 h (vazio "virgem" no dia). O composto segue inteiro (preço dentro de [mínima, máxima] dos 10 dias). Vale nos dois sentidos: HVN abaixo do vazio → compra; HVN acima → venda.
- **Gatilho exato (candle fechado).** Um candle de 15 min **fecha dentro do vazio**, a ≥ 0,10% da borda do HVN, depois de pelo menos 4 fechamentos consecutivos dentro do HVN. É a "aceitação" de um preço onde ninguém negociou: o leilão perdeu a referência e procura a próxima.
- **Zona de entrada (3 fatias limitadas).** Reteste da borda do HVN por dentro do vazio: de borda + 0,15% até borda − 0,05% (compra), pesos 20/30/50% de cima para baixo (a fatia maior na borda). Validade: 8 candles de 15 min (2 h); sem reteste, o aviso morre. Variante B, medida à parte: a mercado no fechamento do gatilho.
- **Stop.** **Meio do HVN deixado para trás** (média aritmética das bordas do HVN) − 0,10%. É estrutural: se o preço volta ao centro do nó de volume, o vazio foi rejeitado. Típico 0,4–0,8% do preço. Nunca "na borda": a borda é onde o reteste acontece.
- **Alvo concreto.** 1º alvo (tirar o risco: realiza 25–50%, stop no preço médio) = **meio do vazio**; alvo final = **borda próxima do HVN do outro lado** − 0,05%. Filtro antes de avisar: (borda do HVN oposto − entrada) ≥ 2 × stop; se não, **não avisa**.
- **R:R típico (HIPÓTESE).** Vazios de 0,8–2,0% no composto de 10 dias do BTC (largura média do valor 6,8%, MEDIDO) contra stop de 0,4–0,8%: 2–3 R.
- **Frequência esperada (HIPÓTESE).** O composto de 10 dias costuma ter 1–3 vazios internos; com o gatilho de 4 fechamentos + 1 fora, 2–4 avisos por semana. Em 6,7 anos, algumas centenas de eventos por lado.
- **De onde vem a vantagem (HIPÓTESE).** O vazio é um preço rejeitado no passado sem que ninguém construísse posição nele; quando o preço entra e **fecha** ali, não há limitadas de quem comprou ou vendeu ali para segurar, e os stops de quem construiu posição no HVN deixado para trás ficam logo atrás. É a leitura de Dalton ("o preço atravessa rápido o LVN") e o "vazio abaixo da VAL" do Tradeiros, usado como corredor e não como lugar de entrada.
- **O que a mata.** O parente mais próximo já reprovou: **continuação depois do extremo de dia/sessão deu 0 de 183 (MEDIDO)** e a regra dos 80% pelo VP não passou em 5m (MEDIDO). A diferença aqui é que o objeto é de volume e tem largura, mas a família "rompeu e continua" tem histórico ruim. Também mata: pavio que entra no vazio e fecha de volta (não é gatilho, e o estudo diz que o pavio costuma atravessar); vazio estreito que não paga 2 R; fim de semana (volume baixo cria vazios falsos no composto); notícia na janela; HVN muito largo (stop longe demais, R:R abaixo de 2).
- **Dados necessários.** **Já existem**: candles de 1 min da Binance desde nov/2019 (`data/historico/BTCUSDT_binance_1m_eventos.csv.gz`) e 5/15 min; os 30 dias de negócios da Bybit servem para validar a aproximação (diagnóstico, linha 6). **Falta no código**: HVN/LVN como zonas contíguas com largura (hoje são 3 linhas), composto por volume de N dias e detecção de vazio entre nós. Nada a coletar.
- **Como medir.** Critério escrito antes, parâmetros fixos (50% / 15% / 0,3% / 0,5% / 4 fechamentos / 0,10%), nenhum iterado. **Três controles**: (1) a **mesma mecânica com o vazio deslocado ao acaso** (mesma largura, posição sorteada dentro do range dos 10 dias), que responde se a estrutura de volume importa ou se "4 fechamentos + 1 fora" já explica tudo; (2) **direção sorteada** no mesmo instante; (3) a linha simples do 1º toque da borda do HVN, para comparar com o que o TPO deu (sorteio). Três períodos (treino 2020–23, validação 2024–jun/25, holdout jul/25–set/26), pessimista (favor e contra no mesmo candle = contra), ≥ 30 decididos por período, custo 0,06%. Aprova só com líquido > 0 nos 3 períodos **e** 2 EP acima dos controles (1) e (2) em treino e validação; o holdout é lido uma vez.

### V2 — "Reteste do bloco de presos" (delta por nível no composto)

- **Perfil usado.** **Perfil de delta por nível** dos **5 dias anteriores** (bins de 0,1%), construído de negócios com lado do agressor: em cada bin, volume comprador a mercado − volume vendedor a mercado, e também o volume total. Sem candles: o delta por nível **exige** negócio a negócio com lado. Um **bloco de presos vendidos** = ≥ 3 bins contíguos com delta/volume ≤ −25% e volume de cada bin ≥ 40% do bin do POC (muita gente vendeu a mercado ali). Bloco de presos comprados = espelho (≥ +25%).
- **Contexto em que vale (HIPÓTESE).** O preço fechou **acima** do bloco de presos vendidos por ≥ 8 candles de 15 min (2 h) e está a ≥ 0,5% do topo do bloco: quem vendeu a mercado ali está perdendo e ainda não foi expulso. O bloco está no quartil de baixo ou no meio-baixo do composto de 10 dias (não vale bloco colado na VAH). Espelho para venda: presos comprados acima do preço.
- **Gatilho exato (candle fechado).** Primeiro candle de 15 min que **toca o bloco** (mínima ≤ topo do bloco) vindo de ≥ 0,5% acima e **fecha acima do topo do bloco**. É o reteste "com dono": os vendidos presos, que agrediram ali, recompram para sair no zero a zero e os compradores que os prenderam defendem a zona.
- **Zona de entrada (3 fatias limitadas).** Terço superior do bloco: de topo + 0,05% até topo − (1/3 da altura do bloco), pesos 20/30/50% de cima para baixo. Validade: 4 candles de 15 min (1 h).
- **Stop.** **Base do bloco − 0,10%.** Se o preço fecha abaixo de onde os vendedores agrediram, eles deixaram de estar presos e o bloco virou resistência. Blocos de 0,3–0,6% dão stop de 0,4–0,8%.
- **Alvo concreto.** 1º alvo = POC por volume dos 5 dias (ou a máxima das 2 h de contexto, o que estiver mais perto, para tirar o risco); alvo final = **próximo HVN acima** (do composto de 10 dias, como em V1) ou o bloco de presos comprados mais próximo acima (quem comprou lá vai vender no zero a zero: é onde o movimento tende a parar). Filtro: alvo final ≥ 2 × stop, senão não avisa.
- **R:R típico (HIPÓTESE).** 2–3 R; blocos estreitos com HVN longe dão 3–4 R.
- **Frequência esperada (HIPÓTESE).** 2–5 blocos vivos por semana em cada lado, 1–3 retestes qualificados por semana. Em 5 dias de perfil, o bloco envelhece e some sozinho.
- **De onde vem a vantagem (HIPÓTESE).** É a regra do Tradeiros em tOeA ("blocos de delta negativo abaixo = vendedores presos") e o que o TPO não pode ver: o TPO sabe que houve negócio no preço, o delta sabe **quem** agrediu. O estudo 2 mediu "presos" por long/short de contas da Bybit (relação de contas, não de preço) e não separou (MEDIDO, H5); aqui o preso tem **endereço** (o bin onde agrediu) e **tamanho** (o volume), que é a definição estrutural que o especialista de TPO pediu e ninguém mediu.
- **O que a mata.** O dado: delta do perpétuo da Bybit é só um pedaço do mercado (o Tradeiros olha Coinbase spot e derivativos somados); se o bloco da Bybit não coincidir com o da Binance, o conceito é frágil. O agressor que vendeu no bloco pode já ter saído (stopado acima) antes do reteste: o bloco envelhece sem avisar. Tendência de baixa forte: o reteste é só o caminho para baixo. Fim de semana e notícia. E a família "reteste de nível" é, no fundo, "nível segura?" (MEDIDO como sorteio para linhas de TPO); o controle (1) abaixo é o que separa.
- **Dados necessários (o que falta coletar).** **Existe**: 30 dias de negócios da Bybit com lado (10/08–08/09/2026), suficientes para construir o perfil de delta e fazer um **piloto** (contagem de blocos, retestes e reações), **não** para veredito (um período só, ~30 eventos). **Falta**: histórico de negócios com lado para 2020–2026. Caminhos: (a) **Bybit público** (`public.bybit.com/trading/BTCUSDT/`, um csv.gz por dia desde 2020, o mesmo formato de `dados/trades_bybit/`): ~60 MB/dia, ~130 GB no total, logo deve ser **reduzido ao baixar** (por dia: delta e volume por bin de 0,1%, poucos KB) e o bruto descartado; (b) **Binance aggTrades** (`data.binance.vision`, spot e futuros USDT-M, campo `is_buyer_maker` dá o lado), para cruzar duas corretoras; (c) **Coinbase** só ao vivo pelo websocket `matches` (não há histórico público): ligar um coletor **agora**, ao lado do `coletor_livro.py`, porque é a referência do Tradeiros e cada dia sem coletar é um dia perdido. Sem (a) ou (b), V2 não pode ser medida em três períodos.
- **Como medir.** Critério escrito antes, parâmetros fixos (5 dias, −25%, 40%, 3 bins, 2 h, 0,5%). **Controles**: (1) **o mesmo bloco pelo volume, sem o sinal do delta** (≥ 3 bins com volume ≥ 40% do POC, delta qualquer): mede se o delta acrescenta algo ao HVN; (2) **bloco de delta deslocado ao acaso** (mesma altura, posição sorteada); (3) direção sorteada. Três períodos, pessimista, ≥ 30 decididos por período, custo 0,06%. Antes de tudo: **piloto nos 30 dias** para fixar os limiares (−25%, 40%) **uma vez** e por escrito; o histórico só é aberto depois. Aprova com líquido > 0 nos 3 períodos e 2 EP acima dos controles (1) e (2).

### V3 — "Volta ao POC do impulso" (perfil ancorado)

- **Perfil usado.** VP **ancorado** no **fundo do impulso** (compra) ou no topo (venda): do candle do fundo até o candle da máxima do movimento, candles de 1 min, bins de 0,1%. Dele saem POC, VAL e VAH **do impulso** (70% do volume do movimento). Fundo = mínima dos 3 dias anteriores à **quebra de estrutura** em 1 h (fechamento de 1 h acima do último topo relevante, definido como o maior high entre dois lows mais altos). O perfil é recalculado a cada candle de 1 h só **enquanto a máxima é renovada**; quando o recuo começa, ele congela.
- **Contexto em que vale (HIPÓTESE).** O impulso tem ≥ 2,5% de amplitude e ≥ 12 h de duração; o POC ancorado está entre **0,382 e 0,786 do impulso** (medido do fundo): o volume do movimento ficou no meio, que é a forma de um impulso "patrocinado". Se o POC está acima de 0,382 do topo (forma **P**: muito volume em cima), não compra: é a definição de compradores presos em cima se falhar. O composto de 10 dias não foi rompido para baixo e o preço não está no quartil de cima do composto.
- **Gatilho exato (candle fechado).** O recuo chega ao POC ancorado (mínima ≤ POC) e um **bloco de 30 min fecha acima do POC**, com o fundo do impulso intacto. É a volta ao "preço justo" do movimento, a mesma lógica da VWAP ancorada do Tradeiros, mas com o preço onde o volume de fato ficou.
- **Zona de entrada (3 fatias limitadas).** De POC + 0,15% até **VAL ancorado** (ou POC − 0,30%, o que for mais perto), pesos 20/30/50% de cima para baixo: a fatia maior fica na borda de baixo do valor do impulso.
- **Stop.** **VAL ancorado − 0,15%**, nunca o fundo do impulso (longe demais para day trade). Se o preço fecha abaixo do valor do impulso, o movimento perdeu o patrocínio. Típico 0,6–1,2%.
- **Alvo concreto.** 1º alvo (tirar o risco) = VAH ancorada; alvo final = **máxima do impulso** − 0,05%. Filtro: (máxima − entrada média) ≥ 2 × stop, senão não avisa. Extensão acima da máxima fica para o especialista de Fibonacci.
- **R:R típico (HIPÓTESE).** Impulso de 3–6% com POC em 0,5–0,618 e stop de 0,8–1,2%: 2–3 R até a máxima.
- **Frequência esperada (HIPÓTESE).** Quebra de estrutura em 1 h com impulso ≥ 2,5% acontece 1–3 vezes por semana; nem todo recuo chega ao POC: 1–2 avisos por semana. É day trade longo, não scalp.
- **De onde vem a vantagem (HIPÓTESE).** No impulso, quem comprou no POC ancorado é a maior parte do volume comprador do movimento; a volta a esse preço é onde essa maioria está no zero a zero e tende a defender, e onde quem perdeu a entrada compra "a correção". É a onda 2 do Tradeiros, lida pelo volume em vez de pela contagem.
- **O que a mata.** É a estratégia mais parecida com o que reprovou: "voltar a um nível e segurar" (POC = sorteio no 1º toque, MEDIDO). A diferença é só a âncora no movimento em vez do calendário, e isso pode não bastar. A definição do fundo/quebra de estrutura tem liberdade (3 dias, 2,5%, 12 h), e cada liberdade é um lugar para sobreajuste. Impulso de notícia (CPI, FOMC) faz POC alto e falso. Em tendência de baixa de grau maior, o recuo não para no POC do impulso (regra 16 do perfil: mínima renovada sem máxima renovada → não compra).
- **Dados necessários.** **Já existem**: candles de 1 min, 15 min e 1 h da Binance; ZigZag/estrutura de `core/elliott_pro/` pode servir de âncora, mas é preferível a definição mecânica acima, mais simples de auditar. **Falta no código**: VP ancorado (início e fim por candle, não por janela fixa) e congelamento no início do recuo. Nada a coletar.
- **Como medir.** Critério escrito antes; os 5 números (3 dias, 2,5%, 12 h, 0,382–0,786, 30 min) fixos. **Controles**: (1) **a mesma volta, a um preço sorteado entre 0,382 e 0,786 do mesmo impulso**: mede se o POC por volume acrescenta algo ao "recuo de Fibonacci" (que já reprovou no scalp 5m como "recuo de Fibonacci da sessão", MEDIDO); (2) direção sorteada; (3) a mesma regra com a **VWAP ancorada** no mesmo fundo, para saber qual preço justo funciona melhor, se algum. Três períodos, pessimista, ≥ 30 decididos por período, custo 0,06%. Aprova com líquido > 0 nos 3 períodos e 2 EP acima do controle (1) em treino e validação.

---

## 3. Ranking, escolha para começar e risco principal

| # | Estratégia | Potencial (0–10) | Por quê a nota | Risco principal |
|---|---|---|---|---|
| 1 | **V2 — reteste do bloco de presos (delta por nível)** | **6,5** | Único ingrediente que **nenhum** estudo teve (lado do agressor); é a leitura central do Tradeiros para os presos; o controle "mesmo bloco sem delta" responde a pergunta certa; o piloto cabe nos 30 dias que já existem | **Não tem dado histórico**: precisa reduzir ~130 GB da Bybit (ou o aggTrades da Binance) a delta por bin antes de medir; e o delta de uma corretora só pode não representar o mercado. Se a coleta não começar hoje, V2 fica em hipótese por meses |
| 2 | **V1 — corredor de vazio (LVN caminho, HVN alvo)** | **6** | Dá para medir **agora** com o 1 min que existe; o objeto tem largura (não é a linha que reprovou); o controle "vazio deslocado" decide de uma vez se a estrutura de volume importa, o que também vale para V2 (cujo bloco é definido sobre volume) | É continuação depois de "sair" de uma zona, e a continuação de extremos deu 0 de 183 (MEDIDO); vazios falsos de fim de semana; se o controle (1) empatar, o VP como estrutura morre e sobra só o delta |
| 3 | **V3 — volta ao POC do impulso (ancorado)** | **5** | Perfil ancorado é o único que vê o "preço justo" de um movimento; casa com a onda 2 e a VWAP ancorada do Tradeiros; dado pronto | É "voltar ao nível" com outra âncora (família reprovada: POC = sorteio, recuo de Fibonacci reprovado em 5m); 5 parâmetros livres na definição do impulso; amostra pequena (1–2/semana) |

Nenhuma passa de 6,5 porque os parentes mais próximos de todas elas foram medidos como sorteio e porque "potencial"
aqui é a opinião de um especialista sobre o que falta medir, não uma expectativa de ganho.

**Escolha para começar: V1, com a coleta de V2 ligada no mesmo dia.**

- **Por que V1 primeiro:** (1) não depende de coleta: o 1 min da Binance desde 2019 e a aproximação uniforme bastam, e os 30 dias de negócios reais validam a aproximação antes de rodar (diagnóstico, linha 6); (2) a definição é fechada (seis números fixos) e o controle do vazio deslocado é limpo; (3) o resultado ensina mesmo em reprovação: se o vazio deslocado reage igual ao vazio real, HVN/LVN saem de gatilho para sempre e ficam só como mapa de alvos e stops, e V2 passa a ser medida já sabendo que o volume por si não separa.
- **Por que a coleta de V2 começa hoje:** o delta por nível é o único caminho que acrescenta informação nova, e o gargalo é o dado, não a ideia. A redução diária (delta e volume por bin de 0,1%) é pequena e pode rodar em segundo plano enquanto V1 é medida; o coletor da Coinbase (websocket `matches`) começa a construir a série que não existe em lugar nenhum.
- **Risco principal da escolha:** V1 é da família "rompeu e continua", a que mais reprovou no projeto (continuação 0 de 183, regra dos 80% pelo VP em 5m). Por isso o filtro de largura (vazio ≥ 2× stop) e o controle de vazio deslocado entram no critério **antes** de rodar, e a nota 6 já desconta esse histórico. Se V1 reprovar e V2 ficar sem dado, o VP fica neste projeto como **mapa** (HVN = alvo e stop; vazio = onde não entrar) e não como gatilho, que é o uso compatível com tudo o que foi medido até aqui.

### O que este documento não promete

- Nenhuma das três tem número. Frequências, R:R e "de onde vem a vantagem" são HIPÓTESES até o estudo com critério
  escrito antes, custo real, três períodos, leitura pessimista e controles sorteados.
- O que passar vira aviso com % e n ao lado (formato de `docs/CONSELHO_ESPECIALISTAS.md`, seção 4.1); o que não
  passar vira linha na lista de "medido e reprovado" do agente, para não ser repetido.
