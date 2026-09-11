"""
Backtest da regra de assimetria do usuário (core/assimetria.py), com treino e validação.

    python scripts/cenarios_historicos.py --tf 4h        # uma vez, gera data/cenarios/4h.jsonl.gz
    python scripts/backtest_assimetria.py --tf 4h

Variantes fixadas ANTES de rodar (quatro por timeframe, e só elas):
    stop       'grupo' (onde todas as contagens do movimento morreram) ou 'maioria' (onde metade do peso morreu)
    saída      só stop/alvo, ou também no fechamento em que o grupo deixa de ser maioria
Treino até 2024-07-01, validação depois. Critério em core/backtest_assimetria.py.
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.backtest_assimetria import CRITERIO, BacktestAssimetria, avaliar  # noqa: E402

FONTES = {"1d": "BTCUSD_bitstamp_1d.csv", "4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv",
          "15m": "BTCUSDT_binance_15m.csv"}
VARIANTES = [("grupo", False), ("grupo", True), ("maioria", False), ("maioria", True)]


def ms(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="4h", choices=list(FONTES))
    ap.add_argument("--inicio", default="2022-01-01")
    ap.add_argument("--corte", default="2024-07-01")
    ap.add_argument("--salvar")
    a = ap.parse_args()
    with gzip.open(os.path.join("data", "cenarios", f"{a.tf}.jsonl.gz"), "rt", encoding="utf-8") as f:
        linhas = [json.loads(x) for x in f]
    df = pd.read_csv(os.path.join("data", "historico", FONTES[a.tf]))
    candles = {int(r.timestamp): (float(r.open), float(r.high), float(r.low), float(r.close)) for r in df.itertuples(index=False)}
    ini, corte = ms(a.inicio), ms(a.corte)
    fmt = lambda t: dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
    print(f"{a.tf}: {len(linhas)} candles com contagens | treino {a.inicio} a {a.corte} | validação {a.corte} a {fmt(linhas[-1]['ts'])}")
    print(f"critério (fixado antes): {CRITERIO}\n")
    relatorio = {"tf": a.tf, "treino": [a.inicio, a.corte], "variantes": {}}
    for tipo_stop, virada in VARIANTES:
        nome = f"stop no {tipo_stop}{' + sai na virada' if virada else ''}"
        tr = BacktestAssimetria(linhas, candles, tipo_stop, virada).executar(ini, corte)
        va = BacktestAssimetria(linhas, candles, tipo_stop, virada).executar(corte)
        ok, falhas = avaliar(tr, va)
        print(nome)
        for rot, r in (("treino", tr), ("validação", va)):
            if not r["trades"]:
                print(f"  {rot:<10} sem trades")
                continue
            print(f"  {rot:<10} {r['trades']:>4} trades  acerto {r['acerto']:>4.0%}  R:R médio {r['rr_medio']:>4}  "
                  f"risco {r['risco_pct_mediano']:>5}%  bruto {r['bruto_r']:+.3f}R  líquido {r['liquido_r']:+.3f}R  "
                  f"soma {r['soma_r']:+7.1f}R  FL {r['fator_lucro']}  DD {r['dd_max_r']}R  saídas {r['saidas']}  por ano {r['por_ano_r']}")
        print(f"  -> {'APROVADA' if ok else 'reprovada: ' + '; '.join(falhas)}\n")
        relatorio["variantes"][nome] = {"treino": {k: v for k, v in tr.items() if k != "lista"},
                                        "validacao": {k: v for k, v in va.items() if k != "lista"},
                                        "aprovada": ok, "falhas": falhas}
    if a.salvar:
        with open(a.salvar, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
