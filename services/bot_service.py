# --- ARQUIVO 2: services/bot_service.py ---
from sqlalchemy.orm import Session

from models.bot import Bot
from models.bot_indicador import BotIndicador
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class BotService:
    def __init__(self, db: Session):
        self.db = db

    def create_bot(self, data: dict):
        bot = Bot(
            nome=data['nome'],
            ativo=data['ativo'],
            timeframe=data['timeframe'],
            estilo_trade=data.get('estilo_trade', 'daytrade'),
            modo_execucao=data.get('modo_execucao', 'simulador'),
            alavancagem=data.get('alavancagem', 1),
            quantidade=data['quantidade'],
            usar_trailing_stop=data.get('usar_trailing_stop', False),
            sl_tipo=data.get('sl_tipo', 'percentual'),
            sl_variacao_pct=data.get('sl_variacao_pct', 1.0),
            ativo_bot=data.get('ativo_bot', True),
            usar_api_macro=data.get('usar_api_macro', False)
        )
        self.db.add(bot)
        self.db.flush()  # recupera o ID do bot

        for indicador in data.get('indicadores', []):
            self.db.add(BotIndicador(
                bot_id=bot.id,
                nome=indicador['nome'],
                parametros=indicador.get('parametros', {})
            ))

        self.db.commit()
        return bot

    def get_bots(self):
        return self.db.query(Bot).all()

    def get_bot(self, bot_id: int):
        return self.db.query(Bot).filter(Bot.id == bot_id).first()

    def update_bot(self, bot_id: int, data: dict):
        bot = self.get_bot(bot_id)
        for campo, valor in data.items():
            setattr(bot, campo, valor)
        self.db.commit()
        return bot

    def delete_bot(self, bot_id: int):
        bot = self.get_bot(bot_id)
        self.db.delete(bot)
        self.db.commit()

    def get_indicadores(self, bot_id: int):
        return self.db.query(BotIndicador).filter(BotIndicador.bot_id == bot_id).all()
