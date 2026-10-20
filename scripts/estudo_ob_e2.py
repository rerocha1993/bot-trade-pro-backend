# scripts/estudo_ob_e2.py
"""
OB E2 — "Varredura de liquidez + volta" (plano_gestao.md 2.2; docs/especialistas/order_block.md E2). Passo 5 da seção 4.
BTCUSDT Binance, 2020-01 a 2026-09. CRITÉRIO ESCRITO ANTES DE RODAR; nenhum parâmetro iterado.
Estrutura: conselho/estrutura.py (swing 3+3, FVG, estado de 4 h); motor e custos: conselho/regua.py (sem core/).
Execução em 5 min. Sem tabela de eventos macro: a regra "varredura feita pelo dado não conta" NÃO é aplicada.

Descrição para VENDA depois de varredura de topo; a COMPRA é o espelho exato (fundos, mínimas, candle de baixa).
LIQUIDEZ (1 h):
  - topos iguais: dois swings de alta de 1 h (3 candles de cada lado; conhecidos 3 candles depois) separados por ≥ 12
    candles e no máximo 240, a ≤ 0,2% um do outro, sem máxima entre eles acima do maior; nível = o maior; vale desde
    o fechamento do candle que confirma o 2º swing (um nível a menos de 0,05% de outro ativo é ignorado);
  - máxima de ontem (dia UTC anterior), válida durante o dia; máxima da semana passada (seg–dom), válida na semana.
  Um nível é consumido na 1ª vez que uma máxima de 1 h passa dele (varrido ou rompido).
VARREDURA: candle de 1 h cuja máxima passa o nível em ≥ 0,05% e ≤ 0,8% e fecha abaixo do nível; ou fecha acima e o
  candle seguinte fecha abaixo com a máxima dos dois ≤ nível + 0,8% (confirmação no fechamento do 2º). Excursão > 0,8%:
  rompimento, não varredura. Máxima da varredura Hs = maior máxima dos candles da varredura. Vários níveis no mesmo
  candle e lado = um evento (prioridade semana > ontem > iguais). Confirmação no fim de semana: não entra.
CONTEXTO 4 h: estado (conselho/estrutura.estado_4h) no último fechamento de 4 h até a confirmação: venda só com
  "baixa" ou "lateral"; compra só com "alta" ou "lateral".
CHoCH (15 min): SL15 = último swing de baixa de 15 min (3+3) anterior ao candle de 15 min que fez Hs e já conhecido na
  confirmação. Nos 8 candles de 15 min depois da confirmação, o 1º que FECHA abaixo de SL15 é o CHoCH; se antes disso
  alguma máxima de 15 min atingir o stop (Hs + 0,10%), não há aviso.
OB (15 min): último candle de alta (fech > abert) no candle de Hs ou nos 12 anteriores; deslocamento = máxima do OB −
  menor mínima do candle seguinte ao OB até o CHoCH ≥ ATR(14, 15 min) no CHoCH; FVG de baixa entre o OB e o CHoCH
  (máxima[i+1] < mínima[i−1]). Sem OB, sem deslocamento ou sem FVG: não há aviso. Zona = [abertura, máxima] do OB.
ENTRADA A (reteste): 3 limitadas post-only: abertura (20%), abertura + 50% da zona (30%), abertura + 75% (50%), acima do
  fechamento do CHoCH e abaixo do stop; válidas por 16 candles de 15 min (4 h). ENTRADA B: a mercado no fechamento do
  CHoCH.
STOP = Hs + 0,10%, a mercado. Stop < 0,4% do médio planejado: não sai.
ALVO = a liquidez mais próxima abaixo do médio planejado a ≥ 2R entre: fundos iguais de 1 h ativos, mínima de ontem,
  mínima da semana passada, naked POCs (30 dias, não tocados até o gatilho), VAL do composto de 10 dias e o topo do
  FVG de alta de 1 h não preenchido mais próximo (30 dias). Sem alvo a ≥ 2R: não sai.
GESTÃO: 1R realiza 50% e o stop do resto vai ao médio; teto de 24 h desde o 1º preenchimento.
VARIANTES (fixas, 4): entrada A × B; "base" × "quartil" (fechamento do CHoCH no quartil permitido do composto de 10
  dias: p > 0,75 venda, p < 0,25 compra — regra 0.1 do plano). Tipo de liquidez só como leitura (não é variante).
CONTROLES (mesma gestão, mesmo stop/alvo pela mesma regra, mesmos filtros de dia, 4 h e quartil):
  (1) OB SEM QUALIFICAÇÃO: o detector antigo (core/order_block.py) em 15 min — candle de alta seguido de candle de baixa,
      mínima dos 3 seguintes abaixo da mínima dos 5 anteriores, deslocamento ≥ 1,5 ATR(14); conhecido 3 candles depois;
      as 3 limitadas na zona [abertura, máxima] ficam 4 h; stop = máxima do OB + 0,10%; sem varredura nem CHoCH.
  (2) ZONA SORTEADA (só A): 20 sorteios de uma zona da mesma altura uniforme entre o fechamento do CHoCH e o stop.
  (3) DIREÇÃO SORTEADA: esperança exata da moeda (média de mesma e oposta) na 1ª execução, stop a R_plan, alvo a RR_plan.
  (4) VARREDURA SEM CHoCH: toda varredura válida (mesmos filtros), a mercado no fechamento que confirma a volta.
APROVAÇÃO (por variante): líquido > 0 nos 3 períodos com ≥ 30 preenchidos e, em treino e validação, média ≥ cada
  controle aplicável + 2 EP. Holdout olhado uma vez. n < 30 em algum período = inconclusiva, nunca aprovada.
Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09.
Saídas: data/estudo_ob_e2.csv, data/estudo_ob_e2_controles.csv e data/estudo_ob_e2_resumo.md.
"""
from __future__ import annotations

