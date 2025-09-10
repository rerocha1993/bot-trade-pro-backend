# services/bot_executor.py

import logging
import time
import asyncio
import html
from datetime import datetime
from core.strategy_engine import StrategyEngine
from core.executor_real import ExecutorReal
from core.conexoes.conexao_bybit import BybitConnector
from services.telegram_alert_service import TelegramAlertService
from models.log_execucao import LogExecucaoBot
from sqlalchemy import DECIMAL
from core.datasource_ws_universal import DataSourceWebsocketUniversal
from core.order_flow import OrderFlowAnalyzerPro
from services.ponto_institucional_service import PontoInstitucionalService
from types import SimpleNamespace

class BotExecutor:
    def __init__(self, bot, db):
        # Se for dict, converte para objeto
        if isinstance(bot, dict):
            bot = SimpleNamespace(**bot)
        self.bot = bot
        self.db = db
        self.bot.ativo_bot = True
        self.alertas = TelegramAlertService()
        self.con = BybitConnector(modo_execucao=bot.modo_execucao)
        self.executor = ExecutorReal(par=bot.ativo, modo_execucao=bot.modo_execucao)
        self.delay_execucao = getattr(bot, "delay_execucao", 10)
        self.ultimo_exec = 0.0
        self.posicoes_abertas = []
        self.ultimo_candle_timestamp = None
        self.posicao_aberta = None
        
          # Exemplo de lógica para escolher o URL:
        if self.bot.exchange == "bybit":
            if bot.modo_execucao == "real":
                ws_url = "wss://stream.bybit.com/v5/public/linear"
            else :
                ws_url = "wss://stream-testnet.bybit.com/v5/public/linear"
            
        elif self.bot.exchange == "bybit-testnet":
            ws_url = "wss://stream-testnet.bybit.com/v5/public/linear"
        else:
            ws_url = "..."

        self.data_ws = DataSourceWebsocketUniversal(
            exchange=bot.exchange,
            symbol_spot=bot.ativo,
            websocket_url=ws_url
        )


    async def _enviar_alerta(self, metodo, *args):
        safe_args = [html.escape(str(a)) for a in args]
        await metodo(*safe_args)

    def calcular_tamanho_ordem(self, preco_entrada, sl):
        # Sempre converta explicitamente!
        banca = float(str(self.bot.banca))  # garante Decimal mesmo se vier como string ou float
        risco_pct = float(self.bot.risco_pct)
        risco_por_trade = float(banca) * risco_pct  # Pode manter em float se preferir, ou Decimal
        # ... restante do cálculo

        # Proteção para evitar operação com None
        if preco_entrada is None or sl is None:
            logging.error(f"Preço de entrada ou SL inválido: preco_entrada={preco_entrada}, sl={sl}")
            return 0

        distancia_ate_sl = abs(preco_entrada - sl)
        if distancia_ate_sl == 0:
            return 0

        tamanho = risco_por_trade / distancia_ate_sl
        min_lote = getattr(self.bot, "min_lote", 0.001)
        tamanho = max(round(tamanho, 6), min_lote)
        return tamanho


    def exposicao_total(self):
        return sum(pos['quantidade'] * pos['preco'] for pos in self.posicoes_abertas)
    
    def aplicar_trailing_stop(self, preco_atual):
        if not self.posicao_aberta:
            return
        trailing_ativo = self.posicao_aberta.get("trailing_ativo", False)
        preco_entrada = self.posicao_aberta["preco"]
        sl_atual = self.posicao_aberta["sl"]
        acao = self.posicao_aberta["tipo"]
        ativador_trailing = getattr(self.bot, "ativador_trailing", 0.005)  # 0.5%
        distancia_trailing = getattr(self.bot, "distancia_trailing", 0.003)  # 0.3%

        # Ativação automática
        if not trailing_ativo:
            if acao == "buy" and preco_atual >= preco_entrada * (1 + ativador_trailing):
                self.posicao_aberta["trailing_ativo"] = True
            elif acao == "sell" and preco_atual <= preco_entrada * (1 - ativador_trailing):
                self.posicao_aberta["trailing_ativo"] = True

        # Ajuste dinâmico do SL enquanto ativo
        if self.posicao_aberta["trailing_ativo"]:
            if acao == "buy":
                novo_sl = max(sl_atual, preco_atual * (1 - distancia_trailing))
                if novo_sl > sl_atual:
                    self.posicao_aberta["sl"] = novo_sl
            elif acao == "sell":
                novo_sl = min(sl_atual, preco_atual * (1 + distancia_trailing))
                if novo_sl < sl_atual:
                    self.posicao_aberta["sl"] = novo_sl

    def executar(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. Inicialize o datasource WS universal com o ativo/config do bot
        self.data_ws = DataSourceWebsocketUniversal(
            exchange=self.bot.exchange,           # 'bybit' ou 'coinbase', do seu bot/config
            symbol_spot=self.bot.ativo            # Ex: 'BTC/USDT', dinâmico!
        )
        self.data_ws.start()
        print(f"[Executor] WebSocket iniciado para {self.bot.exchange} - {self.bot.ativo}")

        while self.bot.ativo_bot:
            try:
                agora = time.time()
                if agora - self.ultimo_exec < self.delay_execucao:
                    time.sleep(1)
                    continue

                # 2. Dados ao vivo do market
                trades = self.data_ws.get_trades()
                order_book = self.data_ws.get_order_book()
                
                # Continua usando ohlcv do seu conector (API ou csv/backtest)
                ohlcv = self.con.obter_ohlcv(self.bot.ativo.replace("/", ""), self.bot.timeframe, 200)
                preco_atual = ohlcv[-1][4]
                candle_timestamp = ohlcv[-1][0]

                PontoInstitucionalService.atualizar_pontos_testados_ou_rompidos(
                    self.db,
                    preco_atual,
                    self.bot.ativo,
                    self.bot.exchange
                )
                            # 3. Trailing Stop
                if self.posicao_aberta:
                    self.aplicar_trailing_stop(preco_atual)
                    if getattr(self.bot, "trailing_manual", False):
                        self.posicao_aberta["trailing_ativo"] = True
                        self.aplicar_trailing_stop(preco_atual)

                # 4. Encerramento de posição por SL/TP
                if self.posicao_aberta:
                    tipo = self.posicao_aberta["tipo"]
                    sl = self.posicao_aberta["sl"]
                    tp = self.posicao_aberta["tp"]
                    preco_entrada = self.posicao_aberta["preco"]

                    if sl is not None and tp is not None:
                        # Condição de saída por SL/TP atingido
                        if (
                            (tipo == "buy" and (preco_atual <= sl or preco_atual >= tp)) or
                            (tipo == "sell" and (preco_atual >= sl or preco_atual <= tp))
                        ):
                            acao_saida = "sell" if tipo == "buy" else "buy"

                            self.executor.executar_ordem(
                                direcao=acao_saida,
                                quantidade=self.bot.quantidade,
                                preco_entrada=preco_atual,
                                stop_loss=sl,
                                take_profit=tp
                            )

                            loop.run_until_complete(
                                self._enviar_alerta(self.alertas.alerta_ordem,
                                    self.bot.nome, self.bot.ativo, acao_saida, preco_atual
                                )
                            )

                            # Cálculo correto do resultado conforme a direção da operação
                            if acao_saida == "buy":
                                resultado = round(preco_atual - preco_entrada, 8)
                            elif acao_saida == "sell":
                                resultado = round(preco_entrada - preco_atual, 8)
                            else:
                                resultado = None

                            log = LogExecucaoBot(
                                bot_id=self.bot.id,
                                tipo_operacao="saida",
                                direcao=acao_saida,
                                preco_entrada=preco_entrada,
                                preco_saida=preco_atual,
                                resultado=resultado,
                                motivo="SL/TP atingido",
                                data_execucao=datetime.utcnow()
                            )
                            self.db.add(log)
                            self.db.commit()
                            self.posicao_aberta = None
                            self.ultimo_exec = agora
                            continue

                # 5. Decisão para abrir nova posição (pluga todos indicadores nos dados ao vivo)
                # Passe trades e order_book para os indicadores avançados:
                
                engine = StrategyEngine(
                        ohlcv, 
                        self.bot, 
                        db=self.db,
                        trades=trades,              # self.data_ws.get_trades()
                        order_book=order_book       # self.data_ws.get_order_book()
                    )
                decisao = engine.decidir()
                acao = decisao["acao"]
                motivo = decisao.get("motivo", "")

                if not self.posicao_aberta and acao in ("buy", "sell"):
                    sl = decisao.get("sl")
                    tp = decisao.get("tp")
                    preco_entrada = preco_atual
                    tamanho = self.calcular_tamanho_ordem(preco_entrada, sl)

                    self.executor.executar_ordem(
                        direcao=acao,
                        quantidade=tamanho,
                        preco_entrada=preco_entrada,
                        stop_loss=sl,
                        take_profit=tp
                    )
                    loop.run_until_complete(
                        self._enviar_alerta(self.alertas.alerta_ordem,
                                        self.bot.nome, self.bot.ativo, acao, preco_entrada)
                    )
                    log = LogExecucaoBot(
                        bot_id=self.bot.id,
                        tipo_operacao="entrada",
                        direcao=acao,
                        preco_entrada=preco_entrada,
                        sl=sl,
                        tp=tp,
                        motivo=motivo,
                        data_execucao=datetime.utcnow()
                    )
                    self.db.add(log)
                    self.db.commit()
                    self.posicao_aberta = {
                        "tipo": acao,
                        "preco": preco_entrada,
                        "sl": sl,
                        "tp": tp,
                        "trailing_ativo": getattr(self.bot, "trailing_manual", False)
                    }
                    self.ultimo_exec = agora

                else:
                    logging.info(f"[{self.bot.nome}] Sem mudança: aguarda posição fechar")

                self.ultimo_exec = agora

            except Exception as e:
                logging.error(f"Erro no bot {self.bot.nome}: {e}")
                try:
                    loop.run_until_complete(
                        self._enviar_alerta(self.alertas.alerta_erro, self.bot.nome, e)
                    )
                except Exception as inner:
                    logging.error(f"Falha ao enviar alerta de erro: {inner}")
                time.sleep(5)

        self.data_ws.stop()
        loop.close()

    def parar(self):
        self.bot.ativo_bot = False
