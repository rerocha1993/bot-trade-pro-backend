# services/telegram_alert_service.py
import asyncio
import html
import logging
import os
import threading

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class TelegramAlertService:
    """
    Alertas via Telegram. Se token/chat id não estiverem configurados, o serviço fica desativado
    silenciosamente (nada quebra). Métodos síncronos podem ser chamados de qualquer thread.
    """

    def __init__(self, token: str = None, chat_id: str = None):
        # strip: um .env salvo no Windows deixa um \r no fim de cada valor
        self.token = (token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat_id = (chat_id or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        self.ativo = bool(self.token and ":" in str(self.token) and self.chat_id and self.chat_id != "TELEGRAM_CHAT_ID")
        self._lock = threading.Lock()
        self.bot = None
        if self.ativo:
            try:
                from telegram import Bot
                self.bot = Bot(token=self.token)
            except Exception as e:
                logger.warning("Telegram desativado: %s", e)
                self.ativo = False

    async def enviar_alerta(self, mensagem: str):
        if not self.ativo:
            return False
        try:
            from telegram.constants import ParseMode
            await self.bot.send_message(chat_id=self.chat_id, text=mensagem, parse_mode=ParseMode.HTML)
            return True
        except Exception as e:
            logger.error("Erro ao enviar alerta Telegram: %s", e)
            return False

    def enviar(self, mensagem: str) -> bool:
        """Versão síncrona (thread-safe)."""
        if not self.ativo:
            return False
        with self._lock:
            try:
                return asyncio.run(self.enviar_alerta(mensagem))
            except Exception as e:
                logger.error("Erro Telegram: %s", e)
                return False

    async def alerta_ordem(self, bot_nome, par, acao, preco, extra: str = ""):
        msg = (f"🚨 <b>Ordem executada</b>\nBot: {html.escape(str(bot_nome))}\nPar: {html.escape(str(par))}\n"
               f"Ação: {html.escape(str(acao).upper())}\nPreço: {float(preco):.2f}")
        if extra:
            msg += f"\n{html.escape(extra)}"
        await self.enviar_alerta(msg)

    async def alerta_erro(self, bot_nome, erro):
        await self.enviar_alerta(f"❗ <b>Erro detectado</b>\nBot: {html.escape(str(bot_nome))}\nErro: {html.escape(str(erro))[:500]}")

    def ordem(self, bot_nome, par, acao, preco, extra: str = "") -> bool:
        return self.enviar(f"🚨 <b>Ordem executada</b>\nBot: {html.escape(str(bot_nome))}\nPar: {html.escape(str(par))}\n"
                           f"Ação: {html.escape(str(acao).upper())}\nPreço: {float(preco):.2f}" + (f"\n{html.escape(extra)}" if extra else ""))

    def erro(self, bot_nome, erro) -> bool:
        return self.enviar(f"❗ <b>Erro detectado</b>\nBot: {html.escape(str(bot_nome))}\nErro: {html.escape(str(erro))[:500]}")

    def info(self, texto: str) -> bool:
        return self.enviar(html.escape(texto))
