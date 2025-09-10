# models/elliott_contagem_candidata.py

from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, JSON
from api.database import Base
from datetime import datetime
from sqlalchemy.orm import relationship

class ElliottContagemCandidata(Base):
    __tablename__ = "elliott_contagens_candidatas"
    id = Column(Integer, primary_key=True)
    par = Column(String(20), nullable=False)             # ex: BTCUSDT
    timeframe = Column(String(10), nullable=False)        # ex: '1h', '1d'
    ondas_detectadas = Column(JSON, nullable=False)       # JSON serializado com sequência de ondas
    score_confianca = Column(Float, nullable=True)
    data_inicio = Column(DateTime, nullable=False)
    data_fim = Column(DateTime, nullable=False)
    nivel_ciclo = Column(String(20), nullable=False)      # macro/micro/meso/etc
    status = Column(String(20), nullable=False)           # 'proposta', 'descartada', 'promovida'
    timestamp = Column(DateTime, default=datetime.utcnow)
    parent_id = Column(Integer, ForeignKey('elliott_contagens_candidatas.id'), nullable=True)  # Chave para parent

        # Se quiser, pode adicionar um relacionamento SQLAlchemy para acesso fácil:
    parent = relationship('ElliottContagemCandidata', remote_side=[id])
