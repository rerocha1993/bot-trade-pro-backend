# Briefing para o Claude Design: painel do Bot Trade Pro

Cole este texto inteiro como pedido no Claude Design. Ele descreve o produto, o estilo, as sete telas, os componentes e os dados que cada bloco mostra. Todos os dados citados já existem na API do backend; os nomes dos endpoints estão no fim.

---

## 1. O que é o produto

Bot Trade Pro é um painel web de operação de robôs de trading de Bitcoin em contratos perpétuos na Bybit. A decisão dos robôs é baseada em Ondas de Elliott com vários cenários concorrentes (cada cenário com probabilidade, fase da onda, preço de invalidação e alvos), validada por indicadores institucionais (TPO, Volume Profile, VWAP, Order Flow, Order Blocks) e filtrada por um score de sentimento de mercado. O usuário é um trader experiente que quer ver, em segundos, **por que** cada robô está comprado, vendido ou parado, e acompanhar risco e resultado.

Cada robô tem um estilo (scalping, daytrade ou swing), que define o "grau" de Elliott que ele opera (timeframe operacional, de contexto e macro), um perfil de confluência (conservador ou turbo) e um modo de execução (simulador, testnet ou real).

## 2. Estilo visual

- Tema escuro, denso mas legível, estilo terminal profissional (referências: Bybit, TradingView, Exocharts). Sem gradientes chamativos, sem emojis, sem cantos muito arredondados.
- Fundo quase preto levemente frio (ex.: #0b0f14), painéis um tom acima (#111820), bordas sutis (#233040), texto claro (#e6edf3), texto secundário cinza-azulado (#8a98a8).
- Um único destaque: ciano (#22d3ee) para seleção, ações primárias e o robô/cenário em foco.
- Verde (#34d399) somente para compra e lucro; vermelho (#f87171) somente para venda e prejuízo; âmbar (#fbbf24) para avisos (testnet, chave expirada, sentimento em zona de atenção).
- Tipografia: uma sans neutra para interface (IBM Plex Sans ou similar) e uma monoespaçada para todos os números, preços e horários (IBM Plex Mono ou similar). Corpo em 12 a 13 px, títulos de tela em 20 px.
- Ícones em linha, traço fino, sem preenchimento.
- Desktop primeiro (1440 px). Não precisa de versão mobile agora.

## 3. Estrutura comum

Barra lateral fixa à esquerda (220 px) com logotipo, os sete itens de navegação (Dashboard, Bots, Mercado, Pontos institucionais, Sentimento, Histórico, Configurações) e, no rodapé, três indicadores de saúde: Bybit dados públicos (ok), Bybit conta (ok ou "chave expirada"), cesta de exchanges (quantas responderam, ex.: 5/5).

Cabeçalho de cada tela: título à esquerda; à direita o par e o relógio, e nas telas de robô os botões de ação.

## 4. Telas

### 4.1 Dashboard

1. Linha de seis indicadores (cartões pequenos, número grande em monoespaçada, legenda abaixo): P&L do dia, P&L acumulado, trades hoje (com o limite diário), taxa de acerto, drawdown máximo, robôs rodando/total.
2. Um medidor de sentimento em meia-lua no canto direito do cabeçalho, escala de -1 (medo extremo) a +1 (ganância extrema), com o valor e a zona ("neutro", "ganância").
3. Grade de cartões, um por robô (quatro robôs de exemplo: "Scalp Fluxo" scalping 1m turbo, "Day TPO" daytrade 15m conservador, "Swing Estrutura" swing 4h conservador, "Elliott Puro" daytrade 30m turbo). Cada cartão: nome, estilo e timeframe, etiquetas de perfil e modo (modo com cor: simulador cinza, testnet âmbar, real vermelho), ponto de status (rodando/parado), posição aberta (direção, preço de entrada, SL, TP) ou "sem posição", P&L flutuante, última decisão (ação, fase da onda, probabilidade do cenário primário), botões Detalhes e Parar/Ativar.
4. Lista de alertas recentes: hora, robô, texto (entrada, saída com P&L, bloqueio por sentimento ou zona institucional, erro), com cor por tipo.

### 4.2 Detalhe do robô (tela principal, a mais importante)

Cabeçalho: nome do robô, etiquetas (estilo e timeframe, perfil, modo), status "rodando · ciclo há 4 s", botões Ativar trailing, Fechar posição (vermelho), Parar.

Corpo em três colunas:

**Coluna 1, gráfico (cerca de 60% da largura).** Abas para os três graus (ex.: "15m operacional", "4h contexto", "1d macro"). Gráfico de candles com overlays ligáveis por etiquetas abaixo: pivôs do ZigZag ligados por linha tracejada ciano com os rótulos das ondas do cenário primário (1, 2, 3, 4, 5 ou A, B, C); linha tracejada vermelha de invalidação com o preço; linhas tracejadas verdes dos alvos (ex.: "alvo 1,0x 80 623"); histograma de TPO deitado na borda direita do gráfico com o POC em ciano e a value area destacada; retângulos translúcidos dos order blocks (verde demanda, vermelho oferta); VWAP com bandas; linhas finas dos pontos institucionais com tooltip (tipo, timeframe, relevância, testado ou rompido); triângulos marcando entradas e saídas do robô. Preço atual grande no canto superior direito do gráfico com variação percentual.

**Coluna 2, cenários de Elliott (cerca de 25%).** Título "Cenários de Elliott" com subtítulo "grau operacional · 15m · 4 cenários ativos". Barra empilhada de probabilidade: verde (bull), vermelho (bear), cinza (indefinido), com os três percentuais abaixo (ex.: Bull 62% · Bear 26% · Indefinido 12%). Lista de cenários ordenada por probabilidade; cada item é um cartão com: seta para cima ou para baixo colorida, nome (ex.: "Impulso de alta: onda 3 em andamento (1,2x onda 1)"), percentual à direita, barra fina de probabilidade, etiquetas com a fase (meio_onda_3) e o estado (primário / em andamento / completo), e uma linha monoespaçada "inval. 79 483 · alvos 80 623 · 81 320". O cenário primário tem borda ciano. Abaixo, bloco "Alinhamento multi-grau": três linhas (Operacional 15m, Contexto 4h, Macro 1d) com fase e viés de cada grau, e uma frase de conclusão ("Alinhado: os três graus apontam para alta" ou "Bloqueado: contexto contrário").

**Coluna 3, decisão e risco (cerca de 15%), empilhada em cartões pequenos.**
- Decisão: a ação em destaque (COMPRA em verde, VENDA em vermelho, AGUARDAR em cinza), a fase, e o motivo em texto curto. Abaixo, os validadores como etiquetas com resultado: "VWAP ✓" verde, "TPO ✓" verde, "Order Flow ✗" vermelho, "Volume Profile –" cinza.
- Alvo e proteção: TP (verde) e SL (vermelho) com a fonte de cada um (elliott, fibonacci, tpo, vwap, orderblock, atr) e o risco:retorno com o mínimo exigido.
- Tamanho e limites: risco em USDT e percentual, quantidade em BTC, trades do dia sobre o limite, perda máxima do dia.
- Filtros: sentimento (score e zona), zona institucional próxima (ou "nenhuma"), evento macro.

Rodapé: tabela "Decisões recentes" com colunas Hora, Ação (colorida), Fase, Cenário primário, Probabilidade, Motivo. Inclui decisões de aguardar, porque o usuário quer ver o motivo de não entrar.

### 4.3 Mercado

Mesma composição do detalhe, sem robô: seletores no topo (par, timeframe, estilo, perfil, cesta de exchanges) e botão Analisar; gráfico com overlays; coluna de cenários compacta; e um cartão "Níveis agora" em tabela (POC, VAH, VAL do TPO composto, VWAP e bandas, order blocks do gráfico), cada um com preço e fonte. Serve para estudar o mercado antes de criar um robô.

### 4.4 Pontos institucionais

Filtros em etiquetas (ativos, testados, rompidos; timeframes 30m, 4h, 1d, 1w; tipos TPO, VP, VWAP, OB, Order Flow). À esquerda, uma "escada de preços": faixa vertical de ±2% ao redor do preço atual, o preço atual como linha branca, e cada ponto como linha horizontal colorida por tipo (OB de demanda verde, OB de oferta vermelho, TPO âmbar, VWAP ciano), opacidade proporcional à relevância, tracejada quando testado, com rótulo do tipo e do timeframe. À direita, tabela dos pontos na faixa: tipo, preço, relevância, status (ativo verde, testado âmbar, rompido vermelho), data de identificação. Botões: Rodar detector, Marcar rompido.

### 4.5 Sentimento

À esquerda, medidor grande em meia-lua com o score (ex.: +0,20) e a zona, e o texto da regra em vigor ("acima de +0,60 as novas compras ficam bloqueadas no perfil conservador; abaixo de -0,60, as vendas"). À direita, quatro cartões, um por componente, cada um com valor bruto, legenda, contribuição normalizada (de -1 a +1, colorida) e o peso: Fear & Greed (peso 40%), funding rate (25%), razão long/short (20%), open interest 24h contra variação de preço (15%). Um quinto cartão "X/Twitter" aparece esmaecido como "não configurado". Abaixo, gráfico de linha do score nos últimos 30 dias com as duas linhas tracejadas de zona extrema.

### 4.6 Histórico

Linha de indicadores (trades, acerto, fator de lucro, R médio, drawdown máximo, resultado em USDT). Gráfico de curva de capital. Tabela de posições fechadas: abertura, robô, direção, entrada, saída, P&L, R, fase da onda, motivo da saída (SL, TP, saída estrutural com a frase). Botões: Rodar backtest (abre um pequeno formulário: fonte, timeframe, estilo, perfil) e Exportar CSV.

### 4.7 Formulário do robô (criar e editar)

Cartões em duas colunas:
- Identificação: nome, par, timeframe, estilo (scalping, daytrade, swing), perfil (conservador, turbo).
- Execução: modo (simulador, testnet, real), alavancagem, modo de posição (one-way, hedged), margem (cross, isolated), subconta.
- Risco: banca em USDT, risco por trade em %, alocação máxima em %, quantidade mínima e máxima, trades por dia, perda máxima por dia em %.
- Indicadores e filtros, como interruptores: Elliott (sempre ligado, desabilitado), Fibonacci, TPO, Volume Profile, VWAP, Order Flow, Order Block, filtro de sentimento, alinhamento com tendência macro, calendário macro.
- Trailing stop: ativa após (%), distância (%), interruptor de trailing automático.
Botões no cabeçalho: Cancelar e Salvar robô (primário).

## 5. Componentes reutilizáveis

Cartão de indicador (número grande), etiqueta/chip (perfil, modo, fase, status), cartão de robô, cartão de cenário com barra de probabilidade, barra empilhada bull/bear/indefinido, medidor em meia-lua, tabela densa com cabeçalho cinza e linhas separadas por borda fina, botões (primário ciano, secundário com borda, perigo em vermelho), interruptor, campo de formulário com rótulo pequeno acima, gráfico de candles com painel de histograma lateral.

## 6. Estados a prever

Robô parado (cartão esmaecido), sem posição, chave da Bybit expirada (aviso âmbar na barra lateral e no cabeçalho do robô em modo testnet/real), exchange da cesta fora do ar (contador 4/5 em âmbar), decisão bloqueada (ação AGUARDAR com o motivo do bloqueio em âmbar), erro no ciclo (linha de alerta vermelha).

## 7. Dados de exemplo

Use BTCUSDT por volta de 79 900. Exemplos coerentes com o backend: cenário primário "Impulso de alta: onda 3 em andamento (1,2x onda 1)" com 44%, invalidação 79 483, alvos 80 623 e 81 320; alternativas "Zigzag de baixa concluído: retomada de alta" 18%, "Diagonal final de alta: reversão esperada" 15%, "Onda 1 de baixa concluída: onda 2 em andamento" 11%; TPO com POC 79 707, VAH 80 031, VAL 79 477; sentimento +0,20 neutro (Fear & Greed 73, funding 0,003%, long/short 54,5%).

## 8. De onde vem cada dado (endpoints do backend)

- Estado dos robôs, posição, última decisão: `GET /status/`, `GET /status/bots/{id}`
- Decisões e posições: `GET /status/bots/{id}/decisoes`, `GET /status/bots/{id}/posicoes`
- Cenários multi-grau: `GET /status/elliott?par=&timeframe=&estilo=&perfil=`
- Níveis para o gráfico: `GET /status/mercado/niveis`, candles: `GET /status/mercado/candles`
- Sentimento: `GET /status/sentimento`
- Pontos institucionais: `GET /pontos-institucionais?par=&status=&preco_atual=&faixa_pct=`
- Order blocks: `GET /orderblocks/`
- Controle: `POST /bot-control/{id}/ativar`, `POST /bot-control/{id}/desativar`, `POST /bots/`, `PUT /bots/{id}`
- Diagnóstico da Bybit: `GET /status/bybit?modo=`
