from sqlalchemy import Column, Integer, String, Boolean, Float, DECIMAL, Text
from api.database import Base


class Bot(Base):
    """
    Configuração de um robô.

    modo_execucao : 'simulador' (paper trading, sem ordens) | 'testnet' | 'real'
    estilo_trade  : 'scalping' | 'daytrade' | 'swing'  -> define o grau de Elliott operado
    confluencia_tipo: 'conservador' (todos os validadores alinhados) | 'turbo' (basta 1)
    """
    __tablename__ = "Bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    ativo = Column(String(20), nullable=False)            # par, ex.: BTCUSDT
    timeframe = Column(String(10), nullable=False)        # timeframe operacional
    estilo_trade = Column(String(20), default="daytrade")
    modo_execucao = Column(String(20), default="simulador")
    alavancagem = Column(Integer, default=1)
    quantidade = Column(Float, nullable=False)            # quantidade fixa (fallback quando banca = 0)
    exchange = Column(String(32), nullable=False, default="bybit")

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
    usar_api_macro = Column(Boolean, default=False)       # calendário macro (bloqueia perto de eventos)

    position_mode = Column(String, default="one-way")     # "one-way" ou "hedged"
    margin_mode = Column(String, default="cross")         # "cross" ou "isolated"
    subconta = Column(String, default="principal")

    banca = Column(DECIMAL(18, 2), nullable=False, default=0)
    risco_pct = Column(Float, nullable=False, default=0.01)
    max_alocacao_pct = Column(Float, nullable=False, default=0.5)
    min_quantidade = Column(Float, nullable=True)
    max_quantidade = Column(Float, nullable=True)
    confluencia_tipo = Column(String(20), nullable=False, default="conservador")

    # trailing stop (colunas já existentes no banco)
    ativador_trailing = Column(Float, default=0.005)      # fração do preço a favor para ativar
    distancia_trailing = Column(Float, default=0.003)     # distância do SL ao preço quando ativo
    trailing_manual = Column(Boolean, default=False)

    # novos (criados pelo scripts/setup_db.py se não existirem)
    usar_sentimento = Column(Boolean, default=True)       # filtro contrário de sentimento
    usar_tendencia_macro = Column(Boolean, default=True)  # exige alinhamento com o grau superior
    max_trades_dia = Column(Integer, default=10)
    max_perda_dia_pct = Column(Float, default=0.03)       # 3% da banca
    delay_execucao = Column(Integer, default=10)          # segundos entre ciclos
    usar_filtro_regime = Column(Boolean, default=True)    # bloqueia entradas em compressão/serrilhado
    prob_sucesso_minima = Column(Float, default=0.45)     # mínimo da probabilidade calibrada do cenário
    tipo_entrada = Column(String(10), default="mercado")  # 'mercado' | 'limite' (post-only no nível do cenário)
    limite_candles_espera = Column(Integer, default=3)    # candles até cancelar a ordem limitada
    usar_websocket = Column(Boolean, default=False)       # trades em tempo real (scalp) em vez de REST
    taxa_historica_minima = Column(Float, default=0.0)    # modo seletivo: só tipos de cenário com acerto histórico >= X (0 = desligado)
    rr_minimo = Column(Float, default=0.0)                # risco:retorno mínimo (0 = padrão do perfil)

    # modo inverse (short-only em range, acumulação de BTC)
    estrategia = Column(String(20), default="elliott")    # 'elliott' | 'inverse_range'
    categoria = Column(String(10), default="linear")      # 'linear' (USDT) | 'inverse' (BTC/USD, margem em BTC)
    range_low = Column(Float, nullable=True)
    range_high = Column(Float, nullable=True)
    range_status = Column(String(12), nullable=True)      # proposto | aprovado | stopado
    range_motivo = Column(String(255), nullable=True)
    short_base_max = Column(Float, default=0.5)
    folga_stop = Column(Float, default=0.01)
    escada_json = Column(String(500), nullable=True)
    grade_json = Column(Text, nullable=True)              # estado da grade inversa (fatias abertas, BTC realizado)
    saida_estrutural = Column(Boolean, default=False)     # grade: fechar quando Elliott virar impulso de alta acima do topo

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
