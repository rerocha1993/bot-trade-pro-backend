# core/risk_manager.py
"""Limites de risco por dia e cálculo de stop por tipo (percentual, ATR, candle, fibonacci)."""
from core.utils_indicadores import atr


class RiskManager:
    def __init__(self, config: dict):
        self.config = config
        self.trades_realizados = 0
        self.perda_acumulada = 0.0

    def pode_operar(self):
        if self.trades_realizados >= self.config.get("max_trades_dia", 10):
            return False, "Limite de trades diário atingido"
        if self.perda_acumulada >= self.config.get("max_perda_dia", float("inf")):
            return False, "Limite de perda diária atingido"
        return True, ""

    def registrar_trade(self, resultado: float):
        self.trades_realizados += 1
        if resultado < 0:
            self.perda_acumulada += abs(resultado)

    def calcular_stop_loss(self, preco_entrada, direcao="buy", dados=None, fib=None, candle_anterior=None):
        tipo = self.config.get("sl_tipo", "percentual")
        s = 1 if direcao == "buy" else -1
        if tipo == "fibonacci" and fib is not None:
            nivel = fib.retracao(0.618)
            if (direcao == "buy" and nivel < preco_entrada) or (direcao == "sell" and nivel > preco_entrada):
                return nivel
        if tipo in ("volatilidade", "atr") and dados:
            a = atr(dados, 14)
            if a:
                return preco_entrada - s * self.config.get("atr_mult", 1.5) * a
        if tipo == "candle" and candle_anterior:
            return candle_anterior[3] if direcao == "buy" else candle_anterior[2]
        variacao = preco_entrada * (self.config.get("sl_variacao_pct", 1.0) / 100)
        return round(preco_entrada - s * variacao, 2)
