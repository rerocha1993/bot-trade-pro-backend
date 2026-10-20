# Conselho de especialistas e mesa de avisos — diagnóstico e desenho

Data: 20/10/2026. Pedido do usuário: deixar de ter um robô que opera e passar a ter um sistema que
**avisa** quando entrar, para que lado, com entrada, alvo e stop, por tipo de indicador, e com a
probabilidade de cada aviso dar certo. Foco em scalp e day trade com capital pequeno.

Este documento é a análise antes de qualquer código novo, como o usuário pediu nas outras vezes.

---

## 1. O que o projeto já tem (levantado hoje)

### 1.1 Indicadores e leituras

| Leitura | Onde está | O que entrega hoje | Falta para o conselho |
|---|---|---|---|
| **TPO por sessão** (o "de verdade", 30 min, faixa fixa de 0,1%) | `core/tpo_sessao.py` | perfil por dia UTC e por sessão (Ásia 00–08h, Europa 08–13h30, América 13h30–20h), POC/VAH/VAL, máxima/mínima, single prints, caudas, merge de N dias, naked POCs | perfil **semanal, mensal e anual** (só existe merge de N dias); sessão da noite (20–24h) |
| TPO de janela (antigo) | `core/tpo.py`, `core/volume_profile_pro.py` | POC/VA sobre os últimos N candles; sinal de ROMPIMENTO (acima da VAH = compra) | é o contrário do jogo responsivo; não entra no conselho |
| Range (merge adaptativo) | `core/range_tradeiros.py` | VAL/VAH/POC do composto de 3–20 dias, aceitação, toques, plano de borda | — |
| Aberturas e pivô virgem | `tradeiros/leitura.py` | abertura do dia, semana, mês; pivô diário virgem | — |
| **Elliott multi-grau** | `core/elliott_pro/` | várias contagens vivas com probabilidade calibrada, próximo movimento, invalidação (= stop) e alvos (Fibonacci) | em 1 min é ruído (medido); usar só 15m/1h/4h como mapa |
| **Presos** (long/short de contas) | `core/contexto_derivativos.py` | LSR da Bybit contra a mediana de 30 dias: vendidos presos no VAL, comprados presos na VAH | é a única leitura que já mostrou diferença em borda (ver §2) |
| Funding, OI, Fear & Greed | `tradeiros/leitura.py`, `core/dados_derivativos.py` | histórico desde 2020 (OI/LSR 1h, funding 8h) | — |
| Order flow (CVD, delta, absorção, imbalance do livro) | `core/order_flow.py`, `core/motor_fluxo.py` | ao vivo pelo websocket da Bybit; histórico só 30 dias de negócios (ago–set/2026) | — |
| **Livro de ordens ("nuvens")** | `api/routes/nuvens_endpoint.py`, `core/market_data.order_book_composto` | lê o livro da Coinbase, Binance e Bybit **na hora**, soma por faixa de distância, imbalance | **nunca foi gravado**: não existe histórico para medir nada |
| Liquidações | `core/dados_derivativos.liquidacoes()` | total de 24h da Coinglass (chave vazia) | sem mapa de liquidação, sem coleta |
| VWAP, Order Block, Fibonacci, regime | `core/vwap.py`, `core/order_block.py`, `core/fibonacci*.py`, `core/regime.py` | níveis e sinais por candle | já testados no scalp (§2) |

### 1.2 Dados históricos

- Candles Binance BTCUSDT 5m/15m/1h/4h/1d de ago/2017 a **12/09/2026** (precisam ser atualizados até hoje
  com `scripts/baixar_historico.py`). O 1m só existe em janelas de 3h em volta de 1.530 eventos.
- OI e long/short da Bybit de hora em hora desde ago/2020; funding desde 2018 (inverse) e 2020 (linear).
- Negócios reais da Bybit: 30 dias (10/08 a 08/09/2026), 1,9 GB.
- Livro de ordens: **nada**. Liquidações: **nada**.

### 1.3 Avisos e execução

- Telegram já existe (`services/telegram_alert_service.py`), mas está **desligado**: no `.env` o token e o
  chat_id estão com o texto literal do nome da variável. Basta o usuário preencher os dois.
