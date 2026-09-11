"""
A memória de situações (RAG) prevê alguma coisa? Teste no histórico, antes de gastar uma chamada de API.

    python scripts/ia_memoria.py --tf 4h

Para cada candle do período de teste, busca as k situações mais parecidas cujo desfecho JÁ ERA CONHECIDO
naquele momento e usa o retorno médio delas como previsão. Mede:
    - correlação entre a previsão e o que de fato aconteceu
    - acerto do lado (subiu/caiu) contra a taxa base
    - uma estratégia simples: compra se os vizinhos sobem em média, vende se caem, segura H candles, com custo
Se a memória não prever nada aqui, mostrar vizinhos ao Claude é mostrar ruído — e isso muda o papel dele.
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.executor_real import TAXA_TAKER  # noqa: E402
from core.ia.memoria import Memoria, Situacao, desfecho, vetor_situacao  # noqa: E402

FONTES = {"4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv"}
DUR = {"4h": 14_400_000, "1h": 3_600_000}
HORIZONTE = {"4h": 30, "1h": 48}       # 5 dias no 4h, 2 dias no 1h


def ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def situacoes(tf: str):
    df = pd.read_csv(os.path.join("data", "historico", FONTES[tf])).sort_values("timestamp")
    c = df[["timestamp", "open", "high", "low", "close", "volume"]].values
    pos = {int(t): i for i, t in enumerate(c[:, 0])}
    ant = np.r_[c[0, 4], c[:-1, 4]]
    tr = np.maximum(c[:, 2] - c[:, 3], np.maximum(np.abs(c[:, 2] - ant), np.abs(c[:, 3] - ant)))
    atr_l = pd.Series(tr).ewm(alpha=1 / 100, adjust=False).mean().values
    H = HORIZONTE[tf]
    out = []
    with gzip.open(os.path.join("data", "cenarios", f"{tf}.jsonl.gz"), "rt", encoding="utf-8") as f:
        for linha in f:
            x = json.loads(linha)
            i = pos.get(int(x["ts"]))
            if i is None or i < 40:
                continue
            v = vetor_situacao(x["cenarios"], c[i - 40:i + 1, 4], x["atr"], atr_l[i])
            fut = c[i + 1:i + 1 + H]
            des = desfecho(fut.tolist(), float(c[i, 4]), x["atr"]) if len(fut) == H else None
            out.append(Situacao(int(x["ts"]), v, float(c[i, 4]), "", des, int(x["ts"]) + H * DUR[tf]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="4h", choices=list(FONTES))
    ap.add_argument("--teste", default="2024-07-01")
    ap.add_argument("--k", type=int, default=20)
    a = ap.parse_args()
    s = situacoes(a.tf)
    mem = Memoria(s)
    teste = [x for x in s if x.ts >= ms(a.teste) and x.desfecho is not None]
    print(f"{a.tf}: {len(mem)} situações com desfecho | teste desde {a.teste}: {len(teste)} candles | k={a.k} | horizonte {HORIZONTE[a.tf]} candles")
    prev, real = [], []
    for x in teste:
        viz = mem.vizinhos(x.vetor, a.k, ate_ts=x.ts)
        if len(viz) < a.k:
            continue
        prev.append(np.mean([v["desfecho"]["ret_pct"] for v in viz]))
        real.append(x.desfecho["ret_pct"])
    prev, real = np.array(prev), np.array(real)
    corr = float(np.corrcoef(prev, real)[0, 1])
    acerto = float(np.mean(np.sign(prev) == np.sign(real)))
    base = max(float(np.mean(real > 0)), float(np.mean(real < 0)))
    print(f"correlação previsão x real: {corr:+.3f} | acerto do lado {acerto:.1%} (taxa base {base:.1%})")
    # estratégia sem sobreposição: a cada H candles, segue o sinal dos vizinhos, com custo taker de ida e volta
    H = HORIZONTE[a.tf]
    for limiar in (0.0, 0.5, 1.0):
        res = []
        for j in range(0, len(prev), H):
            if abs(prev[j]) <= limiar:
                continue
            lado = np.sign(prev[j])
            res.append(lado * real[j] - 2 * TAXA_TAKER * 100)
        if res:
            print(f"  segue os vizinhos quando |previsão| > {limiar:.1f}%: {len(res)} trades, médio {np.mean(res):+.2f}% "
                  f"(desvio {np.std(res):.2f}%), soma {np.sum(res):+.1f}%, acerto {np.mean(np.array(res) > 0):.0%}")


if __name__ == "__main__":
    main()
