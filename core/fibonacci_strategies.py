# Arquivo: core/fibonacci_strategies.py

from core.fibonacci import Fibonacci

class FibonacciStrategies:
    def __init__(self, ohlcv):
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        self.high = max(highs)
        self.low = min(lows)
        self.fib = Fibonacci(self.high, self.low)
        self.levels = self.fib.levels

    def retracao_onda2(self):
        return self._validar_sl_tp({
            "sl": self.levels.get('78.6%'),
            "tp": self.levels.get('161.8%')
        })

    def retracao_onda4(self):
        return self._validar_sl_tp({
            "sl": self.levels.get('50.0%'),
            "tp": self.levels.get('100.0%')
        })

    def extensao_onda3(self):
        return self._validar_sl_tp({
            "sl": self.levels.get('61.8%'),
            "tp": self.levels.get('261.8%')
        })

    def extensao_onda5(self):
        return self._validar_sl_tp({
            "sl": self.levels.get('100.0%'),
            "tp": self.levels.get('161.8%')
        })

    def generico(self):
        return self._validar_sl_tp({
            "sl": self.levels.get('61.8%'),
            "tp": self.levels.get('161.8%')
        })

    def _validar_sl_tp(self, resultado):
        """Só retorna SL/TP se estiverem dentro do range institucional, ou retorna None."""
        # Permite TP > high se for extensão, mas nunca aceita SL/TP negativos ou fora do range extremo
        sl, tp = resultado.get("sl"), resultado.get("tp")
        max_limit = self.high * 1.02
        min_limit = self.low * 0.98
        if sl is not None and not (min_limit <= sl <= max_limit):
            resultado["sl"] = None
        if tp is not None and tp < 0:
            resultado["tp"] = None
        return resultado
