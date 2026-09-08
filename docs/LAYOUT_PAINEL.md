# Layout do painel (especificação para o mockup)

Objetivo: um painel de operação que mostre, para cada robô, **por que** ele está comprado/vendido/parado, com os cenários de Elliott concorrentes, os níveis institucionais e o risco, sem exigir leitura de logs. Estilo: escuro, denso mas legível (referências: Bybit, TradingView, Exocharts). Uma cor de destaque (ciano ou dourado), verde/vermelho só para compra/venda e P&L.

Todos os dados abaixo já existem na API (`/status/...`, `/bot-control/`, `/pontos-institucionais`, `/logs/{id}/grafico-dados`).

## Navegação (barra lateral fixa)

Dashboard · Bots · Mercado (Elliott) · Pontos institucionais · Sentimento · Histórico · Configurações

## 1. Dashboard

- **Faixa superior (KPIs)**: P&L do dia, P&L acumulado, trades hoje, taxa de acerto, drawdown, bots rodando/total, estado da Bybit (público/privado ok), sentimento atual (gauge -1..+1 com a zona: medo extremo / neutro / ganância extrema).
- **Cards por bot** (grade): nome, par, timeframe, estilo (scalp/daytrade/swing), perfil (conservador/turbo), modo (simulador/testnet/real) com cor, status (rodando/parado), posição aberta (direção, entrada, SL, TP, P&L flutuante), última decisão (ação + fase da onda + probabilidade do cenário primário), botões Ativar/Parar/Detalhes.
- **Linha de alertas** recentes (entradas, saídas, erros, bloqueios por sentimento/zona institucional).

## 2. Detalhe do bot (tela principal de operação)

Layout em três colunas:

- **Coluna esquerda (gráfico, 60% da largura)**: candles do timeframe operacional com overlays selecionáveis: pivôs do ZigZag e rótulos das ondas do cenário primário (1-2-3-4-5 / A-B-C), linhas de invalidação (vermelho tracejado) e alvos (verde tracejado), TPO/Volume Profile como histograma lateral direito (POC, VAH, VAL), VWAP com bandas ±1σ/±2σ, order blocks como retângulos, pontos institucionais como linhas finas com tooltip (tipo, timeframe, relevância, testado/rompido), marcadores de entrada/saída do bot. Abaixo do gráfico: abas com os três graus (operacional / contexto / macro) para trocar o timeframe exibido.
- **Coluna central (cenários de Elliott, 25%)**: lista dos cenários ordenada por probabilidade. Cada item: barra de probabilidade, viés (seta ↑/↓ colorida), nome (ex.: "Impulso de alta: onda 3 em andamento (1,2x onda 1)"), fase, invalidação, alvos, indicador de completo/em andamento. No topo, um resumo: "Bull 62% · Bear 28% · Indefinido 10%" e o consenso. Um bloco "Alinhamento multi-grau" mostrando operacional / contexto / macro com fase e viés de cada um, e o motivo do bloqueio quando houver.
- **Coluna direita (decisão e risco, 15%)**: última decisão (ação, motivo em texto), votos dos validadores (chips: VWAP ✓, TPO ✗, Order Flow –), TP/SL escolhidos com fonte (Elliott / Fibonacci / TPO / VWAP / OB) e R:R, sentimento (score e componentes), zonas institucionais próximas, tamanho calculado (risco em USDT e quantidade), limites do dia (trades usados, perda máxima). Botões: fechar posição, ativar trailing, pausar.

Rodapé: tabela de decisões (hora, ação, fase, cenário, probabilidade, motivo) com filtro por ação.

## 3. Mercado (Elliott sem bot)

Mesma composição da tela de detalhe, mas para qualquer par/timeframe/estilo escolhido nos seletores, para estudar o mercado. Inclui o painel de níveis (`/status/mercado/niveis`) e a origem dos dados compostos (quais exchanges responderam).

## 4. Pontos institucionais

Tabela e gráfico de "escada de preços": cada ponto como linha horizontal na faixa de ±5% do preço, cor por tipo (TPO, VP, VWAP, OB, Order Flow), opacidade pela relevância, ícone de testado/rompido, filtro por timeframe/tipo/status. Ações: marcar testado/rompido manualmente, rodar o detector.

## 5. Sentimento

Gauge principal, série histórica do score, cards por componente (Fear & Greed, funding, long/short, open interest, X/Twitter se configurado) e a regra em vigor ("ganância extrema: novas compras bloqueadas no perfil conservador").

## 6. Histórico e backtest

Lista de posições fechadas com P&L, R, motivo de saída, fase e cenário; curva de capital; resumo por fase/direção/motivo. Botão para disparar backtest (fonte, timeframe, estilo, perfil) e comparar resultados.

## 7. Formulário do bot

Campos agrupados: Identificação (nome, par, timeframe, estilo, perfil) · Execução (modo, alavancagem, modo de posição, margem, subconta) · Risco (banca, risco %, alocação máxima, quantidade mín/máx, trades/dia, perda/dia) · Indicadores (Elliott sempre ligado; toggles para Fibonacci, TPO, VWAP, Order Flow, Volume Profile, Order Block) · Filtros (sentimento, tendência macro, calendário macro) · Trailing (ativador, distância, manual).
