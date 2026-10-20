# Recomendação do conselho — como usar cada indicador

20/10/2026. Síntese dos 10 especialistas (`.claude/agents/especialista-*.md`), das propostas em `docs/especialistas/`,
do plano de gestão (`plano_gestao.md`) e das três lives lidas hoje (contagem: TZND78d0dVY; presos no footprint: xc2nq9ti8Ns).

## A resposta curta

Nenhum indicador, sozinho, avisa uma entrada que ganhe do acaso. Isso foi medido no projeto em tudo que lê só o candle.
O que o Tradeiros faz, e o que dá para copiar, é **dividir o trabalho**: cada indicador responde uma pergunta diferente
e o aviso só sai quando todas respondem a favor.

| Pergunta | Quem responde | Como usar | Como NÃO usar |
|---|---|---|---|
| **Onde** operar | **TPO** (composto de 10 dias, valor de ontem, sessões) | Só no quarto de baixo do composto compra, no quarto de cima vende, no meio nada. POC, naked POC e single print são **alvo**. Máxima e mínima de dia/sessão são **stop**. | Entrar porque o preço tocou o POC/VAH/VAL. Medido: igual a um preço sorteado em 5 e 15 min. Extremos de sessão são piores que o sorteio. |
| **Quando** | **Regime** (tipo de dia pela 1ª hora) | Dia de rotação ou "abriu fora e voltou": bordas valem. Dia de tendência: só a favor. Evento (±30 min) e fim de semana: sem aviso. | Filtro de Kaufman do robô antigo: não salvou nada. |
| **Se segura / quem está preso** | **Footprint** (presos) e **nuvens** (livro agregado) | Preso = agressor que entrou num nível e viu a vela fechar do outro lado. Entra-se **no reteste** contra ele. Nuvem compradora persistente sob o suporte = calço. | Proporção long/short como "presos": é outra coisa e já foi medida sem resultado. |
| **Lado, stop e teto do alvo** | **Elliott** (método deles) | Grau maior veta o lado. Onda 2 em camadas 0,382/0,5/0,618/0,786 com stop por camada. Alvo 1 = topo da onda 1. Duas contagens vivas; operar o trecho comum. | Contagem como gatilho. A calibração já mostrou odds justas. Em 1 e 5 min é ruído. |
| **Saída** | **Fibonacci** | Em 1R tira o risco (realiza 25–50%, stop no médio). Parciais em 0,5/0,618. Alvo final ≥ 2R, senão não avisa. | Alvo no Fibonacci mais perto: infla o acerto e mata o R:R. |
| **Tamanho** | **Derivativos** (funding, OI) | Funding no percentil 90 + OI subindo = "esticado": stop e alvo 1,5× maiores. Capitulação veta venda. | Vender porque o funding está alto. Medido: não inverte o preço. |
| **Preço justo** | **VWAP ancorada** no pivô do movimento | Como alvo da volta depois de esticar. | VWAP de sessão como gatilho de scalp: medido, sem vantagem. |
| **Zonas de volume** | **Volume Profile** | HVN = onde o preço para, LVN = onde corre. Delta por nível = presos no composto. | Linha do POC como entrada. |
| **Varredura** | **Order Block** qualificado | Só com deslocamento + quebra de estrutura + FVG, de preferência depois de varrer liquidez. | Qualquer candle contrário antes de um impulso: 900 trades, zero. |

## As nuvens (TRDR)

O que você vê no TRDR é o **Order Book Depth Overlay**: o livro de várias corretoras somado em faixas de distância
(0–1%, 1–2,5%, 2,5–5%, 5–10%, 10–25%), verde embaixo para compras e vermelho em cima para vendas. As linhas
horizontais são os 10 maiores níveis do livro.

- **Recriado no projeto:** o coletor grava Coinbase, Binance e Bybit a cada 30 s com essas categorias e o top 10. A
  tela `/nuvens` desenha as bandas sobre o gráfico de 5 min.
- **Limite honesto:** a Coinbase entrega o livro inteiro; a Binance chega a cerca de 1% e a Bybit a cerca de 0,1%. As
  faixas largas vêm quase só da Coinbase.
- **Como usar, segundo o especialista de fluxo:** "esticado contra nuvem" é a sua ideia. Preço com a VWAP a 2 desvios,
  OI subindo, funding caro e varejo comprado, encostando numa nuvem vermelha que não some. A venda entra depois de 1 min
  de rejeição, com stop acima da nuvem e alvo na VWAP.
