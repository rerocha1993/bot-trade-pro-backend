from sqlalchemy import Column, Integer, Float, Numeric, String, DateTime
from datetime import datetime
from api.database import Base


class LogExecucaoBot(Base):
    """
    Log de eventos de execução (entrada, saída, erro, ajuste de stop).

    acao        : 'buy' | 'sell' | 'hold' | 'erro' | 'ajuste_sl'
    tipo_operacao: 'entrada' | 'saida' | 'info'
    resultado   : P&L em USDT já com quantidade e taxas (só em saídas)
    """
    __tablename__ = "LogExecucaoBot"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer)
    data_execucao = Column(DateTime, default=datetime.utcnow)
    preco = Column(Float)
    acao = Column(String)
    motivo = Column(String)
    resultado = Column(Float)
    erro = Column(String)
    tipo_operacao = Column(String)
    direcao = Column(String)
    preco_entrada = Column(Float)
    preco_saida = Column(Float)
    sl = Column(Numeric(18, 8))
    tp = Column(Numeric(18, 8))
    quantidade = Column(Numeric(18, 8))

    def as_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        for k in ("sl", "tp", "quantidade"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        return d
