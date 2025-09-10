from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, DECIMAL, NVARCHAR
from datetime import datetime
from api.database import Base


class PontoInstitucionalLog(Base):
    __tablename__ = "PontosInstitucionaisLog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ponto_id = Column(Integer, nullable=False)
    preco = Column(DECIMAL(18, 8), nullable=False)
    tipo = Column(NVARCHAR(32), nullable=False)
    par = Column(NVARCHAR(16), nullable=False)
    exchange = Column(NVARCHAR(16), nullable=False)
    acao = Column(NVARCHAR(16), nullable=False)           # testado, rompido, etc
    relevancia = Column(Float, nullable=True)
    data_evento = Column(DateTime, default=datetime.utcnow, nullable=False)
    detalhe = Column(NVARCHAR(255), nullable=True)
