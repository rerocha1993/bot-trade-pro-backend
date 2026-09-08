# Graph Report - .  (2026-09-07)

## Corpus Check
- Large corpus: 187 files · ~508.808 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 1646 nodes · 3695 edges · 78 communities detected
- Extraction: 82% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 642 edges (avg confidence: 0.58)
- Token cost: 2.170.784 tokens de subagente (12 agentes de extracao semantica; entrada+saida combinadas, medido pelo orquestrador). A extracao AST de 150 arquivos de codigo foi deterministica e nao custou tokens.
- Edge kinds: calls: 611 · contains: 493 · method: 478 · uses: 434 · references: 298 · imports_from: 275 · imports: 203 · describes: 179 · depends_on: 175 · conceptually_related_to: 165 · implements: 156 · rationale_for: 156 · semantically_similar_to: 38 · inherits: 21 · shares_data_with: 9 · cites: 4

## God Nodes (most connected - your core abstractions)
1. `BybitConnector` - 67 edges
2. `BotExecutor` - 60 edges
3. `StrategyEngine` - 58 edges
4. `ScenarioEngine` - 46 edges
5. `ElliottService` - 43 edges
6. `FibonacciElliott` - 42 edges
7. `Elliott Wave` - 39 edges
8. `TPOProfile` - 38 edges
9. `Bot Trade Pro README` - 38 edges
10. `VWAPCalculator` - 33 edges

## Surprising Connections (you probably didn't know these)
- `run_all_bots.py (Executor Multiprocess)` --semantically_similar_to--> `BotExecutor`  [INFERRED] [semantically similar]
  doc explicacao/chat 1.txt → core/bot_executor.py
- `Proposed PosicaoAtivaBot Table` --semantically_similar_to--> `PosicaoBot`  [INFERRED] [semantically similar]
  doc explicacao/chat 1 - flutter.txt → models/posicao_bot.py
- `Institutional-Zone Trade Block Logic` --semantically_similar_to--> `StrategyEngine`  [INFERRED] [semantically similar]
  doc explicacao/chat 2 - flutter.txt → core/strategy_engine.py
- `Detector Integration Plan (TPO/VWAP/OrderFlow/VolumeProfile/OrderBlock)` --semantically_similar_to--> `DetectorPontoInstitucionalService`  [INFERRED] [semantically similar]
  doc explicacao/chat 2 - flutter.txt → services/detector_ponto_institucional_service.py
- `Botão 'Insights' do Robô` --semantically_similar_to--> `HipoteseViva`  [INFERRED] [semantically similar]
  doc explicacao/chat 6.txt → frontend/src/api/types.ts

## Hyperedges (group relationships)
- **Fluxo Detector -> Registro -> Bloqueio de Trade** — tpo, chat8_registro_ponto_service, chat8_strategy_engine_bloqueio [INFERRED 0.80]
- **Arquitetura Multi-Exchange Parametrizavel** — chat8_pairs_exchanges_dinamico, core_exchange_factory, core_detector_institucional [INFERRED 0.85]
- **Ciclo de Vida do Ponto: Teste, Rompimento e Log** — chat8_atualizacao_status_service, chat8_log_institucional, models_ponto_institucional_log [EXTRACTED 0.90]
- **Fluxo de Decisão Elliott-Pro-Master** — fase_onda, confluencia, tp_sl_conservador [INFERRED 0.75]
- **Validação Multi-Padrão via Fibonacci Elliott** — fibonacci, score_confianca [INFERRED 0.80]
- **Lacuna de Bootstrap Institucional Multi-Timeframe** — bootstrap_institucional, multi_timeframe_hierarquico, elliottcompletopart2_big_range [INFERRED 0.70]
- **Elliott-led Decision, Confluence, Fibonacci Risk Pipeline** — elliott_e_lei, confluencia_indicadores [INFERRED 0.85]
- **Flutter Web Chart Rendering Stack** — chat1flutter_chartviewwidget, chat1flutter_tradingview_chart_html, postmessage_bridge [INFERRED 0.80]
- **Institutional Points Detection Pipeline** — chat2flutter_detector_integration_plan, chat2flutter_pontoinstitucional_model_plan, chat2flutter_bloqueio_institucional [INFERRED 0.80]
- **Multi-Degree Alignment by Trading Style** — scalp, daytrade, swing [INFERRED 0.75]
- **Ambiguidade Onda 3 vs Onda B** — onda_3, onda_b, chat6_cenario_intersecao [INFERRED 0.75]
- **Requisito Visual de TPO (POC/VAH/VAL)** — tpo, poc, chat7_elliott_tpo_visual_requisito [INFERRED 0.80]
- **Validação institucional de ordem (SL/TP coerentes)** — ajustes_validar_operacao, stop_loss, take_profit [INFERRED 0.80]
- **Pilares da arquitetura avançada (perfis, zonas de memória, ML)** — chat4_perfis_operacionais, chat4_zonas_memoria_liquidez, chat4_ml_trader_inteligente_plano [INFERRED 0.80]
- **Indicadores implicados no bug de pontos fantasma** — tpo, vwap, volume_profile [INFERRED 0.75]
- **Elliott como Núcleo Obrigatório da Estratégia** — elliott_wave, strategy_engine, requisito_original [INFERRED 0.85]
- **CRUD Completo como Pilar do Sistema Profissional** — crud_completo, chat2_bot_service_crud, chat2_indicador_disponivel_gap [INFERRED 0.80]
- **Feature de Sensibilidade a Eventos Macroeconômicos** — macro_event_checker, chat2_etapa13_macro_scraping, chat2_etapa13b_macro_api [INFERRED 0.85]
- **Cascata de falha no detector institucional (TypeError -> rollback -> pair expirado)** — erro_tpo_column_length_typeerror, erro_pendingrollback_cascata, erro_rundetector_pair_expired [INFERRED 0.85]
- **Pipeline backend de pontos institucionais (modelo + API + confluencia)** — novidade_modelo_dados_ponto, novidade_endpoints_rest, novidade_orquestracao_strategyengine_confluencia [INFERRED 0.80]
- **Bugs de metodos ausentes na camada API/service de bots** — erro_botexecutor_executar_ausente, erro_botservice_get_all_bots_ausente, erro_bot_as_dict_ausente [INFERRED 0.85]
- **Fluxo de Decisão a Cada Candle Fechado** — elliott_wave, fase_onda, validadores_indicadores, sentimento_contrario, ponto_institucional [INFERRED 0.85]
- **Camada do Trader Governando Alinhamento e Hedge** — superciclo, subordinacao_graus, hedge_dial, mesa_do_trader [INFERRED 0.85]
- **Arquitetura de Três Camadas do Orquestrador** — indicadores_independentes, plano_mercado, bots_orquestrados [EXTRACTED 0.95]
- **Análise multi-grau no detalhe do robô** — grafico_candles, cenarios_concorrentes, alinhamento_multi_grau [INFERRED 0.80]
- **Composição da visão geral do dashboard** — inspiracaopainel_kpicards, inspiracaopainel_botcards, inspiracaopainel_alertasrecentes [INFERRED 0.80]
- **Composição da tela de sentimento** — medidor_sentimento, inspiracaopainel_sentcomponentes, inspiracaopainel_scorehistorico [INFERRED 0.85]

