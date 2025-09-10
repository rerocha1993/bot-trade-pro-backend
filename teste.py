from datetime import datetime
from core.spot_candles_fetcher import SpotCandlesFetcher
from services.elliott_service import ElliottService
from core.varredura_institucional import iniciar_varredura_elliott_institucional, vincular_hierarquia_multi_timeframe
from api.database import SessionLocal  # Ou o nome do seu factory/session

session = SessionLocal()
par = "BTC/USDT"

import ccxt
exchange = ccxt.bybit({'options': {'defaultType': 'spot'}})
print(exchange.timeframes)

timeframes = ["1M"]  # Pode ser só 2 ou 3 timeframes para teste rápido
data_inicio = datetime(2015, 1, 1)
data_fim = datetime(2025, 2, 1)

print("Rodando varredura...")
iniciar_varredura_elliott_institucional(par, timeframes, data_inicio, data_fim, session)
print("Rodando vinculação hierárquica...")
vincular_hierarquia_multi_timeframe(par, timeframes, data_inicio, data_fim, session)
