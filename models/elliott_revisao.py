# models/elliott_revisao.py

from sqlalchemy import Column, Integer, String, DateTime, JSON
from api.database import Base
from datetime import datetime

class ElliottRevisao(Base):
    __tablename__ = "elliott_revisoes"
    id = Column(Integer, primary_key=True)
    contagem_id = Column(Integer, nullable=False)
    tipo_revisao = Column(String(30), nullable=False)   # 'rollback', 'recalculo', etc
    motivo = Column(String(200), nullable=False)
    dados_anteriores = Column(JSON, nullable=True)
    dados_corrigidos = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
