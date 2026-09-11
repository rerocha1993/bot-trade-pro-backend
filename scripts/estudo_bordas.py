"""
ESTUDO DOS TOQUES NAS BORDAS DO RANGE: o contexto de order flow separa a borda que segura da que rompe?

    python scripts/estudo_bordas.py

Cada vez que o preço chega na zona do VAL (ou do VAH) de um range válido (merge adaptativo, core/range_tradeiros.py),
vindo de longe, conta um TOQUE. Resultado do toque: SEGUROU se o preço foi até o POC antes de passar do extremo
do range (com folga), em até 3 dias.

Hipóteses fixadas ANTES de olhar (tiradas das lives do Tradeiros, espelhadas no VAH):
    H1 presos     chegou no VAL com o open interest SUBINDO nas últimas 6 h (shorts novos no fundo) -> segura mais
    H2 funding    funding negativo no VAL (vendidos pagando)                                  -> segura mais
    H3 long/short proporção long/short abaixo da mediana no VAL (mais contas vendidas)         -> segura mais
    H4 toques     1º toque sem rotação segura mais que o 2º; o 3º ou mais rompe
Cada uma é comparada com a taxa base, com o erro padrão (duas vezes o erro é o mínimo para levar a sério).
"""
import datetime as dt
import json
import os
import sys
from bisect import bisect_right

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.range_tradeiros import ParametrosRange, contexto  # noqa: E402
from core.tpo_sessao import DIA_MS, Perfil, blocos_30m  # noqa: E402

P = ParametrosRange()
HORIZONTE = 144                  # 3 dias em blocos de 30 min


def ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def serie(caminho, chave=None):
    if not os.path.exists(caminho):
        return [], []
    d = json.load(open(caminho))
    if chave:
        d = d[chave]
    pares = sorted((int(k), float(v)) for k, v in d.items())
    return [p[0] for p in pares], [p[1] for p in pares]


def ultimo(ts_lista, vals, ts):
    i = bisect_right(ts_lista, ts) - 1
    return vals[i] if i >= 0 else None


