# scripts/backtest.py
"""
Backtest da estratégia.
    python scripts/backtest.py --fonte csv --tf 1h --estilo daytrade --perfil conservador
    python scripts/backtest.py --fonte bybit --tf 15m --dias 30 --estilo scalping --perfil turbo
"""
import argparse
import json
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.backtest_engine import BacktestEngine, bot_padrao, carregar_binance_csv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonte", default="csv", choices=["csv", "bybit"])
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--dias", type=int, default=60)
    ap.add_argument("--estilo", default="daytrade")
    ap.add_argument("--perfil", default="conservador")
    ap.add_argument("--passo", type=int, default=1)
    ap.add_argument("--banca", type=float, default=10000)
    ap.add_argument("--risco", type=float, default=0.01)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--saida", default="data/backtest_trades.csv")
    args = ap.parse_args()

    if args.fonte == "csv":
        ohlcv = carregar_binance_csv("binance_csv")
    else:
        from core.conexoes.conexao_bybit import BybitConnector
        con = BybitConnector("simulador")
        since = int((time.time() - args.dias * 86400) * 1000)
        ohlcv = con.obter_ohlcv_historico("BTCUSDT", args.tf, since)
    bot = bot_padrao(timeframe=args.tf, estilo_trade=args.estilo, confluencia_tipo=args.perfil, banca=args.banca, risco_pct=args.risco)
    bt = BacktestEngine(ohlcv, bot, timeframe=args.tf, passo=args.passo, verbose=args.verbose)
    r = bt.executar()
    trades = r.pop("lista_trades")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    os.makedirs(os.path.dirname(args.saida), exist_ok=True)
    bt.salvar_resultado(args.saida)
    print(f"{len(trades)} trades salvos em {args.saida}")


if __name__ == "__main__":
    main()
