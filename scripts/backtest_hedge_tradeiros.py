"""
HEDGE DE CARTEIRA DO TRADEIROS no inverse, ano a ano, medido em BTC contra só segurar.

    python scripts/backtest_hedge_tradeiros.py

Carteira de 1 BTC. O hedge vende em escada na resistência de um range válido (até 35% da carteira), recompra
metade no POC e o resto no VAL, fecha no rompimento e recebe (ou paga) o funding do contrato inverse da Bybit.
Cada ano começa de novo com 1 BTC. Sensibilidade: 20% e 40% da carteira no total, sem funding,
stop só por preço (sem a aceitação) e sem stop nenhum.
"""
import datetime as dt
import json
import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.hedge_tradeiros import BacktestHedgeTradeiros, ParametrosHedge  # noqa: E402
from core.tpo_sessao import blocos_30m  # noqa: E402


def ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def main():
    df = pd.read_csv(os.path.join("data", "historico", "BTCUSDT_binance_15m.csv")).sort_values("timestamp")
    df = df[df["timestamp"] >= ms("2018-11-01")]
    bl = blocos_30m(df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist())
    fund = {int(k): float(v) for k, v in json.load(open(os.path.join("data", "historico", "funding_bybit.json")))["inverse"].items()}
    variantes = {
        "35% (padrão)": ParametrosHedge(),
        "20%": ParametrosHedge(fatia=0.05),
        "40%": ParametrosHedge(fatia=0.10),
        "35% sem funding": ParametrosHedge(funding=False),
        "35% stop só preço": ParametrosHedge(stop="preco"),
        "35% sem stop": ParametrosHedge(stop="nenhum"),
    }
    anos = list(range(2019, 2027))
    print(f"{'ano':<6}" + "".join(f"{n:>20}" for n in variantes) + f"{'vendas/recompras/stops':>26}{'funding':>10}")
    total = {n: 1.0 for n in variantes}
    for ano in anos:
        linha, extra = f"{ano:<6}", ""
        for n, p in variantes.items():
            r = BacktestHedgeTradeiros(bl, fund, p).executar(ms(f"{ano}-01-01"), ms(f"{ano + 1}-01-01"))
            total[n] *= r["btc_final"]
            linha += f"{r['ganho_btc_pct']:>+19.2f}%"
            if n == "35% (padrão)":
                extra = f"{r['vendas']:>12}/{r['recompras']}/{r['stops']}({r['stops_aceitacao']} aceit.){'':<2}{r['funding_btc'] * 100:>+9.2f}%"
        print(linha + extra)
    print(f"{'total':<6}" + "".join(f"{(v - 1) * 100:>+19.2f}%" for v in total.values()))
    print("\n(ganho em BTC sobre só segurar; a grade atual do robô 8 deu -3,40% em BTC de 2019 até hoje)")


if __name__ == "__main__":
    main()
