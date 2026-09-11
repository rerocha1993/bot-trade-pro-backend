"""
Backtest do jogo do range do Tradeiros (core/range_tradeiros.py) no BTC, blocos de 30 min.

    python scripts/backtest_range.py
    python scripts/backtest_range.py --desde 2019-06-01

Seis variantes fixadas ANTES de rodar: jogada (borda, desvio, reteste) x gestão (tradeiros = metade no POC/1:1 e
stop no zero a zero; sem = segura até o alvo ou o stop). Cada uma roda uma vez no período inteiro e o resultado é
separado em treino, validação e holdout (este só é olhado no fim).
"""
import argparse
import datetime as dt
import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.range_tradeiros import BacktestRange, resumo  # noqa: E402
from core.tpo_sessao import blocos_30m  # noqa: E402

PERIODOS = (("treino", "2020-01-01", "2023-07-01"), ("validação", "2023-07-01", "2025-01-01"), ("HOLDOUT", "2025-01-01", None))


def ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def linha(rot, r):
    if not r["trades"]:
        return f"    {rot:<10} sem trades"
    return (f"    {rot:<10} {r['trades']:>4} trades  acerto {r['acerto']:>4.0%}  médio {r['medio_r']:+.4f}R  soma {r['soma_r']:+7.1f}R  "
            f"FL {r['fator_lucro']}  | compra {r['n_compra']} {r['compra_r']:+.1f}R, venda {r['n_venda']} {r['venda_r']:+.1f}R  | {r['saidas']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2019-10-01")
    a = ap.parse_args()
    df = pd.read_csv(os.path.join("data", "historico", "BTCUSDT_binance_15m.csv")).sort_values("timestamp")
    df = df[df["timestamp"] >= ms(a.desde)]
    blocos = blocos_30m(df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist())
    print(f"{len(blocos)} blocos de 30 min desde {a.desde}")
    for jogada in ("borda", "desvio", "reteste"):
        for gestao in ("tradeiros", "sem"):
            r = BacktestRange(blocos, jogada, gestao).executar(ms("2020-01-01"))
            print(f"\n{jogada} · gestão {gestao}")
            anos = {}
            for t in r["lista"]:
                y = dt.datetime.fromtimestamp(t["ts"] / 1000, dt.timezone.utc).year
                anos[y] = round(anos.get(y, 0) + t["liquido_r"], 1)
            for rot, ini, fim in PERIODOS:
                sel = [t for t in r["lista"] if t["ts"] >= ms(ini) and (fim is None or t["ts"] < ms(fim))]
                print(linha(rot, resumo(sel)))
            print(f"    por ano: {anos}")


if __name__ == "__main__":
    main()
