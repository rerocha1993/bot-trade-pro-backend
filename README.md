# Bot Trade Pro (backend)

Robô de trading para contratos perpétuos USDT na **Bybit**, com decisão baseada em **Ondas de Elliott multi-cenário e multi-grau**, validação por indicadores institucionais (TPO, Volume Profile, VWAP, Order Flow, Order Blocks) calculados sobre uma **cesta de exchanges igual ao índice BTCUSD da TradingView** (Bitstamp + Coinbase + Bitfinex + Kraken) mais a Bybit, filtro contrário de **sentimento** (Fear & Greed, funding, long/short, open interest) e gestão de risco por banca.

## Como rodar

```bash
# 1) dependências (Python 3.12/3.13, venv já existente em .venv)
.venv\Scripts\python -m pip install -r requirements.txt

# 2) banco (SQL Server LocalDB dbo_trading_bot): cria tabelas/colunas novas e normaliza os bots
.venv\Scripts\python scripts\setup_db.py

# 3) diagnóstico de conectividade (Bybit público/testnet, cesta multi-exchange, sentimento)
.venv\Scripts\python scripts\testar_bybit.py

# 4) API + bots (um thread por bot ativo)  ->  http://localhost:8000/docs
.venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# alternativas
.venv\Scripts\python scripts\rodar_bot.py 1 --ciclos 3        # um bot no terminal
.venv\Scripts\python run_all_bots.py                           # todos os bots sem a API
.venv\Scripts\python scripts\backtest.py --fonte csv --tf 1h   # backtest nos CSVs da Binance
.venv\Scripts\python scripts\detectar_pontos.py                # pontos institucionais
.venv\Scripts\python -m pytest tests -q                        # testes
```

Variáveis do `.env`: `BYBIT_API_KEY_REAL/BYBIT_SECRET_KEY_REAL`, `BYBIT_API_KEY_TESTNET/BYBIT_SECRET_KEY_TESTNET`, `TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID` (opcional), `X_BEARER_TOKEN` (opcional, sentimento no X), `INICIAR_BOTS=0` (sobe só a API), `MANUTENCAO_INSTITUCIONAL=0` (desliga o detector periódico).

## Modos de execução do bot (`Bots.modo_execucao`)

| Modo | Onde roda | Dinheiro | Chaves | Backtest obrigatório |
|---|---|---|---|---|
| `simulador` | dados públicos da mainnet | nenhum | nenhuma | não |
| `demo` | Demo Trading da conta OFICIAL (`api-demo.bybit.com`) | fictício | `*_DEMO` | não |
| `testnet` | `testnet.bybit.com` | fictício | `*_TESTNET` | sim |
| `real` | mainnet | real | `*_REAL` | sim |

**Use `demo`, não `testnet`.** O testnet é um cadastro separado do site oficial: ele não tem o seu KYC nem o
status da sua conta, e por isso responde `10024 regulatory restrictions` a partir de países restritos. O Demo
Trading vive dentro de `bybit.com`, herda a sua conta e a sua verificação, e usa dinheiro fictício com a
infraestrutura real de ordens.

Como criar a chave de demo:

1. Entre em `bybit.com` com a sua conta oficial.
2. Passe o mouse no ícone de perfil e escolha Demo Trading. Isso abre uma conta de demonstração com id próprio.
3. Ainda no modo Demo Trading, no mesmo menu de perfil, clique em API e crie a chave.
4. Marque leitura e escrita, com permissão de Unified Trading.
5. Coloque em `BYBIT_API_KEY_DEMO` e `BYBIT_SECRET_KEY_DEMO`. Para subcontas, use `BYBIT_SUB_<NOME>_API_KEY_DEMO`.

A chave de demo só funciona no domínio de demo. Se você usá-la contra a mainnet, a Bybit recusa, e vice-versa.
Ordens de demo expiram em 7 dias e nem todos os endpoints existem lá.

## Fluxo de decisão (a cada candle fechado)

