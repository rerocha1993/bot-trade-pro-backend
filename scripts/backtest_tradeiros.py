"""
PORTAL TRADEIROS — backtest da carteira do Shaka e do Maroja, em BTC, ano a ano.

    python scripts/backtest_tradeiros.py                      # 2019 até o fim dos dados, 30 sorteios
    python scripts/backtest_tradeiros.py --sorteios 50 --anos 2022 2026 --perfis maroja

CRITÉRIO ESCRITO ANTES DE RODAR (não mudar depois de ver o resultado):
    carteira     1 BTC de colateral no inverse; plano refeito todo dia com o que fechou (tradeiros/carteira.py)
    HODL         1 BTC parado: ganho em BTC zero por definição; o USD mostra quanto o hedge amorteceu
    hedge fixo   o mesmo % médio de hedge que o perfil usou no ano, parado o ano inteiro (mede se mexer no hedge ajuda)
    sorteio      a MESMA carteira, mesmas ordens e candles, com a direção de cada trade e de cada escada sorteada
    vantagem     o BTC final do período passa do percentil 95 dos sorteios E do hedge fixo
    períodos     treino 2019–2022, validação 2023–2024, holdout 2025–2026. Os parâmetros vieram das lives
                 (docs/tradeiros/perfil_por_regime.md, gabarito.json), não de otimização — o treino não foi usado para
                 ajustar nada, mas continua separado para ninguém ajustar olhando o holdout.
"""
import argparse
import datetime as dt
import json
import os
import random
import sys
import time

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tradeiros.carteira import Carteira, planejador_tradeiros  # noqa: E402
from tradeiros.leitura import Dados  # noqa: E402
from tradeiros.regras import PERFIS, Plano  # noqa: E402

PERIODOS = {"treino": (2019, 2022), "validação": (2023, 2024), "holdout": (2025, 2026)}
SAIDA = os.path.join("data", "estudo_tradeiros.json")


def ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def hedge_fixo(frac):
    def planejador(ts, hedge_atual):
        return Plano("hedge_fixo", ts, 0.0, frac, [], {}, [])
    return planejador


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sorteios", type=int, default=30)
    ap.add_argument("--anos", type=int, nargs=2, default=[2019, 2026])
    ap.add_argument("--perfis", nargs="*", default=["shaka", "maroja"])
    args = ap.parse_args()

    dados = Dados.do_projeto(".")
    fund = dict(zip(dados.funding[0], dados.funding[1]))
    fim_dados = dados.blocos_ts[-1] + 30 * 60 * 1000
    saida = {"criterio": __doc__, "anos": {}, "periodos": {}}
    for nome in args.perfis:
        pf = PERFIS[nome]
        plan = planejador_tradeiros(dados, pf)
        print(f"\n=== {nome.upper()} ===")
        print(f"{'ano':<6}{'BTC':>8}{'USD':>9}{'HODL$':>9}{'ddBTC':>8}{'dd$':>8}{'ddHODL':>8}{'hedge':>7}{'trades':>7}"
              f"{'R':>7}{'fixo':>8}{'sort.med':>9}{'sort.p95':>9}{'pct':>6}{'s':>6}")
        por_ano = {}
        for ano in range(args.anos[0], args.anos[1] + 1):
            ini, fim = ms(f"{ano}-01-01"), min(ms(f"{ano + 1}-01-01"), fim_dados)
            if ini >= fim:
                continue
            t0 = time.time()
            r = Carteira(dados.blocos, plan, pf, fund).executar(ini, fim)
            fixo = Carteira(dados.blocos, hedge_fixo(r["hedge_medio_pct"] / 100), pf, fund).executar(ini, fim)
            sort = [Carteira(dados.blocos, plan, pf, fund, sortear=random.Random(ano * 1000 + i)).executar(ini, fim)["btc_final"]
                    for i in range(args.sorteios)]
            pct = sum(x < r["btc_final"] for x in sort) / len(sort)
            p95 = float(np.percentile(sort, 95))
            por_ano[ano] = {"carteira": {k: v for k, v in r.items() if k not in ("log", "lista_trades")},
                            "fixo_btc": fixo["btc_final"], "sorteios_btc": sort}
            print(f"{ano:<6}{r['ganho_btc_pct']:>+7.1f}%{r['retorno_usd_pct']:>+8.1f}%{r['hodl_usd_pct']:>+8.1f}%"
                  f"{r['dd_btc_pct']:>7.1f}%{r['dd_usd_pct']:>7.1f}%{r['dd_hodl_pct']:>7.1f}%{r['hedge_medio_pct']:>6.0f}%"
                  f"{r['trades']:>7}{r['r_total']:>+7.1f}{(fixo['btc_final'] - 1) * 100:>+7.1f}%"
                  f"{(float(np.median(sort)) - 1) * 100:>+8.1f}%{(p95 - 1) * 100:>+8.1f}%{pct:>6.0%}{time.time() - t0:>6.0f}")
        saida["anos"][nome] = por_ano

        print(f"\n{'período':<11}{'BTC':>9}{'fixo':>9}{'sort.p95':>10}{'pct':>6}  vantagem?")
        saida["periodos"][nome] = {}
        for per, (a0, a1) in PERIODOS.items():
            anos = [a for a in range(a0, a1 + 1) if a in por_ano]
            if not anos:
                continue
            btc = float(np.prod([por_ano[a]["carteira"]["btc_final"] for a in anos]))
            fx = float(np.prod([por_ano[a]["fixo_btc"] for a in anos]))
            sorteios = [float(np.prod([por_ano[a]["sorteios_btc"][i] for a in anos])) for i in range(args.sorteios)]
            p95 = float(np.percentile(sorteios, 95))
            pct = sum(x < btc for x in sorteios) / len(sorteios)
            ok = btc > p95 and btc > fx
            saida["periodos"][nome][per] = {"anos": anos, "btc": btc, "fixo": fx, "p95_sorteio": p95, "percentil": pct, "vantagem": ok}
            print(f"{per:<11}{(btc - 1) * 100:>+8.1f}%{(fx - 1) * 100:>+8.1f}%{(p95 - 1) * 100:>+9.1f}%{pct:>6.0%}  {'SIM' if ok else 'não'}")

    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print(f"\nresultado salvo em {SAIDA}")


if __name__ == "__main__":
    main()