import bisect
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from conselho import regua as R  # noqa: E402
from conselho import estrutura as S  # noqa: E402

SAIDA = RAIZ / "data" / "estudo_ob_e2.csv"
SAIDA_CTRL = RAIZ / "data" / "estudo_ob_e2_controles.csv"
SAIDA_MD = RAIZ / "data" / "estudo_ob_e2_resumo.md"

TOL_IGUAIS = 0.002
SEP_MIN, SEP_MAX = 12, 240
EXC_MIN, EXC_MAX = 0.0005, 0.008
JANELA_CHOCH = 8
BUSCA_OB = 12
FOLGA = 0.001
STOP_MIN = 0.004
RR_MIN = 2.0
VALIDADE = 48
TETO = 288
N_SORTEIOS = 20
SEMENTE = 20261020
INICIO = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
FRAC_ZONA = [(0.0, 0.2), (0.5, 0.3), (0.75, 0.5)]


class Serie:
    def __init__(self, tf):
        df = R.carregar(tf, "2019-09-01")
        self.dt = R.TF_MS[tf]
        self.ts = df["timestamp"].to_numpy(np.int64)
        self.o, self.h, self.l, self.c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        self.atr = S.atr(self.h, self.l, self.c)
        self.pos = {int(t): i for i, t in enumerate(self.ts)}

    def idx_fecha_ate(self, t):
        """Índice do último candle que fechou até t (inclusive)."""
        return int(np.searchsorted(self.ts + self.dt, t, side="right")) - 1


# ---------------------------------------------------------------------------------------------------- liquidez 1 h
def niveis_iguais(h1: Serie):
    """Topos (d=-1) e fundos (d=+1) iguais: lista de [preço, t_conhecido, t_consumido]."""
    altas, baixas = S.swings_rapido(h1.h, h1.l)
    out = {-1: [], 1: []}
    for d, sw, serie in ((-1, altas, h1.h), (1, baixas, h1.l)):
        idxs = [s[0] for s in sw]
        for jj, (j, pj, cj) in enumerate(sw):
            a = bisect.bisect_left(idxs, j - SEP_MAX)
            for ii in range(a, jj):
                i, pi_, _ = sw[ii]
                if j - i < SEP_MIN:
                    continue
                nv = max(pi_, pj) if d == -1 else min(pi_, pj)
                if abs(pi_ - pj) > TOL_IGUAIS * max(pi_, pj):
                    continue
                meio = serie[i + 1:j]
                if len(meio) and ((d == -1 and meio.max() > nv) or (d == 1 and meio.min() < nv)):
                    continue
                out[d].append([nv, int(h1.ts[cj]) + h1.dt, None])
    # consumo: 1ª máxima (mínima) de 1 h além do nível depois de conhecido
    for d in (-1, 1):
        for lv in out[d]:
            k = h1.pos.get(lv[1])
            if k is None:
                k = int(np.searchsorted(h1.ts, lv[1]))
            seg = h1.h[k:] if d == -1 else h1.l[k:]
            hit = np.flatnonzero(seg > lv[0]) if d == -1 else np.flatnonzero(seg < lv[0])
            lv[2] = int(h1.ts[k + hit[0]]) if len(hit) else 1 << 62
    return out


