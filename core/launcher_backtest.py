# launcher_backtest.py

from binance_csv_normalizer import BinanceCSVNormalizer
from backtest_engine import BacktestEngine

def rodar_normalizacao():
    print("📦 Normalizando arquivos CSV da Binance...")
    normalizador = BinanceCSVNormalizer(
        pasta_csv_bruto="binance_csv", 
        arquivo_saida="binance_csv/btcusdt_1h_unificado.csv"
    )
    normalizador.normalizar_e_unificar()

def rodar_backtest():
    print("⚙️ Executando backtest...")
    engine = BacktestEngine("binance_csv/btcusdt_1h_unificado.csv")
    resultado = engine.executar()
    resultado.to_csv("binance_csv/resultado_backtest.csv", index=False)
    print("✅ Resultado salvo em: binance_csv/resultado_backtest.csv")

if __name__ == "__main__":
    rodar_normalizacao()
    rodar_backtest()
