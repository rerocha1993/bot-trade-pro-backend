# scripts/evoluir_contagens.py
"""
Reproduz a evolução das contagens de Elliott desde 2011, ano a ano, sem look-ahead:
quais hipóteses nasceram, sobreviveram a testes, foram invalidadas ou se cumpriram.

    python scripts/evoluir_contagens.py                  # ciclo (semanal, 40%) e primário (diário, 22%)
    python scripts/evoluir_contagens.py --grau ciclo --pct 0.35
Saída: docs/EVOLUCAO_CONTAGENS.md e data/evolucao_contagens.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.elliott_pro.calibracao import Calibrador  # noqa: E402
from core.elliott_pro.memoria import evoluir, evoluir_hierarquico  # noqa: E402
from core.market_data import reamostrar  # noqa: E402


def carregar():
    df = pd.read_csv(os.path.join("data", "historico", "BTCUSD_bitstamp_1d.csv")).sort_values("timestamp")
    d1 = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
    return d1, reamostrar(d1, "1d", "1w")


def fim_de_ano(anos):
    return [int(datetime(a, 12, 31, tzinfo=timezone.utc).timestamp() * 1000) for a in anos]


def fim_de_trimestre(anos):
    out = []
    for a in anos:
        for m in (3, 6, 9):
            if a == 2012 and m < 6:
                continue
            out.append(int(datetime(a, m + 1, 1, tzinfo=timezone.utc).timestamp() * 1000) - 86_400_000)
    return sorted(out)


def acerto_consenso(res, serie, snaps=None, detalhe=True):
    """Compara o consenso de cada snapshot com a variação de preço nos 12 meses seguintes."""
    import bisect
    ts_list = [c[0] for c in serie]
    linhas, acertos, total = [], 0, 0
    for snap in (snaps if snaps is not None else res["snapshots"]):
        i = bisect.bisect_left(ts_list, snap["ts"] + 365 * 86_400_000)
        if i >= len(serie):
            continue
        p1 = serie[min(i, len(serie) - 1)][4]
        var = p1 / snap["preco"] - 1
        d = snap["direcao"]
        certo = (d == "buy" and var > 0.1) or (d == "sell" and var < -0.1) or (d == "hold" and abs(var) <= 0.3)
        if d != "hold":
            total += 1
            acertos += int(certo)
        sc = snap.get("superciclo") or {}
        extra = f" | {sc.get('estado', '')}" if sc else ""
        linhas.append(f"| {snap['data']} | {snap['preco']:,.0f} | {d} ({max(snap['prob_bull'], snap['prob_bear']):.0%}){extra} | {var:+.0%} | {'certo' if certo else 'errado'} |")
    cab = ["| Data | Preço | Consenso | 12 meses depois | Avaliação |", "|---|---|---|---|---|"]
    resumo = f"Direções não-neutras: {acertos}/{total} certas ({(acertos / total):.0%})" if total else "sem direções não-neutras"
    if not detalhe:
        return resumo + chr(10)
    return chr(10).join(cab + linhas) + chr(10) + chr(10) + resumo + chr(10)


def relatorio(nome, res, anos, serie=None):
    linhas = [f"## Grau {nome}", ""]
    if serie is not None:
        linhas.append("### Consistência do consenso (sem look-ahead)")
        linhas.append(acerto_consenso(res, serie))
        if res.get("snapshots_trimestrais"):
            linhas.append("Fins de trimestre (robustez, " + str(len(res["snapshots_trimestrais"])) + " datas): " + acerto_consenso(res, serie, res["snapshots_trimestrais"], detalhe=False))
    ev = res["eventos"]
    cont = {}
    for e in ev:
        cont[e["evento"]] = cont.get(e["evento"], 0) + 1
    linhas.append("Eventos no período: " + ", ".join(f"{k} {v}" for k, v in sorted(cont.items())))
    linhas.append("")
    for snap in res["snapshots"]:
        linhas.append(f"### {snap['data']}  preço {snap['preco']:,.0f}  |  vivas {snap['n_vivas']}  |  bull {snap['prob_bull']:.0%} / bear {snap['prob_bear']:.0%}  |  consenso {snap['direcao']}")
        for h in snap["vivas"][:4]:
            inv = f"{h['invalidacao']:,.0f}" if h.get("invalidacao") else "-"
            alvos = ", ".join(f"{a:,.0f}" for a in (h.get("alvos") or [])[:3]) or "-"
            linhas.append(f"- {h['probabilidade_madura']:.0%} {h['nome']} | fase {h['fase']} | nasceu {h['nascimento']} ({h['idade_passos']} passos, {h['testes']} testes, {h['alvos_batidos']} alvos) | inval {inv} | alvos {alvos}")
        linhas.append("")
    linhas.append("### Hipóteses encerradas (as que 'olhando para trás' se consolidaram ou morreram)")
    for h in res["historico"]:
        if h["status"] in ("cumprida", "invalidada") and h["idade_passos"] >= 8:
            linhas.append(f"- {h['status'].upper():11} {h['nome']} | {h['nascimento']} -> {h['fim']} ({h['idade_passos']} passos, {h['testes']} testes, {h['alvos_batidos']} alvos) | preço final {h['fim_preco']:,.0f}")
    linhas.append("")
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grau", default=None)
    ap.add_argument("--pct", type=float, default=None)
    args = ap.parse_args()
    d1, w1 = carregar()
    anos = list(range(2012, 2027))
    cal = Calibrador()
    graus = [("ciclo", w1, 0.40, 1), ("primario", d1, 0.22, 1)]
    if args.grau:
        graus = [g for g in graus if g[0] == args.grau]
        if args.pct:
            graus = [(g[0], g[1], args.pct, g[3]) for g in graus]
    saida_md = ["# Evolução das contagens de Elliott desde 2011 (sem look-ahead)", "",
                "Cada hipótese nasce quando o motor a gera pela primeira vez, sobrevive a testes da invalidação, bate alvos, e morre por",
                "invalidação, se cumpre, ou é abandonada. A probabilidade 'madura' pondera aderência às regras, calibração histórica,",
                "idade, testes sobrevividos e alvos batidos.", ""]
    saida_json = {}
    for nome, serie, pct, passo in graus:
        print(f"[{nome}] evoluindo {len(serie)} candles a {pct:.0%} ...")
        res = evoluir(serie, nome, pct, passo_candles=passo, calibrador=cal, snapshots=fim_de_ano(anos))
        res.pop("memoria")
        saida_json[nome] = {k: v for k, v in res.items()}
        saida_md.append(relatorio(nome, res, anos, serie))
        cf = res["consenso_final"]
        print(f"[{nome}] hoje: vivas {cf['n_vivas']} | bull {cf['prob_bull']:.0%} bear {cf['prob_bear']:.0%} | {cf['primaria']['nome'] if cf['primaria'] else None}")
    if not args.grau:
        print("[hierarquico] ciclo (semanal) mandando no primário (diário) ...")
        fins = fim_de_ano(anos)
        tri = fim_de_trimestre(anos)
        res = evoluir_hierarquico(d1, calibrador=cal, snapshots=sorted(set(fins + tri)))
        res.pop("memoria")
        res["snapshots_trimestrais"] = list(res["snapshots"])
        res["snapshots"] = [x for x in res["snapshots"] if any(abs(x["ts"] - f) < 2 * 86_400_000 for f in fins)]
        saida_json["trader"] = res
        saida_md.append(relatorio("TRADER: superciclo (log) + ciclo mandando no primário", res, anos, d1))
        cf = res["consenso_final"]
        print(f"[trader] hoje: {cf['direcao']} | superciclo {cf['superciclo'].get('estado')} | {cf['superciclo'].get('leitura')}")
        print(f"[trader] subordinado {cf['subordinado']} | ciclo {cf['ciclo']}")
        print(acerto_consenso(res, d1))
        print("trimestres: " + acerto_consenso(res, d1, res["snapshots_trimestrais"], detalhe=False))
    os.makedirs("docs", exist_ok=True)
    with open(os.path.join("docs", "EVOLUCAO_CONTAGENS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(saida_md))
    with open(os.path.join("data", "evolucao_contagens.json"), "w", encoding="utf-8") as f:
        json.dump(saida_json, f, ensure_ascii=False, default=str)
    print("salvo em docs/EVOLUCAO_CONTAGENS.md")


if __name__ == "__main__":
    main()
