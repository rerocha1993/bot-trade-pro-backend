# conselho/mercado.py
"""
Dados públicos da Bybit (perpétuo linear), sem chave e só leitura: candles e último preço.

Substitui o conector de robôs (core/conexoes/conexao_bybit.py) que o serviço de avisos usava até 20/10/2026.
API v5: GET /v5/market/kline devolve até 1000 candles por chamada, do mais novo para o mais velho, como
[início_ms, open, high, low, close, volume, turnover]; GET /v5/market/tickers traz o lastPrice.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

BASE = "https://api.bybit.com"
CATEGORIA = "linear"
TIMEOUT_S = 10.0
CABECALHOS = {"User-Agent": "bot-trade-pro/1.0 (conselho)"}
LIMITE = 1000
INTERVALO_MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "6h": 360,
                 "12h": 720, "1d": 1440}
# o parâmetro `interval` da Bybit é em minutos, menos o diário, que é "D"
INTERVALO_API = {tf: ("D" if tf == "1d" else str(m)) for tf, m in INTERVALO_MIN.items()}


def _get(caminho: str, params: dict, sessao: Optional[requests.Session] = None) -> dict:
    http = sessao or requests
    r = http.get(BASE + caminho, params=params, headers=CABECALHOS, timeout=TIMEOUT_S)
    r.raise_for_status()
    dados = r.json()
    if dados.get("retCode") != 0:
        raise RuntimeError(f"Bybit {caminho}: {dados.get('retCode')} {dados.get('retMsg')}")
    return dados.get("result") or {}


def candles(simbolo: str, timeframe: str, desde_ms: int, ate_ms: Optional[int] = None,
            sessao: Optional[requests.Session] = None, pausa_s: float = 0.1) -> List[list]:
    """Candles fechados e abertos de `desde_ms` até `ate_ms` (ou agora), em ordem crescente, sem repetição."""
    minutos = INTERVALO_MIN.get(timeframe)
    if minutos is None:
        raise ValueError(f"timeframe sem suporte: {timeframe}")
    passo = minutos * 60_000
    ate_ms = int(ate_ms or time.time() * 1000)
    cursor = int(desde_ms) - int(desde_ms) % passo
    vistos = {}
    while cursor <= ate_ms:
        fim = min(ate_ms, cursor + passo * LIMITE - 1)
        res = _get("/v5/market/kline", {"category": CATEGORIA, "symbol": simbolo, "interval": INTERVALO_API[timeframe],
                                        "start": cursor, "end": fim, "limit": LIMITE}, sessao)
        for c in res.get("list") or []:
            ts = int(c[0])
            if int(desde_ms) - passo < ts <= ate_ms:
                vistos[ts] = [ts, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
        cursor = fim + 1
        if cursor <= ate_ms and pausa_s:
            time.sleep(pausa_s)
    return [vistos[k] for k in sorted(vistos)]


def preco(simbolo: str, sessao: Optional[requests.Session] = None) -> Optional[float]:
    """Último preço negociado; None se a Bybit não responder."""
    try:
        res = _get("/v5/market/tickers", {"category": CATEGORIA, "symbol": simbolo}, sessao)
        lista = res.get("list") or []
        return float(lista[0]["lastPrice"]) if lista else None
    except Exception as e:
        logger.warning("preço da Bybit indisponível: %s", e)
        return None
