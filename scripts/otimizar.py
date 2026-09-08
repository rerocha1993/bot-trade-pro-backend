# scripts/otimizar.py
"""
Walk-forward honesto: otimiza parâmetros SÓ no período de treino e mede no período de teste.

    python scripts/otimizar.py --tf 1h --fonte historico --treino-ate 2024-06-01 --estilo daytrade --perfil conservador
    python scripts/otimizar.py --tf 1h --fonte csv           # usa binance_csv/ (2023-2025)

Grade (pequena de propósito; cada combinação é um backtest completo):
    fator_atr do ZigZag      1.6 / 2.0 / 2.5
    limiar da saída estrutural 0.6 / 0.7 / 0.8
    R:R mínimo               1.0 / 1.5
    filtro de regime         ligado / desligado
Resultado: tabela ordenada pelo fator de lucro no TREINO, com o mesmo parâmetro medido no TESTE.
"""
import argparse
import itertools
import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.backtest_engine import BacktestEngine, bot_padrao, carregar_binance_csv  # noqa: E402
from core.elliott_pro import multidegree  # noqa: E402
from core import strategy_engine  # noqa: E402


def carregar_historico(tf):
    nome = {"1d": "BTCUSD_bitstamp_1d.csv", "4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv",
            "15m": "BTCUSDT_binance_15m.csv", "5m": "BTCUSDT_binance_5m.csv"}[tf]
    df = pd.read_csv(os.path.join("data", "historico", nome)).sort_values("timestamp")
    return df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()


def rodar(ohlcv, tf, estilo, perfil, fator_atr, limiar, rr, regime, passo):
    # aplica os parâmetros globais usados pelo motor
    for cfg in multidegree.PERFIS.values():
        cfg["fator_atr"] = fator_atr
    multidegree.AnaliseMultiGrau.LIMIAR_SAIDA = limiar
    strategy_engine.RR_MINIMO[perfil] = rr
    bot = bot_padrao(timeframe=tf, estilo_trade=estilo, confluencia_tipo=perfil, usar_filtro_regime=regime)
    r = BacktestEngine(ohlcv, bot, timeframe=tf, passo=passo).executar()
    return {k: r[k] for k in ("trades", "taxa_acerto", "retorno_pct", "fator_lucro", "drawdown_max_pct", "r_medio")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1h")
    ap.add_argument("--fonte", default="csv", choices=["csv", "historico"])
    ap.add_argument("--treino-ate", default="2024-06-01")
    ap.add_argument("--desde", default="2020-01-01")
    ap.add_argument("--estilo", default="daytrade")
    ap.add_argument("--perfil", default="conservador")
    ap.add_argument("--passo", type=int, default=1)
    ap.add_argument("--saida", default="data/otimizacao.csv")
    args = ap.parse_args()

    ohlcv = carregar_binance_csv("binance_csv") if args.fonte == "csv" else carregar_historico(args.tf)
    desde = int(datetime.fromisoformat(args.desde).replace(tzinfo=timezone.utc).timestamp() * 1000)
    corte = int(datetime.fromisoformat(args.treino_ate).replace(tzinfo=timezone.utc).timestamp() * 1000)
    ohlcv = [c for c in ohlcv if c[0] >= desde]
    treino = [c for c in ohlcv if c[0] < corte]
    teste = [c for c in ohlcv if c[0] >= corte - 300 * (ohlcv[1][0] - ohlcv[0][0])]  # inclui janela de aquecimento
    print(f"treino {len(treino)} candles | teste {len(teste)} candles ({args.tf})")

    grade = list(itertools.product([1.6, 2.0, 2.5], [0.6, 0.7, 0.8], [1.0, 1.5], [True, False]))
    linhas = []
    t0 = time.time()
    for i, (fa, lim, rr, reg) in enumerate(grade, 1):
        rt = rodar(treino, args.tf, args.estilo, args.perfil, fa, lim, rr, reg, args.passo)
        rs = rodar(teste, args.tf, args.estilo, args.perfil, fa, lim, rr, reg, args.passo)
        linhas.append({"fator_atr": fa, "limiar_saida": lim, "rr_min": rr, "regime": reg,
                       **{f"treino_{k}": v for k, v in rt.items()}, **{f"teste_{k}": v for k, v in rs.items()}})
        print(f"[{i}/{len(grade)}] atr={fa} saida={lim} rr={rr} regime={reg} | treino PF={rt['fator_lucro']} ret={rt['retorno_pct']}% "
              f"| teste PF={rs['fator_lucro']} ret={rs['retorno_pct']}% dd={rs['drawdown_max_pct']}% ({time.time() - t0:.0f}s)")
    df = pd.DataFrame(linhas).sort_values("treino_fator_lucro", ascending=False)
    os.makedirs(os.path.dirname(args.saida), exist_ok=True)
    df.to_csv(args.saida, index=False)
    print(df.head(8).to_string(index=False))
    print("salvo em", args.saida)


if __name__ == "__main__":
    main()
