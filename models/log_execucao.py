from sqlalchemy import Column, Integer, Float, Numeric, String, DateTime, ForeignKey
from datetime import datetime
from api.database import Base


class LogExecucaoBot(Base):
    __tablename__ = "LogExecucaoBot"
    
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer)
    data_execucao = Column(DateTime)
    preco = Column(Numeric(18,8))
    acao = Column(String)
    motivo = Column(String)
    resultado = Column(String)
    erro = Column(String)
    tipo_operacao = Column(String)
    direcao = Column(String)
    preco_entrada = Column(Numeric(18,8))
    preco_saida = Column(Numeric(18,8))
    sl = Column(Numeric(18,8))
    tp = Column(Numeric(18,8))
    quantidade = Column(Numeric(18,8))