def varreduras(h1: Serie, iguais, B: R.Blocos):
    """Eventos de varredura confirmados (dicts)."""
    eventos = []
    ativos = {-1: [], 1: []}       # [preço, tipo, t_expira]
    pend = {d: sorted(iguais[d], key=lambda x: x[1]) for d in (-1, 1)}
    ip = {-1: 0, 1: 0}
    n = len(h1.c)
    for k in range(n - 1):
        t = int(h1.ts[k])
        dn = t // R.DIA_MS
        if t % R.DIA_MS == 0 and (dn - 1) in B.dia_ini:
            _, _, _, mx, mn, _ = B.perfil_dia(dn - 1)
            ativos[-1].append([mx, "ontem", t + R.DIA_MS])
            ativos[1].append([mn, "ontem", t + R.DIA_MS])
            if R.dia_semana(t) == 0:
                ds = [x for x in range(dn - 7, dn) if x in B.dia_ini]
                if ds:
                    ativos[-1].append([max(B.perfil_dia(x)[3] for x in ds), "semana", t + 7 * R.DIA_MS])
                    ativos[1].append([min(B.perfil_dia(x)[4] for x in ds), "semana", t + 7 * R.DIA_MS])
        for d in (-1, 1):
            while ip[d] < len(pend[d]) and pend[d][ip[d]][1] <= t:
                nv = pend[d][ip[d]][0]
                if not any(a[1] == "iguais" and abs(a[0] - nv) <= 0.0005 * nv for a in ativos[d]):
                    ativos[d].append([nv, "iguais", t + 30 * R.DIA_MS])
                ip[d] += 1
            ativos[d] = [a for a in ativos[d] if a[2] > t]
        hi, lo, cl = h1.h[k], h1.l[k], h1.c[k]
        for d in (-1, 1):
            achados = []
            resto = []
            for a in ativos[d]:
                nv = a[0]
                passou = hi > nv if d == -1 else lo < nv
                if not passou:
                    resto.append(a)
                    continue
                exc = (hi / nv - 1) if d == -1 else (1 - lo / nv)
                if exc < EXC_MIN or exc > EXC_MAX:
                    continue
                volta = cl < nv if d == -1 else cl > nv
                if volta:
                    achados.append((a, k, hi if d == -1 else lo))
                    continue
                h2, l2, c2 = h1.h[k + 1], h1.l[k + 1], h1.c[k + 1]
                ext = max(hi, h2) if d == -1 else min(lo, l2)
                exc2 = (ext / nv - 1) if d == -1 else (1 - ext / nv)
                if exc2 <= EXC_MAX and ((d == -1 and c2 < nv) or (d == 1 and c2 > nv)):
                    achados.append((a, k + 1, ext))
            ativos[d] = resto
            for kc in sorted(set(x[1] for x in achados)):
                grupo = [x for x in achados if x[1] == kc]
                prio = {"semana": 0, "ontem": 1, "iguais": 2}
                grupo.sort(key=lambda x: prio[x[0][1]])
                a, _, ext = grupo[0]
                tc = int(h1.ts[kc]) + h1.dt
                if tc < INICIO:
                    continue
                eventos.append({"d": d, "nivel": a[0], "tipo": a[1], "tipos": ",".join(sorted(set(g[0][1] for g in grupo))),
                                "k_ini": k, "k_conf": kc, "t_conf": tc, "extremo": float(ext)})
    return eventos


