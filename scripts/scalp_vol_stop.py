"""
Scalp de volatilidade com STOP MAIS LARGO (pedido do usuário em 13/09/2026, depois de ver o resultado).

    python scripts/scalp_vol_stop.py

Mesmos eventos, mesmas zonas, execução em 1 min (cache de scripts/scalp_vol_1m.py). Variantes fixadas antes de rodar:
stop 1x (a regra original), 1,5x, 2x e 3x a distância original.
    A: alvo 2R e realização em 1R acompanham o stop maior
    B: alvo continua na outra borda do vácuo; só o stop se afasta
Atenção: a variação nasceu DEPOIS de ver o holdout — todas as variantes são mostradas, nenhuma é escolhida por aqui.
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.scalp_volatilidade import ParametrosScalpVol, resumo, simular  # noqa: E402
from scripts.backtest_scalp_vol import PERIODOS, linha, ms  # noqa: E402
from scripts.scalp_vol_1m import CACHE, MIN_MS  # noqa: E402


def main():
    ev = pd.read_csv(os.path.join("data", "estudo_scalp_vol.csv"))
    um = pd.read_csv(CACHE).reset_index(drop=True)
    ts1 = um["timestamp"].to_numpy(np.int64)
    h1, l1, c1 = (um[k].to_numpy(float) for k in ("high", "low", "close"))
    fds1 = pd.to_datetime(ts1, unit="ms").dayofweek.to_numpy() >= 5
    pos = {int(t): i for i, t in enumerate(ts1)}
    for jogada in ("A", "B"):
        linhas = ev[ev["jogada"] == jogada].to_dict("records")
        for mult in (1.0, 1.5, 2.0, 3.0):
            p = dataclasses.replace(ParametrosScalpVol(), janela_barras=120, tempo_barras=60, mult_stop=mult)
            tr = []
            for row in linhas:
                i = pos.get(int(row["ts"]) + 4 * MIN_MS)
                if i is None:
                    continue
                r = simular(i, ts1, h1, l1, c1, fds1, (row["zona_lo"], row["zona_hi"]), int(row["lado_impulso"]),
                            jogada, p, barra_ms=MIN_MS)
                if r is not None:
                    tr.append(r)
            print(f"\njogada {jogada} · stop {mult:g}x")
            for rot, ini, fim in PERIODOS:
                sel = [x for x in tr if x["ts"] >= ms(ini) and (fim is None or x["ts"] < ms(fim))]
                print(linha(rot, resumo(sel)))


if __name__ == "__main__":
    main()
