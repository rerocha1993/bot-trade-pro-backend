# scripts/calibrar_elliott.py
"""
Calibra as probabilidades dos cenários de Elliott com o histórico baixado por scripts/baixar_historico.py.

    python scripts/calibrar_elliott.py                       # 1d, 4h, 1h (Bitstamp 2012+) + 15m (Binance 2017+)
    python scripts/calibrar_elliott.py --tf 1h 4h --passo 2
    python scripts/calibrar_elliott.py --teste 2024-01-01    # treina antes da data, avalia depois (fora da amostra)

Saída: data/calibracao_elliott.json (modelo usado pelo bot) e data/calibracao_dataset.csv (amostras).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.elliott_pro.calibracao import ARQUIVO_PADRAO, Calibrador, construir_dataset, salvar_modelo, treinar, vetor  # noqa: E402

FONTES = {"1d": "BTCUSD_bitstamp_1d.csv", "4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv",
          "15m": "BTCUSDT_binance_15m.csv", "5m": "BTCUSDT_binance_5m.csv"}
HORIZONTE = {"1d": 40, "4h": 60, "1h": 72, "15m": 96, "5m": 120}
PASSO = {"1d": 1, "4h": 1, "1h": 2, "15m": 4, "5m": 8}
FATOR = {"1d": 2.2, "4h": 2.2, "1h": 2.0, "15m": 2.0, "5m": 1.8}


def carregar(tf):
    caminho = os.path.join("data", "historico", FONTES[tf])
    if not os.path.exists(caminho):
        return None
    df = pd.read_csv(caminho).sort_values("timestamp")
    return df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()


def avaliar(modelo, linhas, rotulo):
    if not linhas:
        return
    cal = Calibrador(modelo=modelo)
    p = np.array([cal.prob(f) for f in linhas]); y = np.array([f["y"] for f in linhas])
    acc = float(np.mean((p >= 0.5) == (y == 1)))
    ll = float(-np.mean(y * np.log(p + 1e-9) + (1 - y) * np.log(1 - p + 1e-9)))
    print(f"{rotulo}: {len(y)} amostras, taxa real {y.mean():.3f}, acurácia {acc:.3f}, logloss {ll:.3f}")
    ordem = np.argsort(p); m = len(y)
    for d in range(5):
        idx = ordem[d * m // 5:(d + 1) * m // 5]
        print(f"   quintil {d + 1}: previsto {p[idx].mean():.3f} | real {y[idx].mean():.3f} (n={len(idx)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", nargs="*", default=["1d", "4h", "1h", "15m"])
    ap.add_argument("--passo", type=int, default=None)
    ap.add_argument("--teste", default=None, help="data YYYY-MM-DD: treina antes, avalia depois")
    ap.add_argument("--saida", default=None)
    ap.add_argument("--par", default=None, help="outra moeda (histórico da Bybit via BacktestService, ex.: ETHUSDT)")
    ap.add_argument("--dias", type=int, default=1460, help="dias de histórico da Bybit quando --par é usado")
    args = ap.parse_args()
    if args.par:
        args.par = args.par.replace("/", "").upper()
        args.saida = args.saida or ARQUIVO_PADRAO.replace(".json", f"_{args.par}.json")
        from api.database import SessionLocal
        from services.backtest_service import BacktestService
        svc = BacktestService(SessionLocal)
    args.saida = args.saida or ARQUIVO_PADRAO

    todas = []
    for tf in args.tf:
        ohlcv = svc.historico(args.par, tf, args.dias) if args.par else carregar(tf)
        if not ohlcv:
            print(f"[{tf}] sem histórico em data/historico (rode scripts/baixar_historico.py)")
            continue
        t0 = time.time()
        print(f"[{tf}] {len(ohlcv)} candles de {datetime.fromtimestamp(ohlcv[0][0] / 1000, tz=timezone.utc):%Y-%m-%d} a {datetime.fromtimestamp(ohlcv[-1][0] / 1000, tz=timezone.utc):%Y-%m-%d}")
        linhas = construir_dataset(ohlcv, tf, fator_atr=FATOR[tf], horizonte=HORIZONTE[tf], passo=args.passo or PASSO[tf])
        print(f"[{tf}] {len(linhas)} amostras em {time.time() - t0:.0f}s")
        todas += linhas
    if not todas:
        print("nada para calibrar")
        return
    pd.DataFrame(todas).to_csv(os.path.join("data", "calibracao_dataset.csv"), index=False)

    if args.teste:
        corte = int(datetime.fromisoformat(args.teste).replace(tzinfo=timezone.utc).timestamp() * 1000)
        treino = [f for f in todas if f["ts"] < corte]
        teste = [f for f in todas if f["ts"] >= corte]
        if len(treino) < 200 or len(teste) < 50:
            print("amostras insuficientes para o teste fora da amostra; treinando com tudo")
            args.teste = None
    if args.teste:
        modelo = treinar(treino)
        avaliar(modelo, treino, "dentro da amostra")
        avaliar(modelo, teste, f"FORA da amostra (após {args.teste})")
        caminho_treino = args.saida.replace(".json", f"_ate_{args.teste}.json")
        salvar_modelo(modelo, caminho_treino)
        print("modelo só-treino salvo em", caminho_treino)
    modelo = treinar(todas)
    salvar_modelo(modelo, args.saida)
    print("taxa histórica por padrão|fase (n >= 200):")
    for k, t in sorted(modelo["tabela"].items(), key=lambda kv: -kv[1]["n"]):
        if t["n"] >= 200:
            print(f"   {k:45} n={t['n']:6d} acerto={t['taxa']:.3f}")
    print("modelo salvo em", args.saida)


if __name__ == "__main__":
    main()
