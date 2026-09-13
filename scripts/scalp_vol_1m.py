"""
Refaz o scalp de volatilidade com candles de 1 MINUTO na execução (mesmos eventos, mesmas zonas).

    python scripts/scalp_vol_1m.py

Por quê: com candles de 5 min, o candle da entrada muitas vezes contém a entrada E o stop, e a regra conservadora
conta stop. Na jogada B isso foi 42% dos trades — o preço desce até a borda vindo de cima, então a máxima do candle
pode ter acontecido ANTES da entrada. Aqui a detecção e o perfil continuam em 5 min (como combinado), e só a execução
desce para 1 min, onde essa ambiguidade quase some.

Lê os eventos de data/estudo_scalp_vol.csv (gerado por scripts/backtest_scalp_vol.py), baixa só as janelas de 3 h de
cada evento da API pública da Binance e guarda em data/historico/BTCUSDT_binance_1m_eventos.csv.gz.
"""
import dataclasses
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.scalp_volatilidade import ParametrosScalpVol, resumo, simular  # noqa: E402
from scripts.backtest_scalp_vol import PERIODOS, linha, ms  # noqa: E402

MIN_MS = 60_000
BARRAS_JANELA = 190                       # 5 min da detecção + 120 de espera + 60 de trade + folga
CACHE = os.path.join("data", "historico", "BTCUSDT_binance_1m_eventos.csv.gz")
URL = "https://api.binance.com/api/v3/klines"
COLS = ["timestamp", "open", "high", "low", "close", "volume"]


def baixar(inicios):
    tem = pd.read_csv(CACHE) if os.path.exists(CACHE) else pd.DataFrame(columns=COLS)
    feitos = set(tem["timestamp"].astype("int64")) if len(tem) else set()
    faltam = [t for t in inicios if t not in feitos]
    print(f"{len(inicios)} janelas de evento; {len(faltam)} para baixar")
    novos = []
    for n, t in enumerate(faltam, 1):
        for tentativa in range(4):
            try:
                r = requests.get(URL, params={"symbol": "BTCUSDT", "interval": "1m", "startTime": t,
                                              "limit": BARRAS_JANELA}, timeout=20)
                r.raise_for_status()
                novos += [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in r.json()]
                break
            except Exception as e:
                print(f"  janela {t}: {type(e).__name__}, nova tentativa")
                time.sleep(2 * (tentativa + 1))
        time.sleep(0.12)
        if n % 250 == 0:
            print(f"  {n}/{len(faltam)} janelas")
    if not novos:
        return tem
    tudo = pd.concat([tem, pd.DataFrame(novos, columns=COLS)]).drop_duplicates("timestamp").sort_values("timestamp")
    tudo.to_csv(CACHE, index=False)
    return tudo


def por_periodo(trades):
    for rot, ini, fim in PERIODOS:
        sel = [x for x in trades if x["ts"] >= ms(ini) and (fim is None or x["ts"] < ms(fim))]
        print(linha(rot, resumo(sel)))


def main():
    ev = pd.read_csv(os.path.join("data", "estudo_scalp_vol.csv"))
    um = baixar(sorted({int(t) for t in ev["ts"]})).reset_index(drop=True)
    ts1 = um["timestamp"].to_numpy(np.int64)
    h1, l1, c1 = (um[k].to_numpy(float) for k in ("high", "low", "close"))
    fds1 = pd.to_datetime(ts1, unit="ms").dayofweek.to_numpy() >= 5
    pos = {int(t): i for i, t in enumerate(ts1)}
    p1 = dataclasses.replace(ParametrosScalpVol(), janela_barras=120, tempo_barras=60)

    saida = []
    for jogada in ("A", "B"):
        linhas = ev[ev["jogada"] == jogada]
        em_5m = linhas.to_dict("records")
        em_1m, sem_dado = [], 0
        for row in em_5m:
            i = pos.get(int(row["ts"]) + 4 * MIN_MS)          # último minuto do candle de 5 min da detecção
            if i is None:
                sem_dado += 1
                continue
            r = simular(i, ts1, h1, l1, c1, fds1, (row["zona_lo"], row["zona_hi"]), int(row["lado_impulso"]),
                        jogada, p1, barra_ms=MIN_MS)
            if r is not None:
                r["mesmo_candle"] = r["i_saida"] == r["i_entrada"]
                em_1m.append(r)
                saida.append(r)
        mesmo = sum(1 for r in em_1m if r["mesmo_candle"])
        print(f"\njogada {jogada} · execução em 5 min (os mesmos eventos)")
        por_periodo(em_5m)
        print(f"jogada {jogada} · execução em 1 min  ({sem_dado} sem dado de 1 min; stop no próprio minuto da entrada: "
              f"{mesmo} de {len(em_1m)} = {mesmo / max(len(em_1m), 1):.0%})")
        por_periodo(em_1m)
    pd.DataFrame(saida).to_csv(os.path.join("data", "estudo_scalp_vol_1m.csv"), index=False)


if __name__ == "__main__":
    main()
