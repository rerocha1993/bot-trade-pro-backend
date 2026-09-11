# Graph Report - .  (2026-09-11)

## Corpus Check
- Large corpus: 230 files · ~555.404 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 2456 nodes · 5743 edges · 129 communities detected
- Extraction: 75% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 1407 edges (avg confidence: 0.54)
- Token cost: 9.500 input · 14.000 output
- Edge kinds: uses: 1178 · calls: 1079 · contains: 895 · method: 610 · rationale_for: 377 · imports_from: 364 · references: 302 · imports: 251 · conceptually_related_to: 167 · depends_on: 155 · describes: 143 · implements: 141 · semantically_similar_to: 39 · inherits: 21 · shares_data_with: 19 · cites: 2

## God Nodes (most connected - your core abstractions)
1. `BybitConnector` - 110 edges
2. `BotExecutor` - 105 edges
3. `StrategyEngine` - 80 edges
4. `TPOProfile` - 65 edges
5. `Barra` - 59 edges
6. `VolumeProfilePRO` - 59 edges
7. `Contexto` - 54 edges
8. `OrderBlockDetector` - 53 edges
9. `Nivel` - 51 edges
10. `ElliottMestreService` - 48 edges

## Surprising Connections (you probably didn't know these)
- `Proposed PosicaoAtivaBot Table` --semantically_similar_to--> `PosicaoBot`  [INFERRED] [semantically similar]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 1 - flutter.txt → C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/models/posicao_bot.py
- `run_all_bots.py (Executor Multiprocess)` --semantically_similar_to--> `BotExecutor`  [INFERRED] [semantically similar]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 1.txt → C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/core/bot_executor.py
- `Institutional-Zone Trade Block Logic` --semantically_similar_to--> `StrategyEngine`  [INFERRED] [semantically similar]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 2 - flutter.txt → C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/core/strategy_engine.py
- `Detector Integration Plan (TPO/VWAP/OrderFlow/VolumeProfile/OrderBlock)` --semantically_similar_to--> `DetectorPontoInstitucionalService`  [INFERRED] [semantically similar]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 2 - flutter.txt → C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/services/detector_ponto_institucional_service.py
- `PontoInstitucional ORM Model & Endpoints (planned)` --semantically_similar_to--> `PontoInstitucional`  [INFERRED] [semantically similar]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 2 - flutter.txt → C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/models/ponto_institucional.py

## Hyperedges (group relationships)
- **Flutter Web Chart Rendering Stack** — chat1flutter_chartviewwidget, chat1flutter_tradingview_chart_html, postmessage_bridge [INFERRED 0.80]
- **Elliott como Núcleo Obrigatório da Estratégia** — elliott_wave, strategy_engine, requisito_original [INFERRED 0.85]
- **Institutional Points Detection Pipeline** — chat2flutter_detector_integration_plan, chat2flutter_pontoinstitucional_model_plan, chat2flutter_bloqueio_institucional [INFERRED 0.80]
- **Pilares da arquitetura avançada (perfis, zonas de memória, ML)** — chat4_perfis_operacionais, chat4_zonas_memoria_liquidez, chat4_ml_trader_inteligente_plano [INFERRED 0.80]
- **Elliott-led Decision, Confluence, Fibonacci Risk Pipeline** — elliott_e_lei, confluencia_indicadores [INFERRED 0.85]
- **Ambiguidade Onda 3 vs Onda B** — onda_3, onda_b, chat6_cenario_intersecao [INFERRED 0.75]
- **Requisito Visual de TPO (POC/VAH/VAL)** — tpo, poc, chat7_elliott_tpo_visual_requisito [INFERRED 0.80]
- **Fluxo Detector -> Registro -> Bloqueio de Trade** — tpo, chat8_registro_ponto_service, chat8_strategy_engine_bloqueio [INFERRED 0.80]
- **Ciclo de Vida do Ponto: Teste, Rompimento e Log** — chat8_atualizacao_status_service, chat8_log_institucional [EXTRACTED 0.90]
- **Multi-Degree Alignment by Trading Style** — scalp, daytrade, swing [INFERRED 0.75]
- **Validação institucional de ordem (SL/TP coerentes)** — ajustes_validar_operacao, stop_loss, take_profit [INFERRED 0.80]
- **Indicadores implicados no bug de pontos fantasma** — tpo, vwap, volume_profile [INFERRED 0.75]
- **CRUD Completo como Pilar do Sistema Profissional** — crud_completo, chat2_bot_service_crud, chat2_indicador_disponivel_gap [INFERRED 0.80]
- **Feature de Sensibilidade a Eventos Macroeconômicos** — macro_event_checker, chat2_etapa13_macro_scraping, chat2_etapa13b_macro_api [INFERRED 0.85]
- **Fluxo de Decisão Elliott-Pro-Master** — fase_onda, confluencia, tp_sl_conservador [INFERRED 0.75]
- **Validação Multi-Padrão via Fibonacci Elliott** — fibonacci, score_confianca [INFERRED 0.80]
- **Lacuna de Bootstrap Institucional Multi-Timeframe** — bootstrap_institucional, multi_timeframe_hierarquico, elliottcompletopart2_big_range [INFERRED 0.70]
- **Cascata de falha no detector institucional (TypeError -> rollback -> pair expirado)** — erro_tpo_column_length_typeerror, erro_pendingrollback_cascata, erro_rundetector_pair_expired [INFERRED 0.85]
- **Bugs de metodos ausentes na camada API/service de bots** — erro_botexecutor_executar_ausente, erro_botservice_get_all_bots_ausente, erro_bot_as_dict_ausente [INFERRED 0.85]
- **Pipeline backend de pontos institucionais (modelo + API + confluencia)** — novidade_modelo_dados_ponto, novidade_endpoints_rest, novidade_orquestracao_strategyengine_confluencia [INFERRED 0.80]
- **Camada do Trader Governando Alinhamento e Hedge** — superciclo, subordinacao_graus, hedge_dial [INFERRED 0.85]
- **Análise multi-grau no detalhe do robô** — grafico_candles, cenarios_concorrentes, alinhamento_multi_grau [INFERRED 0.80]
- **Composição da visão geral do dashboard** — inspiracaopainel_kpicards, inspiracaopainel_botcards, inspiracaopainel_alertasrecentes [INFERRED 0.80]
- **Composição da tela de sentimento** — medidor_sentimento, inspiracaopainel_sentcomponentes, inspiracaopainel_scorehistorico [INFERRED 0.85]
- **Três camadas: indicadores independentes -> trader/plano -> bots orquestrados** — leituras_leitura, plano, strategy_engine_strategyengine [EXTRACTED 1.00]
- **Fluxo de decisão por candle fechado** — elliott_pro, fase_onda_rules, strategy_engine_strategyengine, sentimento_mercado, bot_executor [EXTRACTED 1.00]
- **Leitura do superciclo governando plano, alinhamento e hedge** — superciclo, memoria_memoriahierarquica, trader_service, plano_service, hedge_dial_hedgedial, elliott_pro_analisemultigrau [INFERRED 0.80]

## Communities

### Community 0 - "Fibonacci e Elliott (histórico)"
Cohesion: 0.05
Nodes (51): ABC Correction, Fibonacci Target, Bootstrap/Varredura Institucional Inicial, Pergunta: Bots Comerciais de Elliott Existem?, Decision: Split Fibonacci into Wave-Specific Strategy Methods, Decisão em zona de interseção de cenários, Q&A: Elliott + Fibonacci sem ML, Validação de contagens enviadas por imagem (+43 more)

