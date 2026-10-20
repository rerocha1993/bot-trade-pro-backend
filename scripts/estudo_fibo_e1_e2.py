# scripts/estudo_fibo_e1_e2.py
"""
Fibonacci E1 — "Escada 0,5–0,786 depois de quebra de microestrutura" + Fibonacci E2 — "Régua de saída"
(plano_gestao.md 2.3; docs/especialistas/fibonacci.md E1 e E2). Passo 4 da seção 4 do plano.
BTCUSDT Binance, 2020-01 a 2026-09, em 15 min e 1 h. CRITÉRIO ESCRITO ANTES DE RODAR; nenhum parâmetro iterado.
Motor e custos: conselho/regua.py; perna e quebra: conselho/estrutura.py (sem core/). Execução das fatias em 5 min.
Sem tabela de eventos macro: o veto de evento NÃO é aplicado.

PERNA E GATILHO (compra; venda espelhada)
  Tempo da perna TF ∈ {15m, 1h}; tempo da micro: 5m (para 15m) e 15m (para 1h).
  ZigZag ATR(14) fator 2,0 no TF; ZigZag ATR(14) fator 1,0 na micro; ATR = média móvel do true range até o candle;
  só pivôs confirmados (conhecidos no fechamento do candle que confirma).
  Fundo B = último pivô de baixa confirmado do TF. Pivô de micro P = último pivô de ALTA confirmado da micro que
  começou pelo menos 1 candle de TF depois do candle de B e já é conhecido no fechamento do candle de TF.
  Gatilho: o 1º candle de TF que FECHA acima de P (um gatilho por fundo B; se a mínima depois de B furou B, nada).
  Segunda a sexta (gatilho no fim de semana não entra).
  Topo T = máxima de TF de B até o candle do gatilho (congelado). L = T − B; só avisa se L/B ≥ 0,8%.
  Nível f da perna = T − f·L (f = 0,5 … 0,786 retração; f = 1 é o fundo; f = −0,618 é a extensão 1,618).
ENTRADA: 5 limitadas post-only em f = 0,50 / 0,572 / 0,643 / 0,714 / 0,786, pesos 10/15/20/25/30% (renormalizados
  entre as postas: abaixo do fechamento do gatilho, acima do stop). Válidas por 8 candles de TF (15m: 2 h; 1h: 8 h).
  Sem refazer a perna (simplificação: a perna fica congelada no gatilho).
STOP = B − 0,10%, a mercado. Stop < 0,4% do médio planejado: não sai.
SAÍDA — régua E2 para aviso de continuação (é a saída do E1):
  1R: realiza 33% e o stop do resto vai ao médio; parcial de 25% em T (f = 1,0 acima, o reteste do topo) só se T está a
  ≥ 1,5R do médio planejado; alvo final na extensão 1,618 (T + 0,618·L) e só avisa se ele está a ≥ 2R do médio
  planejado. Teto: 15m 24 h, 1h 72 h desde o 1º preenchimento (a mercado). Stop móvel atrás de pivô: NÃO simulado.
VARIANTES (fixas, 4): TF 15m e 1h × contexto "base" (sem filtro) e "terço" (fechamento do gatilho no terço de baixo do
  composto de 10 dias para compra, p < 1/3; terço de cima para venda, p > 2/3). O "ou Elliott permite" do especialista
  não é reproduzível sem o motor antigo: por isso o contexto vira variante, não filtro único.

CONTROLES DE E1 (todos com a mesma régua de saída):
  (1) FAIXA SORTEADA NA MESMA PERNA: 20 sorteios por evento, início u ~ U(0,1; 0,614), fatias em u + {0; 0,072; 0,143;
      0,214; 0,286} com os mesmos pesos, mesmo stop e mesmos filtros (0,4%, alvo a 2R).
  (2) DIREÇÃO SORTEADA: na 1ª execução, entrada única, stop a R_plan, parcial e alvo nos mesmos múltiplos de R, 1R 33%;
      esperança exata da moeda (média de mesma e oposta).
  (3) ENTRADA ÚNICA EM 0,618 com o mesmo stop e a régua recalculada para essa entrada.
APROVAÇÃO E1 (por variante): líquido > 0 nos 3 períodos com ≥ 30 preenchidos e, em treino e validação, média ≥ cada
  controle + 2 EP. Holdout olhado uma vez. Com 4 variantes, ~1 passa em 2 períodos por acaso: olhar o conjunto.

E2 — RÉGUA DE SAÍDA, nas MESMAS entradas do E1 (mesmos preenchimentos):
  (a) alvo fixo 2R sem 1R nem parciais; (b) a régua acima; (c) 1R 33% + stop no médio e o resto no alvo fixo 2R;
  (d) régua com níveis deslocados: parcial e alvo em múltiplos de R sorteados (20 vezes) entre os (parcial, alvo) da
  régua dos OUTROS eventos da mesma variante (mesma distribuição de distância, sem a proporção da perna).
  Nas entradas de direção sorteada: (b) e (a) com os mesmos múltiplos de R.
APROVAÇÃO E2 (por variante): em treino e validação, diferença pareada (b) − (a) > 2 EP e (b) − (d) > 2 EP nas entradas
  reais, E (b) − (a) NÃO > 2 EP nas entradas de direção sorteada (se ganha no sorteio, é tendência, não régua).

Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09.
Saídas: data/estudo_fibo_e1_e2.csv e data/estudo_fibo_e1_e2_resumo.md.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from conselho import regua as R  # noqa: E402
from conselho import estrutura as S  # noqa: E402

SAIDA = RAIZ / "data" / "estudo_fibo_e1_e2.csv"
SAIDA_MD = RAIZ / "data" / "estudo_fibo_e1_e2_resumo.md"

FRACS = [0.50, 0.572, 0.643, 0.714, 0.786]
PESOS = [0.10, 0.15, 0.20, 0.25, 0.30]
OFFS = [f - FRACS[0] for f in FRACS]
L_MIN = 0.008
FOLGA = 0.001
STOP_MIN = 0.004
FRAC_1R = 0.33
PARC_FR = 0.25
PARC_MIN_R = 1.5
RR_MIN = 2.0
N_SORTEIOS = 20
SEMENTE = 20261020
CONF = {"15m": {"micro": "5m", "validade": 24, "teto": 288},
        "1h": {"micro": "15m", "validade": 96, "teto": 864}}


def eventos(tf: str, B: R.Blocos):
    """Gatilhos de quebra de microestrutura no TF. Lista de dicts."""
    micro = CONF[tf]["micro"]
    dt = R.TF_MS[tf]
    dm = R.TF_MS[micro]
    g = R.carregar(tf, "2019-10-01")
    mi = R.carregar(micro, "2019-10-01")
    gh, gl, gc, gts = (g[c].to_numpy(float) for c in ("high", "low", "close", "timestamp"))
    gts = g["timestamp"].to_numpy(np.int64)
    mh, ml, mc = (mi[c].to_numpy(float) for c in ("high", "low", "close"))
    mts = mi["timestamp"].to_numpy(np.int64)
    piv = S.zigzag_atr(gh, gl, S.atr(gh, gl, gc), 2.0)
    pmi = S.zigzag_atr(mh, ml, S.atr(mh, ml, mc), 1.0)
    # micro: (ts do pivô, preço, tipo, ts em que fica conhecido)
    pmi = sorted([(int(mts[i]), p, t, int(mts[c]) + dm) for i, p, t, c in pmi], key=lambda x: x[3])
    piv = sorted(piv, key=lambda x: x[3])
    out = []
    ip = im = 0
    ult = {"L": None, "H": None}
    ult_m = {"L": None, "H": None}
    usado = set()
    n = len(gc)
    for i in range(n):
        while ip < len(piv) and piv[ip][3] <= i:
            ult[piv[ip][2]] = piv[ip]
            ip += 1
        fecha = int(gts[i]) + dt
        while im < len(pmi) and pmi[im][3] <= fecha:
            ult_m[pmi[im][2]] = pmi[im]
            im += 1
        for d in (1, -1):
            o = ult["L"] if d == 1 else ult["H"]
            mp = ult_m["H"] if d == 1 else ult_m["L"]
            if o is None or mp is None or (d, o[0]) in usado:
                continue
            io, po = o[0], o[1]
            if mp[0] < int(gts[io]) + dt or i <= io:
                continue
            if not ((d == 1 and gc[i] > mp[1]) or (d == -1 and gc[i] < mp[1])):
                continue
            usado.add((d, o[0]))
            seg_h, seg_l = gh[io:i + 1], gl[io:i + 1]
            if (d == 1 and seg_l[1:].min() < po) or (d == -1 and seg_h[1:].max() > po):
                continue
            x = float(seg_h.max()) if d == 1 else float(seg_l.min())
            L = abs(x - po)
            if fecha < int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000):
                continue
            out.append({"d": d, "ts_gat": fecha, "fech": float(gc[i]), "origem": po, "extremo": x, "L": L,
                        "L_pct": L / po, "ts_origem": int(gts[io])})
    print(f"  {tf}: {len(piv)} pivôs TF, {len(pmi)} pivôs micro, {len(out)} gatilhos")
    return out


def nivel(ev, fr):
    return ev["extremo"] - ev["d"] * fr * ev["L"]


def regua(ev, medio, stop):
    """(parciais, alvo, rr_alvo, parc_r) da régua para este médio; None se o alvo não está a ≥ 2R."""
    d = ev["d"]
    r = abs(medio - stop)
    alvo = nivel(ev, -0.618)
    rr = d * (alvo - medio) / r
    if rr < RR_MIN:
        return None
    top = ev["extremo"]
    pr = d * (top - medio) / r
    parc = [(top, PARC_FR)] if pr >= PARC_MIN_R else []
    return parc, alvo, rr, (pr if parc else None)


def montar(ev, fracs, pesos):
    d = ev["d"]
    stop = ev["origem"] * (1 - d * FOLGA)
    fat = R.fatias_postas(d, [(nivel(ev, fr), w) for fr, w in zip(fracs, pesos)], ev["fech"], stop)
    if not fat:
        return None, "sem fatia"
    medio = sum(p * w for p, w in fat)
    if abs(stop - medio) / medio < STOP_MIN:
        return None, "stop < 0,4%"
    rg = regua(ev, medio, stop)
    if rg is None:
        return None, "alvo < 2R"
    return {"fat": fat, "stop": stop, "medio": medio, "r_plan": abs(stop - medio) / medio, "rg": rg}, ""


def rodar(tf: str, m: R.Mercado, B: R.Blocos):
    t0 = time.time()
    val, teto = CONF[tf]["validade"], CONF[tf]["teto"]
    rng = np.random.default_rng(SEMENTE + (1 if tf == "1h" else 0))
    linhas = []
    for ev in eventos(tf, B):
        per = R.periodo_de(ev["ts_gat"])
        if not per or R.fim_de_semana(ev["ts_gat"] - 1) or ev["L_pct"] < L_MIN:
            if per and not R.fim_de_semana(ev["ts_gat"] - 1):
                linhas.append({"tf": tf, "periodo": per, "sai": False, "motivo": "L < 0,8%"})
            continue
        k0 = m.idx(ev["ts_gat"])
        if k0 is None:
            continue
        d = ev["d"]
        dn = (ev["ts_gat"] - 1) // R.DIA_MS
        comp = B.composto(dn)
        p = R.posicao_composto(ev["fech"], comp) if comp else np.nan
        terco = (p < 1 / 3) if d == 1 else (p > 2 / 3)
        reg = {"tf": tf, "data": R.data_de(ev["ts_gat"]), "ano": R.data_de(ev["ts_gat"])[:4], "periodo": per,
               "lado": "compra" if d == 1 else "venda", "L_pct": ev["L_pct"], "p_comp": p, "terco": bool(terco)}
        plano, motivo = montar(ev, FRACS, PESOS)
        if plano is None:
            reg.update({"sai": False, "motivo": motivo})
            linhas.append(reg)
            continue
        fat, stop, medio = plano["fat"], plano["stop"], plano["medio"]
        parc, alvo, rr, parc_r = plano["rg"]
        r = abs(medio - stop)
        sim = lambda fat_, st, alv, fr1, pc: R.simular(m, d, fat_, st, alv, k0, val, teto, False, fr1, pc)  # noqa: E731
        b = sim(fat, stop, alvo, FRAC_1R, parc)
        reg.update({"sai": True, "motivo": "", "r_plan": plano["r_plan"], "rr_alvo": rr, "parc_r": parc_r,
                    "n_fatias": len(fat), "preencheu": b is not None})
        if b is None:
            linhas.append(reg)
            continue
        a = sim(fat, stop, medio + d * 2 * r, 0.0, [])
        c = sim(fat, stop, medio + d * 2 * r, FRAC_1R, [])
        reg.update({"res_b": b["res_r"], "res_a": a["res_r"] if a else np.nan, "res_c": c["res_r"] if c else np.nan,
                    "saida": b["saida"], "tomou_1r": b["tomou_1r"], "frac": b["frac"]})
        # (2) direção sorteada: régua (b) e alvo fixo (a) nos mesmos múltiplos de R
        pr = [(parc_r, PARC_FR)] if parc_r is not None else []
        cb = R.controle_direcao(m, b, d, plano["r_plan"], rr, k0, False, val, teto, FRAC_1R, pr)
        ca = R.controle_direcao(m, b, d, plano["r_plan"], 2.0, k0, False, val, teto, 0.0, [])
        reg.update({"cd_b_m": cb[0], "cd_b_o": cb[1], "cd_a_m": ca[0], "cd_a_o": ca[1]})
        # (3) entrada única em 0,618
        p3, _ = montar(ev, [0.618], [1.0])
        if p3 is not None:
            s3 = sim(p3["fat"], p3["stop"], p3["rg"][1], FRAC_1R, p3["rg"][0])
            reg["res_618"] = s3["res_r"] if s3 else np.nan
        # (1) faixa sorteada na mesma perna
        res1 = []
        for u in rng.uniform(0.1, 0.9 - OFFS[-1], N_SORTEIOS):
            p1, _ = montar(ev, [u + o for o in OFFS], PESOS)
            if p1 is None:
                continue
            s1 = sim(p1["fat"], p1["stop"], p1["rg"][1], FRAC_1R, p1["rg"][0])
            if s1 is not None:
                res1.append(s1["res_r"])
        reg["res_faixa"] = float(np.mean(res1)) if res1 else np.nan
        reg["n_faixa"] = len(res1)
        reg["_ev"] = (k0, fat, stop, medio, r, d)
        linhas.append(reg)
    df = pd.DataFrame(linhas)
    # (d) régua deslocada: (parcial, alvo) em R sorteados entre os outros eventos da mesma variante
    df["res_d_base"] = np.nan
    df["res_d_terco"] = np.nan
    ok = df.index[df.get("preencheu", pd.Series(False, index=df.index)).fillna(False).astype(bool)]
    for var in ("base", "terco"):
        idx = [i for i in ok if var == "base" or df.at[i, "terco"]]
        pares = [(df.at[i, "parc_r"], df.at[i, "rr_alvo"]) for i in idx]
        for i in idx:
            k0, fat, stop, medio, r, d = df.at[i, "_ev"]
            res = []
            for j in rng.integers(0, len(pares), N_SORTEIOS):
                pr_, rr_ = pares[j]
                pc = [(medio + d * pr_ * r, PARC_FR)] if pr_ is not None and not pd.isna(pr_) else []
                s = R.simular(m, d, fat, stop, medio + d * rr_ * r, k0, val, teto, False, FRAC_1R, pc)
                if s is not None:
                    res.append(s["res_r"])
            df.at[i, "res_d_" + var] = float(np.mean(res)) if res else np.nan
    df = df.drop(columns=["_ev"], errors="ignore")
    for x in ("b", "a"):
        df[f"cd_{x}"] = 0.5 * (pd.to_numeric(df.get(f"cd_{x}_m"), errors="coerce")
                               + pd.to_numeric(df.get(f"cd_{x}_o"), errors="coerce"))
    print(f"  {tf}: {len(df)} linhas ({time.time() - t0:.0f}s)")
    return df


# ---------------------------------------------------------------------------------------------------- resumo
def sub(df, tf, var, per=None):
    s = df[(df.tf == tf) & (df.sai == True) & (df.preencheu == True)]
    if var == "terco":
        s = s[s.terco == True]
    if per:
        s = s[s.periodo == per]
    return s


def pareada(x, y):
    dif = (pd.to_numeric(x, errors="coerce") - pd.to_numeric(y, errors="coerce")).dropna()
    e = R.est(dif)
    return e["media"], e["se"], e["n"]


def resumo(df: pd.DataFrame) -> tuple[list[str], dict]:
    out = ["# Fibonacci E1 (escada 0,5–0,786 depois de quebra) + E2 (régua de saída) — passo 4 do plano de gestão\n",
           "Gerado por `scripts/estudo_fibo_e1_e2.py` (regra exata no docstring, escrita antes de rodar). BTCUSDT "
           "Binance, perna e gatilho em 15 min e 1 h, execução em 5 min, dias úteis, 2020-01 a 2026-09. Custo real "
           "(maker 0,02%, taker 0,055% + 0,02%, funding linear), leitura pessimista. Sem veto de evento macro.\n"]
    out.append("## Funil\n")
    out.append("| TF | gatilhos (dias úteis) | L < 0,8% | stop < 0,4% | alvo < 2R | sem fatia | aviso sai | preencheu | no terço |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for tf in CONF:
        s = df[df.tf == tf]
        pre = s[(s.sai == True) & (s.preencheu == True)]
        out.append(f"| {tf} | {len(s)} | {int((s.motivo == 'L < 0,8%').sum())} | {int((s.motivo == 'stop < 0,4%').sum())} | "
                   f"{int((s.motivo == 'alvo < 2R').sum())} | {int((s.motivo == 'sem fatia').sum())} | {int(s.sai.sum())} | "
                   f"{len(pre)} | {int(pre.terco.sum())} |")
    out.append("")
    vered = {}
    out.append("## E1 — entrada em escada com a régua como saída (R líquido por trade preenchido)\n")
    out.append("(1) faixa sorteada na mesma perna (média de 20); (2) direção sorteada; (3) entrada única em 0,618. "
               "Critério: líquido > 0 nos 3 períodos com n ≥ 30 e, em treino e validação, ≥ cada controle + 2 EP.\n")
    out.append("| variante | período | n | acerto | média R ± EP | (1) faixa | (2) direção | (3) 0,618 (n) | ≥(1)+2EP | ≥(2)+2EP | ≥(3)+2EP |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for tf in CONF:
        for var in ("base", "terco"):
            nome = f"E1 {tf} {var}"
            mot = []
            for per, _, _ in R.PERIODOS:
                s = sub(df, tf, var, per)
                e = R.est(s.res_b)
                c1, c2, c3 = R.est(s.res_faixa), R.est(s.cd_b), R.est(s.res_618)
                oks = [e["n"] > 1 and not np.isnan(c["media"]) and e["media"] >= c["media"] + 2 * e["se"] for c in (c1, c2, c3)]
                out.append(f"| {nome} | {per} | {e['n']} | {R.pct(e['acerto'])} | {R.f(e['media'])} ± {R.f(e['se'])} | "
                           f"{R.f(c1['media'])} | {R.f(c2['media'])} | {R.f(c3['media'])} ({c3['n']}) | "
                           + " | ".join("sim" if o else "não" for o in oks) + " |")
                if e["n"] < R.MIN_N:
                    mot.append(f"{per}: n={e['n']} < 30")
                    continue
                if not e["media"] > 0:
                    mot.append(f"{per}: líquido {R.f(e['media'])} ≤ 0")
                if per != "holdout" and not all(oks):
                    mot.append(f"{per}: não fica 2 EP acima de todos os controles")
            v = "APROVADA" if not mot else ("INCONCLUSIVA" if all("< 30" in x for x in mot) else "REPROVADA")
            vered[nome] = (v, mot)
    out.append("")
    out.append("### E1 por lado (base, todos os períodos de treino+validação; informativo)\n")
    out.append("| TF | lado | n | média R (régua) | direção sorteada | faixa sorteada |")
    out.append("|---|---|---|---|---|---|")
    for tf in CONF:
        s = sub(df, tf, "base")
        s = s[s.periodo != "holdout"]
        for lado, q in s.groupby("lado"):
            out.append(f"| {tf} | {lado} | {len(q)} | {R.f(q.res_b.mean())} | {R.f(q.cd_b.mean())} | {R.f(q.res_faixa.mean())} |")
    out.append("")
    out.append("### E1 ano a ano (base)\n")
    out.append("| TF | ano | n | média R | direção sorteada |")
    out.append("|---|---|---|---|---|")
    for tf in CONF:
        for ano, q in sub(df, tf, "base").groupby("ano"):
            out.append(f"| {tf} | {ano} | {len(q)} | {R.f(q.res_b.mean())} | {R.f(q.cd_b.mean())} |")
    out.append("")
    out.append("## E2 — a régua contra outras saídas, nas mesmas entradas\n")
    out.append("Médias em R. Diferenças pareadas (mesmo trade) com EP. (a) alvo fixo 2R; (b) régua; (c) 1R + stop no "
               "médio + resto em 2R; (d) régua com níveis sorteados (mesma distribuição de distância). "
               "Critério: em treino e validação (b)−(a) > 2 EP e (b)−(d) > 2 EP nas entradas reais, e (b)−(a) NÃO > 2 EP "
               "nas entradas de direção sorteada.\n")
    out.append("| variante | período | n | (a) | (b) | (c) | (d) | (b)−(a) ± EP | (b)−(d) ± EP | sorteadas: (b)−(a) ± EP |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for tf in CONF:
        for var in ("base", "terco"):
            nome = f"E2 {tf} {var}"
            mot = []
            for per, _, _ in R.PERIODOS:
                s = sub(df, tf, var, per)
                dcol = "res_d_" + var
                ba = pareada(s.res_b, s.res_a)
                bd = pareada(s.res_b, s[dcol]) if dcol in s else (np.nan, np.nan, 0)
                sa = pareada(s.cd_b, s.cd_a)
                out.append(f"| {nome} | {per} | {len(s)} | {R.f(s.res_a.mean())} | {R.f(s.res_b.mean())} | "
                           f"{R.f(s.res_c.mean())} | {R.f(s[dcol].mean() if dcol in s else np.nan)} | "
                           f"{R.f(ba[0])} ± {R.f(ba[1])} | {R.f(bd[0])} ± {R.f(bd[1])} | {R.f(sa[0])} ± {R.f(sa[1])} |")
                if per == "holdout":
                    continue
                if len(s) < R.MIN_N:
                    mot.append(f"{per}: n={len(s)} < 30")
                    continue
                if not ba[0] > 2 * ba[1]:
                    mot.append(f"{per}: (b) não bate (a) por 2 EP")
                if not bd[0] > 2 * bd[1]:
                    mot.append(f"{per}: (b) não bate (d) por 2 EP")
                if sa[0] > 2 * sa[1]:
                    mot.append(f"{per}: (b) também bate (a) nas entradas sorteadas")
            v = "APROVADA" if not mot else ("INCONCLUSIVA" if all("< 30" in x for x in mot) else "REPROVADA")
            vered[nome] = (v, mot)
    out.append("")
    out.append("### Saídas da régua (base)\n")
    out.append("| TF | saída | n | média R |")
    out.append("|---|---|---|---|")
    for tf in CONF:
        for sd, q in sub(df, tf, "base").groupby("saida"):
            out.append(f"| {tf} | {sd} | {len(q)} | {R.f(q.res_b.mean())} |")
    out.append("")
    out.append("## Veredito pelo critério\n")
    for nome, (v, mot) in vered.items():
        out.append(f"- **{nome}: {v}**" + (" — " + "; ".join(dict.fromkeys(mot)) if mot else ""))
    out.append("")
    return out, vered


def main():
    t0 = time.time()
    m = R.Mercado(R.carregar("5m", "2019-11-01"))
    B = R.Blocos(m)
    print(f"dados ({time.time() - t0:.0f}s)")
    df = pd.concat([rodar(tf, m, B) for tf in CONF], ignore_index=True)
    df.to_csv(SAIDA, index=False)
    md, vered = resumo(df)
    SAIDA_MD.write_text("\n".join(md), encoding="utf-8")
    for k, (v, mot) in vered.items():
        print(f"{k}: {v} {mot}")
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