- Os robôs rodam em threads do `BotManager`; a thread de manutenção é o molde certo para um serviço de
  avisos que roda a cada minuto sem abrir ordem.
- O painel já tem a tela `/range` (perfis por dia e sessão, naked POCs, presos). Uma tela `/avisos` seguiria
  o mesmo padrão.

---

## 2. O que já foi medido (e não vai ser repetido)

Tudo abaixo foi testado com custo real, treino/validação/holdout e, desde 13/09, com a régua da **direção
sorteada** (a mesma regra com o lado sorteado nos mesmos candles; o real precisa ficar acima de ~95% dos sorteios).

| Ideia | Resultado | Fonte |
|---|---|---|
| Elliott calibrado (prob certa, 19% vs 89% fora da amostra) | probabilidade correta, **odds justas**: ~0 R bruto por trade | `scripts/calibracao_lucro.py` |
| Scalp 5m por indicadores (VWAP, VA 80%, OB, Fibonacci) | nenhum dos 6 setups aprovado | `scripts/backtest_scalp.py` |
| Motor de fluxo (barra por volume, absorção) em 30 dias de negócios | bruto zero | `scripts/backtest_fluxo.py` |
| Scalp de volatilidade + single prints (1 min) | negativo antes do custo nos 3 períodos | `scripts/backtest_scalp_vol.py` |
| Jogo do range Tradeiros (compra VAL, vende VAH) | −3,9 / −5,1 / +7,5 R (treino/validação/holdout); ~15 trades/ano | `scripts/backtest_range.py` |
| Carteira Shaka × Maroja em BTC | abaixo do p95 dos sorteios em todos os períodos | `scripts/backtest_tradeiros.py` |
| Votação 2 de 4 + 5 fatias no 4h (robô 9) | era artefato do motor otimista; corrigido caiu a +0,047/+0,025/−0,001 R, indistinguível de sorte | `scripts/checagem_motores.py` |
| **Presos como filtro da borda** (LSR contra a mediana de 30 d) | VAL segura 74% com presos × 64% sem; VAH 70% × 57%; estável 2020–22 e 2023–26; como filtro, a borda foi de +0,1 R para +3,9 R (controle invertido −1,8 R), **mas só 40 trades** | `scripts/estudo_bordas.py`, `scripts/backtest_range_fluxo.py` |

Observação: o item "melhor candidato" no fim de `.claude/agents/perito-btc.md` está desatualizado (é o robô 9
antes da correção do motor). Vou corrigir esse texto quando o usuário aprovar o plano.

**Conclusão honesta:** tudo que lê só o candle paga odds justas. O único sinal que diferenciou foi
**informação fora do candle** (quem está preso). As "nuvens" do livro são exatamente desse tipo, e nunca
foram medidas porque nunca foram gravadas.

### 2.1 Estudo novo de hoje: quais níveis do TPO fazem o preço reagir

Rodando em `scripts/estudo_niveis_tpo.py` (resultado em `data/estudo_niveis_tpo_resumo.md`): para cada nível
(POC/VAH/VAL/máx/mín do dia anterior, de cada sessão de ontem e de hoje, naked POCs, semana, mês, ano, aberturas)
mede a reação no primeiro toque contra **níveis sorteados**, em três períodos. O resultado entra na seção 5
assim que terminar.

---

## 3. O indicador das "nuvens" (nome e o que ele é)

O que o usuário descreveu — junta Coinbase e outras grandes, desenha nuvens vermelhas (venda) e verdes
(compra), mercado esticando contra uma nuvem pesada de venda e depois caindo forte — é o **heatmap de
liquidez do livro de ordens** (Bookmap, Coinglass "Liquidity/Orderbook Heatmap", Hyblock, TensorCharts; no
vocabulário do Tradeiros, o "calço" e as "nuvens" da Coinbase spot). Variante próxima: o **mapa de
liquidações** (onde as posições alavancadas seriam liquidadas), que a Coinglass desenha como nuvens também.

Como ele vira um aviso testável:

- **Parede** = soma de ordens numa faixa de 0,1% muito acima do normal (ex.: > 3× a mediana das faixas a
  mesma distância nas últimas 24h), **persistente** (presente em N snapshots seguidos; parede que some quando
  o preço chega é spoof e não conta).