def fvgs_1h(h1: Serie):
    """FVGs de 1 h: para alvo de VENDA (d=-1) as de alta abaixo (borda de cima); de COMPRA (d=+1) as de baixa acima."""
    out = {-1: [], 1: []}
    h, l = h1.h, h1.l
    for i in range(1, len(h) - 1):
        t_con = int(h1.ts[i + 1]) + h1.dt
        if l[i + 1] > h[i - 1]:                   # FVG de alta: alvo de venda na borda de cima (l[i+1])
            seg = np.flatnonzero(l[i + 2:] <= h[i - 1])
            t_fim = int(h1.ts[i + 2 + seg[0]]) if len(seg) else 1 << 62
            out[-1].append((float(l[i + 1]), t_con, t_fim))
        if h[i + 1] < l[i - 1]:                   # FVG de baixa: alvo de compra na borda de baixo (h[i+1])
            seg = np.flatnonzero(h[i + 2:] >= l[i - 1])
            t_fim = int(h1.ts[i + 2 + seg[0]]) if len(seg) else 1 << 62
            out[1].append((float(h[i + 1]), t_con, t_fim))
    return {d: np.array(v) for d, v in out.items()}


class Alvos:
    def __init__(self, iguais, fvg, B: R.Blocos, m: R.Mercado):
        self.ig = {d: np.array([[x[0], x[1], x[2]] for x in iguais[d]], float) for d in (-1, 1)}
        self.fvg = fvg
        self.B = B
        self.m = m
        self._naked = {}

    def naked(self, dn):
        if dn not in self._naked:
            self._naked[dn] = self.B.naked_pocs(dn)
        return self._naked[dn]

    def candidatos(self, d: int, t: int, k5: int):
        """Níveis de alvo para um trade de direção d (venda = -1 procura fundos) conhecidos em t."""
        dn = (t - 1) // R.DIA_MS
        B = self.B
        out = []
        lado = 1 if d == -1 else -1                # venda mira fundos iguais (d_nivel=+1)
        ig = self.ig[lado]
        if len(ig):
            mk = (ig[:, 1] <= t) & (ig[:, 2] > t) & (t - ig[:, 1] <= 30 * R.DIA_MS)
            out += ig[mk, 0].tolist()
        if (dn - 1) in B.dia_ini:
            pd_ = B.perfil_dia(dn - 1)
            out.append(pd_[4] if d == -1 else pd_[3])
        seg_dia = int(dn - R.dia_semana(dn * R.DIA_MS))
        ds = [x for x in range(seg_dia - 7, seg_dia) if x in B.dia_ini]
        if ds:
            out.append(min(B.perfil_dia(x)[4] for x in ds) if d == -1 else max(B.perfil_dia(x)[3] for x in ds))
        k_dia = self.m.idx_ge(dn * R.DIA_MS)
        if k5 > k_dia:
            hh, ll = float(self.m.a_hi[k_dia:k5].max()), float(self.m.a_lo[k_dia:k5].min())
        else:
            hh, ll = -np.inf, np.inf
        out += [x for x in self.naked(dn) if not (ll <= x <= hh)]
        comp = B.composto(dn)
        if comp:
            out.append(comp[0] if d == -1 else comp[2])
        fv = self.fvg[d]
        if len(fv):
            mk = (fv[:, 1] <= t) & (fv[:, 2] > t) & (t - fv[:, 1] <= 30 * R.DIA_MS)
            out += fv[mk, 0].tolist()
        return out


def alvo_de(d, medio, stop, cands):
    r = abs(medio - stop)
    ok = [x for x in cands if d * (x - medio) >= RR_MIN * r]
    return min(ok, key=lambda x: abs(x - medio)) if ok else None


def trade(m, d, fat, stop, ref, k0, alvos_c, mercado, rng=None):
    """Monta e simula; devolve dict com 'sai' e resultados."""
    if mercado:
        fat = [(ref, 1.0)]
    else:
        fat = R.fatias_postas(d, fat, ref, stop)
        if not fat:
            return {"sai": False, "motivo": "sem fatia"}
    medio = sum(p * w for p, w in fat)
    if (d == -1 and stop <= medio) or (d == 1 and stop >= medio):
        return {"sai": False, "motivo": "stop do lado errado"}
    r_plan = abs(stop - medio) / medio
    if r_plan < STOP_MIN:
        return {"sai": False, "motivo": "stop < 0,4%", "r_plan": r_plan}
    alvo = alvo_de(d, medio, stop, alvos_c)
    if alvo is None:
        return {"sai": False, "motivo": "sem alvo a 2R", "r_plan": r_plan}
    rr = abs(alvo - medio) / abs(medio - stop)
    res = R.simular(m, d, fat, stop, alvo, k0, VALIDADE, TETO, mercado, 0.5)
    return {"sai": True, "motivo": "", "r_plan": r_plan, "rr_plan": rr, "res": res, "fat": fat, "alvo": alvo}


