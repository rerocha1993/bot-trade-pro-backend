# Diagnóstico completo do Bot Trade Pro

Data: 2026-09-06. Escopo: todo o código Python (≈6.000 linhas), o banco `dbo_trading_bot` no SQL Server LocalDB, o `.env`, e a documentação de intenção na pasta `doc explicacao` (≈3,4 MB de transcrições).

Legenda: ✅ está certo | ⚠️ funciona mas está inconsistente | ❌ errado ou quebrado | 🔧 como resolver

---

## 1. Resumo executivo

O sistema tem uma arquitetura boa e uma ideia clara (Elliott como lei, indicadores como validadores, TP/SL institucional, sizing por risco). O que impede de "ir pra frente" não é a ideia, são **quatro travas encadeadas** que fazem os bots nunca operarem, mais uma série de cálculos que produzem números sem significado:

1. **A fase da onda nunca é definida.** `definir_fase()` lê a última contagem *validada* no banco para o timeframe do bot. Só existe uma contagem validada (1M, digitada à mão, 2015-2024). Para bots em 1m, 5m e 30m o retorno é sempre `indefinido`, e para `indefinido` a lista de indicadores permitidos é vazia. Resultado: `hold` em 100% dos ciclos com o motivo "Nenhum indicador ativo permitido para essa fase".
2. **Mesmo com fase válida, o bloqueio institucional bloqueia tudo.** Em `decidir()` a condição é `if fase == "indefinido" or bloquear_zona_institucional(fase) or bloqueio:`. A função `bloquear_zona_institucional` devolve `True` para **todas** as fases exceto `consolidacao`. Ou seja, o bot só poderia operar em consolidação. A intenção era "bloquear SE a flag estiver ligada E o preço estiver dentro de uma zona".
3. **O detector de Elliott que decide a direção é aleatório.** `ElliottDetector.validar_estrutura_basica()` conta picos e vales com `find_peaks(distance=5)`. Com 200 candles sempre há ≥3 picos e ≥2 vales, então é sempre "válido", e a direção é `buy` se houver mais picos que vales. Isso não é contagem de ondas; é moeda ao ar.
4. **A chave da testnet da Bybit expirou.** A API respondeu `retCode 33004: Your api key has expired`. Nenhuma ordem chegaria à exchange até gerar chave nova em testnet.bybit.com.

Além disso: TP/SL por Fibonacci crasha (`'bool' object has no attribute 'get'`), TPO/Volume Profile comparam preço com igualdade exata de float (nunca bate), Order Flow usa 1 minuto fixo, `requirements.txt` está em UTF-16 (o pip não lê), e a saída de posição pode **abrir posição contrária** em conta real (detalhe na seção 5).

---

## 2. O que está certo (manter)

- ✅ **Arquitetura em camadas** (`core/` cálculo, `services/` regras e persistência, `models/` ORM, `api/` FastAPI). Faz sentido e é o padrão que eu manteria.
- ✅ **Filosofia de decisão** documentada: Elliott decide direção, indicadores só validam, Fibonacci nunca decide entrada, só define SL/TP. Correta e coerente com prática institucional.
- ✅ **Fórmula de sizing** `tamanho = (banca * risco_pct) / |entrada - SL|`. É a fórmula certa (risco fixo por trade). Faltam só os limites (seção 5).
- ✅ **Regras de Fibonacci-Elliott** em `fibonacci_elliott.py`: retração da onda 2 em 50-61,8%, onda 3 ≥ 161,8%, onda 4 em 23,6-38,2% sem invadir a onda 1. Os intervalos estão corretos (só a onda 2 poderia aceitar até 78,6% na prática).
- ✅ **Tabela `FASE_ONDA_RULES`**: a ideia de "por fase, quais indicadores validam e quem manda no TP/SL" é boa e deve ser o coração do motor.
- ✅ **Modelo de pontos institucionais** (`testado` baixa relevância, `rompido` inativa, log de eventos). Bem pensado.
- ✅ **Conector Bybit via ccxt com `enableRateLimit` e `recvWindow`**. Escolha certa de biblioteca; os parâmetros é que estavam errados.
- ✅ **Cálculo de VWAP e bandas** (média ponderada por volume e desvio ponderado). A matemática está correta; só usava `close` em vez do preço típico `(H+L+C)/3`, que é o padrão.
- ✅ **`nuvens_endpoint.py`** (agregação do livro por faixas percentuais, imbalance e CVD de profundidade). Está correto e é independente do resto.
- ✅ **Banco LocalDB** existe, com todas as 13 tabelas, 3 bots cadastrados e 970 pontos institucionais. A conexão funciona.

