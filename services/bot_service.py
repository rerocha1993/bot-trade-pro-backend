# services/bot_service.py
from sqlalchemy.orm import Session

from core.alavancagem import normalizar as normalizar_alavancagem
from models.bot import Bot
from models.bot_indicador import BotIndicador

CAMPOS_BOT = {c.name for c in Bot.__table__.columns} - {"id"}
OBRIGATORIOS = ("nome", "ativo", "timeframe", "quantidade")


class BotService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _normalizar(data: dict) -> dict:
        d = {k: v for k, v in data.items() if k in CAMPOS_BOT}
        if d.get("ativo"):
            d["ativo"] = str(d["ativo"]).replace("/", "").upper()
        if d.get("exchange") and "testnet" in str(d["exchange"]).lower():
            d["exchange"] = "bybit"
            d.setdefault("modo_execucao", "testnet")
        if d.get("confluencia_tipo"):
            d["confluencia_tipo"] = str(d["confluencia_tipo"]).lower()
        if d.get("estilo_trade"):
            e = str(d["estilo_trade"]).lower()
            d["estilo_trade"] = "scalping" if "scalp" in e else "swing" if "swing" in e else "daytrade"
        if d.get("modo_execucao"):
            d["modo_execucao"] = str(d["modo_execucao"]).lower()
        if "alavancagem" in d:
            d["alavancagem"] = normalizar_alavancagem(d["alavancagem"])
        return d

    def create_bot(self, data: dict) -> Bot:
        faltando = [c for c in OBRIGATORIOS if data.get(c) in (None, "")]
        if faltando:
            raise ValueError(f"Campos obrigatórios ausentes: {faltando}")
        bot = Bot(**self._normalizar(data))
        self.db.add(bot)
        self.db.flush()
        for indicador in data.get("indicadores", []) or []:
            self.db.add(BotIndicador(bot_id=bot.id, nome=indicador["nome"], parametros=indicador.get("parametros", {})))
        self.db.commit()
        self.db.refresh(bot)
        return bot

    def get_bots(self):
        return self.db.query(Bot).order_by(Bot.id).all()

    def get_bot(self, bot_id: int):
        return self.db.query(Bot).filter(Bot.id == bot_id).first()

    def update_bot(self, bot_id: int, data: dict):
        bot = self.get_bot(bot_id)
        if not bot:
            return None
        for campo, valor in self._normalizar(data).items():
            setattr(bot, campo, valor)
        self.db.commit()
        self.db.refresh(bot)
        return bot

    def delete_bot(self, bot_id: int) -> bool:
        bot = self.get_bot(bot_id)
        if not bot:
            return False
        self.db.query(BotIndicador).filter(BotIndicador.bot_id == bot_id).delete()
        self.db.delete(bot)
        self.db.commit()
        return True

    def get_indicadores(self, bot_id: int):
        return self.db.query(BotIndicador).filter(BotIndicador.bot_id == bot_id).all()
