from sqlalchemy import Column, Integer, String, Boolean, Float
from api.database import Base

from sqlalchemy import DECIMAL

class Bot(Base):
    __tablename__ = "Bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    ativo = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    estilo_trade = Column(String(20))
    modo_execucao = Column(String(20), default="simulador")
    alavancagem = Column(Integer, default=1)
    quantidade = Column(Float, nullable=False)
    exchange = Column(String(32), nullable=False)

    usar_elliott = Column(Boolean, default=True)
    usar_fibonacci = Column(Boolean, default=True)
    usar_tpo = Column(Boolean, default=False)
    usar_orderflow = Column(Boolean, default=False)
    usar_vwap = Column(Boolean, default=False)
    usar_volume_profile = Column(Boolean, default=False)
    usar_orderblock = Column(Boolean, default=False)

    usar_trailing_stop = Column(Boolean, default=False)
    sl_tipo = Column(String(20), default="percentual")
    sl_variacao_pct = Column(Float, default=1.0)

    ativo_bot = Column(Boolean, default=True)
    usar_api_macro = Column(Boolean, default=False)  # novo campo

    position_mode = Column(String, default="one-way")  # "one-way" ou "hedged"
    margin_mode = Column(String, default="cross")      # "cross" ou "isolated"
    subconta = Column(String, default="principal")     # nome da subconta (ex: "swing", "hedge")

    banca = Column(DECIMAL(18, 2), nullable=False, default=0)
    risco_pct = Column(Float, nullable=False, default=0.01)
    max_alocacao_pct = Column(Float, nullable=False, default=0.5)
    min_quantidade = Column(Float, nullable=True)
    max_quantidade = Column(Float, nullable=True)
    confluencia_tipo = Column(String(20), nullable=False, default="conservador")

    def as_dict(self):
     return {c.name: getattr(self, c.name) for c in self.__table__.columns}