---

## 3. Fluxo de decisão (`core/strategy_engine.py`)

| Item | Status | Problema | 🔧 Solução |
|---|---|---|---|
| `verificar_elliott` | ❌ | Direção vem de `len(picos) > len(vales)`. Sem contagem real. | Substituir por um analisador determinístico: ZigZag por ATR → pivôs → encaixe de impulso 1-2-3-4-5 e ABC com as regras de Fibonacci → fase + direção + invalidação + alvos. Tudo em memória, a partir dos candles do próprio bot. |
| `definir_fase` | ❌ | Depende de contagem validada no banco (só existe 1M). Também acessa `contagem.ondas` (atributo inexistente → `AttributeError` a cada loop) e `onda['par']` (chave inexistente). | A fase deve sair do mesmo analisador acima, calculada nos candles ao vivo. O banco vira histórico/auditoria, não pré-requisito. |
| Bloqueio institucional (passo 7) | ❌ | `or bloquear_zona_institucional(fase)` bloqueia todas as fases exceto consolidação. | Trocar por `if fase == "indefinido" or (bloquear_zona_institucional(fase) and bloqueio):`. |
| Raio do bloqueio | ❌ | `tolerancia_preco` de 2-3% do preço. Com 970 pontos espalhados, **sempre** há um ponto a 3% do preço → sempre bloqueado. | Raio de 0,2-0,4%, considerar só pontos com relevância alta e **contra** a direção do trade (resistência acima para compra, suporte abaixo para venda). |
| Confluência conservadora | ⚠️ | `votos == total if total > 0 else True`: se nenhum indicador emitir buy/sell, passa com zero confirmação. | Exigir `total >= 1` e `votos == total` no conservador; `votos >= 1` no turbo. |
| `calcular_tp_sl` / Fibonacci | ❌ | `fib_elliott.validar_onda2()` devolve `bool`; o código faz `fib_result.get("tp")` → crash sempre que Fibonacci está ativo. | Fazer os validadores devolverem dict `{ok, razao, ideal, motivo}` e os alvos virem de funções próprias (`alvos_onda3`, `alvos_onda5`, `alvos_onda_c`). |
| `calcular_tp_sl` / TPO | ❌ | Calcula `tp, sl` e nunca adiciona em `sugestoes` (código morto). | Adicionar VAH/VAL como candidatos, direcionais. |
| `calcular_tp_sl` / OrderBlock | ❌ | `consultar_blocos_ativos` e outros métodos do serviço estão sem `self` e sem `@staticmethod`; ao chamar via instância o Python passa `self` como `session` → `TypeError`. A tabela `orderblocks_institucionais` tem 0 linhas e nada a popula. | Marcar `@staticmethod`, e criar a rotina que detecta e persiste blocos (o método `get_orderblocks` existe mas nunca é chamado). |
| Perfil conservador/turbo no TP/SL | ⚠️ | Conservador escolhe TP mais próximo e SL mais próximo; turbo o contrário. Aceitável, mas sem checagem de risco/retorno. | Exigir R:R mínimo (ex.: 1,2) e fallback de SL por ATR quando nenhum indicador fornecer SL (hoje sem SL o tamanho vira 0 e a ordem ainda é enviada). |
| `FibonacciStrategies` | ❌ | Usa `max/min` de 200 candles sem direção: para venda, SL a 78,6% *abaixo* do topo e TP a 161,8% *acima*. | Níveis direcionais a partir do último swing (fundo→topo para compra, topo→fundo para venda). |
| Sessão de banco | ❌ | `StrategyEngine.__init__` abre `SessionLocal()` a cada ciclo (10 s) e nunca fecha → vazamento de conexões. Também instancia `BybitConnector` sem usar. | Uma sessão por bot, reutilizada; conector criado uma vez no executor. |
| Multi-timeframe | ⚠️ | A visão da documentação é top-down (mensal → menor). Hoje o bot só olha o próprio timeframe. | Rodar o analisador também no timeframe superior (1m→15m, 5m→1h, 15m/30m→4h, 1h→1d) e usar como filtro de tendência no conservador. |

