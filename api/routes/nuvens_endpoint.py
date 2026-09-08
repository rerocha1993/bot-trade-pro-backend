from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List, Tuple, Optional
import httpx, asyncio, time, math
from collections import deque, defaultdict

router = APIRouter(tags=["nuvens"])

# ===================== CONFIG =====================
DEFAULT_INTERVAL_SEC = 30          # 30s ⇒ ~120 pontos/hora
DEFAULT_WINDOW_MINUTES = 10        # quantos minutos manter em memória
BUCKETS = [0, 1, 2.5, 5, 10, 25]   # faixas percentuais (institucionais)

# ===================== STORAGE =====================
# memória por (exchange, pair): deque de snapshots
# snapshot: {
#   "ts", "midPrice", "buyRanges", "sellRanges",
#   "sumBids", "sumAsks", "imbalance", "delta"
# }
_SERIES: Dict[Tuple[str, str], deque] = {}
# tarefas de coleta por (exchange, pair)
_TASKS: Dict[Tuple[str, str], asyncio.Task] = {}

# ===================== HELPERS EXCHANGE =====================
async def fetch_coinbase_orderbook(product: str, level: int = 2) -> Dict[str, Any]:
    url = f"https://api.exchange.coinbase.com/products/{product}/book"
    params = {"level": level}
    headers = {"User-Agent": "bot-trade-pro/1.0"}
    async with httpx.AsyncClient(timeout=7.0) as client:
        r = await client.get(url, params=params, headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Coinbase falhou: {r.text}")
        data = r.json()
        bids = [(float(p), float(q)) for p, q, *_ in data.get("bids", [])]
        asks = [(float(p), float(q)) for p, q, *_ in data.get("asks", [])]
        return {"bids": bids, "asks": asks}

async def fetch_binance_orderbook(symbol: str, limit: int = 1000) -> Dict[str, Any]:
    url = "https://api.binance.com/api/v3/depth"
    params = {"symbol": symbol, "limit": limit}
    headers = {"User-Agent": "bot-trade-pro/1.0"}
    async with httpx.AsyncClient(timeout=7.0) as client:
        r = await client.get(url, params=params, headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Binance falhou: {r.text}")
        data = r.json()
        bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
        asks = [(float(p), float(q)) for p, q in data.get("asks", [])]
        return {"bids": bids, "asks": asks}

def ensure_symbol_formats(exchange: str, pair: str) -> str:
    """Binance: BTCUSDT | Coinbase: BTC-USD"""
    p = pair.upper().replace("/", "").replace("-", "")
    if exchange == "binance":
        return p
    commons = ["USDT", "USD", "USDC", "EUR", "BRL"]
    for q in commons:
        if p.endswith(q):
            base = p[:-len(q)]
            return f"{base}-{q}"
    return "BTC-USD"

# ===================== AGREGAÇÃO =====================
_BUCKET_PAIRS = [(BUCKETS[i], BUCKETS[i+1]) for i in range(len(BUCKETS)-1)]

def aggregate_ranges(bids: List[Tuple[float,float]], asks: List[Tuple[float,float]]) -> Dict[str, Any]:
    if not bids or not asks:
        raise HTTPException(status_code=502, detail="Livro vazio")
    best_bid = max(bids, key=lambda x: x[0])[0]
    best_ask = min(asks, key=lambda x: x[0])[0]
    mid = (best_bid + best_ask) / 2.0

    buy_ranges = [{"range": f"{lo}-{hi}%", "buy_volume": 0.0, "sell_volume": 0.0} for lo, hi in _BUCKET_PAIRS]
    sell_ranges = [{"range": f"{lo}-{hi}%", "buy_volume": 0.0, "sell_volume": 0.0} for lo, hi in _BUCKET_PAIRS]

    # bids (<= mid): dist = (mid - price)/mid * 100
    for price, qty in bids:
        if price <= 0 or qty <= 0: continue
        dist = (mid - price) / mid * 100.0
        if dist < 0: continue
        for i, (lo, hi) in enumerate(_BUCKET_PAIRS):
            if lo <= dist < hi:
                buy_ranges[i]["buy_volume"] += qty
                break

    # asks (>= mid): dist = (price - mid)/mid * 100
    for price, qty in asks:
        if price <= 0 or qty <= 0: continue
        dist = (price - mid) / mid * 100.0
        if dist < 0: continue
        for i, (lo, hi) in enumerate(_BUCKET_PAIRS):
            if lo <= dist < hi:
                sell_ranges[i]["sell_volume"] += qty
                break

    sum_bids = sum(r["buy_volume"] for r in buy_ranges)
    sum_asks = sum(r["sell_volume"] for r in sell_ranges)
    denom = (sum_bids + sum_asks)
    imbalance = ((sum_bids - sum_asks) / denom) if denom > 0 else 0.0  # [-1, +1]
    delta = (sum_bids - sum_asks)  # para CVD de profundidade

    top_bids = [{"price": p, "qty": q} for p, q in sorted(bids, key=lambda x: x[0], reverse=True)[:10]]
    top_asks = [{"price": p, "qty": q} for p, q in sorted(asks, key=lambda x: x[0])[:10]]

    return {
        "midPrice": mid,
        "buyRanges": buy_ranges,
        "sellRanges": sell_ranges,
        "sumBids": sum_bids,
        "sumAsks": sum_asks,
        "imbalance": imbalance,
        "delta": delta,
        "topBids": top_bids,
        "topAsks": top_asks,
    }

# ===================== COLETOR ASSÍNCRONO =====================
async def _collector_loop(exchange: str, pair: str, interval_sec: int, window_minutes: int):
    key = (exchange, pair)
    maxlen = max(1, int((window_minutes*60) / max(1, interval_sec)))
    _SERIES.setdefault(key, deque(maxlen=maxlen))
    while True:
        try:
            if exchange == "binance":
                ob = await fetch_binance_orderbook(ensure_symbol_formats("binance", pair), limit=1000)
                source = f"binance:{ensure_symbol_formats('binance', pair)}"
            else:
                ob = await fetch_coinbase_orderbook(ensure_symbol_formats("coinbase", pair), level=2)
                source = f"coinbase:{ensure_symbol_formats('coinbase', pair)}"

            agg = aggregate_ranges(ob["bids"], ob["asks"])
            snapshot = {
                "ts": int(time.time()),
                "source": source,
                **agg
            }
            _SERIES[key].append(snapshot)
        except Exception as e:
            # não derruba o loop por erro transitório
            # (poderia logar/contabilizar)
            pass
        await asyncio.sleep(interval_sec)

def ensure_task_running(exchange: str, pair: str, interval_sec: int, window_minutes: int):
    key = (exchange, pair)
    if key in _TASKS and not _TASKS[key].done():
        return
    _TASKS[key] = asyncio.create_task(_collector_loop(exchange, pair, interval_sec, window_minutes))

# ===================== ENDPOINTS =====================

def _get_pair_for_bot(bot_id: int) -> str:
    # TODO: troque pelo lookup no seu banco (tabela Bot)
    return "BTCUSDT"

@router.get("/logs/{bot_id}/nuvens-dados")
async def nuvens_dados_timeseries(
    bot_id: int,
    timeframe: str = Query(..., description="Ex.: 30m, 1h (rótulo visual; order book é instantâneo)"),
    exchange: str = Query("coinbase", pattern="^(coinbase|binance)$"),
    pair: Optional[str] = Query(None, description="Se não informado, usa o par do bot (ex.: BTCUSDT)"),
    interval_sec: int = Query(DEFAULT_INTERVAL_SEC, ge=1, le=60, description="Intervalo do snapshot em segundos"),
    window_minutes: int = Query(DEFAULT_WINDOW_MINUTES, ge=1, le=120, description="Janela mantida em memória (min)")
) -> Dict[str, Any]:
    """
    Retorna SÉRIE TEMPORAL de nuvens (order book) agregadas por faixas.
    - Dispara um coletor assíncrono por (exchange,pair) no primeiro acesso.
    - Mantém em memória (ring buffer) os últimos `window_minutes` de snapshots.
    - ~120 pontos/hora com interval_sec=30.
    """
    raw_pair = (pair or _get_pair_for_bot(bot_id)).upper().replace("/", "").replace("-", "")

    # garante coletor em execução
    ensure_task_running(exchange, raw_pair, interval_sec, window_minutes)

    # se ainda não tem dados (primeira chamada), faça uma captura imediata para responder algo
    key = (exchange, raw_pair)
    if key not in _SERIES or len(_SERIES[key]) == 0:
        try:
            if exchange == "binance":
                ob = await fetch_binance_orderbook(ensure_symbol_formats("binance", raw_pair), limit=1000)
            else:
                ob = await fetch_coinbase_orderbook(ensure_symbol_formats("coinbase", raw_pair), level=2)
            agg = aggregate_ranges(ob["bids"], ob["asks"])
            snap = {"ts": int(time.time()), "source": f"{exchange}:{ensure_symbol_formats(exchange, raw_pair)}", **agg}
            _SERIES.setdefault(key, deque(maxlen=max(1, int((window_minutes*60)/max(1, interval_sec))))).append(snap)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Falha ao capturar snapshot inicial: {e}")

    # monta série ordenada
    series = list(_SERIES[key])  # já vem em ordem (deque append)

    # calcula Depth-CVD (cumulativo de delta = sumBids - sumAsks)
    cvd = 0.0
    for s in series:
        cvd += s.get("delta", 0.0)
        s["depthCvd"] = cvd  # adiciona por ponto

    # resposta
    latest = series[-1]
    return {
        "bot_id": bot_id,
        "timeframe": timeframe,
        "exchange": exchange,
        "pair": raw_pair,
        "interval_sec": interval_sec,
        "window_minutes": window_minutes,
        "midPrice": latest["midPrice"],
        "latestImbalance": latest["imbalance"],
        "points": len(series),
        "series": series,  # lista de pontos temporais com buy/sellRanges, imbalance, depthCvd etc.
        "timestamp": int(time.time())
    }
