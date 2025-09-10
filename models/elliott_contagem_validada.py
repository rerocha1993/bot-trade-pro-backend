# models/elliott_contagem_validada.py

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from api.database import Base
from datetime import datetime

class ElliottContagemValidada(Base):
    __tablename__ = "elliott_contagens_validadas"
    id = Column(Integer, primary_key=True)
    par = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    ondas_detectadas = Column(JSON, nullable=False)
    score_confianca = Column(Float, nullable=True)
    data_inicio = Column(DateTime, nullable=False)
    data_fim = Column(DateTime, nullable=False)
    nivel_ciclo = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)   # sempre 'validada' ou 'histórica'
    timestamp = Column(DateTime, default=datetime.utcnow)
