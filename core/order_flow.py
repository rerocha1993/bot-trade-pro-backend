# Arquivo: core/order_flow.py

import numpy as np

class OrderFlowAnalyzerPro:
    def __init__(self, order_book, trades, ohlcv):
        self.order_book = order_book
        self.trades = trades
        self.ohlcv = ohlcv
        # Range institucional para validação de zonas
        self.highs = [c[2] for c in ohlcv] if ohlcv else []
        self.lows = [c[3] for c in ohlcv] if ohlcv else []
        self.max_high = max(self.highs) if self.highs else None
        self.min_low = min(self.lows) if self.lows else None
        self.tolerancia = 0.02

    def calcular_delta_candle(self, candle_trades):
        buy_vol = sum(t['qty'] for t in candle_trades if t['side'] == 'buy')
        sell_vol = sum(t['qty'] for t in candle_trades if t['side'] == 'sell')
        delta = buy_vol - sell_vol
        return delta

    def detectar_absorcao(self, price_level, trades, min_qty=10):
        vol_agressor = sum(t['qty'] for t in trades if t['price'] == price_level)
        if vol_agressor >= min_qty and self._preco_valido(price_level):
            return True
        return False

    def clusterizar_volume(self, price_range=None):
        volumes = {}
        for t in self.trades:
            p = t['price']
            if price_range and not (price_range[0] <= p <= price_range[1]):
                continue
            if not self._preco_valido(p):
                continue
            volumes[p] = volumes.get(p, 0) + t['qty']
        clusters = sorted(volumes.items(), key=lambda x: -x[1])
        return clusters[:10]

    def analisar(self):
        if not self.ohlcv or not self.trades:
            return {"acao": "hold", "motivo": "Sem dados de orderflow"}

        ultimo_candle = self.ohlcv[-1]
        candle_start = ultimo_candle[0]
        candle_end = ultimo_candle[0] + 60 * 1000  # 1min em ms

        candle_trades = [t for t in self.trades if candle_start <= t['timestamp'] < candle_end]

        delta = self.calcular_delta_candle(candle_trades)
        clusters = self.clusterizar_volume()
        maior_cluster = clusters[0][0] if clusters else None

        absorcao = self.detectar_absorcao(maior_cluster, candle_trades) if maior_cluster else False

        if delta > 0 and absorcao:
            return {"acao": "buy", "motivo": f"Delta+ Absorção em {maior_cluster}"}
        elif delta < 0 and absorcao:
            return {"acao": "sell", "motivo": f"Delta- Absorção em {maior_cluster}"}
        elif delta > 0:
            return {"acao": "buy", "motivo": f"Delta positivo: {delta}"}
        elif delta < 0:
            return {"acao": "sell", "motivo": f"Delta negativo: {delta}"}
        else:
            return {"acao": "hold", "motivo": "Order Flow neutro"}

    def _preco_valido(self, preco):
        """Só aceita preço de zona/order flow dentro do range institucional."""
        if self.max_high is None or self.min_low is None:
            return True  # Se range não disponível, não filtra
        min_limit = self.min_low * (1 - self.tolerancia)
        max_limit = self.max_high * (1 + self.tolerancia)
        return min_limit <= preco <= max_limit