---

## 4. Cálculos dos indicadores (`core/`)

| Indicador | Status | Problema | 🔧 Solução |
|---|---|---|---|
| `Fibonacci` | ⚠️ | Níveis corretos para swing de alta, mas `_validar_niveis` apaga níveis fora de `[low*0.98, high*1.02]`, o que nunca acontece (todos estão entre low e high). Código inútil. Sem direção. | Classe direcional (`up`/`down`): retração X% = `topo - X*(topo-fundo)` na alta e espelhado na baixa; extensões `fundo + X*(topo-fundo)`. |
| `VWAP` | ⚠️ | Usa `close` em vez do preço típico; âncora = início da janela de 200 candles (VWAP "de 200 candles", não de sessão); descarta o valor se sair de ±2% do range (sem sentido). `datetime.utcfromtimestamp` está deprecado. | Preço típico `(H+L+C)/3`, âncora configurável (janela ou início do dia UTC), sinal por distância em desvios (z-score), sem clamp. |
| `TPO` | ❌ | Conta só **fechamentos** com bin fixo de `interval=50` (US$ 50). Em BTC a 80k com 200 candles, quase todo close cai em bin próprio → tudo vira "single print", POC sem significado. `sinal_estrategico` compara `preco_atual in single_prints` (igualdade exata de float) → nunca bate. Devolve ações `reversao/defesa/rejeicao` que o motor ignora. Value Area pega os bins mais frequentes em qualquer ordem, não ao redor do POC. | TPO real: cada candle imprime em todos os bins entre `low` e `high`; largura do bin = `range/30`; Value Area expandindo a partir do POC até 70%; proximidade por tolerância; sinal padronizado `buy/sell/hold` (acima da VAH / abaixo da VAL / dentro). |
| `VolumeProfilePRO` | ❌ | Histograma de **closes** ponderado por volume (aproximação pobre); LVN escolhe bins com volume **zero**; `price_signal` usa igualdade exata → sempre `hold`. | Distribuir o volume de cada candle entre os bins que ele atravessa; LVN só entre bins com volume; POC/VAH/VAL com expansão; proximidade por tolerância. |
| `OrderFlowAnalyzerPro` | ❌ | Janela do candle fixa em 60 s (`candle_end = start + 60*1000`) independente do timeframe; qualquer `delta > 0` vira `buy` (sem limiar, muito ruído); absorção por igualdade exata de preço; ignora o livro de ofertas que o executor já passa. | Duração pelo timeframe; razão `delta/volume` com limiar (ex.: ±0,15); imbalance do livro nos 10 melhores níveis; score composto 70/30. |
| `OrderBlockDetector` | ❌ | Marca **todo** candle vermelho seguido de verde como bloco (por isso há 137 blocos "4h" no banco, 970 pontos no total). Sem noção de deslocamento nem de mitigação. | Exigir deslocamento ≥ 1,5 ATR nos 3 candles seguintes **e** rompimento da máxima/mínima dos 5 anteriores; zona `[low, open]` (alta) ou `[open, high]` (baixa); marcar mitigado quando o fechamento atravessa a zona. |
| `ElliottEngine` (varredura) | ❌ | `todas_sequencias_possiveis` faz `combinations(pivôs, 5)`: com 200 pivôs são 2,5 bilhões de combinações (trava). Cada "onda" é um candle (open→close), não um swing entre pivôs. Persiste com `status="proposta"`, a varredura procura `status="candidata"` → nunca promove. `promover_e_validar` exige `onda['validada']` que nunca é `True`. `nivel_ciclo` recebe um `int` numa coluna de texto. | Janela deslizante sobre os pivôs do ZigZag (O(N)); ondas = swings; status coerente (`candidata` → `validada`); `validada` preenchida pelas regras. |
| `RiskManager` | ⚠️ | Correto mas nunca é usado pelo executor. SL por "volatilidade" usa `max-min` dos 5 closes (não é ATR). | Integrar ao executor (limite diário de trades e perda) e usar ATR. |
| `macro_event_checker` | ⚠️ | Depende de `bs4` (não instalado) e de scraping do investing.com (frágil). Nunca é chamado. | Manter como opcional com import protegido; preferir API (TradingEconomics) ou o calendário do próprio provedor. |

---