- **O que falta:** histórico. Uma parede só vale se ficar quando o preço chega, e isso só se mede com semanas de
  gravação. Primeira medida genérica em cerca de 45 dias, a versão completa em cerca de 6 meses. Também falta coletar
  as liquidações (Bybit e Binance, grátis), que formam o painel de baixo do TRDR.

## Resultado das duas primeiras medições (20/10/2026, mesmo dia)

Resumos em `data/estudo_tpo_e1_resumo.md` e `data/estudo_presos_footprint_resumo.md`.

- **TPO E1 reprovada nas 4 variantes, já no treino.** Nenhuma ficou 2 erros padrão acima da direção sorteada nem da
  área de valor deslocada. O filtro de largura deixa só 7 a 18 trades por ano, não 1 a 3 por semana. A área deslocada
  perde quase o mesmo: a mecânica sozinha é que perde, a área de ontem não acrescenta nada.
- **Regime F1 (tipo de dia) não separa:** 8 de 8 linhas reprovadas. A regra classifica os dias muito diferente do
  esperado (rotação em 10–17% dos dias, não 45–55%).
- **Fluxo D, presos no footprint, não aprovada e inconclusiva por amostra.** Em 30 dias de negócios, 1.283 nódulos
  viraram só 16 entradas no 5 min. Essas 16 deram −1,13 R por trade, igual ao nível sorteado da mesma barra (−1,15 R).
  O nódulo igual NÃO preso bateu 1R mais vezes (41%) que o preso (25%): o contrário da hipótese. Com stop típico de
  0,24%, o custo come cerca de 0,4 R por trade. Pela regra do plano, os 60–90 dias extras não foram baixados.

Leitura: a regra objetiva que escrevemos para "presos" é rara e não acerta. Isso não prova que a leitura do Shaka não
funcione: o corte de "volume grande" dele é de olho, e ele combina com lugar e estrutura. Prova que esta tradução em
regra não tem vantagem nos dados que existem.

### Segunda rodada (passos 3 a 6, mesmo dia)

Tabela única em `data/estudo_passos_3a6_tabela.md`.

| Estratégia | Resultado |
|---|---|
| TPO E2, cauda no bloco de 30 min na borda | **Inconclusiva, a única com sinal nos 3 períodos** (+0,23 / +0,06 / +0,41 R). Passa os dois controles no treino, mas validação e holdout têm menos de 30 trades. A cauda sem nível dá zero: o que separa é a borda vinda de longe. Fica para reteste pré-registrado. |
| TPO E3, América contra a manhã | Negativa e com amostra pequena. Sai da fila. |
| Fibonacci E1, escada 0,5–0,786 | Reprovada: uma faixa sorteada na mesma perna rende o mesmo. |
| Fibonacci E2, régua de saída | Reprovada: igual a alvo fixo de 2R e a níveis sorteados. |
| OB E2, varredura + volta | Reprovada ou inconclusiva: 18 retestes em 6,7 anos. Varredura sem quebra de estrutura perde nos 3 períodos. |
| Elliott, "passou 0,786 não é onda 2" | Verdade em 73% dos casos, mas a data sorteada dá 70–72%: é geometria, não leitura de onda. |

## O que começar a receber como aviso (plano original, antes das medições acima)

1. **TPO E1, "abriu fora do valor de ontem e voltou".** É a de menor custo enquanto não há medida (1 a 3 por semana,
   stop de 0,5 a 1%, alvo no próprio nível) e a que se mede primeiro, com dado pronto.
2. **Fluxo D, "presos no footprint".** É a única com informação de dentro da vela e a forma real como eles leem presos.
   Dá para medir já com os negócios públicos da Bybit desde 2020.
3. As outras quatro (varredura de liquidez, escada de Fibonacci, cauda no bloco de 30 min, onda 2 em camadas) vêm
   depois, na ordem do plano de gestão.

Todo aviso sai com **"sem % medido"** até a estratégia passar na régua: lucro nos três períodos e 2 erros padrão
acima do controle sorteado. O modelo de mensagem de cada uma está em `plano_gestao.md`, seção 2.

## O que mais faria perder dinheiro

1. Tratar um aviso "sem % medido" como se tivesse %. O custo é o único número certo: dois trades por dia custam cerca
   de 12% da banca por ano se o acerto for o do acaso.
2. Operar a borda em dia de tendência.
3. Stop limitado em vez de a mercado, ou stop apertado em hora de dado macro.
4. Perseguir o preço que saiu sem preencher, ou segurar uma fatia órfã.
5. Alavancar para caber mais fatias numa banca pequena.
