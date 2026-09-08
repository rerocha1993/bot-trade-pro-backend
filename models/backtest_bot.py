# models/backtest_bot.py
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from datetime import datetime
from api.database import Base


class BacktestBot(Base):
    """
    Resultado de um backtest de validação. Um bot só pode ser ativado com um backtest APROVADO
    recente para o mesmo par/timeframe/estilo/perfil (ver services/backtest_service.py).
    """
    __tablename__ = "BacktestsBot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, nullable=True, index=True)
    par = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    estilo_trade = Column(String(20), nullable=True)
    confluencia_tipo = Column(String(20), nullable=True)
    fonte = Column(String(20), nullable=False, default="bybit")
    dias = Column(Integer, nullable=True)
    data_inicio = Column(DateTime, nullable=True)
    data_fim = Column(DateTime, nullable=True)
    candles = Column(Integer, nullable=True)
    trades = Column(Integer, nullable=True)
    taxa_acerto = Column(Float, nullable=True)
    retorno_pct = Column(Float, nullable=True)
    fator_lucro = Column(Float, nullable=True)
    drawdown_max_pct = Column(Float, nullable=True)
    r_medio = Column(Float, nullable=True)
    aprovado = Column(Boolean, nullable=False, default=False)
    motivo = Column(String(255), nullable=True)
    status = Column(String(12), nullable=False, default="concluido")   # rodando | concluido | erro
    parametros = Column(Text, nullable=True)
    detalhes = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