## Communities

### Community 0 - "Leituras Independentes de Indicadores"
Cohesion: 0.05
Nodes (36): Fix: filtro de ATH/ATL do range analisado, Bug: VWAPCalculator sem obter_vwap_atual, Fix: VWAP/bandas limitadas ao range do OHLCV, Order Flow Pro Roadmap (footprint/absorption/traps), VWAP Multi-Anchor with Deviation Bands, _lado(), Leitura, leitura_elliott() (+28 more)

### Community 1 - "Fibonacci e Ondas de Elliott"
Cohesion: 0.07
Nodes (48): Correção ABC, Fibonacci Target, Bootstrap/Varredura Institucional Inicial, Cenário de Elliott (concorrente), Pergunta: Bots Comerciais de Elliott Existem?, Decisão em zona de interseção de cenários, Q&A: Elliott + Fibonacci sem ML, Validação de contagens enviadas por imagem (+40 more)

### Community 2 - "Executor de Bot e Posições"
Cohesion: 0.07
Nodes (25): Bug: Repeated BUY Orders (One-way Position Bug), Proposed Trade Cooldown Mechanism, Proposed PosicaoAtivaBot Table, Depuração de Erros Telegram (URL malformada, 401/404), Configuração de Alerta Telegram via .env, Incidente: assistente perdeu o contexto da conversa, Reafirmação: sistema deve ser profissional, sem mock, Decisão: criar telegram_alert_service.py profissional (+17 more)

