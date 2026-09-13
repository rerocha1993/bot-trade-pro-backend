"""
SCALP DE VOLATILIDADE (core/scalp_volatilidade.py): só entra quando o mercado acorda, medido nos dados.

    python scripts/backtest_scalp_vol.py

Regras combinadas com o usuário em 13/09/2026 e fixadas ANTES de rodar (detalhe no módulo):
    volatilidade e volume dos últimos 15 min >= 3x a mediana de 7 dias; sem fim de semana; perfil TPO de 5 min dos
    30 min do impulso; single print interno >= 0,15%; jogada A (a favor, alvo 2R, tira o risco em 1R) e jogada B
    (preenchimento, 1:1), testadas separadas; entrada no reteste, nunca no disparo; custo com slippage de janela volátil.

Critério de aprovação (fixado antes): médio líquido > 0 no treino E na validação, com >= 30 trades em cada; só então
o holdout conta, e ele também precisa ser > 0.

Controles: (1) a mesma regra em momentos CALMOS — se ganhar também, a vantagem não é da volatilidade;
(2) limiar 2x e 4x e (3) com fim de semana, só informativos (não escolhem parâmetro).
"""
import dataclasses
import datetime as dt
import os
import sys
from collections import Counter

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.scalp_volatilidade import EstudoScalpVol, resumo  # noqa: E402

CSV = os.path.join("data", "historico", "BTCUSDT_binance_5m.csv")
PERIODOS = (("treino", "2020-01-01", "2023-07-01"), ("validação", "2023-07-01", "2025-01-01"), ("HOLDOUT", "2025-01-01", None))


def ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def data(ts):
    return dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)


def linha(rot, r):
    if not r["trades"]:
        return f"    {rot:<10} sem trades"
    t = f"{r['t']:+.1f}" if r["t"] is not None else "—"
    return (f"    {rot:<10} {r['trades']:>5} trades  acerto {r['acerto']:>4.0%}  médio {r['medio_r']:+.3f}R "
            f"(bruto {r['bruto_r']:+.3f})  soma {r['soma_r']:+8.1f}R  FL {r['fl']}  t {t}  | {dict(r['saidas'])}")


def por_periodo(trades):
    for rot, ini, fim in PERIODOS:
        sel = [x for x in trades if x["ts"] >= ms(ini) and (fim is None or x["ts"] < ms(fim))]
        print(linha(rot, resumo(sel)))


def main():
    df = pd.read_csv(CSV).sort_values("timestamp")
    df = df[df["timestamp"] >= ms("2019-11-01")].reset_index(drop=True)      # 7 dias de base antes de 2020
    est = EstudoScalpVol(df)

    ev = est.eventos("volatil")
    anos = Counter(data(est.ts[i]).year for i in ev)
    print(f"{len(df)} candles de 5 min | momentos de volatilidade por ano (vol e volume >= 3x, sem fim de semana): "
          f"{dict(sorted(anos.items()))}")
    print("\nos 12 mais fortes de 2024 (confere se o detector pega os dias de notícia):")
    ev24 = [i for i in ev if data(est.ts[i]).year == 2024]
    for i in sorted(ev24, key=lambda i: -est.vol_rel[i])[:12]:
        print(f"    {data(est.ts[i]):%Y-%m-%d %a %H:%M} UTC   volatilidade {est.vol_rel[i]:.1f}x   volume {est.volume_rel[i]:.1f}x")

    salvos = []
    for regra, nome in (("volatil", "VOLÁTIL (a regra)"), ("calmo", "CALMO (controle)")):
        for jogada, nj in (("A", "a favor do impulso"), ("B", "preenchimento do vácuo")):
            tr = est.trades(regra, jogada)
            print(f"\n{nome} · jogada {jogada} ({nj})")
            por_periodo(tr)
            if regra == "volatil":
                salvos += tr

    print("\nsensibilidade do limiar (só informativa):")
    for lim in (2.0, 4.0):
        for jogada in ("A", "B"):
            print(f"  limiar {lim:.0f}x · jogada {jogada}")
            por_periodo(est.trades("volatil", jogada, limiar=lim))

    print("\ncom fim de semana (só informativo):")
    est_fds = EstudoScalpVol(df, dataclasses.replace(est.p, fim_de_semana=True))
    for jogada in ("A", "B"):
        print(f"  jogada {jogada}")
        por_periodo(est_fds.trades("volatil", jogada))

    pd.DataFrame(salvos).to_csv(os.path.join("data", "estudo_scalp_vol.csv"), index=False)


if __name__ == "__main__":
    main()
