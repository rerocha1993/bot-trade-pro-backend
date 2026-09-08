# models/decisao_bot.py
from sqlalchemy import BigInteger, Column, Integer, Float, String, DateTime, Text
from datetime import datetime
from api.database import Base


class DecisaoBot(Base):
    """
    Cada decisão do motor (inclusive 'hold') com o contexto completo, para auditoria e painel.
    `detalhes` guarda JSON (cenários de Elliott, votos, níveis, sentimento).
    """
    __tablename__ = "DecisoesBot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, nullable=False, index=True)
    par = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    candle_ts = Column(BigInteger, nullable=True)            # timestamp (ms) do candle analisado
    preco = Column(Float, nullable=False)
    acao = Column(String(8), nullable=False)               # buy | sell | hold
    fase_onda = Column(String(30), nullable=True)
    cenario = Column(String(60), nullable=True)            # nome do cenário primário
    probabilidade = Column(Float, nullable=True)           # do cenário primário
    tendencia_macro = Column(String(12), nullable=True)
    votos = Column(String(255), nullable=True)             # "VWAP,TPO"
    tp = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    sentimento = Column(Float, nullable=True)
    motivo = Column(Text, nullable=True)
    detalhes = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
