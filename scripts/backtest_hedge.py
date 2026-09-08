# scripts/backtest_hedge.py
"""
Backtest do dial de hedge (carteira 100% BTC; short inverso só como proteção) em 4h desde um ano.
    python scripts/backtest_hedge.py --desde 2017 [--exaustao 0.35]
"""
import argparse
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.backtest_hedge import BacktestHedge  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2017)
    ap.add_argument("--exaustao", type=float, default=0.35)
    args = ap.parse_args()
    df = pd.read_csv(os.path.join("data", "historico", "BTCUSD_bitstamp_4h.csv")).sort_values("timestamp")
    h4 = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
    desde = int(datetime(args.desde, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    bt = BacktestHedge(h4, desde_ms=desde, exaustao_minima=args.exaustao)
    res = bt.executar()
    print({k: v for k, v in res.items()})
    print(bt.por_ano().to_string())
    modos = pd.DataFrame(bt.eventos)
    if not modos.empty:
        print(modos.modo.value_counts().to_string())


if __name__ == "__main__":
    main()