1. **Elliott multi-grau** (`core/elliott_pro`): ZigZag por ATR → pivôs → todos os padrões compatíveis (impulso, diagonais, zigzag, flats, triângulos, WXY/WXYXZ, truncada) → **cenários concorrentes** com probabilidade, fase, invalidação e alvos, nos três graus (operacional, contexto, macro) → alinhamento.
2. **Regras da fase x perfil** (`core/fase_onda_rules.py`): quais validadores votam, fonte prioritária de TP/SL, se a fase permite entrar.
3. **Validadores** votam a favor/contra (TPO e Volume Profile sobre velas compostas da cesta TradingView; VWAP, Order Flow e Order Blocks sobre a Bybit).
4. **Filtros**: sentimento contrário (extremos), pontos institucionais contra a direção a < 0,3-0,4%, calendário macro (opcional).
5. **TP/SL**: invalidação/alvos do cenário de Elliott como prioridade, depois Fibonacci direcional, value areas, bandas VWAP e order blocks; fallback de SL por ATR; exige risco:retorno mínimo (1,2 conservador / 1,0 turbo).
6. **Execução** (`core/bot_executor.py`): tamanho = `banca * risco_pct / distância_SL`, limitado por `banca * max_alocacao_pct * alavancagem`; ordem a mercado com SL/TP anexados; trailing enviado à exchange; posição persistida em `PosicoesBot` e reconciliada com a exchange; saída estrutural quando os cenários contrários dominam (≥ 70%); limites diários de trades e perda.

Toda decisão (inclusive `hold`) fica em `DecisoesBot` com cenários, votos, níveis e sentimento, para auditoria e painel.

## Calibração, regime, derivativos e execução

- **Calibração histórica dos cenários** (`core/elliott_pro/calibracao.py`, `scripts/calibrar_elliott.py`): replay do motor em 2011-2026
  (Bitstamp 1h/4h/1d desde dez/2011, Binance 15m/5m desde 2017, baixados por `scripts/baixar_historico.py`). Cada cenário recebe
  `prob_sucesso` = P(1º alvo antes da invalidação) por regressão logística; o modelo fica em `data/calibracao_elliott.json` e o bot
  bloqueia cenários abaixo de `prob_sucesso_minima` e dimensiona a posição por essa probabilidade. Resultado fora da amostra
  (treino até 2023, teste 2024-2026, 107 mil cenários): quintil mais confiável acerta 89%, menos confiável 19%.
- **Filtro de regime** (`core/regime.py`): eficiência de Kaufman + ATR relativo + largura da faixa; bloqueia entradas em compressão
  (exceto rompimento) e em mercado serrilhado. Liga/desliga por bot (`usar_filtro_regime`).
- **Derivativos e calendário** (`core/dados_derivativos.py`): funding médio Bybit/Binance/OKX, open interest multi-exchange,
  liquidações (Coinglass, opcional com `COINGLASS_API_KEY`), calendário macro Forex Factory (gratuito) usado por `usar_api_macro`.
- **Entrada por ordem limitada** (`tipo_entrada = 'limite'`): post-only no recuo sugerido pelo motor (`preco_limite`), taxa maker
  0,02% em vez de 0,055%, cancela após `limite_candles_espera` candles; backtest com o mesmo modelo de execução e `slippage_pct`.
- **WebSocket** (`usar_websocket`): trades e livro da Bybit em tempo real para Order Flow no scalp, poupando chamadas REST.
- **Walk-forward** (`scripts/otimizar.py`): grade de parâmetros otimizada no treino e medida no teste.
- **4 bots de comparação** (`scripts/criar_bots_exemplo.py`): Scalp Fluxo, Day TPO, Swing Estrutura, Elliott Puro.

## Moeda nova: backtest obrigatório antes de operar

