# core/utils_indicadores.py
"""
Funções utilitárias compartilhadas pelos indicadores e pelo motor de estratégia.

Convenção de candle em todo o projeto (formato ccxt):
    [timestamp_ms, open, high, low, close, volume]
"""
from __future__ import annotations

import math
from typing import Iterable, List, Optional, Sequence

TIMEFRAME_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "1D": 86_400_000,
    "1w": 604_800_000,
    "1W": 604_800_000,
    "1M": 2_592_000_000,
}

ORDEM_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w", "1M"]


def normalizar_timeframe(tf: str) -> str:
    """Aceita '1D', '1W', '60', '240'... e devolve o formato ccxt ('1d', '1w', '1h', '4h')."""
    if tf is None:
        return "15m"
    tf = str(tf).strip()
    mapa = {"1D": "1d", "1W": "1w", "D": "1d", "W": "1w", "M": "1M",
            "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
            "60": "1h", "120": "2h", "240": "4h", "360": "6h", "720": "12h"}
    return mapa.get(tf, tf)


def timeframe_ms(tf: str) -> int:
    return TIMEFRAME_MS.get(normalizar_timeframe(tf), 900_000)


def timeframe_maior(tf: str) -> Optional[str]:
    tf = normalizar_timeframe(tf)
    if tf not in ORDEM_TIMEFRAMES:
        return None
    idx = ORDEM_TIMEFRAMES.index(tf)
    return ORDEM_TIMEFRAMES[idx + 1] if idx + 1 < len(ORDEM_TIMEFRAMES) else None


def validar_ohlcv(ohlcv: Sequence, minimo: int = 2) -> bool:
    if not ohlcv or len(ohlcv) < minimo:
        return False
    return all(isinstance(c, (list, tuple)) and len(c) >= 6 for c in ohlcv[:3])


def precos_tipicos(ohlcv: Sequence) -> List[float]:
    """(high + low + close) / 3 de cada candle."""
    return [(float(c[2]) + float(c[3]) + float(c[4])) / 3.0 for c in ohlcv]


def true_ranges(ohlcv: Sequence) -> List[float]:
    trs = []
    prev_close = None
    for c in ohlcv:
        high, low, close = float(c[2]), float(c[3]), float(c[4])
        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = close
    return trs


def atr(ohlcv: Sequence, periodo: int = 14) -> Optional[float]:
    """Average True Range (Wilder). Retorna None se não houver candles suficientes."""
    if not ohlcv or len(ohlcv) < 2:
        return None
    trs = true_ranges(ohlcv)
    periodo = max(1, min(periodo, len(trs)))
    valor = sum(trs[:periodo]) / periodo
    for tr in trs[periodo:]:
        valor = (valor * (periodo - 1) + tr) / periodo
    return valor


def media_movel(valores: Sequence[float], periodo: int) -> Optional[float]:
    if not valores:
        return None
    periodo = max(1, min(periodo, len(valores)))
    return sum(valores[-periodo:]) / periodo


def arredondar_para_step(valor: float, step: Optional[float], modo: str = "down") -> float:
    """Arredonda `valor` para múltiplo de `step` (precisão da exchange)."""
    if valor is None:
        return 0.0
    if not step or step <= 0:
        return float(valor)
    n = valor / step
    if modo == "down":
        n = math.floor(n + 1e-9)
    elif modo == "up":
        n = math.ceil(n - 1e-9)
    else:
        n = round(n)
    casas = max(0, -int(math.floor(math.log10(step)))) if step < 1 else 0
    return round(n * step, casas + 2)


def clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def pct_dist(a: float, b: float) -> float:
    """Distância percentual absoluta entre a e b relativa a b."""
    if not b:
        return float("inf")
    return abs(a - b) / abs(b)


def ultimo_candle_fechado(ohlcv: Sequence, tf: str, agora_ms: Optional[int] = None) -> Sequence:
    """
    Remove o último candle se ele ainda não fechou (timestamp + duração > agora).
    A Bybit devolve o candle em formação como último item da lista.
    """
    if not ohlcv:
        return ohlcv
    import time
    agora_ms = agora_ms or int(time.time() * 1000)
    dur = timeframe_ms(tf)
    if ohlcv[-1][0] + dur > agora_ms:
        return ohlcv[:-1]
    return ohlcv