### Community 3 - "Dados de Mercado Multi-Exchange"
Cohesion: 0.05
Nodes (28): _base_do_par(), BitfinexPublico, MarketDataAggregator, Cliente público multi-exchange com cache curto e tolerância a falhas por exchang, OHLCV de cada exchange da cesta (as que falharem são omitidas e registradas em `, Vela composta por timestamp: OHLC = média simples entre exchanges (como o índice, Une os livros das exchanges (preços em USD/USDT tratados como equivalentes)., Preço médio (último negócio) entre as exchanges da cesta, como o índice da Tradi (+20 more)

### Community 4 - "Motor de Decisão (Strategy Engine)"
Cohesion: 0.06
Nodes (31): Arquitetura do Orquestrador, Blindagem ATH/ATL de Período, Bots Orquestrados, Confluência de Indicadores (filtro duplo), Multi-Indicator Confluence Voting, bloquear_zona_institucional(), direcao_permitida(), get_regras_fase_onda() (+23 more)

### Community 5 - "Grade Inversa e Dial de Hedge"
Cohesion: 0.07
Nodes (15): BacktestGrade, barreiras(), EstadoHedge, exaustao(), HedgeDial, elliott: {'fase', 'vies', 'prob_bull', 'prob_bear', 'alvos', 'invalidacao', 'cic, niveis: [{'preco', 'fonte', 'peso'}] de todas as fontes (elliott, tpo, instituci, Combina sinais de topo em 0..1:
         fear_greed (0..100)     >= 60 começa a (+7 more)

### Community 6 - "Telas e Componentes do Painel"
Cohesion: 0.07
Nodes (35): erroTexto(), useBacktestsBot(), useControleBot(), useMultigrau(), useNiveis(), usePontos(), useSentimento(), Header() (+27 more)

### Community 7 - "Hooks e Tipos do Painel"
Cohesion: 0.07
Nodes (38): useCandles(), useDecisoes(), useDial(), useHistorico(), useMestre(), usePosicoes(), useStatusBot(), useTrader() (+30 more)

### Community 8 - "Backtest de Validação (gate)"
Cohesion: 0.07
Nodes (18): BacktestEngine, bot_padrao(), fetch_ohlcv(tf, n) que só enxerga candles FECHADOS até ts_limite (sem look-ahead, BacktestBot, Resultado de um backtest de validação. Um bot só pode ser ativado com um backtes, ativar_bot(), Ativa o bot. Em testnet/real exige backtest aprovado nos últimos 30 dias (POST /, BacktestService (+10 more)

### Community 9 - "Serviço de Pontos Institucionais"
Cohesion: 0.08
Nodes (23): Institutional-Zone Trade Block Logic, 7-Phase Institutional Points Implementation Plan, Detector Integration Plan (TPO/VWAP/OrderFlow/VolumeProfile/OrderBlock), PontoInstitucional ORM Model & Endpoints (planned), PontoInstitucionalLog Audit Table (planned), Relevance Decay on Retest, HVN (High Volume Node), LVN (Low Volume Node) (+15 more)

### Community 10 - "Dashboard e Formatação"
Cohesion: 0.11
Nodes (24): useBacktests(), useBots(), useDetalhes(), useFechadas(), useLogs(), Posicao, StatusBot, KPI() (+16 more)

### Community 11 - "Estratégias de Fibonacci e Risco"
Cohesion: 0.10
Nodes (11): Decision: Split Fibonacci into Wave-Specific Strategy Methods, Gerenciamento por Banca e % por Operação, Fibonacci, Compatível com o uso antigo `Fibonacci(high, low)`:         direcao='up'   -> sw, _rotulo(), FibonacciStrategies, buy  -> swing de alta: do fundo até o topo posterior (ou o topo mais recente)., Garante coerência direcional com o preço atual:         buy  -> sl < preco < tp (+3 more)

### Community 12 - "CRUD de Bots (API)"
Cohesion: 0.10
Nodes (21): Tabela HistoricoIndicadores (base p/ ML), Bug: BotService sem metodo get_all_bots, IndicadorLoader, Devolve lista de (nome_canonico, parametros) dos indicadores cadastrados para o, AttributeError: Bot sem metodo as_dict, AttributeError: BotExecutor sem metodo executar, AttributeError: BotService sem get_all_bots, Formulário — Indicadores e Filtros (Switches) (+13 more)

### Community 13 - "Memória de Contagens e Superciclo"
Cohesion: 0.12
Nodes (17): chave_hipotese(), _data(), evoluir(), evoluir_hierarquico(), MemoriaContagens, MemoriaHierarquica, Maturidade com a lógica de Elliott: uma hipótese de CONTINUAÇÃO (onda 3/5 em and, Reproduz a memória ao longo de uma série (semanal para ciclo, diária para primár (+9 more)

### Community 14 - "Sentimento e Derivativos"
Cohesion: 0.10
Nodes (12): DadosDerivativos, Liquidações agregadas 24h e razão long/short global (Coinglass API v4, plano gra, Opcional: proporção de tweets recentes com palavras de euforia vs medo. Exige X_, connector: BybitConnector (qualquer modo) para funding/ratio/OI. Se None, cria u, Variação do OI nas últimas 24h (histórico 1h) e variação de preço no mesmo perío, SentimentoMercado, Fear & Greed Index, Funding Rate (+4 more)

### Community 15 - "Persistência de Contagens Elliott"
Cohesion: 0.13
Nodes (15): Base, Contagem Validada, ElliottAnalyzer, ElliottDetector, Wrapper de compatibilidade: aceita lista de preços OU candles., Varredura histórica: percorre os pivôs em janelas deslizantes, guarda os padrões, ElliottContagemCandidata, ElliottContagemValidada (+7 more)

### Community 16 - "Range Inverso Escalonado"
Cohesion: 0.08
Nodes (11): BacktestInverse, alocacao_escada(), decidir_alocacao(), posicao_no_range(), PosicaoInversa, propor_range(), RangeConfig, Proposta automática a partir dos pivôs do grau primário no diário (últimos H e L (+3 more)

### Community 17 - "Arquitetura dos Indicadores"
Cohesion: 0.16
Nodes (28): Bug: pontos institucionais acima do preço nunca negociado, Fix: TPO com range/timeframe customizável, OrderBlock, Fase 4 – Núcleo de Inteligência (Indicadores), Discussão sobre Machine Learning Avançado, BOT TRADE PRO - Arquitetura Estratégica Avançada, Prioridade de dados reais da Coinbase para decisão do bot, Decisão de mercado via confluência Elliott+indicadores (+20 more)

### Community 18 - "Conector Bybit (ordens)"
Cohesion: 0.10
Nodes (10): Id nativo da Bybit (ex.: BTCUSDT)., Baixa candles em blocos de 1000 até `until_ms` (ou agora)., Últimos negócios públicos, no formato usado pelo OrderFlowAnalyzerPro., Retorna a posição aberta (ou None). Só faz sentido para linear., Ajusta alavancagem, modo de margem (cross/isolated) e modo de posição (one-way/h, Envia ordem para a Bybit com SL/TP anexados à posição (um único request)., Altera SL/TP da posição aberta (endpoint /v5/position/trading-stop)., Fecha a posição aberta a mercado (reduceOnly). (+2 more)

### Community 19 - "Trader, Contagem Mestre e Trava"
Cohesion: 0.14
Nodes (12): Pontos institucionais CONTRA a direção, dentro do raio da fase (só se houver ses, Usa a última análise multi-grau para dizer se a posição deve ser encerrada por e, Leitura do TraderService (superciclo + contagens maduras). Só ao vivo: em backte, Bot, Configuração de um robô.
 
     modo_execucao : 'simulador' (paper trading, sem, Backtest da grade inversa (sem stop) em BTC, no histórico 4h da Bitstamp., Leitura do dial de hedge agora: barreira (confluência acima), suporte, exaustão, TPO, Volume Profile, VWAP e order blocks calculados agora (para desenhar no gráf (+4 more)

### Community 20 - "Documentação do Projeto"
Cohesion: 0.11
Nodes (21): Calendário Macro, Calibração Histórica de Elliott, Tipo de Confluência, Contagem Mestre (desde 2011), Derivativos de Mercado, Entrada por Ordem Limitada, Estilo de Trade, Grade Inversa (+13 more)

### Community 21 - "Layout e Cliente da API"
Cohesion: 0.12
Nodes (18): api, ApiError, call(), Params, url(), Decisão: TradingView Lightweight Charts, DiagBybit, NAV (+10 more)

### Community 22 - "Fontes de Dados e WebSocket"
Cohesion: 0.10
Nodes (5): DataSource, DataSourceWebsocket, symbol: símbolo da moeda, ex: btcusdt (sempre minúsculo)
         url: endpoint, Espera até o cache de trades atingir tamanho mínimo (ou timeout)., WebSocket + In-Memory Cache Data Pattern

### Community 23 - "Gráfico de Preço e Overlays"
Cohesion: 0.14
Nodes (17): Candle, NiveisResp, PontoInstitucional, ChartLabel, ChartLevel, ChartMarker, ChartPath, ChartProfile (+9 more)

### Community 24 - "Elliott Institucional (plano)"
Cohesion: 0.19
Nodes (14): Concurrent Scenarios (Multi-Hypothesis), consultar_estruturas_atuais() Method, get_ondas_validadas() Method (Gap Fix), Plano Definitivo Elliott Institucional, promover_e_validar() Method, revisar_rollback() Method, Elliott Institucional Vision, Top-Down Timeframe Flow (+6 more)

### Community 25 - "Pivôs e Pernas do ZigZag"
Cohesion: 0.11
Nodes (16): Elliott Pro: motor de ondas com múltiplos cenários e múltiplos graus.      pivot, ajustar_todos(), Leg, legs_de_pivots(), None se alguma obrigatória falhou; senão 0.55 + 0.45 * (diretrizes ok ponderadas, a está além de b na direção `up`?, Diagonal contrátil (cunha). 'leading' inicia impulsos/zigzags (onda 1/A); 'endin, Detecta flat regular, expandido ou running (B retrai ≥ 90% de A). (+8 more)

### Community 26 - "Perfil TPO e Value Area"
Cohesion: 0.20
Nodes (9): TPO Pro Roadmap (profile shapes, HVN/LVN, single prints), Volume Profile Pro Roadmap (HVN/LVN, adjustable histograms), Requisito: Elliott (consolidada+futura) e TPO com dados reais, Sinal padronizado (buy/sell/hold) + contexto:             preço acima da VAH  ->, TPOProfile, Point of Control (POC), Single Print (TPO), Value Area High (VAH) (+1 more)

### Community 27 - "Testes de Indicadores"
Cohesion: 0.12
Nodes (5): Erro de import relativo core/services, Configuração launch.json como módulo, Absolute Import / PYTHONPATH Fix for core package, tamanho_b / tamanho_a com proteção de divisão por zero., razao()

### Community 28 - "Multi-Grau e Calibração"
Cohesion: 0.16
Nodes (13): Alinhamento Multi-Grau, Calibrador, Aplica o modelo treinado: P(alvo antes da invalidação) para um cenário., analisar_serie(), AnaliseMultiGrau, calibrador_padrao(), normalizar_perfil(), fetch_ohlcv(timeframe, limite) -> candles. Pode ser o conector Bybit, o agregado (+5 more)

### Community 29 - "Utilitários de Indicadores"
Cohesion: 0.13
Nodes (15): arredondar_para_step(), atr(), normalizar_timeframe(), pct_dist(), precos_tipicos(), Arredonda `valor` para múltiplo de `step` (precisão da exchange)., Distância percentual absoluta entre a e b relativa a b., Remove o último candle se ele ainda não fechou (timestamp + duração > agora). (+7 more)

### Community 30 - "Rotas de Elliott"
Cohesion: 0.14
Nodes (9): _dict(), listar_candidatas(), listar_ondas(), listar_revisoes(), listar_validadas(), obter_candidata(), obter_validada(), reconstruir_trader() (+1 more)

### Community 31 - "Briefing de Design do Painel"
Cohesion: 0.12
Nodes (18): Alinhamento Multi-Grau, Bot, LogExecucao, Sentimento, StatusGeral, Briefing de Design do Painel, Alertas Recentes (Dashboard), Cartões de Robôs do Dashboard (+10 more)

### Community 32 - "Ajuste de Padrões de Elliott"
Cohesion: 0.37
Nodes (13): ajustar_diagonal(), ajustar_flat(), ajustar_impulso(), ajustar_triangulo(), ajustar_wxy(), ajustar_wxyxz(), ajustar_zigzag(), _alem() (+5 more)

### Community 33 - "Serviço de Análise Elliott"
Cohesion: 0.17
Nodes (2): ElliottService, Teste rápido: análise de Elliott multi-grau com dados públicos da Bybit.

### Community 34 - "Banco de Dados e Pares"
Cohesion: 0.16
Nodes (6): Bug: Import Circular do Base (SQLAlchemy), Decisao: Pares/Exchanges Parametrizaveis (sem fixo no codigo), ExchangeInstitucional, PairInstitucional, pyodbc Missing Dependency, requirements.txt Missing Backend Packages

### Community 35 - "Executor de Ordens Reais"
Cohesion: 0.16
Nodes (6): Compara posição do banco com a da exchange (testnet/real)., OrderExecutor, position_idx(), one-way -> 0 ; hedged -> 1 (long) / 2 (short)., Ordem limitada post-only com SL/TP anexados. Em simulador devolve um pedido pend, aberta' | 'executada' (com preco_exec/quantidade) | 'cancelada'.

### Community 36 - "Motor de Cenários Concorrentes"
Cohesion: 0.27
Nodes (3): _alem(), Cenario, ScenarioEngine

### Community 37 - "Gerenciador de Bots em Threads"
Cohesion: 0.16
Nodes (3): Roda todos os bots ativos sem a API (um thread por bot). Ctrl+C para parar., BotManager, get_manager()

### Community 38 - "Painel Flutter (abandonado)"
Cohesion: 0.15
Nodes (16): Binance Symbols API (coin autocomplete), ApiService (Flutter, api_service.dart), BotDetailPage (Flutter), ChartViewWidget (Flutter), Bug: Right Price Scale Not Rendering, Flutter SDK / Syncfusion markNeedsBuild Incompatibility, Bug: Candle Timestamp ms vs seconds, tradingview_chart.html (+8 more)

### Community 39 - "Cadastro de Indicadores"
Cohesion: 0.14
Nodes (3): Lacuna: Lista de Indicadores Disponíveis no Banco, IndicadorDisponivel, IndicadorService

### Community 40 - "Mockup do Robô e Histórico"
Cohesion: 0.13
Nodes (15): DecisaoResumo, Curva de Capital (Equity Curve), Alvo e Proteção, Tabela de Decisões Recentes, Filtros de Decisão, Formulário — Execução, Formulário — Identificação, Formulário — Risco (+7 more)

### Community 41 - "Controle e Logs de Bots"
Cohesion: 0.13
Nodes (3): Bybit Kline REST API, Bug: Invalid Simulated Candle Values (open=0), Bug: /logs/{bot_id}/grafico-dados AttributeError

### Community 42 - "Rotas de Status"
Cohesion: 0.14
Nodes (2): historico(), niveis()

### Community 43 - "Log de Execução e Stops"
Cohesion: 0.23
Nodes (13): Fix: ALTER TABLE LogExecucaoBot (sl, tp, quantidade), Bug: 'Unknown format code f for str', Bug: 'sl' invalid keyword argument for LogExecucaoBot, Bug: operações logadas com SL/TP incoerentes, Decisão: SL e TP enviados como ordens separadas, Fix: função validar_operacao central, Infinite Buy Loop / Duplicate Position Bug, Cálculo de Resultado (Gain/Loss) (+5 more)

### Community 44 - "Conexão e Modos da Bybit"
Cohesion: 0.22
Nodes (8): Bug: API key Bybit inválida, Bug: sandboxMode não ativado corretamente, Bybit API / BybitConnector, BybitConnector, Diagnóstico rápido: horário, ticker e (se houver chaves) saldo., Campo modo_execucao (real/simulador/testnet), Modo Simulador, Modo Testnet

### Community 45 - "Planos de Backtest e Painel"
Cohesion: 0.18
Nodes (10): Backtest Institucional (Fase 7), Roteiro de Fases (FASE 14-18+), Explicação do Módulo de Backtest, Primeiro Resultado de Backtest (CSV), Estrutura de Telas Flutter Planejada, Gráfico TradingView Lightweight Charts (WebView), Decisão: Painel Administrativo em Flutter Web, Resumo do Estado do Projeto (chat 7) (+2 more)

### Community 46 - "Detector Institucional"
Cohesion: 0.20
Nodes (11): Zonas de Memória Institucional (planejado), Script de Preenchimento Historico de Pontos Institucionais, detectar_para_par_e_timeframe(), run_detector(), AttributeError: BybitConnector sem obter_trades, Logs DEBUG verbosos no pipeline TPO/Volume Profile, PendingRollbackError em cascata (VWAP, VL Profile, Order Book), Falha ao reacessar pair.par apos sessao quebrada (+3 more)

### Community 47 - "WebSocket Universal"
Cohesion: 0.14
Nodes (5): Campo modo_execucao (simulador vs real) e Testnet Bybit, Bug: DataSourceWebsocketUniversal recebendo websocket_url invalido, DataSourceWebsocketUniversal, exchange: 'bybit' ou 'coinbase'
         symbol_spot: par padrão do seu bot ('BT, Agregacao de dados multi-exchange para confluencia

### Community 48 - "Varredura Histórica Institucional"
Cohesion: 0.19
Nodes (10): Busca TODOS os candles SPOT de symbol/timeframe no intervalo [since, until]., SpotCandlesFetcher, iniciar_varredura_elliott_institucional(), processar_varredura_multi_timeframe(), Varredura histórica de Elliott (persistência de contagens candidatas e promoção, Varredura institucional: detecta, salva candidatas, valida e vincula ondas/ciclo, Vincula hierarquia institucional: ondas macro são parent das contagens/ondas mic, Processa a análise multi-timeframe, do maior para o menor, vinculando parent_id (+2 more)

### Community 49 - "Rotas de Backtest"
Cohesion: 0.23
Nodes (5): backtests_do_bot(), listar(), rodar_backtest(), _svc(), validar_par()

### Community 50 - "Modelo de Ponto Institucional"
Cohesion: 0.22
Nodes (10): Rotina de Atualizacao de Status (testado/rompido), Erros de criacao do banco SQL Server (permissao/objetos duplicados), Log Institucional em SQL (PontosInstitucionaisLog), obter_pontos_institucionais_ativos() (consulta centralizada), Plano de 7 Fases - Pontos Institucionais, Checagem de Zona Institucional no StrategyEngine.decidir(), Escada de Preços (Ladder Institucional), Tabela Pontos na Faixa (+2 more)

### Community 51 - "Schemas e Rotas do Trader"
Cohesion: 0.39
Nodes (11): ContagemCandidataSchema, ContagemValidadaSchema, OndaSchema, RevisaoSchema, BaseModel, contagem_mestre(), leitura_trader(), Leitura do trader humano: estado de superciclo, direção, hipóteses vivas maduras (+3 more)

### Community 52 - "Conectores Binance e Coinbase"
Cohesion: 0.21
Nodes (2): Conectores Binance e Coinbase (novos, via ccxt), BinanceConnector

### Community 53 - "Diagnóstico e Refatoração"
Cohesion: 0.20
Nodes (8): Bug: metodo executar() fora da classe BotExecutor, Checklist Cirurgico de Refatoracao Institucional, Decisao de Separar Deteccao em Daemon Isolado, Diagnóstico Completo do Bot Trade Pro, Atalho: prepara o banco (scripts/setup_db.py) e mostra os bots cadastrados., Dependências Python, Bug requirements.txt em UTF-16, Bug Crítico de Saída de Posição

### Community 54 - "Backtest do Dial de Hedge"
Cohesion: 0.23
Nodes (4): BacktestHedge, leitura_dial_ao_vivo(), Mesma leitura do backtest (níveis, exaustão, Elliott) sobre candles diários ao v, _rsi()

### Community 55 - "Calibração Histórica de Cenários"
Cohesion: 0.24
Nodes (8): construir_dataset(), features_cenario(), _one_hot(), Adiciona prob_sucesso a cada cenário e reordena por score x prob_sucesso., Replay sem look-ahead: em cada candle i usa ohlcv[i-janela+1:i+1] e olha ohlcv[i, _regime_simples(), treinar(), vetor()

### Community 56 - "Nuvens de Order Book"
Cohesion: 0.33
Nodes (11): aggregate_ranges(), _collector_loop(), ensure_symbol_formats(), ensure_task_running(), fetch_binance_orderbook(), fetch_coinbase_orderbook(), _get_pair_for_bot(), nuvens_dados_timeseries() (+3 more)

### Community 57 - "Execução Real e Dimensionamento"
Cohesion: 0.22
Nodes (9): Plano de Ação Institucional (StrategyEngine + indicadores), Fix: cálculo de gain/loss respeitando direção, Position-Sizing Risk Control (banca / risco_pct / max_alocacao_pct), ExecutorReal, Compatibilidade com o nome antigo., Modo Real, Spot vs Futures/Perpetual Execution Mode, Config por bot: exchange_execucao vs exchanges_consulta (+1 more)

### Community 58 - "Checklist de Fases do Projeto"
Cohesion: 0.24
Nodes (10): Checklist Real Revisado (pós-cobrança), Fase 10 – Backtest e Otimização (opcional), Fase 1 – Preparação do Ambiente, Fase 2 – Estrutura de Pastas do Projeto, Fase 5 – Estratégia de Decisão, Fase 6 – Execução (Simulador/Executor/Risk), Fase 9 – Alertas e Monitoramento (original), Lacuna: Sensibilidade a Eventos Econômicos (+2 more)

### Community 59 - "Motor de Backtest e Otimização"
Cohesion: 0.24
Nodes (6): carregar_binance_csv(), Lê os CSVs diários da Binance (klines) e devolve OHLCV em ms., carregar_historico(), main(), rodar(), Walk-Forward

### Community 60 - "Primitiva de Desenho do Gráfico"
Cohesion: 0.22
Nodes (1): Overlay

### Community 61 - "Eventos Macro e Configuração"
Cohesion: 0.25
Nodes (9): Decisão: Usar SQL Server em vez de JSON/SQLite, Fase 3 – Conexão com a Exchange (Bybit), Fase 7 Original (Config via JSON) – Rejeitada, Diretriz Máxima: Sistema Profissional, Nada Fixo, Etapa 13 – Scraping de Eventos Econômicos, Etapa 13B – Integração API TradingEconomics, Campo usar_api_macro no Bot, Macro Event Checker (+1 more)

### Community 62 - "Contagem Mestre por Grau"
Cohesion: 0.33
Nodes (8): analisar_grau(), contagem_mestre(), _data(), trava: dict salvo ao travar (vies, invalidacao, alvos). Devolve status atualizad, ZigZag por reversão percentual sobre high/low. Último pivô é provisório., series: {'1w': candles desde 2011, '1d': candles, '4h': candles} (o que faltar é, verificar_trava(), zigzag_pct()

### Community 63 - "Testes de Elliott"
Cohesion: 0.31
Nodes (4): legs(), test_corretivos(), test_diagonal_e_truncada(), test_impulso_valido_e_invalido()

### Community 64 - "Gráfico em Tempo Real (etapa)"
Cohesion: 0.32
Nodes (8): Bot Executor (loop de execução), API de Controle de Bots (ativar/desativar/histórico), Etapa 14 – Endpoint de Dados para Gráfico em Tempo Real, Bug: chart.addCandlestickSeries is not a function, Checklist consolidado Bot Trade Pro, Esclarecimento: gráfico é só diagnóstico, robô opera com dados reais, Página grafico.html (TradingView Lightweight Charts), Bug: timestamp em segundos vs milissegundos no gráfico

### Community 65 - "Modelo de Bot e Multibots"
Cohesion: 0.29
Nodes (8): Modelo Bot (tabela Bots), Fase 8 – Multibots e Execução Paralela, Tabela LogExecucaoBot, run_all_bots.py (Executor Multiprocess), Tabela BotIndicador (relacional), Criação do BotService (CRUD completo), Requisito: CRUD Completo, Indicador Loader

### Community 66 - "Regime de Mercado"
Cohesion: 0.32
Nodes (4): Regime de Mercado, _serie_ciclos(), test_backtest_ordem_limitada_e_slippage(), test_calibracao_treina_e_aplica()

### Community 67 - "Rotas do Modo Inverso"
Cohesion: 0.39
Nodes (7): aprovar(), backtest(), _bot(), cancelar(), dial(), estado(), proposta()

### Community 68 - "Decisões de Stack e Deploy"
Cohesion: 0.33
Nodes (7): Banco de Dados, Backend FastAPI + SQL Server, Plano de Deploy: VPS + SQL Server + FastAPI, Plano de 5 Etapas do Painel Flutter, Decisão: Frontend em Flutter Web, Rejeição do Painel HTML Estático, Bug: foreign key falhando em inserir_logs_falsos.py

### Community 69 - "Download de Histórico"
Cohesion: 0.57
Nodes (6): baixar_binance(), baixar_bitstamp(), main(), API pública v2 da Bitstamp: /ohlc/btcusd?step=&limit=1000&start= (segundos)., _salvar(), _ultimo_ts()

### Community 70 - "Conector Coinbase"
Cohesion: 0.53
Nodes (1): CoinbaseConnector

### Community 71 - "Fixtures de Teste"
Cohesion: 0.47
Nodes (5): candles_impulso(), gerar_candles(), impulso_5_ondas(), Candles sintéticos a partir de uma lista de fechamentos (high/low com pequena am, Série de preços com um impulso de alta de 5 ondas respeitando as regras:

### Community 72 - "Checagem de Evento Macro"
Cohesion: 0.60
Nodes (4): evento_importante_agora(), evento_via_api(), evento_via_scraping(), Fonte principal: calendário Forex Factory (gratuito). Fallbacks: TradingEconomic

### Community 73 - "Configuração do Vite"
Cohesion: 0.40
Nodes (4): favicon.svg (purple gem mark), Frontend README, ROTAS_API, vite.svg (Vite logo)

### Community 74 - "Simulador de Trades"
Cohesion: 0.40
Nodes (1): SimuladorTrade

### Community 75 - "Inicialização da API"
Cohesion: 0.50
Nodes (1): BotManager + FastAPI Startup Integration

### Community 76 - "Busca de Candles"
Cohesion: 0.67
Nodes (3): get_candles(), log_event(), Candles fechados da Bybit (linear). Cache opcional em disco para reprocessamento

### Community 78 - "Criação de Tabelas de Log"
Cohesion: 1.00
Nodes (1): Compatibilidade: cria/atualiza as tabelas (equivale a scripts/setup_db.py).

## Ambiguous Edges - Review These
- `Binance Symbols API (coin autocomplete)` → `BinanceConnector`  [AMBIGUOUS]
  doc explicacao/chat 1 - flutter.txt · relation: conceptually_related_to
- `Decisão: Frontend em Flutter Web` → `client.ts`  [AMBIGUOUS]
  doc explicacao/chat 2.txt · relation: conceptually_related_to
- `Script de Preenchimento Historico de Pontos Institucionais` → `detector_ponto_institucional_service.py`  [AMBIGUOUS]
  doc explicacao/chat 8 - ponto_institucional.txt · relation: calls
- `Script de Preenchimento Historico de Pontos Institucionais` → `TPO (Time Price Opportunity)`  [AMBIGUOUS]
  doc explicacao/chat 8 - ponto_institucional.txt · relation: references
- `todas_sequencias_possiveis() Pivot Scan` → `Zigzag`  [AMBIGUOUS]
  doc explicacao/chat 9 - elliott pro.txt · relation: conceptually_related_to
- `favicon.svg (purple gem mark)` → `main.tsx`  [AMBIGUOUS]
  frontend/public/favicon.svg · relation: references
- `hero.png (isometric cube graphic)` → `Dashboard.tsx`  [AMBIGUOUS]
  frontend/src/assets/hero.png · relation: conceptually_related_to
- `hero.png (isometric cube graphic)` → `App.tsx`  [AMBIGUOUS]
  frontend/src/assets/hero.png · relation: references
- `icons.svg (social/doc icon sprite)` → `Layout.tsx`  [AMBIGUOUS]
  frontend/public/icons.svg · relation: conceptually_related_to
- `icons.svg (social/doc icon sprite)` → `ui.tsx`  [AMBIGUOUS]
  frontend/public/icons.svg · relation: conceptually_related_to
- `Onda 3` → `Onda B (corretiva ABC)`  [AMBIGUOUS]
  doc explicacao/chat 6.txt · relation: conceptually_related_to
- `elliott_routes.py` → `Bootstrap/Varredura Institucional Inicial`  [AMBIGUOUS]
  doc explicacao/elliott completo - part2.txt · relation: references
- `vite.svg (Vite logo)` → `App.tsx`  [AMBIGUOUS]
  frontend/src/assets/vite.svg · relation: references

## Knowledge Gaps
- **134 isolated node(s):** `Binance: BTCUSDT | Coinbase: BTC-USD`, `Retorna SÉRIE TEMPORAL de nuvens (order book) agregadas por faixas.     - Dispar`, `# TODO: troque pelo lookup no seu banco (tabela Bot)`, `Converte 'BTCUSDT' / 'BTC/USDT' para o símbolo ccxt da categoria.`, `Id nativo da Bybit (ex.: BTCUSDT).` (+129 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Serviço de Análise Elliott`** (2 nodes): `ElliottService`, `Teste rápido: análise de Elliott multi-grau com dados públicos da Bybit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Rotas de Status`** (2 nodes): `historico()`, `niveis()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Conectores Binance e Coinbase`** (2 nodes): `Conectores Binance e Coinbase (novos, via ccxt)`, `BinanceConnector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Primitiva de Desenho do Gráfico`** (1 nodes): `Overlay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Conector Coinbase`** (1 nodes): `CoinbaseConnector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Simulador de Trades`** (1 nodes): `SimuladorTrade`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Inicialização da API`** (1 nodes): `BotManager + FastAPI Startup Integration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Criação de Tabelas de Log`** (1 nodes): `Compatibilidade: cria/atualiza as tabelas (equivale a scripts/setup_db.py).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Binance Symbols API (coin autocomplete)` and `BinanceConnector`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Decisão: Frontend em Flutter Web` and `client.ts`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Script de Preenchimento Historico de Pontos Institucionais` and `detector_ponto_institucional_service.py`?**
  _Edge tagged AMBIGUOUS (relation: calls) - confidence is low._
- **What is the exact relationship between `Script de Preenchimento Historico de Pontos Institucionais` and `TPO (Time Price Opportunity)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `todas_sequencias_possiveis() Pivot Scan` and `Zigzag`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `favicon.svg (purple gem mark)` and `main.tsx`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `hero.png (isometric cube graphic)` and `Dashboard.tsx`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._