def main():
    df = pd.read_csv(os.path.join("data", "historico", "BTCUSDT_binance_15m.csv")).sort_values("timestamp")
    df = df[df["timestamp"] >= ms("2020-05-01")]
    bl = blocos_30m(df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist())
    oi_t, oi_v = serie(os.path.join("data", "historico", "oi_bybit_1h.json"))
    ls_t, ls_v = serie(os.path.join("data", "historico", "lsr_bybit_1h.json"))
    fu_t, fu_v = serie(os.path.join("data", "historico", "funding_bybit.json"), "linear")
    ls_med = float(np.median(ls_v)) if ls_v else None
    por = {}
    for b in bl:
        por.setdefault(b[0] // DIA_MS, []).append(b)
    dias = sorted(por)
    perfis = {d: Perfil(por[d]) for d in dias}
    idx = {b[0]: i for i, b in enumerate(bl)}
    eventos = []
    for k, d in enumerate(dias):
        if k < P.min_dias or d * DIA_MS < ms("2020-06-15"):
            continue
        ctx = contexto([perfis[x] for x in dias[max(0, k - P.max_dias):k]], P)
        if ctx is None or not ctx.valido:
            continue
        w = ctx.largura
        longe = {1: True, -1: True}
        toques = {1: 0, -1: 0}
        for b in por[d]:
            ts, _, h, l, c, _ = b
            for lado in (1, -1):
                de, ate = ctx.zona(lado, P)
                if (c >= ctx.poc) if lado == 1 else (c <= ctx.poc):
                    toques[lado], longe[lado] = 0, True
                    continue
                na_zona = (l <= ate) if lado == 1 else (h >= de)
                if na_zona and longe[lado]:
                    toques[lado] += 1
                    longe[lado] = False
                    extremo = ctx.minima if lado == 1 else ctx.maxima
                    stop = extremo * (1 - lado * P.folga_stop_pct)
                    i0 = idx[ts]
                    res = None
                    for f in bl[i0 + 1:i0 + 1 + HORIZONTE]:
                        if (f[3] <= stop) if lado == 1 else (f[2] >= stop):
                            res = 0
                            break
                        if (f[2] >= ctx.poc) if lado == 1 else (f[3] <= ctx.poc):
                            res = 1
                            break
                    if res is None:
                        continue
                    oi_ag = ultimo(oi_t, oi_v, ts)
                    oi_6h = ultimo(oi_t, oi_v, ts - 6 * 3_600_000)
                    eventos.append({
                        "ts": ts, "lado": lado, "segurou": res, "toque": toques[lado],
                        "oi_6h": (oi_ag / oi_6h - 1) if oi_ag and oi_6h else None,
                        "funding": ultimo(fu_t, fu_v, ts), "lsr": ultimo(ls_t, ls_v, ts),
                    })
                elif (c >= ctx.val + P.afastamento_toque * w) if lado == 1 else (c <= ctx.vah - P.afastamento_toque * w):
                    longe[lado] = True
    e = pd.DataFrame(eventos)
    print(f"{len(e)} toques em bordas de range válido desde jun/2020 "
          f"(VAL {int((e.lado == 1).sum())}, VAH {int((e.lado == -1).sum())})")

    def taxa(m, rot):
        sub = e[m]
        if len(sub) < 20:
            print(f"  {rot:<58} n={len(sub):>4}  (amostra pequena)")
            return
        p = sub.segurou.mean()
        base = e[e.lado.isin(sub.lado.unique())].segurou.mean()
        ep = np.sqrt(base * (1 - base) / len(sub))
        print(f"  {rot:<58} n={len(sub):>4}  segurou {p:.1%}  (base {base:.1%}, diferença {(p - base) / ep:+.1f} erros-padrão)")

    print("\ntaxa base:")
    taxa(e.lado == 1, "VAL (compra)")
    taxa(e.lado == -1, "VAH (venda)")
    print("\nH4 toques sem rotação:")
    for lado, nome in ((1, "VAL"), (-1, "VAH")):
        for t in (1, 2, 3):
            taxa((e.lado == lado) & ((e.toque == t) if t < 3 else (e.toque >= 3)), f"{nome} {t}{'º' if t < 3 else 'º ou mais'} toque")
    tem = e.oi_6h.notna()
    print(f"\nH1 presos (open interest nas 6 h anteriores; {int(tem.sum())} toques com dado):")
    taxa(tem & (e.lado == 1) & (e.oi_6h > 0), "VAL com OI subindo (shorts novos no fundo)")
    taxa(tem & (e.lado == 1) & (e.oi_6h <= 0), "VAL com OI caindo")
    taxa(tem & (e.lado == -1) & (e.oi_6h > 0), "VAH com OI subindo (longs novos no topo)")
    taxa(tem & (e.lado == -1) & (e.oi_6h <= 0), "VAH com OI caindo")
    tf = e.funding.notna()
    print(f"\nH2 funding ({int(tf.sum())} toques com dado):")
    taxa(tf & (e.lado == 1) & (e.funding < 0), "VAL com funding negativo (vendidos pagando)")
    taxa(tf & (e.lado == 1) & (e.funding >= 0), "VAL com funding positivo")
    taxa(tf & (e.lado == -1) & (e.funding > 0.0001), "VAH com funding alto (comprados pagando)")
    taxa(tf & (e.lado == -1) & (e.funding <= 0.0001), "VAH com funding baixo")
    tl = e.lsr.notna()
    print(f"\nH3 long/short ({int(tl.sum())} toques com dado, mediana {ls_med}):")
    if ls_med:
        taxa(tl & (e.lado == 1) & (e.lsr < ls_med), "VAL com mais contas vendidas")
        taxa(tl & (e.lado == 1) & (e.lsr >= ls_med), "VAL com mais contas compradas")
        taxa(tl & (e.lado == -1) & (e.lsr > ls_med), "VAH com mais contas compradas")
        taxa(tl & (e.lado == -1) & (e.lsr <= ls_med), "VAH com mais contas vendidas")
    e.to_csv(os.path.join("data", "estudo_bordas.csv"), index=False)


if __name__ == "__main__":
    main()
