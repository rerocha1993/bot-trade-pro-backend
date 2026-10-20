# conselho/regua.py
"""
Régua comum dos estudos do conselho de avisos (docs/especialistas/plano_gestao.md, seção 4).

Independente de core/: o perfil TPO (faixa de 0,1% arredondada a US$ 10, POC com desempate pelo meio, área de valor
de 70% a partir do POC) é cópia da lógica de core/tpo_sessao.py; o motor de simulação é o de scripts/estudo_tpo_e1.py,
generalizado para parciais e limite de horário.

Execução sempre em candles de 5 min (o 1 min do projeto só existe em dias de evento). Regras do motor:
  - limitada de entrada (post-only) preenche só se o candle ATRAVESSOU o preço (compra: mínima < preço);
  - no candle em que alguma fatia preenche, só o stop conta;
  - favor e contra no mesmo candle = contra (o stop é checado antes de qualquer saída a favor);
  - 1R = médio preenchido ± |stop − médio|; ao tocar, realiza `frac_1r` do preenchido (limitada) e o stop do resto
    vai ao médio; fatias pendentes são canceladas; se o mesmo candle tocou o médio, o resto sai no médio;
  - parciais e alvo são limitadas e só executam com o preço atravessando;
  - teto de duração contado do 1º preenchimento; `k_fim` encerra a mercado no fechamento daquele candle;
  - custos: maker 0,02%; taker 0,055% + slippage 0,02% em toda execução a mercado; funding linear da Bybit cobrado
    na posição aberta a cada 00/08/16 UTC (compra paga taxa positiva);
  - resultado em R por unidade preenchida, R = |stop original − médio preenchido| / médio.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
HIST = RAIZ / "data" / "historico"
FUNDING = HIST / "funding_bybit.json"

PERIODOS = [("treino", "2020-01-01", "2023-12-31"), ("validacao", "2024-01-01", "2025-06-30"),
            ("holdout", "2025-07-01", "2026-09-30")]
MAKER = 0.0002
TAKER = 0.00055 + 0.0002
M5 = 300_000
M15 = 900_000
HORA = 3_600_000
BLOCO_MS = 1_800_000
DIA_MS = 86_400_000
P8H = 8 * HORA
TF_MS = {"5m": M5, "15m": M15, "1h": HORA, "4h": 4 * HORA, "1d": DIA_MS}
TICK_PCT = 0.001
AREA_VALOR = 0.70
MIN_N = 30


# ---------------------------------------------------------------------------------------------------- dados
def carregar(tf: str, inicio: str = "2019-10-01") -> pd.DataFrame:
    df = pd.read_csv(HIST / f"BTCUSDT_binance_{tf}.csv")
    df = df[df["timestamp"] >= int(pd.Timestamp(inicio, tz="UTC").timestamp() * 1000)]
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def data_de(ts_ms: int) -> str:
    return pd.Timestamp(int(ts_ms), unit="ms", tz="UTC").strftime("%Y-%m-%d")


def periodo_de(ts_ms: int) -> str:
    d = data_de(ts_ms)
    for nome, a, z in PERIODOS:
        if a <= d <= z:
            return nome
    return ""


def dia_semana(ts_ms: int) -> int:
    """0 = segunda ... 6 = domingo (1970-01-01 foi quinta)."""
    return int((ts_ms // DIA_MS + 3) % 7)


def fim_de_semana(ts_ms: int) -> bool:
    return dia_semana(ts_ms) >= 5


class Mercado:
    """Candles de 5 min em listas (acesso escalar rápido) + funding."""

    def __init__(self, df: pd.DataFrame):
        self.ts = [int(x) for x in df["timestamp"].to_numpy(np.int64)]
        self.op = df["open"].to_numpy(float).tolist()
        self.hi = df["high"].to_numpy(float).tolist()
        self.lo = df["low"].to_numpy(float).tolist()
        self.cl = df["close"].to_numpy(float).tolist()
        self.a_hi = df["high"].to_numpy(float)
        self.a_lo = df["low"].to_numpy(float)
        self.a_cl = df["close"].to_numpy(float)
        self.a_ts = df["timestamp"].to_numpy(np.int64)
        self.pos = {t: i for i, t in enumerate(self.ts)}
        d = json.load(open(FUNDING))["linear"]
        self.funding = {int(k): float(v) for k, v in d.items()}

    def idx(self, t: int):
        return self.pos.get(int(t))

    def idx_ge(self, t: int) -> int:
        """Primeiro índice com ts >= t."""
        return int(np.searchsorted(self.a_ts, t, side="left"))


# ---------------------------------------------------------------------------------------------------- simulação
def simular(m: Mercado, d: int, fatias, stop: float, alvo, k0: int, validade: int, teto: int,
            mercado: bool = False, frac_1r: float = 0.5, parciais=(), forcar_em=None, k_fim=None):
    """
    d = +1 compra / −1 venda. fatias = [(preço, peso)] com pesos somando 1. mercado=True: a 1ª fatia é executada no
    fechamento do candle k0−1 (tudo conta a partir de k0). forcar_em=k: a fatia única é executada no candle k (só o
    stop conta nele). Senão: limitadas a partir de k0, válidas por `validade` candles. parciais = [(preço, fração do
    preenchido)]. alvo = preço final (ou None). Devolve dict ou None (não preencheu / acabou o dado).
    """
    hi, lo, cl, ts = m.hi, m.lo, m.cl, m.ts
    n = len(hi)
    cheias = []
    pend = []
    t1 = None
    if mercado:
        cheias = [(fatias[0][0], 1.0)]
        t1 = k0
    elif forcar_em is None:
        pend = list(fatias)
    custo_ent = TAKER if mercado else MAKER
    saidas = []
    fund = 0.0
    tomou_1r = False
    parc = sorted(parciais, key=lambda x: d * x[0])
    stop_cur = stop
    tipo = None
    k = k0 if forcar_em is None else forcar_em
    lim_fill = k0 + validade
    fim = n if k_fim is None else min(n, k_fim + 1)
    wf = 0.0
    vend = 0.0
    while k < fim:
        aberto = wf - vend
        if aberto > 1e-12 and ts[k] % P8H == 0:
            fund -= d * m.funding.get(ts[k], 0.0) * aberto
        barra_fill = False
        if forcar_em is not None and k == forcar_em:
            cheias = [(fatias[0][0], 1.0)]
            t1 = k
            barra_fill = True
        elif pend and k < lim_fill and not tomou_1r:
            if d == 1:
                novas = [x for x in pend if lo[k] < x[0]]
            else:
                novas = [x for x in pend if hi[k] > x[0]]
            if novas:
                cheias = cheias + novas
                pend = [x for x in pend if x not in novas]
                barra_fill = True
                if t1 is None:
                    t1 = k
        if not cheias:
            if k >= lim_fill - 1:
                return None
            k += 1
            continue
        wf = sum(w for _, w in cheias)
        medio = sum(p * w for p, w in cheias) / wf
        r_abs = abs(stop - medio)
        aberto = wf - vend
        if (d == 1 and lo[k] <= stop_cur) or (d == -1 and hi[k] >= stop_cur):
            saidas.append((aberto, stop_cur, "mkt"))
            tipo = "medio" if tomou_1r else "stop"
            break
        if not barra_fill:
            if frac_1r > 0 and not tomou_1r:
                n1 = medio + d * r_abs
                if (d == 1 and hi[k] > n1) or (d == -1 and lo[k] < n1):
                    q = min(frac_1r * wf, aberto)
                    saidas.append((q, n1, "lim"))
                    vend += q
                    aberto -= q
                    tomou_1r = True
                    pend = []
                    stop_cur = medio
                    if (d == 1 and lo[k] <= medio) or (d == -1 and hi[k] >= medio):
                        saidas.append((aberto, medio, "mkt"))
                        tipo = "medio"
                        break
            if parc:
                resto = []
                for pp, fr in parc:
                    if aberto > 1e-12 and ((d == 1 and hi[k] > pp) or (d == -1 and lo[k] < pp)):
                        q = min(fr * wf, aberto)
                        saidas.append((q, pp, "lim"))
                        vend += q
                        aberto -= q
                        pend = []
                    else:
                        resto.append((pp, fr))
                parc = resto
                if aberto <= 1e-12:
                    tipo = "parciais"
                    break
            if alvo is not None and ((d == 1 and hi[k] > alvo) or (d == -1 and lo[k] < alvo)):
                saidas.append((aberto, alvo, "lim"))
                tipo = "alvo"
                break
        if t1 is not None and k - t1 + 1 >= teto:
            saidas.append((aberto, cl[k], "mkt"))
            tipo = "tempo"
            break
        if pend and k >= lim_fill - 1:
            pend = []
        k += 1
    else:
        if not cheias or k_fim is None or k_fim >= n:
            return None
        k = fim - 1
        wf = sum(w for _, w in cheias)
        saidas.append((wf - vend, cl[k], "mkt"))
        tipo = "horario"
    wf = sum(w for _, w in cheias)
    medio = sum(p * w for p, w in cheias) / wf
    r_pct = abs(stop - medio) / medio
    pnl = -custo_ent * wf + fund
    for w, p, tp in saidas:
        pnl += w * (d * (p / medio - 1) - (MAKER if tp == "lim" else TAKER))
    pnl /= wf
    return {"res_r": pnl / r_pct, "frac": wf, "saida": tipo, "tomou_1r": tomou_1r, "r_pct": r_pct,
            "k_fill": t1, "p_fill": cheias[0][0], "candles": k - (t1 if t1 is not None else k0) + 1}


def controle_direcao(m: Mercado, res: dict, d: int, r_plan: float, rr_plan: float, k0: int, mercado: bool,
                     validade: int, teto: int, frac_1r: float = 0.5, parciais_r=(), k_fim=None):
    """
    Mesma hora e preço da 1ª execução, entrada única, stop a r_plan e alvo a rr_plan × r_plan (parciais em múltiplos
    de R), nas duas direções. Devolve (mesma, oposta); a direção sorteada é a média das duas (esperança da moeda).
    """
    if res is None:
        return None, None
    p = res["p_fill"]
    out = []
    for dd in (d, -d):
        stop = p * (1 - dd * r_plan)
        alvo = p * (1 + dd * rr_plan * r_plan)
        parc = [(p * (1 + dd * x * r_plan), fr) for x, fr in parciais_r]
        if mercado:
            s = simular(m, dd, [(p, 1.0)], stop, alvo, k0, validade, teto, True, frac_1r, parc, k_fim=k_fim)
        else:
            s = simular(m, dd, [(p, 1.0)], stop, alvo, k0, validade, teto, False, frac_1r, parc,
                        forcar_em=res["k_fill"], k_fim=k_fim)
        out.append(s["res_r"] if s else None)
    return out[0], out[1]


def fatias_postas(d: int, fatias, ref: float, stop: float):
    """Post-only: fatia do lado errado do preço de referência é recusada; fatia além do stop não é posta."""
    out = [(p, w) for p, w in fatias if ((p < ref) if d == 1 else (p > ref)) and ((p > stop) if d == 1 else (p < stop))]
    tw = sum(w for _, w in out)
    return [(p, w / tw) for p, w in out] if out else []


# ---------------------------------------------------------------------------------------------------- estatística
def est(x) -> dict:
    x = np.asarray([v for v in x if v is not None and not (isinstance(v, float) and math.isnan(v))], float)
    n = len(x)
    if n == 0:
        return {"n": 0, "media": float("nan"), "se": float("nan"), "acerto": float("nan")}
    return {"n": n, "media": float(x.mean()), "se": float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan"),
            "acerto": float((x > 0).mean())}


def f(x, casas: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:+.{casas}f}"


def pct(x) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.0f}%"


# ---------------------------------------------------------------------------------------------------- TPO
def tick_para(preco: float) -> float:
    return max(1.0, round(preco * TICK_PCT / 10.0) * 10.0) if preco >= 1000 else max(preco * TICK_PCT, 1e-8)


def perfil(his: np.ndarray, los: np.ndarray, tick: float):
    """(POC, VAL, VAH) do perfil TPO dos blocos dados (cópia de core/tpo_sessao.Perfil)."""
    base = math.floor(float(los.min()) / tick) * tick
    nb = int(math.floor((float(his.max()) - base) / tick)) + 1
    a = np.floor((los - base) / tick).astype(int)
    z = np.floor((his - base) / tick).astype(int)
    dif = np.zeros(nb + 1, dtype=int)
    np.add.at(dif, a, 1)
    np.add.at(dif, z + 1, -1)
    cont = np.cumsum(dif)[:nb]
    mx = cont.max()
    cand = np.flatnonzero(cont == mx)
    meio = (nb - 1) / 2
    i_poc = int(cand[np.argmin(np.abs(cand - meio))])
    poc = base + (i_poc + 0.5) * tick
    total = int(cont.sum())
    lo_i = hi_i = i_poc
    soma = int(cont[i_poc])
    c = cont.tolist()
    while soma < AREA_VALOR * total and (lo_i > 0 or hi_i < nb - 1):
        acima = c[hi_i + 1] if hi_i < nb - 1 else -1
        abaixo = c[lo_i - 1] if lo_i > 0 else -1
        if acima >= abaixo:
            hi_i += 1
            soma += max(acima, 0)
        else:
            lo_i -= 1
            soma += max(abaixo, 0)
    return poc, base + lo_i * tick, base + (hi_i + 1) * tick


class Blocos:
    """Blocos de 30 min completos (6 candles de 5 min) e perfis diários/compostos."""

    def __init__(self, m: Mercado):
        ts = m.a_ts
        bid = ts // BLOCO_MS
        ult = np.flatnonzero(np.diff(bid, append=bid[-1] + 1) != 0)
        prim = np.concatenate(([0], ult[:-1] + 1))
        ok = (ult - prim) == 5
        prim, ult = prim[ok], ult[ok]
        self.ts = bid[ult] * BLOCO_MS
        self.op = np.asarray(m.op)[prim]
        self.cl = m.a_cl[ult]
        idx6 = prim[:, None] + np.arange(6)[None, :]
        self.hi = m.a_hi[idx6].max(axis=1)
        self.lo = m.a_lo[idx6].min(axis=1)
        self.k_ult = ult
        self.k_prim = prim
        self.pos = {int(t): i for i, t in enumerate(self.ts)}
        dn = self.ts // DIA_MS
        self.dia_ini = {}
        self.dia_fim = {}
        for i, x in enumerate(dn.tolist()):
            if x not in self.dia_ini:
                self.dia_ini[x] = i
            self.dia_fim[x] = i + 1
        self._perf = {}
        self._comp = {}

    def dias(self):
        return sorted(self.dia_ini)

    def n_blocos(self, dn: int) -> int:
        return self.dia_fim.get(dn, 0) - self.dia_ini.get(dn, 0)

    def perfil_dia(self, dn: int):
        """(POC, VAL, VAH, máxima, mínima, fechamento) do dia UTC dn."""
        if dn not in self._perf:
            a, z = self.dia_ini[dn], self.dia_fim[dn]
            h, l = self.hi[a:z], self.lo[a:z]
            poc, val, vah = perfil(h, l, tick_para(float(self.cl[z - 1])))
            self._perf[dn] = (poc, val, vah, float(h.max()), float(l.min()), float(self.cl[z - 1]))
        return self._perf[dn]

    def perfil_parcial(self, a: int, z: int):
        """(POC, VAL, VAH) dos blocos [a, z)."""
        return perfil(self.hi[a:z], self.lo[a:z], tick_para(float(self.cl[z - 1])))

    def composto(self, dn: int, n: int = 10):
        """Merge dos n dias UTC anteriores a dn (todos presentes): (VAL, POC, VAH, mínima, máxima) ou None."""
        if dn not in self._comp:
            ds = [x for x in range(dn - n, dn) if x in self.dia_ini]
            if len(ds) < n:
                self._comp[dn] = None
            else:
                a, z = self.dia_ini[ds[0]], self.dia_fim[ds[-1]]
                h, l = self.hi[a:z], self.lo[a:z]
                poc, val, vah = perfil(h, l, tick_para(float(self.cl[z - 1])))
                self._comp[dn] = (val, poc, vah, float(l.min()), float(h.max()))
        return self._comp[dn]

    def naked_pocs(self, dn: int, janela: int = 30):
        """POCs dos dias [dn−janela, dn−1) que nenhum dia seguinte até dn−1 tocou (lista de preços)."""
        out = []
        for x in range(dn - janela, dn - 1):
            if x not in self.dia_ini:
                continue
            poc = self.perfil_dia(x)[0]
            tocado = False
            for y in range(x + 1, dn):
                if y in self.dia_ini:
                    pd_ = self.perfil_dia(y)
                    if pd_[4] <= poc <= pd_[3]:
                        tocado = True
                        break
            if not tocado:
                out.append(poc)
        return out


def posicao_composto(preco: float, comp) -> float:
    val, _, vah, _, _ = comp
    return (preco - val) / (vah - val) if vah > val else float("nan")
