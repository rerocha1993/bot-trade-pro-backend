"""
Laboratório: cria centenas de robôs por votação entre os indicadores e testa todos.

    python scripts/lab_indicadores.py --tf 4h
    python scripts/lab_indicadores.py --tf 1h --passo 2

Períodos: treino (escolhe) -> validação (confirma) -> holdout (olhado uma vez só, no fim, pelos finalistas).
No fim mostra, do melhor robô, quanto cada indicador ACRESCENTA: o resultado com ele e sem ele.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.lab_combinacoes import CRITERIO, Variante, aprovada, rodar, variantes  # noqa: E402
from core.sinais_indicadores import MERCADO, candles, carregar  # noqa: E402


def ms(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def linha(rot, r):
    if not r["trades"]:
        return f"    {rot:<11} sem trades"
    return (f"    {rot:<11} {r['trades']:>4} trades  acerto {r['acerto']:>5.0%}  médio {r['medio_r']:+.4f}R  "
            f"soma {r['soma_r']:+7.1f}R  FL {r['fator_lucro']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="4h")
    ap.add_argument("--passo", type=int, default=1)
    ap.add_argument("--treino", default="2021-01-01")
    ap.add_argument("--validacao", default="2023-07-01")
    ap.add_argument("--holdout", default="2025-01-01")
    ap.add_argument("--horizonte", type=int, default=24)
    ap.add_argument("--finalistas", type=int, default=3)
    ap.add_argument("--salvar")
    a = ap.parse_args()

    d = carregar(a.tf, a.passo)
    c = candles(a.tf)
    vs = variantes(MERCADO)
    print(f"{a.tf}: {len(d)} candles com sinais | {len(vs)} robôs a testar | horizonte {a.horizonte} candles")
    print(f"treino {a.treino}–{a.validacao} | validação {a.validacao}–{a.holdout} | holdout {a.holdout}+")
    print(f"critério (fixado antes): {CRITERIO}\n")
    resultados = []
    for i, v in enumerate(vs):
        tr = rodar(d, c, v, ms(a.treino), ms(a.validacao), a.horizonte)
        va = rodar(d, c, v, ms(a.validacao), ms(a.holdout), a.horizonte)
        resultados.append((v, tr, va, aprovada(tr, va)))
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(vs)} testados ({sum(1 for x in resultados if x[3])} passaram nos dois períodos)", flush=True)
    passaram = [x for x in resultados if x[3]]
    print(f"\n{len(passaram)} de {len(vs)} passaram no treino E na validação.")
    print(f"  (com {len(vs)} tentativas, ~{len(vs) // 4} passariam por puro acaso, então isto ainda não é prova)")
    passaram.sort(key=lambda x: -min(x[1]["medio_r"], x[2]["medio_r"]))
    relatorio = {"tf": a.tf, "variantes": len(vs), "passaram": len(passaram), "finalistas": []}
    # o teste que vale mais que o pódio: TODAS as aprovadas, juntas, seguram no holdout?
    if passaram:
        hos = [rodar(d, c, v, ms(a.holdout), None, a.horizonte) for v, _, _, _ in passaram]
        medios = [h["medio_r"] for h in hos if h["trades"] >= 20]
        if medios:
            import statistics
            positivas = sum(1 for x in medios if x > 0) / len(medios)
            print(f"\nas {len(medios)} aprovadas com amostra no holdout: médio mediano {statistics.median(medios):+.4f}R, "
                  f"{positivas:.0%} delas positivas (se fosse vantagem real, a maioria seguraria)")
            relatorio["holdout_aprovadas"] = {"n": len(medios), "mediana_medio_r": round(statistics.median(medios), 4),
                                              "pct_positivas": round(positivas, 3)}
    for v, tr, va, _ in passaram[:a.finalistas]:
        ho = rodar(d, c, v, ms(a.holdout), None, a.horizonte)
        print(f"\n{v.nome}")
        print(linha("treino", tr)); print(linha("validação", va)); print(linha("HOLDOUT", ho))
        veredito = "VALE INVESTIGAR" if ho["trades"] >= 20 and ho["medio_r"] > 0 else "caiu no holdout"
        print(f"    -> {veredito}")
        # quanto cada indicador acrescenta a este robô (tirar um e ver o que acontece nos 3 períodos)
        if len(v.indicadores) > 2:
            print("    relevância de cada indicador (sem ele, soma nos 3 períodos):")
            base = sum(r["soma_r"] for r in (tr, va, ho))
            for ind in v.indicadores:
                resto = tuple(x for x in v.indicadores if x != ind)
                v2 = Variante(resto, min(v.votos_min, len(resto)), v.usar_elliott, v.usar_regime)
                soma = sum(rodar(d, c, v2, ms(p), f, a.horizonte)["soma_r"]
                           for p, f in ((a.treino, ms(a.validacao)), (a.validacao, ms(a.holdout)), (a.holdout, None)))
                print(f"      sem {ind:<16} {soma:+7.1f}R  (com todos {base:+.1f}R -> acrescenta {base - soma:+.1f}R)")
        relatorio["finalistas"].append({"nome": v.nome, "treino": tr, "validacao": va, "holdout": ho})
    if a.salvar:
        with open(a.salvar, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