### Community 1 - "Contexto do Motor de Fluxo"
Cohesion: 0.10
Nodes (43): Ordem limitada esperando no nivel. Executa quando um negocio imprime no preco ou, SL/TP conferidos negócio a negócio: sabe-se qual preço veio primeiro, sem o palp, Barra, Uma barra fechada. `delta` é a agressão líquida: comprado a mercado menos vendid, Contexto, LeitorContexto, Nivel, ParametrosFluxo (+35 more)

### Community 2 - "VWAP, Order Flow e Order Block"
Cohesion: 0.06
Nodes (30): Fix: filtro de ATH/ATL do range analisado, Bug: VWAPCalculator sem obter_vwap_atual, Fix: VWAP/bandas limitadas ao range do OHLCV, Blindagem ATH/ATL de Período, Detector Integration Plan (TPO/VWAP/OrderFlow/VolumeProfile/OrderBlock), Order Flow Pro Roadmap (footprint/absorption/traps), VWAP Multi-Anchor with Deviation Bands, Multi-Indicator Confluence Voting (+22 more)

### Community 3 - "Painel: Hooks e Tipos"
Cohesion: 0.06
Nodes (46): candlesDaApi(), useCandles(), useDecisoes(), useDial(), useHistorico(), useMestre(), usePlano(), usePosicoes() (+38 more)

