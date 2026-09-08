# core/order_flow.py
"""
Order Flow: delta de agressão (trades a mercado), CVD e desequilíbrio do livro.

Entradas:
    order_book: {'bids': [(preco, qty), ...], 'asks': [(preco, qty), ...]}
    trades:     [{'price', 'qty', 'side' ('buy'|'sell'), 'timestamp' (ms)}, ...]
    ohlcv:      candles [ts, o, h, l, c, v]

Métricas:
    delta_candle   = vol_buy - vol_sell dos trades dentro do candle atual
    razao_delta    = delta / volume total  (-1..+1)
    cvd            = delta acumulado da janela de trades
    imbalance_book = (Σ bids - Σ asks) / (Σ bids + Σ asks) nos N melhores níveis  (-1..+1)
    absorção       = grande volume agredido em um nível sem o preço romper esse nível
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from core.utils_indicadores import timeframe_ms


class OrderFlowAnalyzerPro:
    def __init__(self, order_book: Optional[Dict], trades: Optional[List[Dict]], ohlcv: Sequence,
                 timeframe: str = "1m", niveis_book: int = 10, limiar_delta: float = 0.15,
                 limiar_book: float = 0.20):
        self.order_book = order_book or {"bids": [], "asks": []}
        self.trades = trades or []
        self.ohlcv = list(ohlcv) if ohlcv else []
        self.timeframe = timeframe
        self.niveis_book = niveis_book
        self.limiar_delta = limiar_delta
        self.limiar_book = limiar_book

    # ------------------------------------------------------------ métricas
    @staticmethod
    def calcular_delta_candle(candle_trades: List[Dict]) -> float:
        buy = sum(float(t["qty"]) for t in candle_trades if t.get("side") == "buy")
        sell = sum(float(t["qty"]) for t in candle_trades if t.get("side") == "sell")
        return buy - sell

    def trades_do_candle(self) -> List[Dict]:
        if not self.ohlcv or not self.trades:
            return []
        inicio = int(self.ohlcv[-1][0])
        fim = inicio + timeframe_ms(self.timeframe)
        return [t for t in self.trades if inicio <= int(t["timestamp"]) < fim]

    def cvd(self) -> float:
        return self.calcular_delta_candle(self.trades)

    def imbalance_book(self) -> Optional[float]:
        bids = self.order_book.get("bids") or []
        asks = self.order_book.get("asks") or []
        if not bids or not asks:
            return None
        sb = sum(float(q) for _, q in bids[: self.niveis_book])
        sa = sum(float(q) for _, q in asks[: self.niveis_book])
        if sb + sa <= 0:
            return None
        return (sb - sa) / (sb + sa)

    def clusterizar_volume(self, price_range=None, top: int = 10, agrupamento_pct: float = 0.0005) -> List:
        """Agrupa volume negociado por faixa de preço (0,05% por padrão). Retorna [(preco, volume)]."""
        if not self.trades:
            return []
        volumes: Dict[float, float] = {}
        for t in self.trades:
            p = float(t["price"])
            if price_range and not (price_range[0] <= p <= price_range[1]):
                continue
            passo = max(p * agrupamento_pct, 1e-9)
            chave = round(round(p / passo) * passo, 2)
            volumes[chave] = volumes.get(chave, 0.0) + float(t["qty"])
        return sorted(volumes.items(), key=lambda kv: -kv[1])[:top]

    def detectar_absorcao(self, price_level: Optional[float], trades: List[Dict], min_qty: float = None) -> bool:
        """
        Absorção: volume agredido concentrado num nível (>= 25% do volume do candle, ou min_qty)
        sem que o candle feche além desse nível.
        """
        if price_level is None or not trades or not self.ohlcv:
            return False
        total = sum(float(t["qty"]) for t in trades)
        if total <= 0:
            return False
        tol = price_level * 0.0005
        no_nivel = sum(float(t["qty"]) for t in trades if abs(float(t["price"]) - price_level) <= tol)
        limiar = min_qty if min_qty is not None else 0.25 * total
        close = float(self.ohlcv[-1][4])
        return no_nivel >= limiar and abs(close - price_level) <= price_level * 0.001

    # ---------------------------------------------------------------- sinal
    def analisar(self) -> Dict:
        if not self.ohlcv:
            return {"acao": "hold", "motivo": "Sem candles para order flow", "forca": 0.0}
        candle_trades = self.trades_do_candle()
        janela = candle_trades if candle_trades else self.trades[-500:]
        if not janela:
            imb = self.imbalance_book()
            if imb is None:
                return {"acao": "hold", "motivo": "Sem trades nem livro para order flow", "forca": 0.0}
            if imb > self.limiar_book:
                return {"acao": "buy", "motivo": f"Livro comprador (imbalance {imb:+.2f})", "forca": round(min(abs(imb), 1), 3), "imbalance": imb}
            if imb < -self.limiar_book:
                return {"acao": "sell", "motivo": f"Livro vendedor (imbalance {imb:+.2f})", "forca": round(min(abs(imb), 1), 3), "imbalance": imb}
            return {"acao": "hold", "motivo": f"Livro equilibrado (imbalance {imb:+.2f})", "forca": 0.0, "imbalance": imb}

        delta = self.calcular_delta_candle(janela)
        vol_total = sum(float(t["qty"]) for t in janela)
        razao = delta / vol_total if vol_total > 0 else 0.0
        imb = self.imbalance_book()
        clusters = self.clusterizar_volume()
        maior_cluster = clusters[0][0] if clusters else None
        absorcao = self.detectar_absorcao(maior_cluster, janela)

        # score composto: 70% delta de agressão, 30% livro
        score = razao
        if imb is not None:
            score = 0.7 * razao + 0.3 * imb
        forca = round(min(abs(score) / 0.5, 1.0), 3)
        detalhe = f"delta={delta:+.3f} ({razao:+.2f}), imbalance={'n/a' if imb is None else f'{imb:+.2f}'}"
        base = {"delta": delta, "razao_delta": razao, "imbalance": imb, "cvd": self.cvd(),
                "absorcao": absorcao, "cluster": maior_cluster, "forca": forca}

        if score > self.limiar_delta:
            return {"acao": "buy", "motivo": f"Agressão compradora: {detalhe}{' + absorção' if absorcao else ''}", **base}
        if score < -self.limiar_delta:
            return {"acao": "sell", "motivo": f"Agressão vendedora: {detalhe}{' + absorção' if absorcao else ''}", **base}
        return {"acao": "hold", "motivo": f"Order flow neutro: {detalhe}", **base, "forca": 0.0}