- **Esticado** = VWAP da sessão com z ≥ 2, OI subindo nas últimas horas, funding alto e long/short acima da
  mediana (sardinha comprando a mercado).
- **Aviso** "topo contra nuvem": preço esticado para cima, a menos de 0,3% de uma parede vendedora
  persistente que não some → venda responsiva, stop acima da parede, alvo VWAP/POC. Simétrico para o fundo.

**Pré-requisito que não existe:** histórico do livro. Precisa de um **coletor** gravando o livro da Coinbase,
Binance e Bybit (profundidade 1–5% em faixas de 0,1%) a cada 30 s, em disco. Só depois de algumas semanas
dá para medir se a nuvem segura mais que o sorteio. Sem isso, qualquer "probabilidade" dessa leitura seria
inventada. Por isso o coletor é o **primeiro** passo do plano, e não o último.

---

## 4. Desenho do conselho

Princípio único, aprendido com o motor otimista: **o mesmo código que gera o aviso ao vivo é o que roda no
histórico**. Cada especialista é uma função pura `avaliar(contexto) -> lista de Avisos`; o serviço ao vivo e o
calibrador chamam a mesma função. Nada de robô: o conselho não abre ordem.

### 4.1 O aviso

```
Aviso
  especialista   tpo | elliott | fluxo | nuvens
  tipo           ex.: "VAL do merge, 1º toque, presos a favor"
  lado           compra | venda
  zona_entrada   [preço de cima, preço de baixo]  (para 3–5 limitadas em fatias)
  stop           preço (invalidação)
  tirar_risco    preço de 1 R (realiza 25–50%, stop no médio)
  alvo           preço (2–3 R, ou POC/VAH/VAL/naked POC mais próximo)
  rr             alvo/stop
  prob           % de alvo antes do stop, medida no histórico para ESTE tipo de aviso (com n e período)
  controle       % do mesmo tipo com nível sorteado (para o usuário ver se o aviso vale algo)
  validade       até quando o aviso vale (fim da sessão, ou X candles)
  motivo         texto curto com os números
```

### 4.2 Os especialistas

1. **TPO (níveis e sessões)** — o pai de todos. Fonte: `core/tpo_sessao.py` + perfil semanal/mensal/anual
   (novo: merge por calendário). Avisos responsivos no **primeiro toque** de: VAL/VAH/POC do merge, do dia
   anterior, de cada sessão (Ásia, Europa, América) de ontem e de hoje, naked POC diário/mensal, abertura
   diária/semanal, pivô virgem. Nada no meio do range (o aviso diz "meio: não operar"). Cada tipo de nível
   só entra se o estudo de hoje mostrar reação acima do sorteio em treino E validação.
2. **Elliott (mapa)** — `core/elliott_pro` em 15m/1h/4h. Não gera entrada sozinho: entrega **a direção
   permitida, a invalidação e o alvo** que os outros avisos usam para stop e alvo, e os vetos de ciclo
   (fundo de ciclo ninguém vende; correção recém-iniciada ninguém compra). Aviso próprio só no setup de
   onda 2 (0,5–0,618 com invalidação abaixo do fundo), que é o que o Tradeiros opera.
3. **Fluxo e derivativos (contexto, presos)** — `core/contexto_derivativos.py` + funding/OI. Não gera entrada:
   **qualifica** o aviso do TPO (presos a favor / contra / neutro, OI subindo, funding caro, fim de semana) e
   é a primeira variável da probabilidade, porque é a única que já mostrou diferença medida.
4. **Nuvens (livro)** — começa como **coletor**; vira especialista quando houver histórico. Enquanto isso, o
   aviso mostra as paredes atuais como informação, **sem probabilidade**.

### 4.3 O calibrador (de onde vem o %)

- Reproduz cada especialista sobre o 5m de 2020–2026 (e 1m onde houver), sem olhar o futuro, com stop antes
  do alvo no candle ambíguo, custo maker/taker real.
- Agrupa os avisos por tipo (nível × lado × sessão × presos) e mede: n, % alvo-antes-do-stop, bruto e líquido
  em R, e o **controle** (mesmo tipo com nível sorteado, 20 sorteios).
