# core/get_candles.py
import json
import logging
import os
from datetime import datetime

from core.conexoes.conexao_bybit import BybitConnector

LOG_PATH = "logs/elliott_audit.log"
CACHE_DIR = "cache_candles"
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger(__name__)


def log_event(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")


def get_candles(par, timeframe, limite=1000, modo_execucao="simulador", subconta=None, usar_cache=False):
    """Candles fechados da Bybit (linear). Cache opcional em disco para reprocessamentos."""
    par = par.replace("/", "")
    cache_file = os.path.join(CACHE_DIR, f"{par}_{timeframe}_{modo_execucao}.json")
    if usar_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                log_event(f"LOAD CACHE | {par} | {timeframe}")
                return data
        except Exception as e:
            log_event(f"ERROR LOAD CACHE | {par} | {timeframe} | {e}")
    try:
        con = BybitConnector(modo_execucao="simulador" if modo_execucao not in ("testnet", "real") else modo_execucao)
        candles = con.obter_ohlcv(par, timeframe=timeframe, limite=limite, somente_fechados=True)
        if usar_cache and candles:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(candles, f)
        log_event(f"FETCH BYBIT | {par} | {timeframe} | {len(candles)} candles")
        return candles
    except Exception as e:
        log_event(f"ERROR FETCH | {par} | {timeframe} | {e}")
        raise RuntimeError(f"Falha ao buscar candles de {par} em {timeframe}: {e}")
