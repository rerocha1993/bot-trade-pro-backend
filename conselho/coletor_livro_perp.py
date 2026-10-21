# conselho/coletor_livro_perp.py
"""
Livro dos PERPÉTUOS perto do preço (o "Order Book Depth (aggregation) Perpetuals" do TRDR, até onde dá).

O TRDR mostra o livro dos perpétuos de 0 a 5%; as APIs públicas não vão tão longe (medido em 21/10/2026):
    binance  /fapi/v1/depth limit 1000              ~0,15% de cada lado
    bybit    /v5/market/orderbook linear limit 500  ~0,09%
    okx      /api/v5/market/books-full sz 5000      ~0,8% (contratos de 0,01 BTC)
Por isso a faixa comum é 0 a ``FAIXA_PCT`` (0,1%): a cada ``INTERVALO_S`` grava, por corretora, o BTC de compra e
de venda até 0,1% do meio e até onde o livro chegou. Arquivos em dados/livro_perp/<exchange>/<AAAA-MM-DD>.jsonl.gz.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import requests

from conselho.coletor_livro import RAIZ_PROJETO, gravar_snapshot, logger

PASTA_LIVRO_PERP = os.path.join(RAIZ_PROJETO, "dados", "livro_perp")
FAIXA_PCT = 0.001
INTERVALO_S = 30.0
TIMEOUT_S = 10.0

Livro = Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]   # (bids, asks) em (preço, BTC), melhor primeiro


def _binance() -> Livro:
    r = requests.get("https://fapi.binance.com/fapi/v1/depth", params={"symbol": "BTCUSDT", "limit": 1000}, timeout=TIMEOUT_S)
    r.raise_for_status()
    d = r.json()
    return [(float(p), float(q)) for p, q in d["bids"]], [(float(p), float(q)) for p, q in d["asks"]]


def _bybit() -> Livro:
    r = requests.get("https://api.bybit.com/v5/market/orderbook", params={"category": "linear", "symbol": "BTCUSDT", "limit": 500},
                     timeout=TIMEOUT_S)
    r.raise_for_status()
    d = r.json()["result"]
    return [(float(p), float(q)) for p, q in d["b"]], [(float(p), float(q)) for p, q in d["a"]]


def _okx() -> Livro:
    r = requests.get("https://www.okx.com/api/v5/market/books-full", params={"instId": "BTC-USDT-SWAP", "sz": 5000}, timeout=TIMEOUT_S)
    r.raise_for_status()
    d = r.json()["data"][0]
    return ([(float(x[0]), float(x[1]) * 0.01) for x in d["bids"]], [(float(x[0]), float(x[1]) * 0.01) for x in d["asks"]])


BUSCADORES: Dict[str, Callable[[], Livro]] = {"binance": _binance, "bybit": _bybit, "okx": _okx}


def resumo(exchange: str, ts: float, livro: Livro, faixa_pct: float = FAIXA_PCT) -> Optional[Dict]:
    """BTC de compra e de venda até `faixa_pct` do meio, e até onde o livro chegou de cada lado (fração)."""
    bids, asks = livro
    if not bids or not asks:
        return None
    mid = (bids[0][0] + asks[0][0]) / 2
    return {
        "ts": int(ts), "exchange": exchange, "mid": round(mid, 2), "faixa_pct": faixa_pct,
        "bids": round(sum(q for p, q in bids if p >= mid * (1 - faixa_pct)), 4),
        "asks": round(sum(q for p, q in asks if p <= mid * (1 + faixa_pct)), 4),
        "alcance_bids_pct": round(1 - bids[-1][0] / mid, 6),
        "alcance_asks_pct": round(asks[-1][0] / mid - 1, 6),
    }


class ColetorLivroPerp:
    """Uma thread que lê os três livros a cada `intervalo_s` segundos e grava o resumo de cada um."""

    def __init__(self, buscadores: Dict[str, Callable[[], Livro]] = BUSCADORES, raiz: str = PASTA_LIVRO_PERP,
                 intervalo_s: float = INTERVALO_S, parar: Optional[threading.Event] = None):
        self.buscadores = buscadores
        self.raiz = raiz
        self.intervalo_s = intervalo_s
        self.parar = parar or threading.Event()

    def ciclo(self, agora: Optional[float] = None) -> int:
        n = 0
        ts = agora if agora is not None else time.time()
        for ex, buscar in self.buscadores.items():
            try:
                r = resumo(ex, ts, buscar())
                if r is not None:
                    gravar_snapshot(r, self.raiz)
                    n += 1
            except Exception as e:      # uma corretora fora do ar não para as outras
                logger.warning("livro perpétuo %s: %s: %s", ex, type(e).__name__, str(e)[:120])
        return n

    def _rodar(self) -> None:
        while not self.parar.is_set():
            inicio = time.time()
            self.ciclo(inicio)
            self.parar.wait(max(1.0, self.intervalo_s - (time.time() - inicio)))

    def iniciar(self) -> None:
        threading.Thread(target=self._rodar, name="livro-perp", daemon=True).start()
        logger.info("coletor do livro dos perpétuos iniciado: %s -> %s", ",".join(self.buscadores), self.raiz)
