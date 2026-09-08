# scripts/detectar_pontos.py
"""Roda o detector de pontos institucionais (TPO/VP/VWAP/OrderFlow/OrderBlocks) para os pares cadastrados."""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.detector_institucional import run_detector  # noqa: E402
from core.market_data import MarketDataAggregator  # noqa: E402

if __name__ == "__main__":
    print("pontos registrados/atualizados:", run_detector(market_data=MarketDataAggregator("tradingview")))