`POST /backtest/bots/{id}` (ou `scripts/backtest_bot.py <id>`) baixa o histórico do par na Bybit (cache em `data/historico`),
roda o backtest com a configuração exata do bot e grava em `BacktestsBot` com aprovação automática
(padrão: ≥ 30 trades, fator de lucro ≥ 1,0, drawdown ≤ 25%, retorno > 0). `POST /bot-control/{id}/ativar` recusa bots em
**testnet/real** sem backtest aprovado nos últimos 30 dias (`?forcar=true` ignora); simulador não exige. Para calibrar o
modelo de Elliott na moeda: `scripts/calibrar_elliott.py --par ETHUSDT --tf 1h 4h 1d` (gera `data/calibracao_elliott_ETHUSDT.json`).

## Contagem mestre (desde 2011) e trava de cenário

`GET /api/elliott/mestre?par=BTCUSDT` devolve três graus aninhados: **ciclo** (semanal desde dez/2011, reversões ≥ 40%),
**primário** (diário, ≥ 22%, dentro da onda de ciclo em curso) e **intermediário** (4h, ≥ 12%), cada um com cenários,
pivôs datados, invalidação e alvos. `POST /api/elliott/mestre/travar?grau=ciclo&cenario_id=...` fixa um cenário como trilho:
o viés dele entra no alinhamento de todos os bots do par (conservador não opera contra; turbo opera contra com metade do
tamanho) até o preço cruzar a invalidação, quando a trava é marcada como invalidada e o bot volta ao modo livre.
`POST /api/elliott/mestre/destravar`, `GET /api/elliott/mestre/trava`.

## O trader: superciclo (escala log) + contagens maduras

Camada acima da contagem mestre, `services/trader_service.py` (memória em `data/trader_<PAR>.pkl`, construída em ~4 s desde 2011
e atualizada por candle diário). Lê o superciclo em escala logarítmica (`core/elliott_pro/superciclo.py`: ciclos por topo
histórico + queda >= 60%, retração log da perna anterior, tempo da correção, extensão da perna vs ciclo anterior) e, abaixo dele,
o ciclo semanal mandando no primário diário (`MemoriaHierarquica`). Estados: `impulso_alta`, `zona_onda_2`, `impulso_maduro`,
`correcao_inicial`, `correcao_em_curso`, `fundo_terminal`, `novo_impulso`, `recuo_profundo`.

Teste sem look-ahead (`scripts/evoluir_contagens.py`, `docs/EVOLUCAO_CONTAGENS.md`): direção no fim de cada ano vs 12 meses
seguintes 12/12; fins de trimestre 45/49. Regras e ressalvas em `docs/TRADER_ELLIOTT.md`.

Onde entra: `AnaliseMultiGrau(trader=...)` (nunca vender fundo terminal / retomada, nunca comprar correção recém-iniciada,
metade do tamanho em impulso maduro), `HedgeDial` (hedge 0% em impulso/fundo, permitido em impulso maduro, máximo em correção),
`GET /api/elliott/trader`, `POST /api/elliott/trader/reconstruir`, campo `trader` em `GET /api/elliott/mestre` e em `DecisoesBot`.

## Painel (frontend novo: React + TypeScript + Lightweight Charts)

Pasta `frontend/` (Vite). O backend continua calculando tudo; o painel só desenha e comanda. Inspiração visual em
`docs/design/inspiracao_painel.dc.html` (tokens em `frontend/src/index.css`).

```bash
cd frontend && npm install          # uma vez (Node 22)
npm run dev                         # http://localhost:5173/painel/  (proxy para a API em :8000)
npm run build                       # gera frontend/dist, servido pelo FastAPI em http://localhost:8000/painel/
```

Telas: Dashboard (KPIs, robôs, alertas), Robô (gráfico por grau com ZigZag e ondas, TPO/Volume Profile lateral, order blocks,
VWAP e bandas, POC/VAH/VAL, entradas e saídas; cenários; alinhamento; decisão; alvo e proteção; decisões recentes),
Mesa do trader (superciclo, contagens maduras, contagem mestre com trava, dial de hedge), Mercado, Pontos institucionais,
Sentimento, Histórico (posições, curva de capital, backtests) e formulário do robô. Gráfico: `frontend/src/components/chart/PriceChart.tsx`
(primitiva própria para perfil lateral, retângulos e rótulos). `.claude/launch.json` sobe `api` e `painel`.

