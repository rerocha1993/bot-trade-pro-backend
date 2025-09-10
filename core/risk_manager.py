# Arquivo: trading_bot/core/risk_manager.py

class RiskManager:
    def __init__(self, config):
        """
        config: dicionário com parâmetros de risco, ex:
        {
            "max_trades_dia": 5,
            "max_perda_dia": 100.0,
            "sl_tipo": "fibonacci",  # ou 'volatilidade' ou 'candle'
            "sl_variacao_pct": 1.0
        }
        """
        self.config = config
        self.trades_realizados = 0
        self.perda_acumulada = 0.0

    def pode_operar(self):
        if self.trades_realizados >= self.config["max_trades_dia"]:
            return False, "Limite de trades diário atingido"
        if self.perda_acumulada >= self.config["max_perda_dia"]:
            return False, "Limite de perda diária atingido"
        return True, ""

    def registrar_trade(self, resultado):
        self.trades_realizados += 1
        if resultado < 0:
            self.perda_acumulada += abs(resultado)

    def calcular_stop_loss(self, preco_entrada, dados=None, fib=None, candle_anterior=None):
        tipo = self.config.get("sl_tipo")

        if tipo == "fibonacci" and fib:
            return fib.levels.get("61.8%")

        elif tipo == "volatilidade" and dados:
            ultimos = [c[4] for c in dados[-5:]]  # fechamento
            media = sum(ultimos) / len(ultimos)
            desvio = max(ultimos) - min(ultimos)
            return preco_entrada - desvio

        elif tipo == "candle" and candle_anterior:
            return candle_anterior[3]  # low do candle anterior

        else:  # fallback percentual
            variacao = preco_entrada * (self.config["sl_variacao_pct"] / 100)
            return round(preco_entrada - variacao, 2)

# Exemplo de uso:
if __name__ == "__main__":
    config = {
        "max_trades_dia": 5,
        "max_perda_dia": 150.0,
        "sl_tipo": "fibonacci",
        "sl_variacao_pct": 1.2
    }

    from core.fibonacci import Fibonacci

    fib = Fibonacci(high=25500, low=24500)
    risk = RiskManager(config)

    pode, motivo = risk.pode_operar()
    print("Pode operar?", pode, "| Motivo:", motivo)

    stop = risk.calcular_stop_loss(25200, fib=fib)
    print("Stop Loss sugerido:", stop)