## 5. Execução e Bybit (`core/conexoes`, `core/executor_real.py`, `core/bot_executor.py`)

| Item | Status | Problema | 🔧 Solução |
|---|---|---|---|
| Modo `simulador` | ❌ | No conector, "simulador" = testnet **spot**; no executor, ordens são enviadas do mesmo jeito ("Agora sempre envia, não importa se real ou simulador"). Não existe paper trading de verdade. E o bot é de futuros (alavancagem, position mode), não spot. | Três modos: `simulador` (dados públicos, nenhuma ordem, posição local), `testnet` (ordens em testnet.bybit.com), `real`. Sempre categoria `linear` (perpétuo USDT). |
| Símbolo | ❌ | `BTCUSDT` com `defaultType: spot` e `params={"category": "linear"}` ao mesmo tempo. O cache `BTCUSDT_string_simulador_main.json` está vazio (`[]`) porque a chamada falhou. | Normalizar para o símbolo ccxt da categoria: `BTC/USDT:USDT` (linear). |
| Ordens SL/TP | ❌ | `type='stop_market'` e `'take_profit_market'` não existem no ccxt/Bybit → SL e TP **sempre falham**. Ordem limit passa `price` dentro de `params` em vez do argumento. | Uma única ordem a mercado com `params={'stopLoss': {'triggerPrice': sl}, 'takeProfit': {'triggerPrice': tp}, 'positionIdx': 0}`; a Bybit anexa SL/TP à posição. |
| Saída por SL/TP | ❌ **crítico** | O bot vigia o preço a cada 10 s e, ao cruzar SL/TP, envia ordem contrária com `self.bot.quantidade` (não o tamanho calculado) e **sem `reduceOnly`**, e ainda com novos SL/TP. Se a exchange já fechou a posição pelo SL anexado, essa ordem **abre uma posição oposta**. | Em testnet/real: consultar `fetch_positions`; se a posição sumiu, registrar saída com o P&L realizado (`/v5/position/closed-pnl`). Fechamento manual sempre `reduceOnly=True` com a quantidade real. |
| Posição em memória | ❌ | `posicao_aberta` só existe na RAM. Reiniciar o processo faz o bot "esquecer" a posição enquanto a exchange continua com ela. | Persistir posição em tabela (`PosicoesBot`) e reconciliar com a exchange no início. |
| Sizing | ⚠️ | Falta o limite `banca * max_alocacao_pct` (a regra dos 50% para hedge), a alavancagem, o arredondamento ao passo da exchange (0,001 BTC) e o mínimo. `min_lote` não existe no modelo (`min_quantidade` existe). Sem SL, retorna 0 e a ordem ainda é enviada. | `qty = min(risco/dist_SL, banca*max_aloc*alav/preco)`, arredondar para baixo no `qty_step`, recusar trade sem SL. |
| Trailing stop | ⚠️ | Só altera o dict local; a exchange nunca recebe o novo SL. Lê `bot.trailing_manual`, `ativador_trailing`, `distancia_trailing` que existem no banco mas não no modelo. | Enviar `/v5/position/trading-stop` a cada ajuste; adicionar as colunas ao modelo. |
| P&L registrado | ❌ | `resultado = preco_saida - preco_entrada` (diferença de preço, sem quantidade, sem taxas). Grava em `LogExecucaoBot` sem `acao`, `preco` e `quantidade`, que são justamente os campos que a API e o gráfico leem (`log.acao in ["buy","sell"]`). Resultado: histórico e gráfico sempre vazios. | `pnl = (saida - entrada) * qty * (±1) - taxas`; preencher `acao`, `preco`, `quantidade`, `resultado`. |
| Alavancagem / modo | ❌ | `alavancagem`, `position_mode`, `margin_mode` estão no banco e nunca são enviados à exchange. | `set_leverage`, `set_margin_mode`, `set_position_mode` na inicialização do bot (ignorando "not modified"). |
| WebSocket | ❌ | `DataSourceWebsocketUniversal(exchange="bybit-testnet")`: a classe só conhece `bybit` e `coinbase`, então nenhum tópico é assinado, `start()` não faz nada e trades/livro chegam vazios. Quando funciona, assina o stream **spot** para um bot de futuros. | Passar `exchange="bybit"` e escolher stream `linear` (`wss://stream.bybit.com/v5/public/linear`). Ou simplesmente usar `fetch_trades`/`fetch_order_book` REST (funcionam e bastam para timeframes ≥ 1m). |
| Loop | ⚠️ | Decide a cada 10 s no candle **em formação** (o último da lista). Sinais mudam a cada tick. | Decidir só em candle fechado; usar ticks só para gerir a posição. |
| Chave testnet | ❌ | Expirada (`retCode 33004`). | Gerar nova chave em testnet.bybit.com (Unified Trading, permissões de contrato) e atualizar `BYBIT_API_KEY_TESTNET`/`BYBIT_SECRET_KEY_TESTNET`. |

