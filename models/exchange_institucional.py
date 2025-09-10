from sqlalchemy import Column, Integer, String, Boolean
from api.database import Base


class ExchangeInstitucional(Base):
    __tablename__ = "ExchangesInstitucionais"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(32), nullable=False)
    ativa = Column(Boolean, default=True, nullable=False)
