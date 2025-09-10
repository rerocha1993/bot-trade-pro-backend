from sqlalchemy import DECIMAL, Column, Integer, Float, DateTime, Boolean
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.sql import func
from api.database import Base

class PontoInstitucional(Base):
    __tablename__ = "PontosInstitucionais"

    id = Column(Integer, primary_key=True, autoincrement=True)
    preco = Column(DECIMAL(18, 8), nullable=False)
    data_identificacao = Column(DateTime, server_default=func.getdate(), nullable=False)
    tipo = Column(NVARCHAR(32), nullable=False)
    motivo = Column(NVARCHAR(255), nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    testado = Column(Boolean, default=False, nullable=False)
    rompido = Column(Boolean, default=False, nullable=False)
    data_testado = Column(DateTime, nullable=True)
    data_rompido = Column(DateTime, nullable=True)
    par = Column(NVARCHAR(16), nullable=False)
    exchange = Column(NVARCHAR(16), nullable=False)
    relevancia = Column(Float, default=1.0, nullable=True)
    extra = Column(NVARCHAR('max'), nullable=True)   # <-- aqui está o ajuste!

    def __repr__(self):
        return f"<PontoInstitucional(par={self.par}, preco={self.preco}, tipo={self.tipo}, status={'ativo' if self.ativo else 'inativo'})>"
