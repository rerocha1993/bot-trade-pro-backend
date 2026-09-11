"""
Reconstrói TODAS as contagens de Elliott de cada candle do histórico, sem olhar o futuro, e grava em disco.

    python scripts/cenarios_historicos.py --tf 4h --desde 2021-06-01
    python scripts/cenarios_historicos.py --tf 1h --desde 2021-10-01

Mesmo pipeline da calibração (zigzag por ATR + ScenarioEngine numa janela de 300 candles fechados), mas guarda o
conjunto inteiro de cada candle — viés, próximo movimento, probabilidade, invalidação e alvos — em vez de uma
linha por contagem com o resultado. É o que a regra de assimetria precisa: olhar o GRUPO de contagens que faz o
mesmo movimento, e não uma contagem de cada vez.

Saída: data/cenarios/<tf>.jsonl.gz, uma linha por candle: {"ts", "close", "atr", "cenarios": [...]}
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys
import time

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.elliott_pro.pivots import zigzag_atr  # noqa: E402
from core.elliott_pro.scenarios import ScenarioEngine  # noqa: E402
from core.utils_indicadores import atr as calc_atr  # noqa: E402

FONTES = {"1d": "BTCUSD_bitstamp_1d.csv", "4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv",
          "15m": "BTCUSDT_binance_15m.csv"}
FATOR = {"1d": 2.2, "4h": 2.2, "1h": 2.0, "15m": 2.0}   # os mesmos da calibração
JANELA = 300
PASTA = os.path.join("data", "cenarios")


def candles(tf: str):
    df = pd.read_csv(os.path.join("data", "historico", FONTES[tf])).sort_values("timestamp")
    return df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="4h", choices=list(FONTES))
    ap.add_argument("--desde", default="2021-06-01", help="primeiro candle avaliado (a janela de 300 vem de antes)")
    a = ap.parse_args()
    dados = [[int(c[0])] + [float(x) for x in c[1:6]] for c in candles(a.tf)]
    desde = int(dt.datetime.fromisoformat(a.desde).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    ini = next(i for i, c in enumerate(dados) if c[0] >= desde)
    ini = max(ini, JANELA)
    os.makedirs(PASTA, exist_ok=True)
    caminho = os.path.join(PASTA, f"{a.tf}.jsonl.gz")
    t0, n = time.time(), 0
    with gzip.open(caminho, "wt", encoding="utf-8") as f:
        for i in range(ini, len(dados)):
            win = dados[i - JANELA + 1:i + 1]
            preco = win[-1][4]
            try:
                piv, limiar = zigzag_atr(win, fator_atr=FATOR[a.tf])
                atr_v = calc_atr(win, 14) or 0.0
                res = ScenarioEngine(piv, preco, limiar, atr_v).analisar()
            except Exception:
                continue
            cen = [{"vies": c["vies"], "direcao": c["direcao_trade"], "fase": c["fase"], "padrao": c["padrao"],
                    "prob": c["probabilidade"], "inv": c["invalidacao"], "alvos": c["alvos"][:3]}
                   for c in res.get("cenarios", [])[:8] if c.get("invalidacao") is not None and c.get("alvos")]
            f.write(json.dumps({"ts": win[-1][0], "close": preco, "atr": atr_v, "cenarios": cen}) + "\n")
            n += 1
            if n % 2000 == 0:
                print(f"  {a.tf}: {n} candles ({time.time() - t0:.0f}s)", flush=True)
    print(f"{n} candles de {a.tf} em {time.time() - t0:.0f}s -> {caminho}")


if __name__ == "__main__":
    main()
