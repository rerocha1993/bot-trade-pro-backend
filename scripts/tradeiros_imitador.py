"""
PORTAL TRADEIROS — IMITADOR: o modelo, na data de cada live, decide o mesmo que o Shaka e o Maroja decidiram?

    python scripts/tradeiros_imitador.py            # escreve docs/tradeiros/imitador.md

Para cada live do gabarito (docs/tradeiros/gabarito.json) monta a leitura e o mapa às 13:00 UTC (só o que fechou até ali)
e compara com as decisões do operador:
    tipos     sobreposição (Jaccard) entre os tipos de decisão do modelo e os da live
    zonas     compras/vendas reais com zona numérica: a ordem do modelo do mesmo tipo cai a até 2% dela?
    hedge     o hedge do modelo cai na faixa dita na live (±5 pontos)?
"""
import datetime as dt
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tradeiros.elliott_mapa import MapaElliott  # noqa: E402
from tradeiros.leitura import Dados, LeituraDiaria  # noqa: E402
from tradeiros.regras import MAROJA, SHAKA, planejar  # noqa: E402

TIPOS = ("compra", "venda_direcional", "hedge_aumentar", "hedge_realizar", "ficar_fora")
SAIDA = os.path.join("docs", "tradeiros", "imitador.md")


def zona_real(z):
    if not z or all(x is None for x in z):
        return None
    a, b = z[0] if z[0] is not None else z[1], z[1] if z[1] is not None else z[0]
    return min(a, b), max(a, b)


def perto(zm, zr, tol=0.02):
    return zm[0] * (1 - tol) <= zr[1] and zr[0] <= zm[1] * (1 + tol)


def main():
    dados = Dados.do_projeto(".")
    leitura, mapa = LeituraDiaria(dados), MapaElliott(dados)
    gab = json.load(open(os.path.join("docs", "tradeiros", "gabarito.json"), encoding="utf-8"))
    tot = {p.nome: {"j": 0.0, "n": 0, "zonas": [0, 0], "hedge": [0, 0]} for p in (SHAKA, MAROJA)}
    linhas = []
    for g in gab:
        ts = int(dt.datetime.fromisoformat(g["data"] + "T13:00").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        lt, mp = leitura.ler(ts), mapa.ler(ts)
        for pf in (SHAKA, MAROJA):
            reais = [d for d in g["decisoes"] if d["operador"] in (pf.nome, "ambos") and d["tipo"] in TIPOS]
            if not reais:
                continue
            plano = planejar(lt, mp, pf)
            mod = {d.tipo for d in plano.decisoes}
            real = {d["tipo"] for d in reais}
            j = len(mod & real) / len(mod | real)
            t = tot[pf.nome]
            t["j"] += j
            t["n"] += 1
            zonas_txt = []
            for d in reais:
                zr = zona_real(d.get("zona"))
                if zr is None or d["tipo"] not in ("compra", "venda_direcional", "hedge_aumentar"):
                    continue
                ordens = [x.zona for x in plano.decisoes if x.tipo == d["tipo"] and x.zona]
                ok = any(perto(zm, zr) for zm in ordens)
                t["zonas"][0] += ok
                t["zonas"][1] += 1
                zonas_txt.append(f"{d['tipo']} {zr[0]:,.0f}–{zr[1]:,.0f} {'✓' if ok else '✗'}")
            hp = (g.get("hedge_pct") or {}).get(pf.nome)
            hedge_txt = f"{plano.hedge_alvo:.0%}"
            if hp:
                ok = hp[0] / 100 - 0.05 <= plano.hedge_alvo <= hp[1] / 100 + 0.05
                t["hedge"][0] += ok
                t["hedge"][1] += 1
                hedge_txt += f" (live {hp[0]:g}–{hp[1]:g}% {'✓' if ok else '✗'})"
            linhas.append(f"| {g['data']} | {pf.nome} | {lt.zona} | {hedge_txt} | {j:.2f} | {', '.join(sorted(real - mod)) or '—'} "
                          f"| {', '.join(sorted(mod - real)) or '—'} | {'; '.join(zonas_txt) or '—'} |")

    out = ["# Imitador: modelo × lives do Tradeiros", "",
           f"Gerado por `scripts/tradeiros_imitador.py` em {dt.date.today():%d/%m/%Y}. Leitura e mapa às 13:00 UTC da data da live,",
           "só com candles fechados. As lives decidem várias coisas em horas diferentes; o modelo faz um plano por dia.", "",
           "## Resumo", "", "| operador | lives | tipos (Jaccard médio) | zonas a ≤2% | hedge na faixa (±5 pp) |", "|---|---|---|---|---|"]
    for nome, t in tot.items():
        z = f"{t['zonas'][0]}/{t['zonas'][1]}" if t["zonas"][1] else "—"
        h = f"{t['hedge'][0]}/{t['hedge'][1]}" if t["hedge"][1] else "—"
        out.append(f"| {nome} | {t['n']} | {t['j'] / max(t['n'], 1):.2f} | {z} | {h} |")
    out += ["", "## Por live", "", "| data | operador | zona do preço | hedge do modelo | Jaccard | faltou no modelo | sobrou no modelo | zonas reais |",
            "|---|---|---|---|---|---|---|---|"] + linhas
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out[:12]))
    print(f"\nrelatório em {SAIDA}")


if __name__ == "__main__":
    main()
