# --- ARQUIVO 1: models/bot_indicador.py ---
from sqlalchemy import Column, Integer, String, ForeignKey, JSON

from api.database import Base

class BotIndicador(Base):
    __tablename__ = 'BotIndicadores'

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey('Bots.id'))
    nome = Column(String(50))  # Ex: 'fibonacci', 'vwap', etc.
    parametros = Column(JSON, nullable=True)  # Ex: {"intervalo": 50, "nivel": 61.8}