# services/bot_manager.py
"""
Orquestrador: um thread por bot, cada um com a sua sessão de banco; serviços compartilhados
(agregador de mercado, sentimento, telegram, conectores públicos) com cache e lock.
Também roda a manutenção institucional periódica (detecção de pontos em vários timeframes).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

from api.database import SessionLocal
from core.bot_executor import BotExecutor
from models.bot import Bot

logger = logging.getLogger(__name__)


class BotManager:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.executores: Dict[int, BotExecutor] = {}
        self.threads: Dict[int, threading.Thread] = {}
        self._lock = threading.Lock()
        self._manutencao_thread: Optional[threading.Thread] = None
        self._parar_manutencao = threading.Event()
        self.servicos = self._montar_servicos()
        from services.backtest_service import BacktestService
        self.backtests = BacktestService(session_factory, self.servicos["connectors"]["simulador"])

    def _montar_servicos(self) -> Dict:
        from core.market_data import MarketDataAggregator
        from core.sentimento_mercado import SentimentoMercado
        from core.conexoes.conexao_bybit import BybitConnector
        from services.telegram_alert_service import TelegramAlertService
        from services.orderblock_institutional_service import OrderBlockInstitutionalService
        from services.plano_service import PlanoService
        from services.trader_service import TraderService
        publico = BybitConnector("simulador")
        md = MarketDataAggregator("tradingview", clientes={"bybit": publico.exchange})
        servicos = {"market_data": md, "sentimento": SentimentoMercado(publico), "telegram": TelegramAlertService(),
                "orderblocks": OrderBlockInstitutionalService(md), "connectors": {"simulador": publico},
                "trader": TraderService(publico)}
        servicos["plano"] = PlanoService(servicos, connector=publico)
        return servicos

    # ------------------------------------------------------------ bots
    def listar_ativos(self):
        db = self.session_factory()
        try:
            return db.query(Bot).filter(Bot.ativo_bot == True).all()  # noqa: E712
        finally:
            db.close()

    def start_all(self) -> int:
        n = 0
        for bot in self.listar_ativos():
            if self.start_bot(bot.id):
                n += 1
        return n

    def start_bot(self, bot_id: int, forcar: bool = False) -> bool:
        with self._lock:
            th = self.threads.get(bot_id)
            if th and th.is_alive():
                logger.info("bot %s já está rodando", bot_id)
                return False
            db = self.session_factory()
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                db.close()
                logger.warning("bot %s não encontrado", bot_id)
                return False
            # trava: testnet/real exigem backtest aprovado recente (simulador não)
            from services.backtest_service import BacktestService
            ok, motivo = BacktestService.pode_ativar(db, bot)
            if not ok and not forcar:
                logger.warning("bot %s não ativado: %s", bot_id, motivo)
                self.ultimo_bloqueio = {bot_id: motivo}
                db.close()
                return False
            bot.ativo_bot = True
            db.commit()
            executor = BotExecutor(bot, db, servicos=self.servicos)
            thread = threading.Thread(target=self._rodar, args=(executor, db), name=f"bot-{bot_id}", daemon=True)
            self.executores[bot_id] = executor
            self.threads[bot_id] = thread
            thread.start()
            logger.info("bot %s (%s) iniciado", bot_id, bot.nome)
            return True

    @staticmethod
    def _rodar(executor: BotExecutor, db):
        try:
            executor.executar()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def stop_bot(self, bot_id: int, persistir: bool = True) -> bool:
        ex = self.executores.get(bot_id)
        if not ex:
            return False
        ex.parar()
        if persistir:
            db = self.session_factory()
            try:
                bot = db.query(Bot).filter(Bot.id == bot_id).first()
                if bot:
                    bot.ativo_bot = False
                    db.commit()
            finally:
                db.close()
        return True

    def stop_all(self):
        for bot_id in list(self.executores):
            self.stop_bot(bot_id, persistir=False)
        self._parar_manutencao.set()

    def status(self) -> Dict:
        return {bid: {**ex.status(), "thread_viva": self.threads[bid].is_alive()} for bid, ex in self.executores.items()}

    def status_bot(self, bot_id: int) -> Optional[Dict]:
        ex = self.executores.get(bot_id)
        return None if not ex else {**ex.status(), "thread_viva": self.threads[bot_id].is_alive()}

    # ------------------------------------------------------- manutenção
    def iniciar_manutencao(self, intervalo_min: int = 30):
        if self._manutencao_thread and self._manutencao_thread.is_alive():
            return
        self._parar_manutencao.clear()
        self._manutencao_thread = threading.Thread(target=self._loop_manutencao, args=(intervalo_min,), name="manutencao", daemon=True)
        self._manutencao_thread.start()

    def _loop_manutencao(self, intervalo_min: int):
        from core.detector_institucional import run_detector
        while not self._parar_manutencao.is_set():
            try:
                run_detector(market_data=self.servicos["market_data"])
            except Exception as e:
                logger.error("manutenção institucional falhou: %s", e)
            self._parar_manutencao.wait(intervalo_min * 60)


_manager: Optional[BotManager] = None


def get_manager() -> BotManager:
    global _manager
    if _manager is None:
        _manager = BotManager()
    return _manager
