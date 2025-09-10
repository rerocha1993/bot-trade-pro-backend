from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from api.database import Base

class PairInstitucional(Base):
    __tablename__ = "PairsInstitucionais"
    id = Column(Integer, primary_key=True, autoincrement=True)
    exchange_id = Column(Integer, ForeignKey("ExchangesInstitucionais.id"), nullable=False)
    par = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
