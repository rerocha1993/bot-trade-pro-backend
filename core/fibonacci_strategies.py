# core/fibonacci_strategies.py
"""
Estratégias de SL/TP baseadas em Fibonacci sobre o ÚLTIMO swing relevante, sempre direcionais.

Uso:
    fs = FibonacciStrategies(ohlcv)
    fs.generico("buy")          -> {'sl': ..., 'tp': ..., 'fonte': 'fibonacci', ...}
    fs.para_fase("onda_3", "buy")
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

from core.fibonacci import Fibonacci
from core.utils_indicadores import atr


class FibonacciStrategies:
    def __init__(self, ohlcv: Sequence, janela: int = 100):
        if not ohlcv:
            raise ValueError("ohlcv vazio")
        self.ohlcv = list(ohlcv)[-janela:]
        self.highs = [float(c[2]) for c in self.ohlcv]
        self.lows = [float(c[3]) for c in self.ohlcv]
        self.closes = [float(c[4]) for c in self.ohlcv]
        self.high = max(self.highs)
        self.low = min(self.lows)
        self.idx_high = self.highs.index(self.high)
        self.idx_low = self.lows.index(self.low)
        self.atr = atr(self.ohlcv, 14) or 0.0
        self.preco_atual = self.closes[-1]

    # -------------------------------------------------------------- swing base
    def swing(self, direcao: str) -> Fibonacci:
        """
        buy  -> swing de alta: do fundo até o topo posterior (ou o topo mais recente).
        sell -> swing de baixa: do topo até o fundo posterior.
        """
        if direcao == "buy":
            base_low = self.low
            topo_posterior = max(self.highs[self.idx_low:]) if self.idx_low < len(self.highs) else self.high
            return Fibonacci.de_swing(base_low, topo_posterior)
        base_high = self.high
        fundo_posterior = min(self.lows[self.idx_high:]) if self.idx_high < len(self.lows) else self.low
        return Fibonacci.de_swing(base_high, fundo_posterior)

    # --------------------------------------------------------------- por fase
    def _montar(self, direcao: str, sl: Optional[float], tp: Optional[float], contexto: str) -> Dict:
        return self._validar_sl_tp({"sl": sl, "tp": tp, "fonte": "fibonacci", "contexto": contexto}, direcao)

    def retracao_onda2(self, direcao: str = "buy") -> Dict:
        fib = self.swing(direcao)
        # Onda 2 costuma parar em 50-61.8%; SL abaixo de 78.6% (a invalidação é 100%)
        return self._montar(direcao, fib.retracao(0.786), fib.extensao(1.618), "onda_2")

    def extensao_onda3(self, direcao: str = "buy") -> Dict:
        fib = self.swing(direcao)
        return self._montar(direcao, fib.retracao(0.618), fib.extensao(1.618), "onda_3")

    def retracao_onda4(self, direcao: str = "buy") -> Dict:
        fib = self.swing(direcao)
        return self._montar(direcao, fib.retracao(0.5), fib.extensao(1.0), "onda_4")

    def extensao_onda5(self, direcao: str = "buy") -> Dict:
        fib = self.swing(direcao)
        return self._montar(direcao, fib.retracao(0.382), fib.extensao(1.272), "onda_5")

    def correcao_c(self, direcao: str = "sell") -> Dict:
        fib = self.swing(direcao)
        return self._montar(direcao, fib.retracao(0.618), fib.extensao(1.0), "correcao_c")

    def generico(self, direcao: str = "buy") -> Dict:
        fib = self.swing(direcao)
        return self._montar(direcao, fib.retracao(0.618), fib.extensao(1.618), "generico")

    def para_fase(self, fase_onda: Optional[str], direcao: str) -> Dict:
        fase = (fase_onda or "").lower()
        if "onda_2" in fase:
            return self.retracao_onda2(direcao)
        if "onda_3" in fase:
            return self.extensao_onda3(direcao)
        if "onda_4" in fase:
            return self.retracao_onda4(direcao)
        if "onda_5" in fase:
            return self.extensao_onda5(direcao)
        if "correcao_c" in fase:
            return self.correcao_c(direcao)
        return self.generico(direcao)

    # ------------------------------------------------------------- validação
    def _validar_sl_tp(self, resultado: Dict, direcao: str) -> Dict:
        """
        Garante coerência direcional com o preço atual:
        buy  -> sl < preco < tp ; sell -> tp < preco < sl.
        Se o SL ficar do lado errado (preço já passou do nível), usa fallback por ATR.
        """
        preco = self.preco_atual
        sl, tp = resultado.get("sl"), resultado.get("tp")
        fallback_sl = 1.5 * self.atr if self.atr else preco * 0.01
        if direcao == "buy":
            if sl is None or sl >= preco:
                resultado["sl"] = round(preco - fallback_sl, 2)
                resultado["sl_fallback"] = True
            if tp is None or tp <= preco:
                resultado["tp"] = None
        else:
            if sl is None or sl <= preco:
                resultado["sl"] = round(preco + fallback_sl, 2)
                resultado["sl_fallback"] = True
            if tp is None or tp >= preco:
                resultado["tp"] = None
        return resultado
