from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from api.database import Base

class OrderBlockInstitucional(Base):
    __tablename__ = 'orderblocks_institucionais'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    par = Column(String(20), nullable=False)
    exchange_origem = Column(String(20), nullable=False)
    direcao = Column(String(10), nullable=False)   # 'buy' ou 'sell'
    preco = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='ativo') # 'ativo', 'rompido', etc
    rompido_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = Column(DateTime, nullable=True)
    usado_como = Column(String(20), nullable=True)
    info_extra = Column(Text, nullable=True)
