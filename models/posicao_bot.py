# models/posicao_bot.py
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from datetime import datetime
from api.database import Base


class PosicaoBot(Base):
    """
    Posição aberta/fechada de um bot. Persistida para sobreviver a reinícios e para
    reconciliação com a exchange (testnet/real).
    """
    __tablename__ = "PosicoesBot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, nullable=False, index=True)
    par = Column(String(20), nullable=False)
    modo_execucao = Column(String(20), nullable=False)      # simulador | testnet | real
    direcao = Column(String(4), nullable=False)             # buy | sell
    quantidade = Column(Float, nullable=False)
    preco_entrada = Column(Float, nullable=False)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    sl_inicial = Column(Float, nullable=True)
    trailing_ativo = Column(Boolean, default=False)
    status = Column(String(12), nullable=False, default="aberta")  # aberta | fechada
    preco_saida = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)                      # em USDT, líquido de taxas estimadas
    taxas = Column(Float, nullable=True)
    motivo_entrada = Column(Text, nullable=True)
    motivo_saida = Column(String(255), nullable=True)
    fase_onda = Column(String(30), nullable=True)
    cenario = Column(String(60), nullable=True)
    ordem_id = Column(String(64), nullable=True)
    aberto_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    fechado_em = Column(DateTime, nullable=True)

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
