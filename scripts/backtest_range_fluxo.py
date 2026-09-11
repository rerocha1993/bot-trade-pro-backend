"""
JOGO DO RANGE + CONTEXTO DE ORDER FLOW: o filtro de "presos" (proporção long/short de contas) vira lucro?

    python scripts/backtest_range_fluxo.py

Regra fixada pelo estudo das bordas (scripts/estudo_bordas.py), ANTES deste teste:
    compra no VAL só com mais contas vendidas que a mediana de 30 dias; venda no VAH só com mais contas compradas.
Controle: o filtro invertido (entra só quando a multidão está do mesmo lado) — se ele também melhorar, o ganho é
só de operar menos, não do contexto.
"""
import datetime as dt
import json
import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.contexto_derivativos import ContextoLSR  # noqa: E402
from core.range_tradeiros import BacktestRange, resumo  # noqa: E402
from core.tpo_sessao import blocos_30m  # noqa: E402
from scripts.backtest_range import PERIODOS, linha, ms  # noqa: E402


def main():
    df = pd.read_csv(os.path.join("data", "historico", "BTCUSDT_binance_15m.csv")).sort_values("timestamp")
    df = df[df["timestamp"] >= ms("2020-06-01")]
    blocos = blocos_30m(df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist())
    lsr = ContextoLSR(json.load(open(os.path.join("data", "historico", "lsr_bybit_1h.json"))))
    presos = lsr.filtro()
    inverso = (lambda ts, lado: not presos(ts, lado) and lsr.presos_contra(ts + 1_800_000, lado) is not None)
    inicio = ms("2020-09-01")                       # 30 dias de dado de long/short + uma semana de folga
    for jogada in ("borda", "desvio"):
        for rot_f, f in (("sem filtro", None), ("com presos do outro lado", presos), ("controle invertido", inverso)):
            r = BacktestRange(blocos, jogada, "tradeiros", filtro=f).executar(inicio)
            print(f"\n{jogada} · gestão tradeiros · {rot_f}")
            anos = {}
            for t in r["lista"]:
                y = dt.datetime.fromtimestamp(t["ts"] / 1000, dt.timezone.utc).year
                anos[y] = round(anos.get(y, 0) + t["liquido_r"], 1)
            for rot, ini, fim in PERIODOS:
                sel = [t for t in r["lista"] if t["ts"] >= max(ms(ini), inicio) and (fim is None or t["ts"] < ms(fim))]
                print(linha(rot, resumo(sel)))
            print(f"    por ano: {anos}")


if __name__ == "__main__":
    main()
