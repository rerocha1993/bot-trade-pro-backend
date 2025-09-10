# core/telegram_alert_service.py

import logging
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

class TelegramAlertService:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.chat_id = TELEGRAM_CHAT_ID

    async def enviar_alerta(self, mensagem: str):
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mensagem,
                parse_mode=ParseMode.HTML
            )
            logging.info("✅ Alerta enviado via Telegram.")
        except Exception as e:
            logging.error(f"❌ Erro ao enviar alerta: {e}")

    async def alerta_ordem(self, bot_nome, par, acao, preco):
        mensagem = f"🚨 <b>Ordem executada</b>\nBot: {bot_nome}\nPar: {par}\nAção: {acao.upper()}\nPreço: {float(preco):.2f}"
        await self.enviar_alerta(mensagem)

    async def alerta_erro(self, bot_nome, erro):
        mensagem = f"❗ <b>Erro detectado</b>\nBot: {bot_nome}\nErro: {erro}"
        await self.enviar_alerta(mensagem)