---

## 6. Serviços e pontos institucionais (`services/`)

| Item | Status | Problema | 🔧 Solução |
|---|---|---|---|
| `atualizar_pontos_testados_ou_rompidos` | ❌ | Tolerância de "testado" = **US$ 0,01** absoluto (nunca testa). A regra de rompimento usa prefixos `ORDER_BLOCK_BULLISH`/`HVN`/`SUPORTE` que não existem no banco (os tipos são `OB_BULLISH_4h`, `TPO_HVN_1d`...), e a lógica está invertida (um bloco de alta é suporte: rompe quando o preço cai **abaixo**, não acima). | Tolerância percentual (0,1-0,2%); classificar cada tipo como suporte/resistência/neutro; suporte rompe com fechamento abaixo, resistência com fechamento acima. |
| `registrar_ponto` | ⚠️ | Deduplica por igualdade exata de preço; com o detector de OB atual gera centenas de pontos iguais. | Deduplicar por tolerância percentual e por tipo; limitar quantidade por tipo/timeframe. |
| `OrderBlockInstitutionalService` | ❌ | Métodos sem `self`/`@staticmethod` (crash ao chamar); `ccxt.coinbase()` instanciado em cada ciclo. Símbolo `BTCUSDT` não existe na Coinbase. | `@staticmethod` nos métodos de banco; instância única; mapear símbolo por exchange. |
| `TelegramAlertService` | ⚠️ | `TELEGRAM_CHAT_ID` no `.env` é o texto literal `'TELEGRAM_CHAT_ID'`; cada alerta falha (capturado, mas polui o log). O envio é `async` mas `db/testar_telegram.py` chama sem `await`. | Preencher o chat id real; desligar alertas quando não configurado. |
| `BotManager` | ❌ | `bot_control_controller` chama `BotManager.start_bot(nome)` como método estático; a classe precisa de instância. Uma única sessão SQLAlchemy é compartilhada entre threads (não é thread-safe). | Instância global criada no startup; uma sessão por bot. |
| `IndicadorLoader` | ❌ | Importa `TPOCalculator` e `OrderFlowAnalyzer`, que não existem. Nunca é usado. | Remover ou alinhar nomes. |

---

## 7. API, modelos e infraestrutura

| Item | Status | Problema | 🔧 Solução |
|---|---|---|---|
| `bot_controller.py` | ❌ | Router com `prefix="/bots"` e `main.py` inclui com `prefix="/bots"` → rotas em `/bots/bots/...`. | Prefixo em um lugar só. |
| `elliott_routes.py` | ❌ | Usa `service.model_candidata`, `service.salvar_contagem_validada` etc., que não existem em `ElliottPersistenceService` → 500 em todas as rotas. | Referenciar os modelos diretamente. |
| `order_blocks_routes.py` | ❌ | `from orderblocks_institucionais import ...` (caminho errado; deveria ser `models.orderblocks_institucionais`). Não está incluído em `main.py`. | Corrigir import e incluir. |
| `LogExecucaoBot` | ❌ | `resultado = Column(String)` no modelo, `float` no banco. | `Float`. |
| `Bot` | ⚠️ | Faltam no modelo `trailing_manual`, `ativador_trailing`, `distancia_trailing` (existem no banco). `exchange` dos bots cadastrados é `bybit-testnet` (o código espera `bybit`). | Adicionar colunas; normalizar `exchange='bybit'` e usar `modo_execucao` para testnet/real. |
| `run_all_bots.py` | ⚠️ | Segunda string de conexão (sem `Encrypt=no`), diferente de `api/database.py`. | Reutilizar `api.database`. |
| `launcher.py` | ❌ | A cada execução insere um indicador "fibonacci" no primeiro bot (efeito colateral). | Remover. |
| `requirements.txt` | ❌ | Salvo em UTF-16 (`pip install -r` falha). Faltam `pyodbc` e `beautifulsoup4`. | Regravar em UTF-8. |
| `.env` | ⚠️ | `DATABASE_URL='DATABASE_URL'` e `TELEGRAM_CHAT_ID='TELEGRAM_CHAT_ID'` são placeholders. | Preencher ou remover. |
| `teste.py` | ❌ | Varredura 1M de 2015 a 2025 com o `ElliottEngine` combinatório (trava). | Usar o engine O(N). |
| `.vscode/launch.json` | ⚠️ | Aponta para `teste.py` como módulo principal. | Apontar para `uvicorn api.main:app`. |