## Orquestrador: indicadores independentes e plano de mercado

Camada 1, `core/leituras.py`: cada indicador continua um módulo puro e ganha um adaptador que devolve a mesma
estrutura `Leitura(fonte, vies, forca, acao, niveis, motivo, dados)`. Nenhum adaptador levanta exceção; em erro
devolve leitura neutra com o motivo.

Camada 2, `core/orquestrador/plano.py` e `services/plano_service.py`: um PLANO POR PAR, que todos os bots do par leem.
Junta o superciclo, as contagens maduras, as leituras independentes, a confluência de níveis e a exaustão.

```bash
curl "http://localhost:8000/api/elliott/plano?par=BTCUSDT"
```

Campos que comandam os bots: `modo`, `direcao_grau_maior`, `risco_permitido`, `teto_hedge`, `pode_comprar`,
`pode_vender`, `barreira`, `suporte`, `zonas_compra`, `zonas_venda`. O plano vigente fica em `data/plano_<PAR>.json`.

| Estado do superciclo | Modo | Efeito em todos os bots do par |
|---|---|---|
| fundo_terminal, novo_impulso, zona_onda_2 | acumular | ninguém vende, nem no turbo; hedge zero |
| impulso_alta | deixar_andar | segura comprado, não persegue topo; hedge zero |
| impulso_maduro | nao_perseguir ou reduzir | compra só recuo com metade do tamanho; vira reduzir quando as contagens viram COM exaustão |
| correcao_inicial, correcao_em_curso | hedge | venda e hedge liberados até o teto; ninguém compra |
| recuo_profundo | aguardar | nenhuma posição nova |

## Alavancagem e liquidação

Opções no cadastro do robô: 1x, 2x, 3x, 5x, 10x, 20x, 30x, 50x e 100x (`GET /bots/opcoes/alavancagem`).

A alavancagem **não** aumenta o tamanho da posição: o tamanho continua vindo do risco por trade dividido pela
distância do stop. O que ela muda é quanto o preço pode andar contra antes da liquidação (`core/alavancagem.py`):

| Alavancagem | Liquida em | Stop máximo aceito |
|---|---|---|
| 10x | 9,50% | 7,60% |
| 20x | 4,50% | 3,60% |
| 30x | 2,83% | 2,27% |
| 50x | 1,50% | 1,20% |
| 100x | 0,50% | 0,40% |

Margem isolada, margem de manutenção de 0,5% e folga de 20% para taxas e slippage. Em margem cruzada a banca
inteira sustenta a posição, então a distância real é maior; os números acima são o pior caso.

**Trava de liquidação:** antes de abrir, o executor compara a distância do stop com a distância até a liquidação.
Se o stop ficar além, a entrada é recusada e o log diz qual seria a alavancagem máxima segura para aquele stop.
Sem isso, um stop de 1,5% com 50x seria liquidado exatamente no stop, e a perda deixaria de ser o risco por trade
para virar a margem inteira.

## Subcontas: um robô, uma conta

Na Bybit cada símbolo tem UMA posição por conta. Dois robôs no mesmo par dentro da mesma conta se atrapalham: em
one-way uma ordem fecha a outra, e em hedge as duas viram uma posição só, com um stop só. Por isso cada robô opera
na sua própria subconta.

O campo `subconta` do robô escolhe as chaves no `.env`:

```
BYBIT_SUB_<NOME>_API_KEY_TESTNET     BYBIT_SUB_<NOME>_SECRET_KEY_TESTNET
BYBIT_SUB_<NOME>_API_KEY_REAL        BYBIT_SUB_<NOME>_SECRET_KEY_REAL
```

