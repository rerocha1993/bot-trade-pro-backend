import os
import json
import time
from datetime import datetime
from core.conexoes.conexao_bybit import BybitConnector

# Caminho para salvar os logs e o cache
LOG_PATH = "logs/elliott_audit.log"
CACHE_DIR = "cache_candles"
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)

def log_event(msg):
    with open(LOG_PATH, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")

def get_candles(par, timeframe, limite=1000, modo_execucao="simulador", subconta=None, usar_cache=True):
    """
    Busca candles OHLCV via BybitConnector, com tratamento de erros, log e cache institucional.
    Suporta multi-par e multi-subconta (parametrize pelo nome da subconta se for o caso).
    """
    # Ajusta nome do arquivo de cache por par/timeframe/subconta
    cache_file = os.path.join(
        CACHE_DIR,
        f"{par.replace('/','_')}_{timeframe}_{modo_execucao}_{subconta or 'main'}.json"
    )

    # 1. Tenta carregar do cache se permitido
    if usar_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                log_event(f"LOAD CACHE | {par} | {timeframe} | {modo_execucao} | sub: {subconta}")
                return data
        except Exception as e:
            log_event(f"ERROR LOAD CACHE | {par} | {timeframe} | {e}")

    # 2. Tenta buscar da exchange real
    try:
        connector = BybitConnector(modo_execucao=modo_execucao)
        if subconta:
            # Se for multi-subconta, ative via API CCXT se disponível (exemplo, adaptar para seu fluxo real)
            connector.exchange.headers = {"referer": subconta}
        candles = connector.obter_ohlcv(par, timeframe=timeframe, limite=limite)
        # Salva no cache
        if usar_cache:
            with open(cache_file, "w") as f:
                json.dump(candles, f)
        log_event(f"FETCH BYBIT | {par} | {timeframe} | {modo_execucao} | sub: {subconta}")
        return candles
    except Exception as e:
        log_event(f"ERROR FETCH | {par} | {timeframe} | {modo_execucao} | sub: {subconta} | {e}")
        raise RuntimeError(f"Falha ao buscar candles de {par} em {timeframe}: {str(e)}")