- Só vira aviso ao vivo o tipo que fica acima do controle em treino e validação; o holdout é olhado uma vez.
- O % exibido é o do histórico **com o n ao lado**. Com n < 100 o aviso sai marcado "pouca amostra".

### 4.4 O serviço de avisos

- Thread no molde da manutenção do `BotManager`, a cada 60 s (ou a cada bloco de 30 min para o TPO).
- Saída: Telegram (depois que o usuário preencher token e chat_id) + tabela em `data/avisos.jsonl` +
  tela `/avisos` no painel (aviso aberto, histórico, acerto real dos avisos já enviados).
- **Mapa do dia** às 00:00, 08:00 e 13:30 UTC: os níveis da sessão que começa, com o % de cada um.
- Acompanhamento: cada aviso enviado é fechado depois (alvo, stop ou tempo), e a tela mostra o acerto real
  contra o prometido. É o teste ao vivo da calibração.

---

## 5. Resultado do estudo dos níveis (20/10/2026)

Script `scripts/estudo_niveis_tpo.py`; um toque por linha em `data/estudo_niveis_tpo.csv` (36.335 toques);
tabelas completas e regra exata em `data/estudo_niveis_tpo_resumo.md`. 2.446 dias (2020-01 a 2026-09), 36
tipos de nível, 6 níveis sorteados por dia como controle, três períodos (treino 2020–23, validação 2024–jun/25,
holdout jul/25–set/26), critério escrito antes: líquido > 0 nos três períodos.

Regra: primeiro toque do dia num nível, vindo de >= 0,5% na última hora; reação = anda R a favor antes de
R contra (1:1) ou 2R antes de 1R (2:1), R = 0,3% e 0,6%, limite 4h, stop antes do alvo no candle ambíguo,
custo 0,06% ida e volta.

**Veredito: 0 de 180 combinações (nível × lado × R × formato) com líquido positivo nos três períodos.**

| família | % de reação 1:1, R=0,3% (treino → holdout) | leitura |
|---|---|---|
| controle (sorteio) | 45–46% → 44–49% | a régua |
| POC do dia, da sessão, da semana, do mês, do ano; naked POC | 46–49% → 47–50% | igual ao sorteio |
| VAH / VAL (dia, semana, mês) | 45–48% → 45% | igual ao sorteio |
| máxima / mínima do dia, da sessão, da semana | 37–39% → 41–44% | **pior** que o sorteio: o preço que chega de longe no extremo o atravessa mais que o acaso |
| aberturas (dia, semana, mês) | 42–44% → 47–50% | igual ao sorteio |

Nem a continuação nos extremos (hipótese testada depois, "comprar o rompimento") paga o custo: 0 de 183.
Quebrar por sessão (Ásia/Europa/América/noite) ou por fim de semana não salva nenhum tipo com amostra
razoável; os recortes positivos têm n de 40–75 e erro padrão de 6–8 pontos, o que é o esperado em 150 recortes.

**O que isso significa para o aviso de scalp:** "o preço chegou no POC/VAH/VAL/naked POC" não tem valor
estatístico como gatilho isolado em 5 minutos com alvo de 0,3–0,6%. Os níveis são iguais a um preço
sorteado. Os extremos de dia e sessão são piores: comprar a mínima de ontem ou vender a máxima perde para o
sorteio.

### 5.1 Segundo estudo (mesmo dia): as bordas do composto em 15 min

Script `scripts/estudo_niveis_tpo_2.py`; resumo com regra exata em `data/estudo_niveis_tpo_2_resumo.md`. Mesma
régua (controle sorteado, três períodos, custo real, stop antes do alvo), agora com o composto de 10 dias
(VAL/VAH/POC de `core/range_tradeiros.contexto`), candles de 15 min, R = 1% e 2%, limite de 2 dias. Cinco
hipóteses fixadas antes de rodar:

