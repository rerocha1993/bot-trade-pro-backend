# conselho/tradeiros/recentes.py
"""
O que a carteira ao vivo precisa e os CSVs do projeto não têm (eles param no dia em que foram baixados), buscado das
APIs públicas, sem chave:

    velas        1d, 4h e 30m do BTCUSDT à vista da Binance (o mesmo mercado dos CSVs do backtest)
    funding      do perpétuo inverse BTCUSD da Bybit (é o que o hedge recebe ou paga)
    open interest e long/short de contas, 1 h, do BTCUSDT linear da Bybit (como em scripts/baixar_derivativos.py)
    medo e ganância   alternative.me

Tudo vai por cima do histórico em `Dados.do_projeto(recentes=...)`: no mesmo instante vale o recente.
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import requests

from conselho import velas as V

BYBIT = "https://api.bybit.com/v5/market/"
FNG = "https://api.alternative.me/fng/"
COLS = ["timestamp", "open", "high", "low", "close", "volume"]
SIMBOLO = "BINANCE:BTC-USDT"
#: velas por tempo: 400 diários e ~330 dias de 4h para Elliott e o perfil longo; 25 dias de 30 min para o range
VELAS = {"1d": 400, "4h": 2000, "30m": 1200}
DIAS_DERIVATIVOS = 40          # a leitura usa janelas de 30 dias
HORA_MS = 3_600_000
TIMEOUT = 20


def _velas(http, tempo: str, n: int) -> pd.DataFrame:
    linhas = V.velas(SIMBOLO, tempo, None, n, http)
    return pd.DataFrame([[int(x[0]) * 1000, *x[1:6]] for x in linhas], columns=COLS)


def _funding(http) -> Dict[str, float]:
    r = http.get(BYBIT + "funding/history", params={"category": "inverse", "symbol": "BTCUSD", "limit": 200},
                 timeout=TIMEOUT).json()
    return {x["fundingRateTimestamp"]: float(x["fundingRate"]) for x in r["result"]["list"]}


def _paginas(http, rota: str, params: Dict, desde_ms: int, valor) -> Dict[str, float]:
    """As listas de 1 h da Bybit vêm do mais novo para o mais velho, com cursor."""
    saida: Dict[str, float] = {}
    cursor = None
    for _ in range(10):
        p = dict(params, **({"cursor": cursor} if cursor else {}))
        r = http.get(BYBIT + rota, params=p, timeout=TIMEOUT).json()
        lista = r["result"]["list"]
        for x in lista:
            saida[x["timestamp"]] = valor(x)
        cursor = r["result"].get("nextPageCursor")
        if not lista or not cursor or min(int(x["timestamp"]) for x in lista) < desde_ms:
            break
    return saida


def _medo(http, dias: int) -> pd.DataFrame:
    r = http.get(FNG, params={"limit": dias}, timeout=TIMEOUT).json()
    return pd.DataFrame([[int(x["timestamp"]) * 1000, int(x["value"]), x["value_classification"]] for x in r["data"]],
                        columns=["timestamp", "valor", "classe"])


def buscar(agora_ms: int, http: Optional[requests.Session] = None) -> Dict:
    """Velas e derivativos recentes. Um pedaço que falhar fica de fora (a leitura segue com o histórico)."""
    http = http or requests.Session()
    desde = agora_ms - DIAS_DERIVATIVOS * 24 * HORA_MS
    rec: Dict = {"falhas": []}
    for tempo, n in VELAS.items():
        try:
            rec[tempo] = _velas(http, tempo, n)
        except Exception as e:                                       # noqa: BLE001 — segue sem esse tempo
            rec["falhas"].append(f"velas {tempo}: {type(e).__name__}")
    pedidos = {
        "funding": lambda: _funding(http),
        "oi": lambda: _paginas(http, "open-interest", {"category": "linear", "symbol": "BTCUSDT", "intervalTime": "1h",
                                                       "limit": 200}, desde, lambda x: float(x["openInterest"])),
        "lsr": lambda: _paginas(http, "account-ratio", {"category": "linear", "symbol": "BTCUSDT", "period": "1h",
                                                        "limit": 500}, desde,
                                lambda x: float(x["buyRatio"]) / max(float(x["sellRatio"]), 1e-9)),
        "fear": lambda: _medo(http, DIAS_DERIVATIVOS),
    }
    for nome, f in pedidos.items():
        try:
            rec[nome] = f()
        except Exception as e:                                       # noqa: BLE001
            rec["falhas"].append(f"{nome}: {type(e).__name__}")
    return rec