---

## 8. Sentimento de mercado (sua pergunta)

**Faz sentido, e é usado por fundos.** A tese "mercado eufórico = topo próximo, mercado com medo = fundo próximo" é o indicador contrário clássico. Recomendação de fontes, da mais confiável para a menos:

1. **Fear & Greed Index (alternative.me)**: gratuito, sem chave, 1 valor/dia (0 = medo extremo, 100 = ganância extrema). Já combina volatilidade, volume, redes sociais, dominância e Google Trends.
2. **Posicionamento na própria Bybit** (gratuito, tempo real): *funding rate* (funding muito positivo = multidão comprada alavancada = euforia) e *long/short ratio* (`/v5/market/account-ratio`). São os melhores sinais de "todo mundo do mesmo lado".
3. **Open interest** crescendo com preço subindo em onda 5 = euforia; OI caindo em queda = capitulação.
4. **X/Twitter**: a API de busca é paga (tier Basic ≈ US$ 100/mês) e o sinal é ruidoso; vale como opcional, com chave no `.env`, nunca como obrigatório.
5. **Calendário macro** (FOMC, CPI, payroll): já existe o `macro_event_checker`; útil para **não abrir** posição a 30 min de um evento.

**Como encaixar sem quebrar a "lei" de Elliott**: o sentimento não decide, ele **pesa**. Score de -1 (medo extremo) a +1 (ganância extrema). Regras: ganância extrema (≥ +0,6) proíbe **novas compras** no conservador e reduz o tamanho no turbo; medo extremo (≤ -0,6) proíbe novas vendas. Ele também casa com Elliott: euforia costuma coincidir com onda 5 (não entrar) e medo com fim da onda C (buscar compra).

---

## 9. Ordem sugerida de correção

1. Infra: `requirements.txt` em UTF-8, modelos alinhados ao banco, `.env` sem placeholders, nova chave testnet.
2. Conector Bybit linear com três modos e ordem com SL/TP anexados.
3. Indicadores com sinal padronizado (`buy/sell/hold` + força) e cálculos corretos.
4. Analisador de Elliott em memória (ZigZag + regras) que devolve fase, direção, invalidação e alvos.
5. Motor de estratégia: corrigir o bloqueio institucional, a confluência, o TP/SL e o vazamento de sessão.
6. Executor: paper trading real, reconciliação de posição, `reduceOnly`, P&L com quantidade, trailing na exchange, decisão em candle fechado.
7. Serviços de pontos institucionais e order blocks.
8. API: prefixos, rotas quebradas, endpoint de status ao vivo.
9. Backtest sobre os CSVs de 1h da Binance já presentes (`binance_csv/`) para validar os cálculos com números.
10. Módulo de sentimento como filtro.

---

## 10. O que já foi alterado nesta sessão (antes do seu pedido de só analisar)

Reescrevi 11 arquivos e criei 1 em `core/`, seguindo exatamente as soluções da seção 4 e da seção 5 (conector):

`core/conexoes/conexao_bybit.py`, `core/elliott.py`, `core/fase_onda_rules.py`, `core/fibonacci.py`, `core/fibonacci_elliott.py`, `core/fibonacci_strategies.py`, `core/order_block.py`, `core/order_flow.py`, `core/tpo.py`, `core/volume_profile_pro.py`, `core/vwap.py` e o novo `core/utils_indicadores.py`.

Nada em `services/`, `models/`, `api/`, executor ou motor de estratégia foi tocado, e o banco não foi alterado. As versões originais estão no git; para voltar:

```bash
git checkout -- core/ && rm core/utils_indicadores.py
```