`<NOME>` é o campo `subconta` em maiúsculas com qualquer caractere fora de A-Z0-9 virando `_`. A subconta
`principal` (ou vazia) usa `BYBIT_API_KEY_TESTNET` / `BYBIT_SECRET_KEY_TESTNET`.

Se o robô tem subconta configurada e a chave não existe, o conector **falha**. Ele não usa a conta principal no
lugar: operar na conta errada é pior que não operar.

### Como criar (a ordem importa)

Criar várias chaves na conta principal **não** cria subcontas. Todas apontam para a mesma conta e para a mesma
posição, que é exatamente o problema que a subconta resolve. A subconta vem primeiro, a chave depois.

1. Em `bybit.com`, vá em Subcontas e crie uma subconta padrão por robô (`scalp`, `daytrade`, `swing`, `hedge`).
2. Na mesma tela, na linha da subconta, abra API Management e crie a chave ali. Não é preciso entrar na subconta.
3. Para o modo `demo`, entre na subconta, ligue o Demo Trading dela e crie a chave lá dentro: cada subconta tem a
   própria conta de demonstração, com UID próprio.
4. Transfira saldo para a subconta. Subconta sem saldo conecta mas não opera.

```bash
curl "http://localhost:8000/status/subcontas?modo=demo&verificar_uid=true"
```

A rota mostra qual robô usa qual subconta e se a chave está no ambiente. Com `verificar_uid=true` ela pergunta à
Bybit de quem é cada chave e usa o UID real para apontar conflitos. Dois robôs no mesmo par com o mesmo UID
fecham a posição um do outro: é o teste que prova que a separação está de pé.

## Endpoints principais

- `GET /status/` estado dos bots e serviços; `GET /status/bots/{id}`, `/decisoes`, `/posicoes` (com resumo de P&L)
- `GET /status/elliott?par=&timeframe=&estilo=&perfil=` cenários multi-grau; `GET /api/elliott/cenarios` um grau
- `GET /status/sentimento`, `GET /status/mercado/niveis` (TPO/VP/VWAP/OB para o gráfico), `GET /status/mercado/candles?composto=1`
- `GET /status/bybit?modo=testnet` diagnóstico de chaves
- `POST /bot-control/{id}/ativar|desativar`, `GET /bot-control/`, `GET /bots/`, `POST /bots/`, `PUT /bots/{id}`
- `GET /pontos-institucionais?par=&status=ativo&preco_atual=&faixa_pct=`, `GET /orderblocks/`, `POST /orderblocks/atualizar`
- `GET /logs/{id}/grafico-dados?timeframe=15m` candles + entradas/saídas

## Estrutura

```
core/conexoes/conexao_bybit.py   conector Bybit v5 (linear) com 3 modos, SL/TP anexados, precisão
core/market_data.py              cesta multi-exchange (TradingView + Bybit), velas compostas, livro alinhado
core/elliott_pro/                pivots, patterns, scenarios, multidegree (motor de Elliott)
core/strategy_engine.py          orquestra Elliott + validadores + filtros + TP/SL
core/bot_executor.py             loop do bot, posição, risco, trailing, persistência
core/executor_real.py            executor de ordens (simulador/testnet/real)
core/sentimento_mercado.py       filtro contrário de sentimento
core/tpo.py, volume_profile_pro.py, vwap.py, order_flow.py, order_block.py, fibonacci*.py
core/backtest_engine.py          backtest com a mesma lógica do bot
services/                        bot_manager (threads), pontos institucionais, order blocks, elliott, telegram
api/                             FastAPI (rotas em api/routes)
scripts/                         setup_db, testar_bybit, rodar_bot, backtest, detectar_pontos
tests/                           pytest (indicadores, padrões de Elliott, cenários, motor, executor, backtest)
docs/DIAGNOSTICO_ANALISE.md      diagnóstico do código original (o que estava errado e por quê)
```
