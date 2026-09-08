# core/market_data.py
"""
Agregador de dados de mercado multi-exchange (dados públicos, via ccxt).

Cestas:
    "tradingview" -> Bitstamp + Coinbase + Bitfinex + Kraken (spot USD). É a mesma composição do
                     INDEX:BTCUSD da TradingView: (BITSTAMP + COINBASE + BITFINEX + KRAKEN) / 4.
                     Fonte: https://www.tradingview.com/support/solutions/43000659124-how-is-the-btc-index-being-calculated/
    "execucao"    -> só a exchange onde o bot opera (Bybit linear).
    "completa"    -> cesta TradingView + Bybit + Binance + OKX (volume global).

Composição das velas (mesmo timestamp):
    open/high/low/close = MÉDIA SIMPLES entre exchanges (igual ao índice da TradingView)
    volume              = SOMA dos volumes em moeda base
    range_max/range_min = extremos absolutos entre exchanges (para TPO "mercado completo")

Timeframes ausentes numa exchange (ex.: Coinbase não tem 30m/4h) são reamostrados a partir
de um timeframe menor.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

import ccxt

from core.utils_indicadores import normalizar_timeframe, timeframe_ms

logger = logging.getLogger(__name__)

CESTAS: Dict[str, List[Tuple[str, str]]] = {
    # (id ccxt, símbolo)
    "tradingview": [("bitstamp", "BTC/USD"), ("coinbaseexchange", "BTC/USD"), ("bitfinex", "BTC/USD"), ("kraken", "BTC/USD")],
    "execucao": [("bybit", "BTC/USDT:USDT")],
    "completa": [("bitstamp", "BTC/USD"), ("coinbaseexchange", "BTC/USD"), ("bitfinex", "BTC/USD"), ("kraken", "BTC/USD"),
                 ("bybit", "BTC/USDT:USDT"), ("binance", "BTC/USDT"), ("okx", "BTC/USDT")],
}

# Preferência de símbolo por exchange quando o par não é BTC
QUOTE_POR_EXCHANGE = {
    "bitstamp": "USD", "coinbaseexchange": "USD", "coinbase": "USD", "bitfinex": "USD", "kraken": "USD",
    "bybit": "USDT", "binance": "USDT", "okx": "USDT",
}

_TF_ORDEM = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"]


def _base_do_par(par: str) -> str:
    p = par.upper().replace("-", "").replace(":", "/").split("/")[0]
    for q in ("USDT", "USDC", "USD"):
        if p.endswith(q) and len(p) > len(q):
            return p[: -len(q)]
    return p


def simbolo_para_exchange(exchange_id: str, par: str) -> str:
    base = _base_do_par(par)
    quote = QUOTE_POR_EXCHANGE.get(exchange_id, "USDT")
    if exchange_id == "bybit":
        return f"{base}/USDT:USDT"
    return f"{base}/{quote}"


def reamostrar(ohlcv: Sequence, tf_origem: str, tf_destino: str) -> List[list]:
    """Agrega candles de um timeframe menor em um maior (alinhado à época UTC)."""
    d_ms = timeframe_ms(tf_destino)
    o_ms = timeframe_ms(tf_origem)
    if d_ms <= o_ms or not ohlcv:
        return [list(c) for c in ohlcv]
    saida: Dict[int, list] = {}
    for c in ohlcv:
        chave = (int(c[0]) // d_ms) * d_ms
        if chave not in saida:
            saida[chave] = [chave, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)]
        else:
            s = saida[chave]
            s[2] = max(s[2], float(c[2]))
            s[3] = min(s[3], float(c[3]))
            s[4] = float(c[4])
            s[5] += float(c[5] or 0)
    return [saida[k] for k in sorted(saida)]


def _sem_outliers(grupo: List[list], tol: float = 0.02) -> List[list]:
    """Remove velas cujo fechamento se afasta mais de `tol` da mediana do grupo (dados corrompidos)."""
    if len(grupo) < 3:
        return grupo
    closes = sorted(c[4] for c in grupo)
    mediana = closes[len(closes) // 2]
    return [c for c in grupo if mediana and abs(c[4] - mediana) / mediana <= tol]


class BitfinexPublico:
    """
    Adaptador direto da API pública v2 da Bitfinex (o wrapper ccxt 4.4.82 devolve dados inconsistentes
    para tBTCUSD). Mesma interface mínima usada pelo agregador.
    """
    BASE = "https://api-pub.bitfinex.com/v2"
    timeframes = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "3h": "3h", "6h": "6h",
                  "12h": "12h", "1d": "1D", "1w": "1W"}
    has = {"fetchTrades": True, "fetchOHLCV": True}
    rateLimit = 1000

    def __init__(self, timeout: float = 10.0):
        import requests
        self._req = requests
        self.timeout = timeout

    @staticmethod
    def _sym(simbolo: str) -> str:
        base, quote = simbolo.split("/")[0], simbolo.split("/")[1].split(":")[0]
        return f"t{base}{'UST' if quote == 'USDT' else quote}"

    def fetch_ohlcv(self, simbolo: str, timeframe: str, limit: int = 300, since=None):
        tf = self.timeframes[timeframe]
        r = self._req.get(f"{self.BASE}/candles/trade:{tf}:{self._sym(simbolo)}/hist",
                          params={"limit": min(limit, 10000), "sort": -1}, timeout=self.timeout).json()
        # formato: [mts, open, close, high, low, volume]
        velas = [[int(c[0]), float(c[1]), float(c[3]), float(c[4]), float(c[2]), float(c[5])] for c in r]
        velas.sort(key=lambda c: c[0])
        return velas

    def fetch_order_book(self, simbolo: str, limit: int = 25):
        r = self._req.get(f"{self.BASE}/book/{self._sym(simbolo)}/P0", params={"len": 25 if limit <= 25 else 100},
                          timeout=self.timeout).json()
        bids = [[float(p), float(a)] for p, _, a in r if a > 0]
        asks = [[float(p), float(-a)] for p, _, a in r if a < 0]
        return {"bids": sorted(bids, key=lambda x: -x[0]), "asks": sorted(asks, key=lambda x: x[0])}

    def fetch_trades(self, simbolo: str, limit: int = 300):
        r = self._req.get(f"{self.BASE}/trades/{self._sym(simbolo)}/hist", params={"limit": min(limit, 10000)},
                          timeout=self.timeout).json()
        return [{"price": float(t[3]), "amount": abs(float(t[2])), "side": "buy" if float(t[2]) > 0 else "sell",
                 "timestamp": int(t[1])} for t in r]

    def fetch_ticker(self, simbolo: str):
        r = self._req.get(f"{self.BASE}/ticker/{self._sym(simbolo)}", timeout=self.timeout).json()
        return {"last": float(r[6]), "bid": float(r[0]), "ask": float(r[2])}


class MarketDataAggregator:
    """Cliente público multi-exchange com cache curto e tolerância a falhas por exchange."""

    def __init__(self, cesta: str = "tradingview", incluir_execucao: bool = True, cache_seg: int = 20,
                 timeout_ms: int = 15000, clientes: Optional[Dict[str, object]] = None):
        self.cesta_nome = cesta
        membros = list(CESTAS.get(cesta, CESTAS["tradingview"]))
        if incluir_execucao and ("bybit", "BTC/USDT:USDT") not in membros:
            membros.append(("bybit", "BTC/USDT:USDT"))
        self.membros = membros
        self.cache_seg = cache_seg
        self._cache: Dict[str, Tuple[float, object]] = {}
        self._lock = threading.Lock()
        self._clientes: Dict[str, ccxt.Exchange] = dict(clientes or {})   # instâncias compartilhadas (mesmo rate limiter)
        self.timeout_ms = timeout_ms
        self.falhas: Dict[str, str] = {}

    # ----------------------------------------------------------- clientes
    def _cliente(self, exchange_id: str) -> ccxt.Exchange:
        if exchange_id not in self._clientes:
            if exchange_id == "bitfinex":
                self._clientes[exchange_id] = BitfinexPublico(timeout=self.timeout_ms / 1000.0)
            else:
                cfg = {"enableRateLimit": True, "timeout": self.timeout_ms}
                if exchange_id == "bybit":
                    cfg["options"] = {"defaultType": "swap"}
                self._clientes[exchange_id] = getattr(ccxt, exchange_id)(cfg)
        return self._clientes[exchange_id]

    def _cached(self, chave: str, fn):
        agora = time.time()
        with self._lock:
            item = self._cache.get(chave)
            if item and agora - item[0] < self.cache_seg:
                return item[1]
        valor = fn()
        with self._lock:
            self._cache[chave] = (agora, valor)
        return valor

    # -------------------------------------------------------------- OHLCV
    def _ohlcv_exchange(self, exchange_id: str, simbolo: str, timeframe: str, limite: int) -> List[list]:
        ex = self._cliente(exchange_id)
        tf = normalizar_timeframe(timeframe)
        disponiveis = list((ex.timeframes or {}).keys())
        if tf in disponiveis:
            dados = ex.fetch_ohlcv(simbolo, tf, limit=limite)
            return [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)] for c in dados]
        # reamostra a partir do maior timeframe menor disponível
        menores = [t for t in _TF_ORDEM if t in disponiveis and timeframe_ms(t) < timeframe_ms(tf) and timeframe_ms(tf) % timeframe_ms(t) == 0]
        if not menores:
            raise ValueError(f"{exchange_id} não tem timeframe {tf} nem um menor compatível")
        origem = menores[-1]
        fator = timeframe_ms(tf) // timeframe_ms(origem)
        limite_origem = min(int(limite * fator) + fator, 1000)
        dados = ex.fetch_ohlcv(simbolo, origem, limit=limite_origem)
        base = [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)] for c in dados]
        return reamostrar(base, origem, tf)[-limite:]

    def ohlcv_por_exchange(self, par: str, timeframe: str, limite: int = 300) -> Dict[str, List[list]]:
        """OHLCV de cada exchange da cesta (as que falharem são omitidas e registradas em `falhas`)."""
        def fetch():
            saida = {}
            for exchange_id, _ in self.membros:
                simbolo = simbolo_para_exchange(exchange_id, par)
                try:
                    saida[exchange_id] = self._ohlcv_exchange(exchange_id, simbolo, timeframe, limite)
                    self.falhas.pop(exchange_id, None)
                except Exception as e:
                    self.falhas[exchange_id] = f"{type(e).__name__}: {str(e)[:100]}"
                    logger.warning("OHLCV %s %s %s falhou: %s", exchange_id, simbolo, timeframe, e)
            return saida
        return self._cached(f"ohlcv:{par}:{timeframe}:{limite}", fetch)

    def ohlcv_composto(self, par: str, timeframe: str, limite: int = 300, minimo_exchanges: int = 1) -> List[list]:
        """
        Vela composta por timestamp: OHLC = média simples entre exchanges (como o índice da
        TradingView), volume = soma. Cada vela recebe 2 campos extras: [ts,o,h,l,c,v, range_min, range_max, n_exchanges].
        """
        por_ex = self.ohlcv_por_exchange(par, timeframe, limite)
        if not por_ex:
            raise RuntimeError(f"Nenhuma exchange respondeu para {par} {timeframe}: {self.falhas}")
        buckets: Dict[int, List[list]] = {}
        for exchange_id, candles in por_ex.items():
            for c in candles:
                buckets.setdefault(int(c[0]), []).append(c)
        saida = []
        for ts in sorted(buckets):
            grupo = _sem_outliers(buckets[ts])
            if len(grupo) < minimo_exchanges:
                continue
            n = len(grupo)
            saida.append([
                ts,
                sum(c[1] for c in grupo) / n,
                sum(c[2] for c in grupo) / n,
                sum(c[3] for c in grupo) / n,
                sum(c[4] for c in grupo) / n,
                sum(c[5] for c in grupo),
                min(c[3] for c in grupo),   # range_min absoluto
                max(c[2] for c in grupo),   # range_max absoluto
                n,
            ])
        # descarta velas iniciais em que só parte das exchanges tinha histórico
        if saida:
            n_max = max(c[8] for c in saida)
            corte = 0
            for i, c in enumerate(saida):
                if c[8] >= max(minimo_exchanges, n_max - 1):
                    corte = i
                    break
            saida = saida[corte:]
        return saida[-limite:]

    # ------------------------------------------------------- livro/trades
    def order_book_composto(self, par: str, profundidade: int = 50) -> Dict:
        """Une os livros das exchanges (preços em USD/USDT tratados como equivalentes)."""
        def fetch():
            livros = {}
            for exchange_id, _ in self.membros:
                simbolo = simbolo_para_exchange(exchange_id, par)
                try:
                    ex = self._cliente(exchange_id)
                    lim = 25 if exchange_id == "bitfinex" else profundidade
                    ob = ex.fetch_order_book(simbolo, limit=lim)
                    b = [(float(p), float(q)) for p, q, *_ in ob["bids"][:profundidade] if float(q) > 0]
                    a = [(float(p), float(q)) for p, q, *_ in ob["asks"][:profundidade] if float(q) > 0]
                    if b and a and a[0][0] >= b[0][0]:
                        livros[exchange_id] = (b, a, (b[0][0] + a[0][0]) / 2.0)
                except Exception as e:
                    logger.warning("book %s falhou: %s", exchange_id, str(e)[:80])
            # referência: mid da Bybit (onde o bot executa) ou mediana dos mids
            mids = [m for _, _, m in livros.values()]
            if not mids:
                return {"bids": [], "asks": [], "detalhado": {"bids": [], "asks": []}, "fontes": [], "timestamp": int(time.time() * 1000)}
            mediana = sorted(mids)[len(mids) // 2]
            livros = {k: v for k, v in livros.items() if abs(v[2] - mediana) / mediana <= 0.02}
            ref = livros["bybit"][2] if "bybit" in livros else mediana
            bids, asks, fontes = [], [], []
            for exchange_id, (b, a, mid) in livros.items():
                desloc = ref - mid   # alinha cada livro ao mid de referência (USD x USDT, prêmios)
                bids += [(p + desloc, q, exchange_id) for p, q in b]
                asks += [(p + desloc, q, exchange_id) for p, q in a]
                fontes.append(exchange_id)
            bids.sort(key=lambda x: -x[0])
            asks.sort(key=lambda x: x[0])
            return {"bids": [(p, q) for p, q, _ in bids], "asks": [(p, q) for p, q, _ in asks],
                    "detalhado": {"bids": bids, "asks": asks}, "fontes": fontes, "timestamp": int(time.time() * 1000)}
        return self._cached(f"book:{par}:{profundidade}", fetch)

    def trades_compostos(self, par: str, limite: int = 300) -> List[Dict]:
        def fetch():
            todos = []
            for exchange_id, _ in self.membros:
                simbolo = simbolo_para_exchange(exchange_id, par)
                try:
                    ex = self._cliente(exchange_id)
                    if not ex.has.get("fetchTrades"):
                        continue
                    for t in ex.fetch_trades(simbolo, limit=limite):
                        todos.append({"price": float(t["price"]), "qty": float(t["amount"]),
                                      "side": "buy" if (t.get("side") or "buy") == "buy" else "sell",
                                      "timestamp": int(t["timestamp"] or 0), "exchange": exchange_id})
                except Exception as e:
                    logger.warning("trades %s falhou: %s", exchange_id, str(e)[:80])
            todos.sort(key=lambda t: t["timestamp"])
            return todos
        return self._cached(f"trades:{par}:{limite}", fetch)

    def preco_indice(self, par: str) -> Optional[float]:
        """Preço médio (último negócio) entre as exchanges da cesta, como o índice da TradingView.
        Valores fora de 2% da mediana são descartados (ex.: ticker inconsistente de uma exchange)."""
        precos = []
        for exchange_id, _ in self.membros:
            try:
                t = self._cliente(exchange_id).fetch_ticker(simbolo_para_exchange(exchange_id, par))
                if t.get("last"):
                    precos.append(float(t["last"]))
            except Exception:
                continue
        if not precos:
            return None
        mediana = sorted(precos)[len(precos) // 2]
        validos = [p for p in precos if abs(p - mediana) / mediana <= 0.02]
        return sum(validos) / len(validos) if validos else None

    def status(self) -> Dict:
        return {"cesta": self.cesta_nome, "membros": [e for e, _ in self.membros], "falhas": dict(self.falhas)}


if __name__ == "__main__":
    agg = MarketDataAggregator("tradingview")
    velas = agg.ohlcv_composto("BTCUSDT", "30m", 50)
    print(len(velas), "velas compostas; última:", velas[-1])
    print("status:", agg.status())