### Community 4 - "Barras de Fluxo"
Cohesion: 0.07
Nodes (29): AgregadorBarras, _passo(), Estima o tamanho da barra pelo fluxo observado, mirando uma barra a cada `segund, Recebe negócios NOVOS ({'price', 'qty', 'side', 'timestamp'}) e devolve as barra, No formato que o resto do sistema já entende: [ts, abertura, máxima, mínima, fec, Consome negócios e devolve barras fechadas.      Só recebe negócios NOVOS: que, fluxo_constante(), negocios() (+21 more)

### Community 5 - "Conector Bybit"
Cohesion: 0.08
Nodes (17): BybitConnector, Quem é o dono desta chave, segundo a própria Bybit: UID, tipo (principal ou subc, Só no modo demo: pede saldo fictício para a conta de Demo Trading., Converte 'BTCUSDT' / 'BTC/USDT' para o símbolo ccxt da categoria., Id nativo da Bybit (ex.: BTCUSDT)., Repete uma LEITURA que falhou por rede. Só leitura: reenviar ordem por timeout d, Baixa candles em blocos de 1000 até `until_ms` (ou agora)., Últimos negócios públicos, no formato usado pelo OrderFlowAnalyzerPro. (+9 more)

### Community 6 - "Rotas do Inverse e Trader"
Cohesion: 0.09
Nodes (24): BacktestGrade, Chamado pela thread da API: NÃO pode tocar no ORM, que pertence à sessão da thre, Bot, Configuração de um robô.      modo_execucao : 'simulador' (paper trading, sem, aprovar(), backtest(), _bot(), cancelar() (+16 more)

### Community 7 - "Scalp por Indicadores"
Cohesion: 0.08
Nodes (30): com_fluxo(), Ctx, _mesma_sessao(), montar_contextos(), montar_sinal(), Contexto de cada candle, calculado em sequência e só com o passado.      - VWAP, Piso do stop: meio ATR, 0,12% do preço e 1,5x o custo de ida e volta — o que for, Entrada limitada no fechamento; stop estrutural respeitando o piso; alvo dado ou (+22 more)

### Community 8 - "Utilitários de Indicadores"
Cohesion: 0.07
Nodes (19): Absolute Import / PYTHONPATH Fix for core package, _vies(), tamanho_b / tamanho_a com proteção de divisão por zero., razao(), arredondar_para_step(), atr(), normalizar_timeframe(), pct_dist() (+11 more)

### Community 9 - "Leituras Independentes"
Cohesion: 0.11
Nodes (33): _lado(), Leitura, leitura_elliott(), leitura_fibonacci(), leitura_order_block(), leitura_order_flow(), leitura_regime(), leitura_sentimento() (+25 more)

### Community 10 - "Painel: Hooks de Bots"
Cohesion: 0.09
Nodes (26): useBacktests(), useBots(), useControleBot(), useDetalhes(), useFechadas(), useLogs(), usePontos(), useSentimento() (+18 more)

### Community 11 - "Fonte WebSocket e Logs"
Cohesion: 0.08
Nodes (29): Base, Grava o log em UMA SESSÃO PRÓPRIA, separada da sessão do robô.          Antes, Compara posição do banco com a da exchange (testnet/real)., O motor de fluxo só vale para o scalp: nos graus maiores o candle de tempo é uma, Plano do par, contagem mestre e leitura do trader — as mesmas que o StrategyEngi, Já pode existir candle fechado novo desde a última busca?          Rebuscar 30, O motor de fluxo não decide por candle, mas a gestão de posição ainda precisa de, Ciclo do scalp por fluxo: o gatilho é a barra de volume fechando, não o minuto v (+21 more)

### Community 12 - "Painel: Componentes Elliott/Inverse"
Cohesion: 0.11
Nodes (32): useInverseEstado(), useMultigrau(), useNiveis(), usePropostaRange(), useRangeInverse(), AlinhamentoBox(), CenarioCard(), GrafPainel() (+24 more)

### Community 13 - "Banco LocalDB"
Cohesion: 0.07
Nodes (22): acordar_localdb(), aguardar_banco(), _conecta(), _instancia_localdb(), manter_banco_acordado(), _matar_localdb_orfao(), O 'sqllocaldb start' devolve sucesso mesmo quando a instância NÃO subiu (acontec, LocalDB dorme por ociosidade. Manda iniciar e CONFERE se subiu; se não subiu, li (+14 more)

### Community 14 - "Executor do Robô"
Cohesion: 0.17
Nodes (2): Async Telegram Coroutine Fix, BotExecutor

### Community 15 - "App Flutter (histórico)"
Cohesion: 0.07
Nodes (27): Binance Symbols API (coin autocomplete), Bybit Kline REST API, ApiService (Flutter, api_service.dart), BotDetailPage (Flutter), Bug: Invalid Simulated Candle Values (open=0), ChartViewWidget (Flutter), Bug: /logs/{bot_id}/grafico-dados AttributeError, Bug: Right Price Scale Not Rendering (+19 more)

### Community 16 - "Testes de Ordem Pendente"
Cohesion: 0.09
Nodes (26): _executor(), _executor_fluxo(), _executor_tf(), _Ordens, _Publico, Ordem limitada pendente: ela TEM que envelhecer e morrer, mesmo quando não dá pa, Conector público que pode estar fora do ar., Regressão: a exceção subia e derrubava `_ciclo_fluxo` INTEIRO — e com ele a gest (+18 more)

### Community 17 - "Sentimento e Derivativos"
Cohesion: 0.10
Nodes (12): DadosDerivativos, Liquidações agregadas 24h e razão long/short global (Coinglass API v4, plano gra, Opcional: proporção de tweets recentes com palavras de euforia vs medo. Exige X_, connector: BybitConnector (qualquer modo) para funding/ratio/OI. Se None, cria u, Variação do OI nas últimas 24h (histórico 1h) e variação de preço no mesmo perío, SentimentoMercado, Fear & Greed Index, Funding Rate (+4 more)

### Community 18 - "Cesta Multi-Exchange"
Cohesion: 0.09
Nodes (14): _base_do_par(), BitfinexPublico, MarketDataAggregator, Cliente público multi-exchange com cache curto e tolerância a falhas por exchang, OHLCV de cada exchange da cesta (as que falharem são omitidas e registradas em `, Vela composta por timestamp: OHLC = média simples entre exchanges (como o índice, Une os livros das exchanges (preços em USD/USDT tratados como equivalentes)., Preço médio (último negócio) entre as exchanges da cesta, como o índice da Tradi (+6 more)

### Community 19 - "Motor de Estratégia"
Cohesion: 0.10
Nodes (12): Confluência de Indicadores (filtro duplo), _hold(), Leitura do TraderService (superciclo + contagens maduras). Só ao vivo: em backte, PLANO DE MERCADO do par (core/orquestrador/plano.py). Um plano por par: todos os, Pontos institucionais CONTRA a direção, dentro do raio da fase (só se houver ses, Usa a última análise multi-grau para dizer se a posição deve ser encerrada por e, StrategyEngine, Elliott Pro como Núcleo (Master) da Decisão (+4 more)

### Community 20 - "Testes do Motor de Fluxo"
Cohesion: 0.18
Nodes (31): absorcao_no_suporte(), barra(), bot(), contexto(), enchimento(), grau(), leitor(), motor_com_contexto() (+23 more)

### Community 21 - "Conectores de Exchange"
Cohesion: 0.09
Nodes (15): Conectores Binance e Coinbase (novos, via ccxt), BinanceConnector, credenciais(), _erro_de_rede(), _esperar_vez(), nomes_variaveis(), Pega o proximo lugar na fila global e dorme so o que falta para ele., Vale a pena repetir? Timeout, queda de conexão e limite de chamadas, sim — são t (+7 more)

### Community 22 - "Memória de Contagens"
Cohesion: 0.14
Nodes (14): chave_hipotese(), _data(), evoluir(), evoluir_hierarquico(), MemoriaContagens, MemoriaHierarquica, Maturidade com a lógica de Elliott: uma hipótese de CONTINUAÇÃO (onda 3/5 em and, Reproduz a memória ao longo de uma série (semanal para ciclo, diária para primár (+6 more)

### Community 23 - "Testes de Saída Escalonada"
Cohesion: 0.09
Nodes (16): _executor(), _normalizar(), Saída escalonada: realizar em pedaços conforme o preço avança rumo ao alvo., A ordem já saiu na corretora: se o registro não for gravado na hora, o ciclo seg, test_avanco_grande_realiza_todas_as_fatias_de_uma_vez(), test_desligado_nao_realiza_nada(), test_executor_nao_repete_a_mesma_fatia(), test_executor_realiza_a_fatia_no_avanco_certo() (+8 more)

### Community 24 - "Backtest do Inverse"
Cohesion: 0.08
Nodes (11): BacktestInverse, alocacao_escada(), decidir_alocacao(), posicao_no_range(), PosicaoInversa, propor_range(), RangeConfig, Proposta automática a partir dos pivôs do grau primário no diário (últimos H e L (+3 more)

### Community 25 - "Esquemas Elliott da API"
Cohesion: 0.20
Nodes (21): ContagemCandidataSchema, ContagemValidadaSchema, OndaSchema, RevisaoSchema, BaseModel, Contagem Validada, Wrapper de compatibilidade: aceita lista de preços OU candles., Varredura histórica: percorre os pivôs em janelas deslizantes, guarda os padrões (+13 more)

### Community 26 - "Grade Inversa"
Cohesion: 0.11
Nodes (15): GradeInversa, Ordens limitadas que deveriam estar no livro agora (para o executor real)., Ao montar a grade: níveis abaixo do preço atual só entram depois que o preço cai, Executa as ordens limitadas tocadas pelo candle. Vendas na subida (high >= preco, ParametrosRompimento, Rompimento do range no modo inverse — as regras do usuário, num range de 57k a 8, O único lugar do inverse que vende grande de uma vez precisa de saída se o rompi, Encostar no fundo rompido e fechar ACIMA dele não é rejeição: ainda está sendo t (+7 more)

### Community 27 - "Cliente da API do Painel"
Cohesion: 0.10
Nodes (20): api, ApiError, call(), erroTexto(), Params, url(), Decisão: TradingView Lightweight Charts, DiagBybit (+12 more)

### Community 28 - "Gráfico de Preço"
Cohesion: 0.13
Nodes (20): Candle, Cenario, NiveisResp, Pivot, PontoInstitucional, DrawTarget, OverlayData, Props (+12 more)

### Community 29 - "Rotas Elliott e Candles"
Cohesion: 0.10
Nodes (15): get_candles(), log_event(), Candles fechados da Bybit (linear). Cache opcional em disco para reprocessamento, contagem_mestre(), _dict(), leitura_trader(), listar_candidatas(), listar_ondas() (+7 more)

### Community 30 - "Serviço de Backtest"
Cohesion: 0.10
Nodes (13): BacktestBot, Resultado de um backtest de validação. Um bot só pode ser ativado com um backtes, Ativa o bot. Em testnet/real exige backtest aprovado nos últimos 30 dias (POST /, BacktestService, (ok, motivo). Simulador e demo não arriscam dinheiro e não precisam de backtest;, Candles do par na Bybit (linear), com cache incremental em CSV., Fase 3: o bot é tático e obedece ao plano do par. Quem decide a direção do grau, Demo Trading vive em bybit.com (api-demo), não em testnet.bybit.com. É o caminho (+5 more)

### Community 31 - "Plano Institucional (histórico)"
Cohesion: 0.11
Nodes (24): Plano de Ação Institucional (StrategyEngine + indicadores), Fix: cálculo de gain/loss respeitando direção, Fix: TPO com range/timeframe customizável, BOT TRADE PRO - Arquitetura Estratégica Avançada, Prioridade de dados reais da Coinbase para decisão do bot, Réplica interna de recursos estilo ExoCharts, Plano de ML - Trader Inteligente (Fases 1-4), Perfis operacionais (Scalper, Day Trade, Swing, Macro) (+16 more)

### Community 32 - "Pontos Institucionais (histórico)"
Cohesion: 0.12
Nodes (18): Zonas de Memória Institucional (planejado), Rotina de Atualizacao de Status (testado/rompido), Checklist Cirurgico de Refatoracao Institucional, Erros de criacao do banco SQL Server (permissao/objetos duplicados), Log Institucional em SQL (PontosInstitucionaisLog), obter_pontos_institucionais_ativos() (consulta centralizada), Decisao de Separar Deteccao em Daemon Isolado, Script de Preenchimento Historico de Pontos Institucionais (+10 more)

### Community 33 - "Testes do Rompimento Inverse"
Cohesion: 0.17
Nodes (18): _fundo_rompido(), test_alvo_de_elliott_tem_preferencia_sobre_a_projecao(), test_colado_no_topo_nao_confirma_sozinho(), test_contagem_de_elliott_de_alta_nao_confirma_rompimento_sozinha(), test_dentro_do_range_nao_faz_nada(), test_estado_sobrevive_ao_reinicio_do_servidor(), test_fundo_falso_nao_vende(), test_fundo_retomado_depois_de_confirmado_volta_ao_range_sem_vender() (+10 more)

### Community 34 - "Fonte de Dados"
Cohesion: 0.10
Nodes (5): DataSource, DataSourceWebsocket, symbol: símbolo da moeda, ex: btcusdt (sempre minúsculo)         url: endpoint, Espera até o cache de trades atingir tamanho mínimo (ou timeout)., WebSocket + In-Memory Cache Data Pattern

### Community 35 - "Regras de Fase de Onda"
Cohesion: 0.13
Nodes (17): bloquear_zona_institucional(), direcao_permitida(), get_regras_fase_onda(), get_tolerancia_preco(), get_tp_sl_prioritario(), indicadores_para_fase(), Interseção entre o que a fase permite e o que o bot habilitou., tendencia' | 'contra' | None conforme a fase e o perfil (conservador/turbo). (+9 more)

### Community 36 - "Order Blocks Institucionais"
Cohesion: 0.13
Nodes (8): Realiza pedaços da posição conforme o preço avança rumo ao alvo (core/saida_esca, OrderBlockInstitucional, atualizar_orderblocks(), Lê os livros (Bitstamp, Coinbase, Bitfinex, Kraken, Bybit) e persiste os blocos, OrderBlockInstitutionalService, Bid (demanda) rompe quando o preço fecha abaixo; ask (oferta) rompe quando fecha, niveis: [(preco, qty, exchange)] de UM lado do livro.         Agrupa em faixas d, Detecta, persiste e expira blocos que sumiram do livro.

### Community 37 - "Execução Real"
Cohesion: 0.13
Nodes (11): Uma barra de fluxo fecha a cada poucos segundos: gravar todo 'hold' encheria a t, Stream público de trades/livro da Bybit (linear) para scalp: menos chamadas REST, ExecutorReal, OrderExecutor, position_idx(), Realiza PARTE da posição (reduce_only), mantendo o resto aberto. Usado pela saíd, Compatibilidade com o nome antigo., one-way -> 0 ; hedged -> 1 (long) / 2 (short). (+3 more)

### Community 38 - "Pivôs e Padrões Elliott"
Cohesion: 0.11
Nodes (16): Elliott Pro: motor de ondas com múltiplos cenários e múltiplos graus.      pivot, ajustar_todos(), Leg, legs_de_pivots(), None se alguma obrigatória falhou; senão 0.55 + 0.45 * (diretrizes ok ponderadas, a está além de b na direção `up`?, Diagonal contrátil (cunha). 'leading' inicia impulsos/zigzags (onda 1/A); 'endin, Detecta flat regular, expandido ou running (B retrai ≥ 90% de A). (+8 more)

### Community 39 - "Testes do Plano"
Cohesion: 0.18
Nodes (20): _lateral(), Camada 2: o plano de mercado do par. O superciclo é o veto de todos os bots., Série sem tendência: RSI no meio e sem exaustão, para cair no ramo 'aguardar a b, Regressão medida ao vivo: contagens 82% bear, o trader mandando vender, e o plan, O outro lado da mesma regra: com contagens bull, o impulso maduro continua compr, A regra que o usuário fixou: ninguém vende num fundo terminal, nem o perfil turb, Maduro não é venda: é não perseguir. Só vira 'reduzir' quando as contagens viram, _serie() (+12 more)

### Community 40 - "Discussões Iniciais (histórico)"
Cohesion: 0.20
Nodes (21): Bug: pontos institucionais acima do preço nunca negociado, OrderBlock, Fase 4 – Núcleo de Inteligência (Indicadores), Discussão sobre Machine Learning Avançado, Decisão de mercado via confluência Elliott+indicadores, Estratégia: esperar retração em zona de confluência, Confluência Institucional de Longo Prazo, Servico de Registro de Ponto Institucional (v1 acoplado ao bot) (+13 more)

### Community 41 - "Testes do Gatilho de Fluxo"
Cohesion: 0.30
Nodes (19): absorcao(), barra(), contexto(), enchimento(), test_absorcao_exige_que_a_agressao_esteja_secando(), test_absorcao_exige_que_a_ultima_barra_feche_longe_do_fundo(), test_absorcao_exige_volume_concentrado_no_nivel(), test_absorcao_na_resistencia_vira_venda() (+11 more)

### Community 42 - "Elliott Institucional (histórico)"
Cohesion: 0.21
Nodes (11): Concurrent Scenarios (Multi-Hypothesis), consultar_estruturas_atuais() Method, get_ondas_validadas() Method (Gap Fix), Plano Definitivo Elliott Institucional, promover_e_validar() Method, Elliott Institucional Vision, Institutional Memory / Never-Restart Principle, Current Basic Edge Limitation (+3 more)

### Community 43 - "Testes de Orquestração"
Cohesion: 0.18
Nodes (12): _engine(), _plano(), _serie(), test_info_chave_normaliza_a_resposta_da_bybit(), test_modo_demo_usa_a_conta_oficial_e_nao_o_testnet(), test_plano_bloqueia_compra_em_correcao(), test_plano_bloqueia_venda_em_fundo_de_ciclo(), test_plano_com_erro_nao_bloqueia() (+4 more)

### Community 44 - "Testes do Scalp"
Cohesion: 0.19
Nodes (18): _ctx(), passeio(), _sempre(), test_alvo_padrao_e_2r(), test_limite_de_perda_do_dia_para_o_robo(), test_nada_olha_o_futuro(), test_nenhum_setup_usa_indicador_de_fora(), test_ordem_limitada_executa_so_quando_o_preco_encosta() (+10 more)

### Community 45 - "Alinhamento Multigrau"
Cohesion: 0.16
Nodes (13): Alinhamento Multi-Grau, Calibrador, Aplica o modelo treinado: P(alvo antes da invalidação) para um cenário., analisar_serie(), AnaliseMultiGrau, calibrador_padrao(), normalizar_perfil(), fetch_ohlcv(timeframe, limite) -> candles. Pode ser o conector Bybit, o agregado (+5 more)

### Community 46 - "Serviço Elliott"
Cohesion: 0.16
Nodes (4): revisar_rollback() Method, Pattern Invalidation, Rollback/Revisão Institucional, ElliottService

### Community 47 - "Serviço de Pontos Institucionais"
Cohesion: 0.15
Nodes (9): O último negócio do stream é mais fresco e mais barato que uma chamada REST de p, PontoInstitucionalLog, Rotina de atualizacao de status a cada candle fechado, Deduplicacao de pontos institucionais ja mapeados, classificar_tipo(), PontoInstitucionalService, tolerancia      -> fração do preço para considerar "testado" (0,15%)         tol, Resistências logo acima (para compra) ou suportes logo abaixo (para venda). (+1 more)

### Community 48 - "Perfil de Saída"
Cohesion: 0.13
Nodes (10): perfil(), PerfilSaida, Perfil do estilo; estilo desconhecido ou vazio cai no daytrade, que é o meio ter, Perfil de saída por estilo: o trailing tem que caber no ruído do timeframe., O valor único de 0,30% tirava o swing no primeiro pavio: era a queixa., No alvo curto vale realizar mais; no swing vale deixar correr., Ao ligar, o stop já tem que estar do lado do lucro: ativador > distância nos trê, test_scalp_garante_mais_cedo_que_o_swing() (+2 more)

### Community 49 - "Trava de Instância"
Cohesion: 0.14
Nodes (6): Lock exclusivo de arquivo. `adquirir()` devolve False quando outro processo já t, PID de quem está com a trava, só para a mensagem de erro fazer sentido., TravaInstancia, Dois servidores não podem subir os mesmos robôs.  O `uvicorn` roda o startup da, A trava é uma proteção, não um motivo para o robô não existir: caminho inválido, test_trava_impossivel_nao_impede_o_sistema_de_subir()

### Community 50 - "Backtest do Scalp"
Cohesion: 0.18
Nodes (11): avaliar_criterio(), BacktestScalp, O que reprova um setup. Vazio = aprovado. O critério foi escrito antes de qualqu, Roda entre `inicio_ms` e `fim_ms`. Os contextos já vêm aquecidos pelo histórico, carregar_5m(), deltas_5m(), linha(), main() (+3 more)

### Community 51 - "Ajuste de Padrões Elliott"
Cohesion: 0.37
Nodes (13): ajustar_diagonal(), ajustar_flat(), ajustar_impulso(), ajustar_triangulo(), ajustar_wxy(), ajustar_wxyxz(), ajustar_zigzag(), _alem() (+5 more)

### Community 52 - "Testes de Alavancagem"
Cohesion: 0.11
Nodes (9): Alavancagem: o risco real de 50x e 100x é a liquidação chegar antes do stop., Stop de 1,5% com 100x: a liquidação está a 0,5%, então a posição morre antes do, Bots em 1x (o padrão) não podem ser afetados pela trava., Em cruzada a banca inteira sustenta a posição, então a distância é maior que em, Prova que a trava está ligada no executor, não só na fórmula., test_alavancagem_1_nunca_bloqueia_stop_normal(), test_executor_recusa_entrada_que_liquidaria_antes_do_stop(), test_margem_cruzada_usa_a_banca() (+1 more)

### Community 53 - "Inicialização da API"
Cohesion: 0.15
Nodes (6): BotManager + FastAPI Startup Integration, carregar_binance_csv(), Lê os CSVs diários da Binance (klines) e devolve OHLCV em ms., carregar_historico(), main(), rodar()

### Community 54 - "Briefing de Design"
Cohesion: 0.13
Nodes (17): Bot, LogExecucao, Sentimento, StatusGeral, Briefing de Design do Painel, Alertas Recentes (Dashboard), Cartões de Robôs do Dashboard, Cartões de KPI do Dashboard (+9 more)

### Community 55 - "Checklist Inicial (histórico)"
Cohesion: 0.15
Nodes (17): Checklist Real Revisado (pós-cobrança), Decisão: Usar SQL Server em vez de JSON/SQLite, Fase 10 – Backtest e Otimização (opcional), Fase 1 – Preparação do Ambiente, Fase 2 – Estrutura de Pastas do Projeto, Fase 3 – Conexão com a Exchange (Bybit), Fase 5 – Estratégia de Decisão, Fase 7 Original (Config via JSON) – Rejeitada (+9 more)

### Community 56 - "Motor de Cenários"
Cohesion: 0.27
Nodes (3): _alem(), Cenario, ScenarioEngine

### Community 57 - "Controlador de Bots"
Cohesion: 0.21
Nodes (16): AttributeError: Bot sem metodo as_dict, AttributeError: BotExecutor sem metodo executar, AttributeError: BotService sem get_all_bots, Padrao: metodos chamados antes de implementados (API/service), ativar_trailing(), criar_bot(), desativar_trailing(), editar_bot() (+8 more)

### Community 58 - "Gerenciador de Bots"
Cohesion: 0.16
Nodes (3): Roda todos os bots ativos sem a API (um thread por bot). Ctrl+C para parar., BotManager, get_manager()

### Community 59 - "Testes de Log Isolado"
Cohesion: 0.15
Nodes (10): _executor(), O log não pode derrubar o que o robô fez.  Um log que não cabia na coluna fez um, Sessão que aceita tudo e anota o que foi chamado., Todo acao=/tipo_operacao= escrito no executor precisa caber na largura que o set, O painel pergunta o status pela thread da API; ler o ORM de lá quebra a sessão d, _Sessao, test_log_normal_grava_nas_duas_sessoes(), test_log_que_falha_nao_desfaz_o_estado_do_robo() (+2 more)

### Community 60 - "Catálogo de Indicadores"
Cohesion: 0.14
Nodes (3): Lacuna: Lista de Indicadores Disponíveis no Banco, IndicadorDisponivel, IndicadorService

### Community 61 - "Backtest de Fluxo"
Cohesion: 0.23
Nodes (2): BacktestFluxo, bot_fluxo()

### Community 62 - "Gatilho de Fluxo"
Cohesion: 0.22
Nodes (4): GatilhoFluxo, Espaço a dar ao stop além do nível: meio range médio de barra, com piso de 0,05%, Piso do stop: fora do ruído da própria barra, e bem acima do custo de ida e volt, Stop atrás do nível, alvo no próximo nível contrário, e o risco:retorno medido L

### Community 63 - "Rotas de Status"
Cohesion: 0.13
Nodes (3): historico(), niveis(), subcontas()

### Community 64 - "Serviço de Bots"
Cohesion: 0.16
Nodes (8): BotService, _numero(), `ler_plano` cai no padrão para o robô não parar; `analisar_plano` diz que o text, Com pouca quantidade, as fatias menores nao alcancam o minimo: o plano encolhe e, Se as fatias somam 100% não sobra nada para o alvo: é erro de configuração, não, test_analisar_separa_invalido_de_padrao(), test_mao_media_encolhe_o_plano(), test_plano_que_zera_a_posicao_e_recusado()

### Community 65 - "Inspiração do Painel"
Cohesion: 0.13
Nodes (15): DecisaoResumo, Curva de Capital (Equity Curve), Alvo e Proteção, Tabela de Decisões Recentes, Filtros de Decisão, Formulário — Execução, Formulário — Identificação, Formulário — Risco (+7 more)

### Community 66 - "Banco SQL Server (histórico)"
Cohesion: 0.16
Nodes (15): Banco de Dados (SQL Server), Modelo Bot (tabela Bots), Fase 8 – Multibots e Execução Paralela, Backend FastAPI + SQL Server, Tabela LogExecucaoBot, run_all_bots.py (Executor Multiprocess), Tabela BotIndicador (relacional), Criação do BotService (CRUD completo) (+7 more)

### Community 67 - "Executor do Inverse"
Cohesion: 0.35
Nodes (1): InverseRangeExecutor

### Community 68 - "Máquina de Rompimento"
Cohesion: 0.27
Nodes (3): MaquinaRompimento, Só dentro do range a grade pode vender. Fora dele o range acabou ou está em xequ, Lê um candle FECHADO e devolve {'estado', 'execs', 'fechar_grade', 'concluido',

### Community 69 - "Saída Escalonada"
Cohesion: 0.15
Nodes (11): analisar_plano(), _arredondar(), avanco(), ler_plano(), montar_fatias(), pendentes(), Fatias que o avanço atual já disparou e que ainda não foram realizadas., '50/30, 75/30, 90/25' -> ((0.5, 0.3), (0.75, 0.3), (0.9, 0.25)). None quando o t (+3 more)

### Community 70 - "Perfil TPO"
Cohesion: 0.22
Nodes (4): Sinal padronizado (buy/sell/hold) + contexto:             preço acima da VAH  ->, TPOProfile, Single Print (TPO), TPO com Range Customizável

### Community 71 - "Regime e Fixtures"
Cohesion: 0.19
Nodes (8): candles_impulso(), gerar_candles(), impulso_5_ondas(), Candles sintéticos a partir de uma lista de fechamentos (high/low com pequena am, Série de preços com um impulso de alta de 5 ondas respeitando as regras:, _serie_ciclos(), test_backtest_ordem_limitada_e_slippage(), test_calibracao_treina_e_aplica()

### Community 72 - "Negócios Históricos Bybit"
Cohesion: 0.23
Nodes (13): baixar_dia(), caminho_cache(), carregar(), dias(), fluxo(), ler_arquivo(), Quantos negócios e quanto volume naquele dia — para conferir a régua da barra an, Baixa (ou reaproveita do cache) o arquivo de um dia. None quando a Bybit não pub (+5 more)

### Community 73 - "Varredura e Candles Spot"
Cohesion: 0.19
Nodes (10): Busca TODOS os candles SPOT de symbol/timeframe no intervalo [since, until]., SpotCandlesFetcher, iniciar_varredura_elliott_institucional(), processar_varredura_multi_timeframe(), Varredura histórica de Elliott (persistência de contagens candidatas e promoção, Varredura institucional: detecta, salva candidatas, valida e vincula ondas/ciclo, Vincula hierarquia institucional: ondas macro são parent das contagens/ondas mic, Processa a análise multi-timeframe, do maior para o menor, vinculando parent_id (+2 more)

### Community 74 - "Testes do Escopo do Plano"
Cohesion: 0.19
Nodes (9): _engine(), _plano(), Alcance do plano do par por robô.  O plano é montado a partir do superciclo (sem, A regra que o usuário fixou continua de pé para todos os graus., Para dar para auditar no painel POR QUE um robô obedeceu ou não obedeceu o plano, test_a_decisao_registra_o_alcance_do_plano(), test_ninguem_compra_correcao_de_ciclo_recem_iniciada(), test_ninguem_vende_fundo_de_ciclo_nem_o_scalp() (+1 more)

### Community 75 - "Testes do Livro WebSocket"
Cohesion: 0.34
Nodes (13): _fonte(), _handler(), _msg(), Livro de ofertas via websocket da Bybit.  A Bybit manda um SNAPSHOT (livro intei, Pega o on_message do livro sem abrir conexão de rede., O bug antigo: cada delta virava o livro inteiro, restando um nível só., O estado do livro precisa ser por instância: como atributo de classe, dois bots, test_delta_mantem_os_niveis_que_nao_mudaram() (+5 more)

### Community 76 - "Formulário de Bot"
Cohesion: 0.18
Nodes (10): useAlavancagens(), useBacktestsBot(), Estrutura de Telas Flutter Planejada, Switch(), analisarPlano(), PerfilSaida, PERFIS, NUM (+2 more)

### Community 77 - "Mapa do README"
Cohesion: 0.17
Nodes (11): services/bot_manager, AnaliseMultiGrau, scripts/evoluir_contagens.py, HedgeDial (core/hedge_dial), InverseRangeExecutor (core/inverse_executor.py), api.main:app (FastAPI), MemoriaHierarquica (core/elliott_pro/memoria.py), core/orquestrador/plano.py (+3 more)

### Community 78 - "Pares e Exchanges"
Cohesion: 0.23
Nodes (5): Decisao: Pares/Exchanges Parametrizaveis (sem fixo no codigo), ExchangeInstitucional, PairInstitucional, alargar_colunas(), main()

### Community 79 - "Alertas Telegram"
Cohesion: 0.26
Nodes (4): Fecha quando os graus maiores viram para o LADO OPOSTO. Contexto sem lado não fe, Alertas via Telegram. Se token/chat id não estiverem configurados, o serviço fic, Versão síncrona (thread-safe)., TelegramAlertService

### Community 80 - "Elliott Legado"
Cohesion: 0.20
Nodes (2): ElliottAnalyzer, ElliottDetector

### Community 81 - "Calibração Elliott"
Cohesion: 0.24
Nodes (8): construir_dataset(), features_cenario(), _one_hot(), Adiciona prob_sucesso a cada cenário e reordena por score x prob_sucesso., Replay sem look-ahead: em cada candle i usa ohlcv[i-janela+1:i+1] e olha ohlcv[i, _regime_simples(), treinar(), vetor()

### Community 82 - "Superciclo e Hedge"
Cohesion: 0.20
Nodes (9): aplicar_contexto(), Pesos das hipóteses vivas ajustados pelo contexto de superciclo., Grade Inversa, Hedge Capital Reserve / Hedge Dial, Inverse Range, Bot Trade Pro (backend), Resultados de Backtest, Superciclo (Escala Log) (+1 more)

### Community 83 - "Nuvens de Liquidez"
Cohesion: 0.33
Nodes (11): aggregate_ranges(), _collector_loop(), ensure_symbol_formats(), ensure_task_running(), fetch_binance_orderbook(), fetch_coinbase_orderbook(), _get_pair_for_bot(), nuvens_dados_timeseries() (+3 more)

### Community 84 - "Testes do LocalDB"
Cohesion: 0.26
Nodes (11): r""" Subir um segundo servidor não pode derrubar o banco do primeiro.  O sqls, Anota o que a rotina tentou fazer, sem executar nada de verdade., Já vimos o LocalDB dizer 'Stopped', recusar conexões novas e ainda assim estar s, O estado leva segundos para assentar: concluir cedo demais mataria um banco que, _sem_efeito(), test_aguardar_nem_encosta_na_instancia_com_banco_de_pe(), test_banco_de_pe_nao_e_derrubado(), test_instancia_que_demora_a_subir_nao_e_morta() (+3 more)

### Community 85 - "Testes de Integração Fluxo"
Cohesion: 0.26
Nodes (8): fonte(), negocio(), test_cursor_avisa_quando_o_buffer_girou_antes_de_alguem_consumir(), test_cursor_entrega_cada_negocio_uma_vez_so(), test_ligar_o_motor_liga_o_websocket_junto(), test_negocios_carregam_o_numero_de_serie(), test_numero_invalido_e_recusado_com_explicacao(), test_o_que_o_motor_grava_cabe_nas_colunas()

### Community 86 - "Erros de Import (histórico)"
Cohesion: 0.20
Nodes (6): Erro de import relativo core/services, Configuração launch.json como módulo, Bug: metodo executar() fora da classe BotExecutor, Campo modo_execucao (simulador vs real) e Testnet Bybit, Bug: DataSourceWebsocketUniversal recebendo websocket_url invalido, _modo()

### Community 87 - "Controle de Bots (histórico)"
Cohesion: 0.22
Nodes (11): core/alavancagem.py, Bot Executor, API de Controle de Bots (ativar/desativar/histórico), Etapa 14 – Endpoint de Dados para Gráfico em Tempo Real, Bug: chart.addCandlestickSeries is not a function, Checklist consolidado Bot Trade Pro, Esclarecimento: gráfico é só diagnóstico, robô opera com dados reais, Página grafico.html (TradingView Lightweight Charts) (+3 more)

### Community 88 - "Backtest como Gate"
Cohesion: 0.24
Nodes (7): Backtest como gate de validação de estratégia, Roteiro de Fases (FASE 14-18+), Explicação do Módulo de Backtest, Primeiro Resultado de Backtest (CSV), Decisão: Painel Administrativo em Flutter Web, Resumo do Estado do Projeto (chat 7), BinanceCSVNormalizer

### Community 89 - "Alavancagem"
Cohesion: 0.25
Nodes (10): alavancagem_maxima(), distancia_liquidacao(), normalizar(), Para o painel: cada opção com a distância de liquidação e o stop máximo que aind, Encaixa o valor pedido na opção válida mais próxima para baixo, respeitando o te, Fração do preço que o mercado pode andar contra antes da liquidação. 1x isolado, Maior alavancagem da lista em que um stop a `distancia_sl` (fração do preço) ain, O stop cabe antes da liquidação?      Devolve {ok, distancia_sl, distancia_liqui (+2 more)

### Community 90 - "Backtest por Candle"
Cohesion: 0.25
Nodes (3): BacktestEngine, bot_padrao(), fetch_ohlcv(tf, n) que só enxerga candles FECHADOS até ts_limite (sem look-ahead

### Community 91 - "Motor de Fluxo"
Cohesion: 0.24
Nodes (4): _hold(), _hold(), Decide em cima do estado atual das barras. Chamado quando uma barra de fluxo FEC, Decisão no formato que o executor e o painel já entendem.

### Community 92 - "Serviço do Plano"
Cohesion: 0.36
Nodes (1): PlanoService

### Community 93 - "Gestão de Risco"
Cohesion: 0.20
Nodes (5): Fase 6 – Execução (Simulador/Executor/Risk), Gerenciamento por Banca e % por Operação, RiskManager, Risco por Trade / Gerenciamento de Banca, Risk Manager

### Community 94 - "Diagnóstico e Telegram"
Cohesion: 0.24
Nodes (7): FASE 14 - Alertas via Telegram, Bug asyncio/multiprocessing no Telegram, Diagnóstico Completo do Bot Trade Pro, Atalho: prepara o banco (scripts/setup_db.py) e mostra os bots cadastrados., Dependências Python, Bug requirements.txt em UTF-16, Bug Crítico de Saída de Posição

### Community 95 - "Carregador de Indicadores"
Cohesion: 0.20
Nodes (5): Tabela HistoricoIndicadores (base p/ ML), Bug: BotService sem metodo get_all_bots, IndicadorLoader, Devolve lista de (nome_canonico, parametros) dos indicadores cadastrados para o, Formulário — Indicadores e Filtros (Switches)

### Community 96 - "Dial de Hedge"
Cohesion: 0.27
Nodes (7): barreiras(), EstadoHedge, exaustao(), HedgeDial, elliott: {'fase', 'vies', 'prob_bull', 'prob_bear', 'alvos', 'invalidacao', 'cic, niveis: [{'preco', 'fonte', 'peso'}] de todas as fontes (elliott, tpo, instituci, Combina sinais de topo em 0..1:         fear_greed (0..100)     >= 60 começa a

### Community 97 - "Pesos do Inverse"
Cohesion: 0.20
Nodes (4): pesos_inverse(), O que impede aprovar um range. Devolve (bloqueios, avisos).      BLOQUEIO não pa, Os níveis DENTRO do range, renormalizados para somar 100% no topo.      A grade, validar_aprovacao()

### Community 98 - "Bugs de Chave Bybit"
Cohesion: 0.28
Nodes (9): Bug: API key Bybit inválida, Bug: sandboxMode não ativado corretamente, Bybit API, As Quatro Travas Encadeadas, Detector de Elliott Aleatório (bug), Fase Técnica da Onda, Campo modo_execucao (real/simulador/testnet), Modo Simulador (+1 more)

### Community 99 - "Scripts de Calibração"
Cohesion: 0.25
Nodes (9): scripts/baixar_historico.py, core/elliott_pro/calibracao.py, scripts/calibrar_elliott.py, core/dados_derivativos.py, core/elliott_pro (motor de Elliott), core/fase_onda_rules.py, core/regime.py, core/sentimento_mercado.py (+1 more)

### Community 100 - "Overlay do Gráfico"
Cohesion: 0.22
Nodes (1): Overlay

### Community 101 - "Roadmap TPO/VP"
Cohesion: 0.44
Nodes (9): TPO Pro Roadmap (profile shapes, HVN/LVN, single prints), Volume Profile Pro Roadmap (HVN/LVN, adjustable histograms), Requisito: Elliott (consolidada+futura) e TPO com dados reais, Gráfico TradingView Lightweight Charts (WebView), Decisão: migrar de flutter_inappwebview para iframe, Point of Control (POC), Value Area High (VAH), Value Area Low (VAL) (+1 more)

### Community 102 - "Contagem Mestre"
Cohesion: 0.33
Nodes (8): analisar_grau(), contagem_mestre(), _data(), trava: dict salvo ao travar (vies, invalidacao, alvos). Devolve status atualizad, ZigZag por reversão percentual sobre high/low. Último pivô é provisório., series: {'1w': candles desde 2011, '1d': candles, '4h': candles} (o que faltar é, verificar_trava(), zigzag_pct()

### Community 103 - "Testes Elliott"
Cohesion: 0.31
Nodes (4): legs(), test_corretivos(), test_diagonal_e_truncada(), test_impulso_valido_e_invalido()

### Community 104 - "Bugs de Log (histórico)"
Cohesion: 0.43
Nodes (8): Fix: ALTER TABLE LogExecucaoBot (sl, tp, quantidade), Bug: 'Unknown format code f for str', Bug: 'sl' invalid keyword argument for LogExecucaoBot, Bug: operações logadas com SL/TP incoerentes, Decisão: SL e TP enviados como ordens separadas, Fix: função validar_operacao central, Stop Loss, Take Profit

### Community 105 - "Backtest do Hedge"
Cohesion: 0.32
Nodes (3): BacktestHedge, leitura_dial_ao_vivo(), _rsi()

### Community 106 - "Evolução de Contagens"
Cohesion: 0.46
Nodes (7): acerto_consenso(), carregar(), fim_de_ano(), fim_de_trimestre(), main(), Compara o consenso de cada snapshot com a variação de preço nos 12 meses seguint, relatorio()

### Community 107 - "Stubs de Teste Inverse"
Cohesion: 0.29
Nodes (5): _candle(), _Db, _executor(), test_no_ciclo_rompimento_falso_do_topo_mantem_o_short(), test_no_ciclo_rompimento_real_do_topo_fecha_toda_a_grade()

### Community 108 - "Rotas de Backtest"
Cohesion: 0.52
Nodes (5): backtests_do_bot(), listar(), rodar_backtest(), _svc(), validar_par()

### Community 109 - "Script Backtest Fluxo"
Cohesion: 0.48
Nodes (6): candles(), imprimir(), main(), ms(), Valida o motor de fluxo do scalp sobre os negócios reais publicados pela Bybit., Candles do contexto cobrindo o periodo mais o aquecimento.      Buscar so os u

### Community 110 - "Download de Histórico"
Cohesion: 0.57
Nodes (6): baixar_binance(), baixar_bitstamp(), main(), API pública v2 da Bitstamp: /ohlc/btcusd?step=&limit=1000&start= (segundos)., _salvar(), _ultimo_ts()

### Community 111 - "Launcher de Backtest"
Cohesion: 0.33
Nodes (2): scripts/backtest_bot.py, core/backtest_engine.py

### Community 112 - "Perfis por Estilo"
Cohesion: 0.47
Nodes (6): bot_perfis Profile Configuration, Daytrade Profile, Top-Down Timeframe Flow, Multi-Degree / Multi-Timeframe Hierarchy, Scalp Profile, Swing Profile

### Community 113 - "Bug de Compra Repetida"
Cohesion: 0.40
Nodes (5): Infinite Buy Loop / Duplicate Position Bug, Position-Sizing Risk Control (banca / risco_pct / max_alocacao_pct), Entry/Exit Trade Logging Model, Spot vs Futures/Perpetual Execution Mode, Multiple Simultaneous Positions with Exposure Cap

### Community 114 - "Checagem Macro"
Cohesion: 0.60
Nodes (4): evento_importante_agora(), evento_via_api(), evento_via_scraping(), Fonte principal: calendário Forex Factory (gratuito). Fallbacks: TradingEconomic

### Community 115 - "Configuração Frontend"
Cohesion: 0.40
Nodes (4): favicon.svg (purple gem mark), Frontend README, ROTAS_API, vite.svg (Vite logo)

### Community 116 - "Simulador Legado"
Cohesion: 0.40
Nodes (1): SimuladorTrade

### Community 117 - "Incidente de Contexto"
Cohesion: 0.67
Nodes (4): Incidente: assistente perdeu o contexto da conversa, Reafirmação: sistema deve ser profissional, sem mock, Decisão: criar telegram_alert_service.py profissional, Bug: URL malformada da API do Telegram (404)

### Community 118 - "Script de Calibração"
Cohesion: 0.83
Nodes (3): avaliar(), carregar(), main()

### Community 119 - "Cooldown de Trade"
Cohesion: 0.67
Nodes (3): Bug: Repeated BUY Orders (One-way Position Bug), Proposed Trade Cooldown Mechanism, Proposed PosicaoAtivaBot Table

### Community 120 - "Config Telegram"
Cohesion: 1.00
Nodes (3): Depuração de Erros Telegram (URL malformada, 401/404), Configuração de Alerta Telegram via .env, Alertas via Telegram

### Community 121 - "Subcontas Bybit"
Cohesion: 1.00
Nodes (2): Position Mode / Margin Mode / Subconta, Subcontas Bybit por perfil de estratégia

### Community 122 - "Razão de Delta"
Cohesion: 1.00
Nodes (1): Delta como fração do volume da barra (-1 = só venda a mercado, +1 = só compra).

### Community 123 - "Criação de Tabelas"
Cohesion: 1.00
Nodes (1): Compatibilidade: cria/atualiza as tabelas (equivale a scripts/setup_db.py).

### Community 127 - "Proposta de Orquestrador"
Cohesion: 1.00
Nodes (1): Proposta: indicadores independentes, bot orquestrado, orquestrador como trader humano

### Community 131 - "Script Bots Exemplo"
Cohesion: 1.00
Nodes (1): scripts/criar_bots_exemplo.py

### Community 132 - "Doc Inspiração Painel"
Cohesion: 1.00
Nodes (1): docs/design/inspiracao_painel.dc.html

### Community 134 - "Script Otimizar"
Cohesion: 1.00
Nodes (1): scripts/otimizar.py

### Community 135 - "Doc PriceChart"
Cohesion: 1.00
Nodes (1): PriceChart.tsx (frontend/src/components/chart)

## Ambiguous Edges - Review These
- `Binance Symbols API (coin autocomplete)` → `BinanceConnector`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 1 - flutter.txt · relation: conceptually_related_to
- `Decisão: Frontend em Flutter Web` → `client.ts`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 2.txt · relation: conceptually_related_to
- `Script de Preenchimento Historico de Pontos Institucionais` → `detector_ponto_institucional_service.py`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 8 - ponto_institucional.txt · relation: calls
- `Script de Preenchimento Historico de Pontos Institucionais` → `TPO (Time Price Opportunity)`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 8 - ponto_institucional.txt · relation: references
- `todas_sequencias_possiveis() Pivot Scan` → `Zigzag`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 9 - elliott pro.txt · relation: conceptually_related_to
- `favicon.svg (purple gem mark)` → `main.tsx`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/frontend/public/favicon.svg · relation: references
- `hero.png (isometric cube graphic)` → `Dashboard.tsx`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/frontend/src/assets/hero.png · relation: conceptually_related_to
- `hero.png (isometric cube graphic)` → `App.tsx`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/frontend/src/assets/hero.png · relation: references
- `icons.svg (social/doc icon sprite)` → `Layout.tsx`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/frontend/public/icons.svg · relation: conceptually_related_to
- `icons.svg (social/doc icon sprite)` → `ui.tsx`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/frontend/public/icons.svg · relation: conceptually_related_to
- `InverseRangeExecutor (core/inverse_executor.py)` → `core/orquestrador/plano.py`  [AMBIGUOUS]
  docs/ARQUITETURA_ORQUESTRADOR.md · relation: shares_data_with
- `Wave 3 (Elliott)` → `Onda B (corretiva ABC)`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/chat 6.txt · relation: conceptually_related_to
- `elliott_routes.py` → `Bootstrap/Varredura Institucional Inicial`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/doc explicacao/elliott completo - part2.txt · relation: references
- `vite.svg (Vite logo)` → `App.tsx`  [AMBIGUOUS]
  C:/Users/Usuario/source/repos/bot_trade/bot_trade/trading_bot_corrigido/frontend/src/assets/vite.svg · relation: references

## Knowledge Gaps
- **204 isolated node(s):** `Nome da instância se o servidor for LocalDB, senão string vazia.`, `A única prova que vale: o banco atende ou não atende.`, `Encerra o sqlservr do LocalDB quando ele fica pendurado: a instância aparece com`, `O 'sqllocaldb start' devolve sucesso mesmo quando a instância NÃO subiu (acontec`, `LocalDB dorme por ociosidade. Manda iniciar e CONFERE se subiu; se não subiu, li` (+199 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Executor do Robô`** (2 nodes): `Async Telegram Coroutine Fix`, `BotExecutor`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Backtest de Fluxo`** (2 nodes): `BacktestFluxo`, `bot_fluxo()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Executor do Inverse`** (1 nodes): `InverseRangeExecutor`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Elliott Legado`** (2 nodes): `ElliottAnalyzer`, `ElliottDetector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Serviço do Plano`** (1 nodes): `PlanoService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Overlay do Gráfico`** (1 nodes): `Overlay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Launcher de Backtest`** (2 nodes): `scripts/backtest_bot.py`, `core/backtest_engine.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Simulador Legado`** (1 nodes): `SimuladorTrade`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Subcontas Bybit`** (2 nodes): `Position Mode / Margin Mode / Subconta`, `Subcontas Bybit por perfil de estratégia`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Razão de Delta`** (1 nodes): `Delta como fração do volume da barra (-1 = só venda a mercado, +1 = só compra).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Criação de Tabelas`** (1 nodes): `Compatibilidade: cria/atualiza as tabelas (equivale a scripts/setup_db.py).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Proposta de Orquestrador`** (1 nodes): `Proposta: indicadores independentes, bot orquestrado, orquestrador como trader humano`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Script Bots Exemplo`** (1 nodes): `scripts/criar_bots_exemplo.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Doc Inspiração Painel`** (1 nodes): `docs/design/inspiracao_painel.dc.html`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Script Otimizar`** (1 nodes): `scripts/otimizar.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Doc PriceChart`** (1 nodes): `PriceChart.tsx (frontend/src/components/chart)`
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