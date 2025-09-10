# models/elliott_onda.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from api.database import Base
from datetime import datetime

class ElliottOnda(Base):
    __tablename__ = "elliott_ondas"
    id = Column(Integer, primary_key=True)
    contagem_id = Column(Integer, nullable=False)        # FK lógica, não precisa usar constraint se for multi-origem
    numero_onda = Column(Integer, nullable=False)        # 1,2,3,4,5,A,B,C,etc
    tipo_onda = Column(String(20), nullable=False)       # impulsiva, corretiva, flat, triângulo, diagonal, WXY...
    data_inicio = Column(DateTime, nullable=False)
    data_fim = Column(DateTime, nullable=False)
    preco_inicio = Column(Float, nullable=False)
    preco_fim = Column(Float, nullable=False)
    proporcao_fibonacci = Column(Float, nullable=True)   # ex: 1.618, 0.618
    validada = Column(Boolean, default=False)
    score_confianca = Column(Float, nullable=True)
    timestamp_registro = Column(DateTime, default=datetime.utcnow)