def zona(d, base, ext):
    return [(base + (ext - base) * fr, w) for fr, w in FRAC_ZONA]


# ---------------------------------------------------------------------------------------------------- principal
def main():
    t0 = time.time()
    rng = np.random.default_rng(SEMENTE)
    m = R.Mercado(R.carregar("5m", "2019-10-01"))
    B = R.Blocos(m)
    h1, m15, h4 = Serie("1h"), Serie("15m"), Serie("4h")
    est4 = S.estado_4h(h4.h, h4.l, h4.c)
    iguais = niveis_iguais(h1)
    fvg = fvgs_1h(h1)
    AL = Alvos(iguais, fvg, B, m)
    ev = varreduras(h1, iguais, B)
    sa15, sb15 = S.swings_rapido(m15.h, m15.l)
    sw15 = {-1: sb15, 1: sa15}          # venda usa swing de BAIXA de 15 min; compra, de ALTA
    sw15_idx = {d: [s[0] for s in sw15[d]] for d in (-1, 1)}
    print(f"dados e estrutura: {len(ev)} varreduras ({time.time() - t0:.0f}s)")

    def estado_em(t):
        i = h4.idx_fecha_ate(t)
        return est4[i] if i >= 0 else "lateral"

    def contexto(d, t, preco):
        dn = (t - 1) // R.DIA_MS
        comp = B.composto(dn)
        p = R.posicao_composto(preco, comp) if comp else np.nan
        quart = (p > 0.75) if d == -1 else (p < 0.25)
        return p, bool(quart)

    linhas, ctrl = [], []
    for e in ev:
        d, tc, hs = e["d"], e["t_conf"], e["extremo"]
        per = R.periodo_de(tc - 1)
        if not per or R.fim_de_semana(tc - 1):
            continue
        st4 = estado_em(tc)
        if (d == -1 and st4 == "alta") or (d == 1 and st4 == "baixa"):
            continue
        stop = hs * (1 - d * FOLGA)
        k5c = m.idx(tc)
        if k5c is None:
            continue
        # controle (4): varredura sem CHoCH, a mercado no fechamento que confirma
        p4, q4 = contexto(d, tc, h1.c[e["k_conf"]])
        t4 = trade(m, d, None, stop, float(h1.c[e["k_conf"]]), k5c, AL.candidatos(d, tc, k5c), True)
        if t4["sai"] and t4["res"] is not None:
            ctrl.append({"controle": "sem_choch", "periodo": per, "lado": "compra" if d == 1 else "venda",
                         "quartil": q4, "res_r": t4["res"]["res_r"], "data": R.data_de(tc)})
        reg = {"data": R.data_de(tc), "ano": R.data_de(tc)[:4], "periodo": per, "lado": "compra" if d == 1 else "venda",
               "tipo": e["tipo"], "tipos": e["tipos"], "estado_4h": st4,
               "exc_pct": abs(hs / e["nivel"] - 1)}
        # CHoCH em 15 min
        i_ini = m15.pos.get(int(h1.ts[e["k_ini"]]))
        q_c = m15.idx_fecha_ate(tc)
        if i_ini is None or q_c < 0:
            continue
        seg = m15.h[i_ini:q_c + 1] if d == -1 else m15.l[i_ini:q_c + 1]
        i_hs = i_ini + int(np.argmax(seg) if d == -1 else np.argmin(seg))
        lim = min(i_hs - 1, q_c - 3)
        j = bisect.bisect_right(sw15_idx[d], lim) - 1
        if j < 0:
            reg.update({"choch": False, "motivo": "sem swing 15m"})
            linhas.append(reg)
            continue
        nivel_sw = sw15[d][j][1]
        q = None
        for qq in range(q_c + 1, min(q_c + 1 + JANELA_CHOCH, len(m15.c))):
            if (d == -1 and m15.h[qq] >= stop) or (d == 1 and m15.l[qq] <= stop):
                break
            if (d == -1 and m15.c[qq] < nivel_sw) or (d == 1 and m15.c[qq] > nivel_sw):
                q = qq
                break
        if q is None:
            reg.update({"choch": False, "motivo": "sem CHoCH"})
            linhas.append(reg)
            continue
        reg["choch"] = True
        # OB
        ob = None
        for i in range(i_hs, max(i_hs - BUSCA_OB, 0) - 1, -1):
            if (d == -1 and m15.c[i] > m15.o[i]) or (d == 1 and m15.c[i] < m15.o[i]):
                ob = i
                break
        if ob is None or ob + 1 > q:
            reg.update({"motivo": "sem OB"})
            linhas.append(reg)
            continue
        if d == -1:
            desloc = m15.h[ob] - m15.l[ob + 1:q + 1].min()
            fvg_ok = any(m15.h[i + 1] < m15.l[i - 1] for i in range(ob + 1, q))
            base, ext = m15.o[ob], m15.h[ob]
        else:
            desloc = m15.h[ob + 1:q + 1].max() - m15.l[ob]
            fvg_ok = any(m15.l[i + 1] > m15.h[i - 1] for i in range(ob + 1, q))
            base, ext = m15.o[ob], m15.l[ob]
        if not desloc >= m15.atr[q]:
            reg.update({"motivo": "deslocamento < 1 ATR"})
            linhas.append(reg)
            continue
        if not fvg_ok:
            reg.update({"motivo": "sem FVG"})
            linhas.append(reg)
            continue
        if abs(ext - base) <= 0:
            reg.update({"motivo": "zona vazia"})
            linhas.append(reg)
            continue
        tg = int(m15.ts[q]) + m15.dt
        k0 = m.idx(tg)
        if k0 is None:
            continue
        cq = float(m15.c[q])
        p, quart = contexto(d, tg, cq)
        cands = AL.candidatos(d, tg, k0)
        reg.update({"motivo": "", "p_comp": p, "quartil": quart, "zona_pct": abs(ext - base) / cq})
        for ent, merc in (("A", False), ("B", True)):
            tr = trade(m, d, zona(d, base, ext), stop, cq, k0, cands, merc)
            r = dict(reg)
            r.update({"entrada": ent, "sai": tr["sai"], "motivo": tr["motivo"], "r_plan": tr.get("r_plan", np.nan),
                      "rr_plan": tr.get("rr_plan", np.nan)})
            res = tr.get("res")
            r["preencheu"] = res is not None
            if res is not None:
                r.update({"res_r": res["res_r"], "saida": res["saida"], "tomou_1r": res["tomou_1r"]})
                a, b = R.controle_direcao(m, res, d, tr["r_plan"], tr["rr_plan"], k0, merc, VALIDADE, TETO, 0.5)
                r["cd"] = 0.5 * (a + b) if a is not None and b is not None else np.nan
                if ent == "A":
                    h = abs(ext - base)
                    lo_z, hi_z = (cq, stop - h) if d == -1 else (stop + h, cq)
                    zs = []
                    if hi_z > lo_z:
                        for z0 in rng.uniform(lo_z, hi_z, N_SORTEIOS):
                            b0, e0 = (z0, z0 + h) if d == -1 else (z0, z0 - h)
                            tz = trade(m, d, zona(d, b0, e0), stop, cq, k0, cands, False)
                            if tz["sai"] and tz["res"] is not None:
                                zs.append(tz["res"]["res_r"])
                    r["ctrl_zona"] = float(np.mean(zs)) if zs else np.nan
            linhas.append(r)
    print(f"varreduras processadas ({time.time() - t0:.0f}s)")

    # controle (1): OB sem qualificação (detector antigo) em 15 min
    n15 = len(m15.c)
    for i in range(5, n15 - 4):
        t_conh = int(m15.ts[i + 3]) + m15.dt
        if t_conh < INICIO:
            continue
        for d in (-1, 1):
            o, h, l, c = m15.o[i], m15.h[i], m15.l[i], m15.c[i]
            if d == -1:
                if not (c > o and m15.c[i + 1] < m15.o[i + 1]):
                    continue
                mn = m15.l[i + 1:i + 4].min()
                if not (mn < m15.l[i - 5:i].min() and h - mn >= 1.5 * m15.atr[i + 3]):
                    continue
                base, ext = o, h
            else:
                if not (c < o and m15.c[i + 1] > m15.o[i + 1]):
                    continue
                mx = m15.h[i + 1:i + 4].max()
                if not (mx > m15.h[i - 5:i].max() and mx - l >= 1.5 * m15.atr[i + 3]):
                    continue
                base, ext = o, l
            per = R.periodo_de(t_conh - 1)
            if not per or R.fim_de_semana(t_conh - 1):
                continue
            st4 = estado_em(t_conh)
            if (d == -1 and st4 == "alta") or (d == 1 and st4 == "baixa"):
                continue
            k0 = m.idx(t_conh)
            if k0 is None or abs(ext - base) <= 0:
                continue
            stop = ext * (1 - d * FOLGA)
            ref = float(m15.c[i + 3])
            _, quart = contexto(d, t_conh, ref)
            tr = trade(m, d, zona(d, base, ext), stop, ref, k0, AL.candidatos(d, t_conh, k0), False)
            if tr["sai"] and tr["res"] is not None:
                ctrl.append({"controle": "ob_simples", "periodo": per, "lado": "compra" if d == 1 else "venda",
                             "quartil": quart, "res_r": tr["res"]["res_r"], "data": R.data_de(t_conh)})
        if i % 50000 == 0:
            print(f"  OB simples {i}/{n15} ({time.time() - t0:.0f}s)")
    df = pd.DataFrame(linhas)
    cdf = pd.DataFrame(ctrl)
    df.to_csv(SAIDA, index=False)
    cdf.to_csv(SAIDA_CTRL, index=False)
    md, vered = resumo(df, cdf)
    SAIDA_MD.write_text("\n".join(md), encoding="utf-8")
    for k, (v, mot) in vered.items():
        print(f"{k}: {v} {mot}")
    print(f"total {time.time() - t0:.0f}s")


