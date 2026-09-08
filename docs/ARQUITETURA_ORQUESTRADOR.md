# Proposta: indicadores independentes, bot orquestrado, orquestrador como trader humano

Direção dada pelo usuário em 2026-09-06: *"deixar os indicadores independentes; o robô, quando criado, se torna o
orquestrado; o orquestrador se transforma em um trader humano"*. Este documento diz como isso se encaixa no código atual,
o que já existe, o que falta e as decisões que foram tomadas.

## As três camadas

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 1. INDICADORES INDEPENDENTES (módulos puros, sem saber uns dos outros)        │
│    Elliott multi-grau + memória · TPO · Volume Profile · VWAP · Order Flow    │
│    Order Blocks · Fibonacci · Regime · Sentimento (F&G, funding, L/S, OI)    │
│    Derivativos · Calendário macro                                             │
│    Entrada: candles/book/trades. Saída padronizada: Leitura                   │
│    {fonte, vies, forca 0..1, niveis[{preco, tipo, peso}], validade, motivo}   │
├──────────────────────────────────────────────────────────────────────────────┤
│ 2. O TRADER (um por par; orquestrador)                                        │
│    Lê na ordem de um humano: superciclo (log) -> ciclo -> primário ->          │
│    contexto do estilo -> leituras independentes -> confluência de níveis.     │
│    Emite o PLANO DE MERCADO do par:                                           │
│    {estado, direcao_grau_maior, zonas_compra[], zonas_venda[], invalidacao,   │
│     barreira, suporte, risco_permitido, modo: acumular|deixar_andar|hedge|   │
│     reduzir|aguardar, motivo}                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ 3. BOTS ORQUESTRADOS (instâncias táticas)                                     │
│    Cada bot = estilo (scalp/day/swing/hedge inverso) + timeframe + risco +    │
│    indicadores que ele usa para VALIDAR e TEMPORIZAR a entrada.               │
│    O bot não decide direção de grau maior: executa dentro do plano            │
│    (escalonado, ordens limitadas, trailing, saída estrutural).                │
└──────────────────────────────────────────────────────────────────────────────┘
```

## O que já existe (e onde está)

| Camada | Já existe | Onde | Falta |
|---|---|---|---|
| 1 | Todos os indicadores são classes puras | `core/tpo.py`, `core/volume_profile_pro.py`, `core/vwap.py`, `core/order_flow.py`, `core/order_block.py`, `core/fibonacci*.py`, `core/regime.py`, `core/sentimento_mercado.py`, `core/dados_derivativos.py`, `core/elliott_pro/` | Saída padronizada `Leitura` (hoje cada um devolve um dict próprio); tirar os acessos a banco dos serviços `services/*_service.py` |
| 2 | Superciclo + ciclo mandando no primário + leitura persistida | `core/elliott_pro/superciclo.py`, `core/elliott_pro/memoria.py`, `services/trader_service.py` | Plano de mercado completo (zonas, barreiras por confluência de TODAS as leituras, modo). Hoje `core/hedge_dial.barreiras()` faz a confluência só para o hedge e `core/strategy_engine.py` mistura decisão de grau maior com validação tática |
| 3 | Executores por estilo | `core/bot_executor.py` (linear), `core/inverse_executor.py` (grade), `HedgeDial` | Receber o plano em vez de recalcular tudo; `StrategyEngine` vira "tática" (timing, TP/SL, tamanho) |

## Decisões tomadas (2026-09-07)

As três perguntas em aberto foram decididas pelo usuário, com a recomendação aceita em todas:

1. **Um plano por par, com direção por grau.** Existe um único trader por par. Ele publica a leitura de cada grau e o
   estado do superciclo. Cada estilo obedece ao grau dele mais o VETO do superciclo. Não existe um trader por bot:
   o ciclo do BTC é um só.
2. **Turbo pode operar contra o grau menor com metade do tamanho, nunca contra o superciclo.** Em `fundo_terminal`,
   `novo_impulso` e `zona_onda_2` ninguém vende. Em `correcao_inicial` ninguém compra. Nem o turbo.
3. **O hedge inverso vira bot orquestrado** pelo mesmo plano: o modo do plano liga ou desliga o dial, e a barreira e o
   suporte vêm prontos. A execução em fatias escalonadas do dial não muda.

**Subcontas (decidido junto).** Na Bybit cada símbolo tem uma posição por conta. Scalp, daytrade e swing no mesmo par
dentro da mesma conta se atrapalham: em one-way uma ordem fecha a outra, e em hedge duas compras viram uma posição só
com um stop só. Então cada robô precisa da sua subconta, com chave própria e saldo próprio. O campo `Bots.subconta` já
existe, mas hoje é só rótulo: o conector lê um par de chaves global. Ligar isso é a fase 3.

## Refatoramento proposto (4 fases, cada uma entregável e testável)

1. **`Leitura` padronizada** — FEITO. `core/leituras.py`: uma dataclass `Leitura(fonte, vies, forca, acao, niveis, ...)`
   e um adaptador por indicador (TPO, Volume Profile, VWAP, Order Flow, Order Block, Fibonacci, regime, sentimento,
   Elliott). O cálculo de cada indicador não mudou. Nenhum adaptador levanta exceção: em erro devolve leitura neutra
   com o motivo, porque o orquestrador não pode quebrar por causa de um indicador. Testes em `tests/test_leituras.py`.
2. **Plano de mercado** — FEITO. `core/orquestrador/plano.py` (função pura) + `services/plano_service.py` (busca os
   dados, cache de 5 min, grava `data/plano_<PAR>.json`) + `GET /api/elliott/plano`. O plano junta superciclo,
   contagens maduras, as leituras independentes, a confluência de níveis (barreira, suporte, zonas de compra e venda)
   e a exaustão. Saída: `modo`, `direcao_grau_maior`, `risco_permitido`, `teto_hedge`, `pode_comprar`, `pode_vender`.
   Modos: `acumular`, `deixar_andar`, `nao_perseguir`, `reduzir`, `hedge`, `aguardar`. Testes em `tests/test_plano.py`.
3. **Bots orquestrados** — FEITO no código. `StrategyEngine` lê o plano (`servicos['plano']`, um por par, cache de
   5 min) e obedece: compra bloqueada quando `pode_comprar` é falso, venda bloqueada quando `pode_vender` é falso, e
   o tamanho fica limitado por `risco_permitido`. O limite do grau maior é o MENOR entre o fator do alinhamento e o
   risco do plano, nunca o produto: os dois vêm da mesma leitura de superciclo e multiplicar contaria duas vezes.
   Se o plano estiver indisponível o bot continua operando pela análise própria, em vez de travar.
   **Subcontas**: `BybitConnector(subconta=...)` lê `BYBIT_SUB_<NOME>_API_KEY_<MODO>`; em testnet/real cada robô cria
   o próprio conector, e uma subconta sem chave FALHA em vez de cair para a conta principal. Diagnóstico em
   `GET /status/subcontas`, que também aponta robôs disputando o mesmo par na mesma conta.
   Falta exercitar contra chaves reais, e ligar `InverseRangeExecutor`/`HedgeDial` no mesmo plano.
4. **Painel "Mesa do trader"** — FEITO. O plano do par é o primeiro cartão da tela: modo, direção do grau maior,
   risco permitido, teto de hedge, compra e venda liberadas ou bloqueadas, e as zonas de compra e de venda com as
   fontes de cada confluência.

## O que falta (estado em 2026-09-07)

| Fase | Estado |
|---|---|
| 1. Leitura padronizada | pronta, com testes |
| 2. Plano de mercado | pronto, com testes e rota |
| 3. Bots orquestrados + subcontas | código pronto e testado; subcontas aguardam chaves reais para validação |
| 4. Tela "Mesa do trader" mostrando o plano | pronta |

Bloqueios fora do código: a chave de testnet da Bybit expirou (código 33004) e a chave real está inválida (código
10003). Só o modo simulador opera hoje.
