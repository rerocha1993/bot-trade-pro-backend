# scripts/estudo_tpo_e2_e3.py
"""
TPO E2 — "Cauda no bloco de 30 min na borda" (plano_gestao.md 2.4; docs/especialistas/tpo.md E2) e
TPO E3 — "A América contra a manhã" (docs/especialistas/tpo.md E3). Passo 3 da seção 4 do plano.
BTCUSDT 5 min (Binance), 2020-01 a 2026-09. CRITÉRIO ESCRITO ANTES DE RODAR; nenhum parâmetro iterado.
Motor, custos e leitura pessimista: conselho/regua.py (sem core/). Execução em 5 min. Sem tabela de eventos macro no
projeto: o veto de evento (regra 9) NÃO é aplicado (ressalva no resumo).

==================================================================================================== TPO E2
Dias: segunda a sexta (UTC). Mapa fixado às 00:00 do dia D:
  composto = merge dos 10 dias UTC anteriores (VAL, POC, VAH); ontem = perfil de D−1 (≥ 40 blocos);
  naked POCs = POCs dos 30 dias anteriores que nenhum dia seguinte até D−1 tocou.
Níveis de COMPRA: VAL do composto, VAL de ontem, naked POCs; de VENDA: VAH do composto, VAH de ontem, naked POCs.
  Só valem no quartil de fora do composto: p = (nível − VAL_c)/(VAH_c − VAL_c) < 0,25 (compra) ou > 0,75 (venda).
  Naked POC tocado hoje antes do bloco deixa de valer.
Blocos elegíveis: blocos de 30 min que começam entre 08:00 e 19:30 UTC (Europa e América; madrugada não conta).
Gatilho de COMPRA no bloco b e nível ℓ (venda espelhada):
  mínima < ℓ < fechamento; "de longe": algum fechamento de 5 min nas 4 h antes do bloco ≥ ℓ × 1,005;
  cauda = min(abertura, fechamento) − mínima ≥ 0,30% do fechamento e ≥ 60% da amplitude do bloco;
  fechamento no terço superior do bloco (≥ mínima + 2/3 da amplitude).
  Vários níveis no mesmo bloco e lado = 1 evento (prioridade composto > ontem > naked). Um aviso por nível por dia.
Zona (compra): 3 limitadas post-only: fechamento (20%), fechamento − 25% da cauda (30%), fechamento − 50% da cauda
  (50%). Válidas por 24 candles de 5 min (2 h) a partir do fechamento do bloco.
Stop = mínima do bloco − 0,10%, a mercado. Stop < 0,4% do médio planejado: o aviso não sai.
Alvo = o nível mais próximo acima do médio planejado a ≥ 2R entre POC do dia em formação (blocos de D até b),
  POC de ontem e naked POCs ainda não tocados. Sem nível a ≥ 2R: o aviso não sai.
Gestão: 1R realiza 50% e o stop do resto vai ao médio; teto de 8 h desde o 1º preenchimento ou até 20:00 UTC do dia
  (o que vier primeiro), a mercado. "Sem 1R" (alvo inteiro) só como informação.
Controles:
  (a) CAUDA SEM NÍVEL: todo bloco elegível (mesmos dias e horas) com a mesma cauda (0,30%, 60%, terço) em que nenhum
      nível do mapa daquele lado (composto, ontem, naked) está dentro da cauda (entre a mínima e o fechamento); sem
      "de longe", sem quartil; mesma zona, stop, piso, regra de alvo, validade e teto. População inteira (sem sorteio).
      Cauda num nível que não qualifica (quartil, "de longe", nível já usado no dia) não entra em nenhum dos grupos.
  (a') informativo: (a) só com o fechamento do bloco no quartil de fora do composto.
  (b) DIREÇÃO SORTEADA: mesma hora e preço da 1ª execução, entrada única, stop a R_plan, alvo a RR_plan × R_plan,
      mesma gestão; esperança exata da moeda = média de (mesma direção, direção oposta).
APROVAÇÃO: líquido médio > 0 nos 3 períodos com ≥ 30 preenchidos em cada (abaixo de 30 = inconclusivo) E, em treino e
  validação, média ≥ (a) + 2 EP e ≥ (b) + 2 EP (EP = desvio/√n da estratégia). Holdout lido uma vez.
  Se (a) ficar igual ou acima de E2, o nível não acrescenta nada à cauda: o TPO sai de gatilho.

==================================================================================================== TPO E3
Dias: segunda a sexta. Manhã = os 27 blocos de 00:00 a 13:30 UTC (todos presentes); ontem com ≥ 40 blocos.
  POC_M, máx_M, mín_M = perfil da manhã; posPOC = (POC_M − mín_M)/(máx_M − mín_M); P13 = fechamento às 13:30.
VENDA (forma P): posPOC ≥ 2/3, P13 > VAH de ontem, P13 > POC_M e P13 dentro de [mínima, máxima] do composto de 10 dias.
COMPRA (forma b): posPOC ≤ 1/3, P13 < VAL de ontem, P13 < POC_M e P13 dentro do composto.
Gatilho: o 1º bloco da América que começa às 13:30, 14:00, 14:30, 15:00 ou 15:30 e fecha abaixo de POC_M (venda) /
  acima (compra). Se a América já passou do stop antes do gatilho: o aviso não sai.
Zona (venda): 3 limitadas post-only: POC_M − 0,05% (20%), POC_M + 0,075% (30%), POC_M + 0,20% (50%); compra espelhada.
  Válidas até 18:00 UTC.
Stop = máxima da manhã + 0,10% (venda) / mínima − 0,10% (compra), a mercado. Stop < 0,4% do médio: não sai.
Alvo (venda) = o nível mais próximo abaixo do médio a ≥ 2R entre mínima da Ásia (00:00–08:00), VAH/POC/VAL de ontem e
  naked POCs não tocados até o gatilho (compra: máxima da Ásia e os mesmos). Sem nível a ≥ 2R: não sai.
Gestão: 1R realiza 50%, stop no médio; teto de 24 h desde o 1º preenchimento.
Controles: (1) NÍVEL SORTEADO: 20 sorteios por dia de um nível uniforme em [mín_M, máx_M] no lugar do POC_M no gatilho,
  na condição P13 vs nível e na zona (a forma P/b continua a do POC real); stop e alvo pela mesma regra.
  (2) DIREÇÃO SORTEADA como em E2.
APROVAÇÃO: por lado (forma P = venda, forma b = compra, medidas separadas), como em E2, com (1) e (2) no lugar de (a)/(b).

Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09.
Saídas: data/estudo_tpo_e2.csv, data/estudo_tpo_e2_resumo.md, data/estudo_tpo_e3.csv, data/estudo_tpo_e3_resumo.md.
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

SAIDA_E2 = RAIZ / "data" / "estudo_tpo_e2.csv"
SAIDA_E2_MD = RAIZ / "data" / "estudo_tpo_e2_resumo.md"
SAIDA_E3 = RAIZ / "data" / "estudo_tpo_e3.csv"
SAIDA_E3_MD = RAIZ / "data" / "estudo_tpo_e3_resumo.md"

CAUDA_MIN = 0.003
CAUDA_FRAC = 0.60
LONGE = 0.005
JANELA_LONGE = 48          # candles de 5 min = 4 h
FOLGA = 0.001
STOP_MIN = 0.004
RR_MIN = 2.0
VALIDADE_E2 = 24
TETO_E2 = 96
TETO_E3 = 288
N_SORTEIOS = 20
SEMENTE = 20261020


# ---------------------------------------------------------------------------------------------------- E2
def cauda(d: int, o: float, h: float, l: float, c: float):
    """Tamanho da cauda se o bloco tem a cauda do gatilho no lado d (compra = cauda de baixo), senão None."""
    amp = h - l
    if amp <= 0:
        return None
    if d == 1:
        t = min(o, c) - l
        terco = c >= l + 2 * amp / 3
    else:
        t = h - max(o, c)
        terco = c <= l + amp / 3
    if t >= CAUDA_MIN * c and t >= CAUDA_FRAC * amp and terco:
        return t
    return None


def alvo_mais_proximo(d: int, medio: float, stop: float, candidatos) -> float | None:
    r = abs(medio - stop)
    ok = [x for x in candidatos if x is not None and d * (x - medio) >= RR_MIN * r]
    if not ok:
        return None
    return min(ok, key=lambda x: abs(x - medio))


def trade_e2(m: R.Mercado, d: int, o, h, l, c, k_ult: int, k_fim: int, alvos_cand):
    t = cauda(d, o, h, l, c)
    stop = l * (1 - FOLGA) if d == 1 else h * (1 + FOLGA)
    fat = [(c, 0.2), (c - d * 0.25 * t, 0.3), (c - d * 0.5 * t, 0.5)]
    fat = R.fatias_postas(d, fat, c * (1 + d * 1e-9), stop)
    if not fat:
        return {"sai": False, "motivo": "sem fatia"}
    medio = sum(p * w for p, w in fat)
    r_plan = abs(stop - medio) / medio
    base = {"cauda_pct": t / c, "r_plan": r_plan, "medio_plan": medio, "stop": stop}
    if r_plan < STOP_MIN:
        return {**base, "sai": False, "motivo": "stop < 0,4%"}
    alvo = alvo_mais_proximo(d, medio, stop, alvos_cand)
    if alvo is None:
        return {**base, "sai": False, "motivo": "sem alvo a 2R"}
    rr = abs(alvo - medio) / abs(medio - stop)
    k0 = k_ult + 1
    com = R.simular(m, d, fat, stop, alvo, k0, VALIDADE_E2, TETO_E2, False, 0.5, k_fim=k_fim)
    sem = R.simular(m, d, fat, stop, alvo, k0, VALIDADE_E2, TETO_E2, False, 0.0, k_fim=k_fim)
    a, b = R.controle_direcao(m, com, d, r_plan, rr, k0, False, VALIDADE_E2, TETO_E2, 0.5, k_fim=k_fim)
    return {**base, "sai": True, "alvo": alvo, "rr_plan": rr, "com": com, "sem": sem, "cd_mesma": a, "cd_oposta": b}


def rodar_e2(m: R.Mercado, B: R.Blocos):
    t0 = time.time()
    cl5 = m.a_cl
    # máx/mín dos fechamentos de 5 min nas 4 h ANTES de cada índice k (janela [k−48, k))
    from numpy.lib.stride_tricks import sliding_window_view as sw
    mx = np.full(len(cl5) + 1, np.nan)
    mn = np.full(len(cl5) + 1, np.nan)
    w = sw(cl5, JANELA_LONGE)
    mx[JANELA_LONGE:] = w.max(axis=1)
    mn[JANELA_LONGE:] = w.min(axis=1)
    linhas = []
    for dn in B.dias():
        ts_d = dn * R.DIA_MS
        per = R.periodo_de(ts_d)
        if not per or R.fim_de_semana(ts_d) or (dn - 1) not in B.dia_ini or B.n_blocos(dn - 1) < 40:
            continue
        comp = B.composto(dn)
        if comp is None:
            continue
        val_c, _, vah_c, _, _ = comp
        if not vah_c > val_c:
            continue
        poc_o, val_o, vah_o, *_ = B.perfil_dia(dn - 1)
        naked = B.naked_pocs(dn)
        a, z = B.dia_ini[dn], B.dia_fim[dn]
        k_fim = m.idx(ts_d + 20 * R.HORA - R.M5)
        if k_fim is None:
            continue
        usados = set()
        hi_hoje, lo_hoje = -np.inf, np.inf
        for bi in range(a, z):
            bts = int(B.ts[bi])
            o, h, l, c = float(B.op[bi]), float(B.hi[bi]), float(B.lo[bi]), float(B.cl[bi])
            hora = (bts % R.DIA_MS) / R.HORA
            naked_validos = [x for x in naked if not (lo_hoje <= x <= hi_hoje)]
            hi_hoje, lo_hoje = max(hi_hoje, h), min(lo_hoje, l)
            if not (8 <= hora <= 19.5):
                continue
            k_prim, k_ult = int(B.k_prim[bi]), int(B.k_ult[bi])
            p_bloco = (c - val_c) / (vah_c - val_c)
            for d in (1, -1):
                if d == 1:
                    cand = [("composto_VAL", val_c), ("ontem_VAL", val_o)] + [("naked", x) for x in naked_validos]
                else:
                    cand = [("composto_VAH", vah_c), ("ontem_VAH", vah_o)] + [("naked", x) for x in naked_validos]
                niveis = []
                algum_nivel = False
                for nome, lv in cand:
                    if not ((d == 1 and l < lv < c) or (d == -1 and h > lv > c)):
                        continue
                    algum_nivel = True
                    p = (lv - val_c) / (vah_c - val_c)
                    if (d == 1 and p >= 0.25) or (d == -1 and p <= 0.75):
                        continue
                    ref = mx[k_prim] if d == 1 else mn[k_prim]
                    if np.isnan(ref) or not ((d == 1 and ref >= lv * (1 + LONGE)) or (d == -1 and ref <= lv * (1 - LONGE))):
                        continue
                    chave = (d, nome, round(lv, 2))
                    if chave in usados:
                        continue
                    niveis.append((nome, lv, chave))
                t = cauda(d, o, h, l, c)
                if t is None:
                    continue
                if algum_nivel and not niveis:
                    continue          # cauda num nível do mapa que não qualifica: nem E2 nem controle
                grupo = "E2" if niveis else "sem_nivel"
                if niveis:
                    for _, _, ch in niveis:
                        usados.add(ch)
                poc_hoje = B.perfil_parcial(a, bi + 1)[0]
                alvos = [poc_hoje, poc_o] + list(naked_validos)
                tr = trade_e2(m, d, o, h, l, c, k_ult, k_fim, alvos)
                reg = {"data": R.data_de(bts), "ano": R.data_de(bts)[:4], "periodo": per, "hora": hora,
                       "grupo": grupo, "lado": "compra" if d == 1 else "venda",
                       "nivel": niveis[0][0] if niveis else "", "preco_nivel": niveis[0][1] if niveis else np.nan,
                       "n_niveis": len(niveis), "p_bloco": p_bloco,
                       "quartil_fora": (p_bloco < 0.25) if d == 1 else (p_bloco > 0.75),
                       "sai": tr["sai"], "motivo": tr.get("motivo", "")}
                for kk in ("cauda_pct", "r_plan", "rr_plan"):
                    reg[kk] = tr.get(kk, np.nan)
                if tr["sai"]:
                    com, sem = tr["com"], tr["sem"]
                    reg.update({"preencheu": com is not None, "res_r": com["res_r"] if com else np.nan,
                                "res_r_sem1r": sem["res_r"] if sem else np.nan,
                                "saida": com["saida"] if com else "", "tomou_1r": com["tomou_1r"] if com else False,
                                "cd_mesma": tr["cd_mesma"], "cd_oposta": tr["cd_oposta"]})
                else:
                    reg["preencheu"] = False
                linhas.append(reg)
        if dn % 365 == 0:
            print(f"  E2 {R.data_de(ts_d)} linhas={len(linhas)} ({time.time() - t0:.0f}s)")
    df = pd.DataFrame(linhas)
    df["cd"] = 0.5 * (pd.to_numeric(df.get("cd_mesma"), errors="coerce") + pd.to_numeric(df.get("cd_oposta"), errors="coerce"))
    df.to_csv(SAIDA_E2, index=False)
    print(f"E2: {len(df)} linhas ({time.time() - t0:.0f}s)")
    return df


# ---------------------------------------------------------------------------------------------------- E3
def evento_e3(m, B, a, d, nivel, stop, ts_d):
    """Primeiro bloco da América (13:30..15:30) que fecha além do nível. Devolve (bi, fechamento) ou None."""
    for j in range(5):
        tb = ts_d + 13 * R.HORA + 30 * 60_000 + j * R.BLOCO_MS
        bi = B.pos.get(tb)
        if bi is None:
            return None
        h, l, c = float(B.hi[bi]), float(B.lo[bi]), float(B.cl[bi])
        if (d == -1 and h >= stop) or (d == 1 and l <= stop):
            return None
        if (d == -1 and c < nivel) or (d == 1 and c > nivel):
            return bi, c
    return None


def trade_e3(m, B, d, nivel, stop, bi, c, k_val_fim, alvos_cand):
    fat = [(nivel * (1 + 0.0005), 0.2), (nivel * (1 - 0.00075), 0.3), (nivel * (1 - 0.002), 0.5)] if d == 1 else \
          [(nivel * (1 - 0.0005), 0.2), (nivel * (1 + 0.00075), 0.3), (nivel * (1 + 0.002), 0.5)]
    fat = R.fatias_postas(d, fat, c, stop)
    if not fat:
        return {"sai": False, "motivo": "sem fatia"}
    medio = sum(p * w for p, w in fat)
    r_plan = abs(stop - medio) / medio
    base = {"r_plan": r_plan, "medio_plan": medio}
    if (d == -1 and stop <= medio) or (d == 1 and stop >= medio):
        return {**base, "sai": False, "motivo": "stop do lado errado"}
    if r_plan < STOP_MIN:
        return {**base, "sai": False, "motivo": "stop < 0,4%"}
    alvo = alvo_mais_proximo(d, medio, stop, alvos_cand)
    if alvo is None:
        return {**base, "sai": False, "motivo": "sem alvo a 2R"}
    rr = abs(alvo - medio) / abs(medio - stop)
    k0 = int(B.k_ult[bi]) + 1
    validade = max(1, k_val_fim - k0 + 1)
    com = R.simular(m, d, fat, stop, alvo, k0, validade, TETO_E3, False, 0.5)
    sem = R.simular(m, d, fat, stop, alvo, k0, validade, TETO_E3, False, 0.0)
    out = {**base, "sai": True, "alvo": alvo, "rr_plan": rr, "com": com, "sem": sem}
    out["cd_mesma"], out["cd_oposta"] = R.controle_direcao(m, com, d, r_plan, rr, k0, False, validade, TETO_E3, 0.5)
    return out


def rodar_e3(m: R.Mercado, B: R.Blocos):
    t0 = time.time()
    rng = np.random.default_rng(SEMENTE)
    linhas, ctrl = [], []
    for dn in B.dias():
        ts_d = dn * R.DIA_MS
        per = R.periodo_de(ts_d)
        if not per or R.fim_de_semana(ts_d) or (dn - 1) not in B.dia_ini or B.n_blocos(dn - 1) < 40:
            continue
        comp = B.composto(dn)
        if comp is None:
            continue
        a = B.dia_ini[dn]
        manha = [B.pos.get(ts_d + j * R.BLOCO_MS) for j in range(27)]
        if any(x is None for x in manha) or manha[0] != a:
            continue
        poc_m, _, _ = B.perfil_parcial(a, a + 27)
        hi_m, lo_m = float(B.hi[a:a + 27].max()), float(B.lo[a:a + 27].min())
        if not hi_m > lo_m:
            continue
        pos_poc = (poc_m - lo_m) / (hi_m - lo_m)
        p13 = float(B.cl[a + 26])
        poc_o, val_o, vah_o, *_ = B.perfil_dia(dn - 1)
        dentro = comp[3] <= p13 <= comp[4]
        if pos_poc >= 2 / 3 and p13 > vah_o and p13 > poc_m and dentro:
            d = -1
        elif pos_poc <= 1 / 3 and p13 < val_o and p13 < poc_m and dentro:
            d = 1
        else:
            continue
        stop = hi_m * (1 + FOLGA) if d == -1 else lo_m * (1 - FOLGA)
        asia_hi, asia_lo = float(B.hi[a:a + 16].max()), float(B.lo[a:a + 16].min())
        k_val_fim = m.idx(ts_d + 18 * R.HORA - R.M5)
        if k_val_fim is None:
            continue
        naked = B.naked_pocs(dn)

        def alvos_ate(bi):
            hh, ll = float(B.hi[a:bi + 1].max()), float(B.lo[a:bi + 1].min())
            nk = [x for x in naked if not (ll <= x <= hh)]
            return [asia_lo if d == -1 else asia_hi, vah_o, poc_o, val_o] + nk

        reg = {"data": R.data_de(ts_d), "ano": R.data_de(ts_d)[:4], "periodo": per,
               "lado": "compra" if d == 1 else "venda", "poc_manha": poc_m, "pos_poc": pos_poc, "p13": p13}
        ev = evento_e3(m, B, a, d, poc_m, stop, ts_d)
        if ev is None:
            reg.update({"gatilho": False, "sai": False, "motivo": "sem gatilho", "preencheu": False})
        else:
            bi, c = ev
            tr = trade_e3(m, B, d, poc_m, stop, bi, c, k_val_fim, alvos_ate(bi))
            reg.update({"gatilho": True, "bloco": (int(B.ts[bi]) % R.DIA_MS) / R.HORA, "sai": tr["sai"],
                        "motivo": tr.get("motivo", ""), "r_plan": tr.get("r_plan", np.nan),
                        "rr_plan": tr.get("rr_plan", np.nan)})
            if tr["sai"]:
                com, sem = tr["com"], tr["sem"]
                reg.update({"preencheu": com is not None, "res_r": com["res_r"] if com else np.nan,
                            "res_r_sem1r": sem["res_r"] if sem else np.nan, "saida": com["saida"] if com else "",
                            "cd_mesma": tr["cd_mesma"], "cd_oposta": tr["cd_oposta"]})
            else:
                reg["preencheu"] = False
        linhas.append(reg)
        # controle (1): nível sorteado na faixa da manhã
        for s, nv in enumerate(rng.uniform(lo_m, hi_m, N_SORTEIOS)):
            if not ((d == -1 and p13 > nv) or (d == 1 and p13 < nv)):
                continue
            ev2 = evento_e3(m, B, a, d, nv, stop, ts_d)
            if ev2 is None:
                continue
            tr2 = trade_e3(m, B, d, nv, stop, ev2[0], ev2[1], k_val_fim, alvos_ate(ev2[0]))
            if tr2["sai"] and tr2["com"] is not None:
                ctrl.append({"periodo": per, "lado": reg["lado"], "sorteio": s, "res_r": tr2["com"]["res_r"]})
    df = pd.DataFrame(linhas)
    df["cd"] = 0.5 * (pd.to_numeric(df.get("cd_mesma"), errors="coerce") + pd.to_numeric(df.get("cd_oposta"), errors="coerce"))
    df.to_csv(SAIDA_E3, index=False)
    print(f"E3: {len(df)} dias com forma, controle {len(ctrl)} ({time.time() - t0:.0f}s)")
    return df, pd.DataFrame(ctrl)


# ---------------------------------------------------------------------------------------------------- resumo
def linha_tab(nome, per, e, ctrls: dict, sem=None):
    cols = [nome, per, str(e["n"]), R.pct(e["acerto"]), f"{R.f(e['media'])} ± {R.f(e['se'])}"]
    oks = []
    for k, (cm, cn) in ctrls.items():
        ok = e["n"] > 1 and not np.isnan(cm) and e["media"] >= cm + 2 * e["se"]
        cols.append(f"{R.f(cm)} ({cn})")
        oks.append(ok)
    cols += ["sim" if o else "não" for o in oks]
    if sem is not None:
        cols.append(R.f(sem))
    return "| " + " | ".join(cols) + " |", oks


def veredito(res_por_per: dict, oks_por_per: dict) -> tuple[str, list[str]]:
    """REPROVADA se algum período com n ≥ 30 falha (líquido ≤ 0 ou, em treino/validação, < controle + 2 EP);
    senão INCONCLUSIVA se algum período tem n < 30; senão APROVADA."""
    falhas, curtos = [], []
    for per, _, _ in R.PERIODOS:
        e = res_por_per[per]
        if e["n"] < R.MIN_N:
            curtos.append(f"{per}: n={e['n']} < 30")
            continue
        if not e["media"] > 0:
            falhas.append(f"{per}: líquido {R.f(e['media'])} ≤ 0")
        if per in oks_por_per and per != "holdout" and not all(oks_por_per[per]):
            falhas.append(f"{per}: não fica 2 EP acima de todos os controles")
    if falhas:
        return "REPROVADA", falhas + curtos
    if curtos:
        return "INCONCLUSIVA", curtos
    return "APROVADA", []


def resumo_e2(df: pd.DataFrame) -> tuple[list[str], dict]:
    out = ["# TPO E2 — cauda no bloco de 30 min na borda (passo 3 do plano de gestão)\n",
           "Gerado por `scripts/estudo_tpo_e2_e3.py` (regra exata no docstring, escrita antes de rodar). "
           "BTCUSDT 5 min Binance, dias úteis, blocos das 08:00 às 20:00 UTC, 2020-01 a 2026-09. "
           "Custo real (maker 0,02%, taker 0,055% + 0,02% de slippage, funding linear), leitura pessimista. "
           "Sem veto de evento macro (não há tabela no projeto).\n"]
    out.append("## Funil\n")
    out.append("| grupo | lado | eventos com cauda | stop < 0,4% | sem alvo a 2R | sem fatia | aviso sai | preencheu |")
    out.append("|---|---|---|---|---|---|---|---|")
    for g in ("E2", "sem_nivel"):
        for lado in ("compra", "venda"):
            s = df[(df.grupo == g) & (df.lado == lado)]
            out.append(f"| {g} | {lado} | {len(s)} | {int((s.motivo == 'stop < 0,4%').sum())} | "
                       f"{int((s.motivo == 'sem alvo a 2R').sum())} | {int((s.motivo == 'sem fatia').sum())} | "
                       f"{int(s.sai.sum())} | {int(s.preencheu.fillna(False).astype(bool).sum())} |")
    out.append("")
    ok_df = df[(df.sai == True) & (df.preencheu == True)]
    e2 = ok_df[ok_df.grupo == "E2"]
    sn = ok_df[ok_df.grupo == "sem_nivel"]
    out.append("## Resultado (R líquido por trade preenchido, 1R realiza 50% e stop no médio)\n")
    out.append("(a) = mesma cauda sem nível (população); (b) = direção sorteada (média de mesma e oposta). "
               "Critério: líquido > 0 nos 3 períodos com n ≥ 30 e, em treino e validação, ≥ (a) + 2 EP e ≥ (b) + 2 EP.\n")
    out.append("| linha | período | n | acerto (>0) | média R ± EP | (a) cauda sem nível (n) | (b) direção sorteada (n) | ≥ (a)+2EP | ≥ (b)+2EP | sem 1R |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    vered = {}
    for lado_f, nome in ((None, "E2 (compra+venda)"), ("compra", "E2 compra"), ("venda", "E2 venda")):
        res, oks = {}, {}
        for per, _, _ in R.PERIODOS:
            s = e2[e2.periodo == per]
            c = sn[sn.periodo == per]
            if lado_f:
                s, c = s[s.lado == lado_f], c[c.lado == lado_f]
            e = R.est(s.res_r)
            ea = R.est(c.res_r)
            eb = R.est(s.cd)
            lin, ok = linha_tab(nome, per, e, {"a": (ea["media"], ea["n"]), "b": (eb["media"], eb["n"])},
                                R.est(s.res_r_sem1r)["media"])
            out.append(lin)
            res[per], oks[per] = e, ok
        vered[nome] = veredito(res, oks)
    out.append("")
    out.append("### Controle (a') informativo: cauda sem nível com o fechamento no quartil de fora do composto\n")
    out.append("| período | n | acerto | média R ± EP |")
    out.append("|---|---|---|---|")
    for per, _, _ in R.PERIODOS:
        c = sn[(sn.periodo == per) & (sn.quartil_fora == True)]
        e = R.est(c.res_r)
        out.append(f"| {per} | {e['n']} | {R.pct(e['acerto'])} | {R.f(e['media'])} ± {R.f(e['se'])} |")
    out.append("")
    out.append("### Por nível (E2, todos os períodos; informativo)\n")
    out.append("| nível | n | acerto | média R ± EP |")
    out.append("|---|---|---|---|")
    for nv, s in e2.groupby("nivel"):
        e = R.est(s.res_r)
        out.append(f"| {nv} | {e['n']} | {R.pct(e['acerto'])} | {R.f(e['media'])} ± {R.f(e['se'])} |")
    out.append("")
    out.append("### Ano a ano (E2)\n")
    out.append("| ano | n | média R | (a) média | (b) média |")
    out.append("|---|---|---|---|---|")
    for ano, s in e2.groupby("ano"):
        c = sn[sn.ano == ano]
        out.append(f"| {ano} | {len(s)} | {R.f(R.est(s.res_r)['media'])} | {R.f(R.est(c.res_r)['media'])} | "
                   f"{R.f(R.est(s.cd)['media'])} |")
    out.append("")
    out.append("### Saídas (E2)\n")
    out.append("| saída | n | média R |")
    out.append("|---|---|---|")
    for sd, s in e2.groupby("saida"):
        out.append(f"| {sd} | {len(s)} | {R.f(s.res_r.mean())} |")
    out.append("")
    out.append("## Veredito pelo critério\n")
    for nome, (v, mot) in vered.items():
        out.append(f"- **{nome}: {v}**" + (" — " + "; ".join(mot) if mot else ""))
    out.append("")
    return out, vered


def resumo_e3(df: pd.DataFrame, ctrl: pd.DataFrame) -> tuple[list[str], dict]:
    out = ["# TPO E3 — a América contra a manhã (passo 3 do plano de gestão)\n",
           "Gerado por `scripts/estudo_tpo_e2_e3.py` (regra exata no docstring, escrita antes de rodar). "
           "BTCUSDT 5 min Binance, dias úteis, 2020-01 a 2026-09. Custo real, leitura pessimista, sem veto de evento.\n"]
    out.append("## Funil\n")
    out.append("| lado | dias com forma | gatilho | stop < 0,4% | sem alvo a 2R | sem fatia | aviso sai | preencheu |")
    out.append("|---|---|---|---|---|---|---|---|")
    for lado in ("venda", "compra"):
        s = df[df.lado == lado]
        out.append(f"| {lado} | {len(s)} | {int(s.gatilho.sum())} | {int((s.motivo == 'stop < 0,4%').sum())} | "
                   f"{int((s.motivo == 'sem alvo a 2R').sum())} | {int((s.motivo == 'sem fatia').sum())} | "
                   f"{int(s.sai.sum())} | {int(s.preencheu.fillna(False).astype(bool).sum())} |")
    out.append("")
    ok = df[(df.sai == True) & (df.preencheu == True)]
    out.append("## Resultado (R líquido por trade preenchido)\n")
    out.append("(1) = nível sorteado na faixa da manhã (20 sorteios por dia, regra inteira refeita); (2) = direção "
               "sorteada. Critério por lado: líquido > 0 nos 3 períodos com n ≥ 30 e, em treino e validação, "
               "≥ (1) + 2 EP e ≥ (2) + 2 EP.\n")
    out.append("| linha | período | n | acerto (>0) | média R ± EP | (1) nível sorteado (n) | (2) direção sorteada (n) | ≥ (1)+2EP | ≥ (2)+2EP | sem 1R |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    vered = {}
    for lado, nome in (("venda", "E3 venda (forma P)"), ("compra", "E3 compra (forma b)"), (None, "E3 (os dois lados)")):
        res, oks = {}, {}
        for per, _, _ in R.PERIODOS:
            s = ok[ok.periodo == per]
            c = ctrl[ctrl.periodo == per] if len(ctrl) else ctrl
            if lado:
                s = s[s.lado == lado]
                c = c[c.lado == lado] if len(c) else c
            e = R.est(s.res_r)
            e1 = R.est(c.res_r) if len(c) else {"media": np.nan, "n": 0}
            e2 = R.est(s.cd)
            lin, oo = linha_tab(nome, per, e, {"1": (e1["media"], e1["n"]), "2": (e2["media"], e2["n"])},
                                R.est(s.res_r_sem1r)["media"])
            out.append(lin)
            res[per], oks[per] = e, oo
        vered[nome] = veredito(res, oks)
    out.append("")
    out.append("### Ano a ano\n")
    out.append("| ano | venda n | venda média | compra n | compra média |")
    out.append("|---|---|---|---|---|")
    for ano, s in ok.groupby("ano"):
        v, c = s[s.lado == "venda"], s[s.lado == "compra"]
        out.append(f"| {ano} | {len(v)} | {R.f(R.est(v.res_r)['media'])} | {len(c)} | {R.f(R.est(c.res_r)['media'])} |")
    out.append("")
    out.append("## Veredito pelo critério\n")
    for nome, (v, mot) in vered.items():
        out.append(f"- **{nome}: {v}**" + (" — " + "; ".join(mot) if mot else ""))
    out.append("")
    return out, vered


def main():
    t0 = time.time()
    m = R.Mercado(R.carregar("5m", "2019-11-01"))
    B = R.Blocos(m)
    print(f"dados: {len(m.ts)} candles, {len(B.ts)} blocos ({time.time() - t0:.0f}s)")
    df2 = rodar_e2(m, B)
    md2, v2 = resumo_e2(df2)
    SAIDA_E2_MD.write_text("\n".join(md2), encoding="utf-8")
    df3, c3 = rodar_e3(m, B)
    md3, v3 = resumo_e3(df3, c3)
    SAIDA_E3_MD.write_text("\n".join(md3), encoding="utf-8")
    for k, (v, mot) in {**v2, **v3}.items():
        print(f"{k}: {v} {mot}")
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