| hipótese | resultado | combinações positivas nos 3 períodos |
|---|---|---|
| H1 tempo maior: VAL compra, VAH vende, POC reage (composto fixo e adaptativo) | igual ao sorteio | 0 de 16 e 0 de 24 |
| H2 desvio (fechou fora e voltou) × dentro do valor | sem vantagem; o desvio confirmado tem 71/26/20 toques e reagiu em 25% no holdout | 2 de 13, nenhuma 2 EP acima do controle |
| H3 toque virgem × 2º × 3º+ | não aparece o gradiente "cada toque enfraquece" | 0 de 12 |
| H4 escada de 5 limitadas em ±0,25% | é a mesma operação que a entrada única (95–98% preenchido) | 0 de 16 |
| H5 presos (long/short contra a mediana), OI subindo, funding do lado | **não separa** VAL nem VAH nesta régua | 1 de 36 (o complemento da hipótese) |

Com 117 testes, 3 positivas é o que o acaso produz, e nenhuma ficou 2 erros padrão acima do controle em
período algum. Durante a rodada apareceu um olhar-futuro na H2 (entrada no nível condicionada ao fechamento
do mesmo candle); ele inflou o **controle sorteado** para positivo nos três períodos e foi corrigido antes da
leitura das hipóteses — mais uma prova de que a régua do sorteio é o que salva o estudo.

Ressalva sobre os presos: o estudo de 11/09 (`scripts/estudo_bordas.py`, VAL segura 74% × 64%) media outra
coisa (chegar ao POC antes de perder o extremo, em 3 dias, só em range válido). Nesta régua de 1–2% em 2 dias
o efeito não aparece. Os dois resultados convivem; o que não existe é um sinal de entrada medido.

Única linha para guardar: "VAL com fechamento abaixo nas últimas 4 h, entrada no nível" ficou positiva em 2 dos
4 formatos (+0,03/+0,16/+0,11 R e +0,09/+0,03/+0,15 R, n = 225), sem ★. Candidata a **reteste pré-registrado em
dados novos**, não a aprovação.

**Conclusão dos dois estudos:** nenhum nível de TPO, em 5 min nem em 15 min, com nenhuma das qualificações
do método (desvio, toque virgem, fatias, presos), produz reação acima de um preço sorteado depois do custo.

---

## 6. Ordem de execução proposta

1. **Coletor do livro** (Coinbase + Binance + Bybit, 30 s, faixas de 0,1% até ±5%, em disco). Ligar hoje
   porque cada dia sem coleta é um dia a menos de histórico. Sem risco: só lê.
2. **Atualizar candles** até hoje e baixar o 1m contínuo de 2024–2026 (para scalp o 5m é grosseiro).
3. ~~Segundo estudo dos níveis~~ **Feito em 20/10 (seção 5.1): nada aprovado.** O especialista TPO não tem
   nenhum nível com % acima do sorteio para avisar, nem em 5 min nem em 15 min.
4. **Especialista TPO + calibrador**: sem base. O que ainda faz sentido construir do TPO é o **mapa do dia**
   (níveis das sessões, composto, naked POCs, aberturas) como informação para o humano, **sem %**, e o aviso
   de proximidade ("preço a 0,2% do VAL do composto"), deixando claro que o nível sozinho não bate o sorteio.
   Reteste pré-registrado da linha "VAL com fechamento abaixo nas 4 h" quando houver 6+ meses de dados novos.
5. **Serviço de avisos** + Telegram + tela `/avisos` + acompanhamento do acerto real.
6. **Elliott como mapa** (direção permitida, invalidação, alvo, veto de ciclo) acoplado aos avisos.
7. Depois de 4–6 semanas de livro gravado: **medir as nuvens** contra o sorteio e, se passar, ligar o
   quarto especialista com %.

O que depende do usuário: preencher `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env` (e trocar as chaves
vazadas, pendência antiga); dizer se o scalp é em 1 min ou 5 min; manter o servidor (ou o coletor) ligado
para o livro ser gravado.

## 7. O que este desenho não promete

- O % de cada aviso vai ser **o medido**, e tudo que foi medido até hoje em candle fica perto de odds
  justas. O ganho esperado de um aviso de TPO puro, pelo que se sabe, é zero antes do custo; o que pode
  mudar isso é a qualificação por presos e, mais tarde, pelo livro. O sistema vai mostrar o controle ao lado
  do % justamente para o usuário não confiar num número que não bate o sorteio.
- O humano continua sendo quem decide: o conselho tira a necessidade de olhar a tela, não a necessidade
  de julgar.
