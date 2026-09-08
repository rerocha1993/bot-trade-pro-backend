# scripts/testar_bybit.py
"""Diagnóstico de conectividade Bybit nos três modos + cesta multi-exchange + sentimento."""
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.conexoes.conexao_bybit import BybitConnector  # noqa: E402


def main():
    for modo in ("simulador", "testnet", "real"):
        if modo == "real" and "--real" not in sys.argv:
            print("real: pulado (use --real para testar a chave da mainnet; somente leitura de saldo)")
            continue
        try:
            print(f"== {modo}:", json.dumps(BybitConnector(modo).testar_conexao(), indent=2, default=str, ensure_ascii=False))
        except Exception as e:
            print(f"== {modo}: ERRO {e}")
    from core.market_data import MarketDataAggregator
    agg = MarketDataAggregator("tradingview")
    velas = agg.ohlcv_composto("BTCUSDT", "15m", 5)
    print("== cesta TradingView+Bybit:", agg.status(), "| última vela composta:", velas[-1] if velas else None)
    from core.sentimento_mercado import SentimentoMercado
    print("== sentimento:", json.dumps(SentimentoMercado().score("BTCUSDT"), default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
