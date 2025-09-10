from sqlalchemy import Column, Integer, String, JSON
from api.database import Base


class IndicadorDisponivel(Base):
    __tablename__ = 'IndicadoresDisponiveis'

    id = Column(Integer, primary_key=True)
    nome = Column(String(50), unique=True, nullable=False)
    descricao = Column(String(255), nullable=True)
    parametros_padrao = Column(JSON, nullable=True)