# ---------------------------------------------------------------------------------------------------- resumo
def resumo(df: pd.DataFrame, cdf: pd.DataFrame):
    out = ["# OB E2 — varredura de liquidez + volta (passo 5 do plano de gestão)\n",
           "Gerado por `scripts/estudo_ob_e2.py` (regra exata no docstring, escrita antes de rodar). BTCUSDT Binance: "
           "liquidez e varredura em 1 h, CHoCH e OB em 15 min, direção em 4 h, execução em 5 min; dias úteis, "
           "2020-01 a 2026-09. Custo real, leitura pessimista, sem veto de evento macro.\n"]
    base = df[df.get("entrada").notna()] if "entrada" in df else df.iloc[0:0]
    out.append("## Funil (varreduras confirmadas em dia útil com o 4 h permitindo)\n")
    nv = df.drop_duplicates(subset=["data", "lado", "tipo", "exc_pct"])
    out.append(f"- varreduras: {len(nv)} (venda {int((nv.lado == 'venda').sum())}, compra {int((nv.lado == 'compra').sum())})")
    for mot in ("sem swing 15m", "sem CHoCH", "sem OB", "deslocamento < 1 ATR", "sem FVG", "zona vazia"):
        out.append(f"- {mot}: {int((nv.motivo == mot).sum())}")
    a = base[base.entrada == "A"]
    out.append(f"- com CHoCH + OB + deslocamento + FVG: {len(a)}")
    for ent in ("A", "B"):
        s = base[base.entrada == ent]
        out.append(f"- entrada {ent}: stop < 0,4% {int((s.motivo == 'stop < 0,4%').sum())}, sem alvo a 2R "
                   f"{int((s.motivo == 'sem alvo a 2R').sum())}, sem fatia {int((s.motivo == 'sem fatia').sum())}, "
                   f"aviso sai {int(s.sai.sum())}, preencheu {int(s.preencheu.sum())}, no quartil "
                   f"{int((s.preencheu & s.quartil.fillna(False).astype(bool)).sum())}")
    out.append("")
    out.append("## Resultado (R líquido por trade preenchido, 1R realiza 50% e stop no médio)\n")
    out.append("(1) OB sem qualificação (detector antigo, população); (2) zona sorteada (só A, média de 20); (3) direção "
               "sorteada; (4) varredura sem CHoCH (a mercado na volta). Critério: líquido > 0 nos 3 períodos com n ≥ 30 "
               "e, em treino e validação, ≥ cada controle aplicável + 2 EP.\n")
    out.append("| variante | período | n | acerto | média R ± EP | (1) OB simples (n) | (2) zona | (3) direção | (4) sem CHoCH (n) | passa controles |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    vered = {}
    ok = base[(base.sai == True) & (base.preencheu == True)]
    for ent in ("A", "B"):
        for var in ("base", "quartil"):
            nome = f"OB E2 {ent} {var}"
            falhas, curtos = [], []
            for per, _, _ in R.PERIODOS:
                s = ok[(ok.entrada == ent) & (ok.periodo == per)]
                c = cdf[cdf.periodo == per] if len(cdf) else cdf
                if var == "quartil":
                    s = s[s.quartil == True]
                    c = c[c.quartil == True] if len(c) else c
                e = R.est(s.res_r)
                c1 = R.est(c[c.controle == "ob_simples"].res_r) if len(c) else R.est([])
                c4 = R.est(c[c.controle == "sem_choch"].res_r) if len(c) else R.est([])
                c2 = R.est(s.ctrl_zona) if ent == "A" else None
                c3 = R.est(s.cd)
                cs = [c1, c3, c4] + ([c2] if c2 else [])
                oks = [e["n"] > 1 and not np.isnan(x["media"]) and e["media"] >= x["media"] + 2 * e["se"] for x in cs]
                out.append(f"| {nome} | {per} | {e['n']} | {R.pct(e['acerto'])} | {R.f(e['media'])} ± {R.f(e['se'])} | "
                           f"{R.f(c1['media'])} ({c1['n']}) | {R.f(c2['media']) if c2 else '—'} | {R.f(c3['media'])} | "
                           f"{R.f(c4['media'])} ({c4['n']}) | {'sim' if all(oks) else 'não'} |")
                if e["n"] < R.MIN_N:
                    curtos.append(f"{per}: n={e['n']} < 30")
                    continue
                if not e["media"] > 0:
                    falhas.append(f"{per}: líquido {R.f(e['media'])} ≤ 0")
                if per != "holdout" and not all(oks):
                    falhas.append(f"{per}: não fica 2 EP acima de todos os controles")
            vered[nome] = ("REPROVADA", falhas + curtos) if falhas else (("INCONCLUSIVA", curtos) if curtos else ("APROVADA", []))
    out.append("")
    out.append("### Por tipo de liquidez e lado (entrada A, base, todos os períodos; informativo)\n")
    out.append("| tipo | lado | n | acerto | média R ± EP |")
    out.append("|---|---|---|---|---|")
    sA = ok[ok.entrada == "A"]
    for (tp, lado), s in sA.groupby(["tipo", "lado"]):
        e = R.est(s.res_r)
        out.append(f"| {tp} | {lado} | {e['n']} | {R.pct(e['acerto'])} | {R.f(e['media'])} ± {R.f(e['se'])} |")
    out.append("")
    out.append("### Ano a ano (entrada A e B, base)\n")
    out.append("| ano | A n | A média | B n | B média | (4) sem CHoCH média |")
    out.append("|---|---|---|---|---|---|")
    for ano in sorted(ok.ano.unique()):
        A_, B_ = ok[(ok.ano == ano) & (ok.entrada == "A")], ok[(ok.ano == ano) & (ok.entrada == "B")]
        c4 = cdf[(cdf.controle == "sem_choch") & (cdf.data.str[:4] == ano)] if len(cdf) else cdf
        out.append(f"| {ano} | {len(A_)} | {R.f(R.est(A_.res_r)['media'])} | {len(B_)} | {R.f(R.est(B_.res_r)['media'])} | "
                   f"{R.f(R.est(c4.res_r)['media']) if len(c4) else '-'} |")
    out.append("")
    out.append("### Controles por período e lado (informativo)\n")
    out.append("| controle | período | lado | n | média R ± EP |")
    out.append("|---|---|---|---|---|")
    if len(cdf):
        for (ct, per, lado), s in cdf.groupby(["controle", "periodo", "lado"]):
            e = R.est(s.res_r)
            out.append(f"| {ct} | {per} | {lado} | {e['n']} | {R.f(e['media'])} ± {R.f(e['se'])} |")
    out.append("")
    out.append("## Veredito pelo critério\n")
    for nome, (v, mot) in vered.items():
        out.append(f"- **{nome}: {v}**" + (" — " + "; ".join(dict.fromkeys(mot)) if mot else ""))
    out.append("")
    return out, vered


if __name__ == "__main__":
    main()
