# scripts/estudo_tpo_e1.py
"""
TPO E1 — "Abriu fora do valor de ontem e voltou" (docs/especialistas/plano_gestao.md 2.1, passo 1 da seção 4)
+ Regime F1 — tipo de dia pela 1ª hora como filtro das bordas (docs/especialistas/regime.md 2.3 e F1).
BTCUSDT 5 min (Binance), 2020-01 a 2026-09. CRITÉRIO ESCRITO ANTES DE RODAR; nenhum parâmetro iterado.

==================================================================================================== PARTE 1: TPO E1
Valor de ontem = perfil TPO do dia UTC D-1 (core/tpo_sessao.dias, blocos de 30 min): VAL, POC, VAH.
Sem aviso de sábado 00:00 a segunda 00:00 (regra 10): D = sábado ou domingo não entra.
Tabela de eventos macro não existe no projeto: o veto de evento (regra 9) NÃO é aplicado (ressalva no resumo).

Sessões (as 4 variantes = sessão × entrada):
  - "dia":     abertura = open do 1º candle de 5 min de D (00:00 UTC); janela do gatilho 00:00–04:00 (8 blocos).
  - "america": abertura = open do candle de 13:30 UTC;                janela do gatilho 13:30–17:30 (8 blocos).
Abriu fora: abertura > VAH (VENDA) ou < VAL (COMPRA). Dentro: não há evento.
Gatilho: fechamento do 2º bloco de 30 min CONSECUTIVO que fecha dentro de [VAL, VAH] (o primeiro par na janela).
Excursão = máxima (venda) / mínima (compra) da sessão desde a abertura até o fim do bloco do gatilho.
Stop = excursão + 0,10% (venda: × 1,001; compra: × 0,999), a mercado.
Entradas:
  - "fechamento": a mercado no fechamento do bloco do gatilho (taker 0,055% + slippage 0,02%).
  - "reteste": 3 limitadas post-only (venda) VAH − 0,10% (20%), VAH + 0,02% (30%), VAH + 0,15% (50%); compra espelhada
    no VAL. Post-only: fatia do lado errado do fechamento do gatilho é recusada; fatia além do stop não é posta; pesos
    renormalizados entre as postas. Válidas por 4 blocos (2 h) a partir do gatilho. Preenche só se o candle de 5 min
    ATRAVESSOU o preço (venda: máxima > preço). Maker 0,02%.
Filtros do aviso (calculados no gatilho com o médio PLANEJADO das fatias postas, ou com a entrada a mercado):
  - largura (VAH − VAL) / médio ≥ 2 × stop% (stop% = |stop − médio| / médio);
  - alvo = borda oposta de ontem (venda: VAL; compra: VAH) a ≥ 2R do médio. Falhando qualquer um: o aviso não sai.
Gestão: 1R = médio ± (stop − médio), recalculado a cada preenchimento; no 1R realiza 50% do preenchido (limitada,
  maker) e o stop do resto vai ao médio; fatias não preenchidas são canceladas no 1R. Resto sai no alvo (limitada,
  maker), no médio (a mercado) ou no teto de 24 h desde o 1º preenchimento (a mercado no fechamento do candle).
Pessimista: favor e contra no mesmo candle = contra; no candle em que alguma fatia preenche só o stop conta; no
  candle do 1R, se ele também tocou o médio, o resto sai no médio; limitadas de saída só com o preço atravessando.
Custos: maker 0,02%; taker 0,055% + slippage 0,02% em toda saída/entrada a mercado; funding linear da Bybit cobrado
  na posição aberta a cada 00/08/16 UTC (compra paga taxa positiva). Resultado em R por unidade preenchida
  (R = |stop − médio final| / médio). "Sem 1R" (alvo inteiro, stop fixo) é rodado só como informação.
Controles:
  (D) direção sorteada: mesma hora e preço da 1ª execução, entrada única, stop a R_plan e alvo a RR_plan × R_plan,
      mesma gestão; direção por moeda, 20 sorteios (média dos 20).
  (A) área de valor deslocada ao acaso: para cada dia e sessão, 20 sorteios do centro da área uniforme em
      [mínima, máxima] dos 10 dias anteriores, mesma largura (VAL/VAH deslocados juntos); TODA a regra é refeita com
      a área deslocada (abriu fora, 2 blocos dentro, stop, filtros, alvo na borda oposta deslocada).
Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09.
APROVAÇÃO (por variante, holdout olhado uma vez, nas 4 de uma vez):
  (1) líquido médio > 0 nos 3 períodos com ≥ 30 trades preenchidos em cada; abaixo de 30 = inconclusivo;
  (2) em treino e validação, média ≥ controle D + 2 EP e ≥ controle A + 2 EP (EP = desvio/√n da variante);
  (3) compra e venda e ano a ano são mostrados; com 4 variantes, ~1 passa em 2 períodos por acaso: olhar o conjunto.

==================================================================================================== PARTE 2: REGIME F1
Estratégia-base = H1 do estudo 2 (data/estudo_niveis_tpo_2.csv, gerado por scripts/estudo_niveis_tpo_2.py): toque
  no VAL compra, no VAH venda, R = 1%, corridas 1:1 e 2:1, compostos fixo10 e adapt; custo 0,06 R; média só de decididos
  (bruto 1:1 = 2p − 1; 2:1 = 3p − 1).
Tipo de dia (regime.md 2.3) declarado às 01:00 (Ásia: 1ª hora 00:00–01:00, P pela abertura de 00:00) e às 14:30
  (América: 1ª hora 13:30–14:30, P pelo preço de 13:30), sempre contra o valor de D-1:
  ATR_d = média de 14 dias do true range diário até D-1; A1 = amplitude de D-1 / ATR_d; IB = (máx − mín) da 1ª hora /
  ATR_d, em tercil pelos 60 dias anteriores da mesma sessão (≥ 30 valores); E1 = |fech − abert| / (máx − mín) da 1ª hora.
  F = sábado/domingo; X = A1 ≥ 1,8; D = IB tercil alto e E1 ≥ 0,6; A = P fora e a 1ª hora inteira fora (mín > VAH ou
  máx < VAL) e IB tercil médio/alto; V = P fora e fechamento da 1ª hora dentro do valor de D-1; C = A1 ≤ 0,6 e IB
  tercil baixo e fechamento da 1ª hora dentro do composto de 10 dias; R = P dentro e IB tercil baixo/médio e E1 ≤ 0,6;
  senão N. Precedência F > X > D > A > V > C > R (E não existe: sem tabela de eventos).
Toque das 01:00 às 13:30 usa o tipo da Ásia; das 14:30 às 24:00 o da América; 00:00–01:00 e 13:30–14:30 ficam fora.
Grupos: sem filtro (mesmas horas elegíveis) · FILTRADO (R ou V) · INVERTIDO (A ou D) · SORTEADO (rótulos de cada sessão
  embaralhados entre os dias, mesma proporção, 20 sorteios).
APROVAÇÃO (por linha base × corrida): líquido > 0 nos 3 períodos com ≥ 30 decididos **e** filtrado acima de ≥ 19 dos
  20 sorteados no holdout **e** invertido pior que o sem-filtro nos 3 períodos. Faltando qualquer um, F1 não separa.

Saídas: data/estudo_tpo_e1.csv (trades da E1), data/estudo_tpo_e1_f1.csv (toques com tipo de dia) e
data/estudo_tpo_e1_resumo.md.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from conselho.composto import ParametrosRange, contexto  # noqa: E402
from conselho.tpo import BLOCO_MS, DIA_MS, dias  # noqa: E402

CSV5 = RAIZ / "data" / "historico" / "BTCUSDT_binance_5m.csv"
FUNDING = RAIZ / "data" / "historico" / "funding_bybit.json"
TOQUES_EST2 = RAIZ / "data" / "estudo_niveis_tpo_2.csv"
SAIDA_CSV = RAIZ / "data" / "estudo_tpo_e1.csv"
SAIDA_F1 = RAIZ / "data" / "estudo_tpo_e1_f1.csv"
SAIDA_MD = RAIZ / "data" / "estudo_tpo_e1_resumo.md"

INICIO_DADOS = "2019-11-01"
PERIODOS = [("treino", "2020-01-01", "2023-12-31"), ("validacao", "2024-01-01", "2025-06-30"),
            ("holdout", "2025-07-01", "2026-09-30")]
M5 = 300_000
HORA = 3_600_000
SESSOES = {"dia": 0, "america": 13 * HORA + 30 * 60_000}
JANELA_GATILHO = 8          # blocos de 30 min
VALIDADE_FILL = 24          # candles de 5 min = 2 h
TETO = 288                  # candles de 5 min = 24 h
FOLGA_STOP = 0.001
FATIAS_VENDA = [(-0.0010, 0.2), (0.0002, 0.3), (0.0015, 0.5)]   # offsets sobre o VAH (venda); compra espelha no VAL
MAKER = 0.0002
TAKER = 0.00055 + 0.0002
RR_MIN = 2.0
N_SORTEIOS = 20
SEMENTE = 20261020
MIN_N = 30
P_FIXO = ParametrosRange(range_adaptativo=False, n_dias=10)


# ---------------------------------------------------------------------------------------------------- dados
def carregar():
    df = pd.read_csv(CSV5)
    df = df[df["timestamp"] >= int(pd.Timestamp(INICIO_DADOS, tz="UTC").timestamp() * 1000)]
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def periodo_de(data: str) -> str:
    for nome, a, z in PERIODOS:
        if a <= data <= z:
            return nome
    return ""


class Mercado:
    def __init__(self, df: pd.DataFrame):
        self.ts = df["timestamp"].to_numpy(np.int64)
        self.op = df["open"].to_numpy(float)
        self.hi = df["high"].to_numpy(float)
        self.lo = df["low"].to_numpy(float)
        self.cl = df["close"].to_numpy(float)
        self.pos = {int(t): i for i, t in enumerate(self.ts)}
        d = json.load(open(FUNDING))["linear"]
        self.funding = {int(k): float(v) for k, v in d.items()}

    def idx(self, t: int):
        return self.pos.get(int(t))


# ---------------------------------------------------------------------------------------------------- simulação
def simular(m: Mercado, d: int, fatias: list[tuple[float, float]], stop: float, alvo: float, k0: int,
            mercado: bool, parcial: bool = True, forcar_em: int | None = None) -> dict | None:
    """
    d = +1 compra / -1 venda. fatias = [(preço, peso)]. mercado=True: a fatia única é executada no fechamento do
    candle k0-1 (tudo conta a partir de k0). forcar_em=k: a fatia única é executada no candle k (regra do candle de
    preenchimento: só o stop conta nele). Senão: limitadas a partir de k0, válidas por VALIDADE_FILL candles.
    """
    hi, lo, cl, ts = m.hi, m.lo, m.cl, m.ts
    n = len(hi)
    cheias: list[tuple[float, float]] = []
    pend = []
    t1 = None
    if mercado:
        cheias = [(fatias[0][0], 1.0)]
        t1 = k0
    elif forcar_em is None:
        pend = list(fatias)
    custo_ent = TAKER if mercado else MAKER
    saidas: list[tuple[float, float, str]] = []    # (peso, preço, 'lim'|'mkt')
    fund = 0.0
    tomou_1r = False
    stop_cur = stop
    saida_tipo = None
    k = k0 if forcar_em is None else forcar_em
    while k < n:
        aberto = sum(w for _, w in cheias) - sum(w for w, _, _ in saidas)
        if aberto > 1e-12 and ts[k] % (8 * HORA) == 0:
            fund -= d * m.funding.get(int(ts[k]), 0.0) * aberto
        barra_fill = False
        if forcar_em is not None and k == forcar_em:
            cheias = [(fatias[0][0], 1.0)]
            t1 = k
            barra_fill = True
        elif pend and not tomou_1r and k < k0 + VALIDADE_FILL:
            novas = [(p, w) for p, w in pend if (d == -1 and hi[k] > p) or (d == 1 and lo[k] < p)]
            if novas:
                cheias += novas
                pend = [x for x in pend if x not in novas]
                barra_fill = True
                if t1 is None:
                    t1 = k
        if not cheias:
            if k >= k0 + VALIDADE_FILL - 1:
                return None
            k += 1
            continue
        wf = sum(w for _, w in cheias)
        medio = sum(p * w for p, w in cheias) / wf
        r_abs = abs(stop - medio)
        aberto = wf - sum(w for w, _, _ in saidas)
        # stop (toque)
        if (d == 1 and lo[k] <= stop_cur) or (d == -1 and hi[k] >= stop_cur):
            saidas.append((aberto, stop_cur, "mkt"))
            saida_tipo = "medio" if tomou_1r else "stop"
            break
        if not barra_fill:
            atravessa = (lambda p: hi[k] > p) if d == 1 else (lambda p: lo[k] < p)
            if parcial and not tomou_1r:
                n1 = medio + d * r_abs
                if atravessa(n1):
                    saidas.append((0.5 * wf, n1, "lim"))
                    tomou_1r = True
                    pend = []
                    stop_cur = medio
                    aberto = 0.5 * wf
                    if (d == 1 and lo[k] <= medio) or (d == -1 and hi[k] >= medio):
                        saidas.append((aberto, medio, "mkt"))
                        saida_tipo = "medio"
                        break
            if atravessa(alvo):
                saidas.append((aberto, alvo, "lim"))
                saida_tipo = "alvo"
                break
        if t1 is not None and k - t1 + 1 >= TETO:
            saidas.append((aberto, float(cl[k]), "mkt"))
            saida_tipo = "tempo"
            break
        if pend and k >= k0 + VALIDADE_FILL - 1:
            pend = []
        k += 1
    else:
        return None
    wf = sum(w for _, w in cheias)
    medio = sum(p * w for p, w in cheias) / wf
    r_pct = abs(stop - medio) / medio
    pnl = -custo_ent * wf + fund
    for w, p, tp in saidas:
        pnl += w * (d * (p / medio - 1) - (MAKER if tp == "lim" else TAKER))
    pnl /= wf
    return {"res_r": pnl / r_pct, "frac": wf, "saida": saida_tipo, "tomou_1r": tomou_1r, "r_pct": r_pct,
            "k_fill": t1, "p_fill": cheias[0][0], "candles": k - (t1 or k0) + 1}


# ---------------------------------------------------------------------------------------------------- evento E1
def evento_e1(m: Mercado, blocos: dict, t_ini: int, val: float, vah: float):
    """Detecta abriu-fora-e-voltou na sessão que começa em t_ini. Devolve dict ou None."""
    k_ini = m.idx(t_ini)
    if k_ini is None or not (vah > val):
        return None
    abertura = m.op[k_ini]
    if abertura > vah:
        d = -1
    elif abertura < val:
        d = 1
    else:
        return None
    b0 = t_ini // BLOCO_MS
    dentro_ant = False
    for j in range(JANELA_GATILHO):
        b = blocos.get(b0 + j)
        if b is None:
            return None
        dentro = val <= b[0] <= vah
        if dentro and dentro_ant:
            k_fim = b[1]                       # índice do último candle de 5 min do bloco
            seg_h, seg_l = m.hi[k_ini:k_fim + 1], m.lo[k_ini:k_fim + 1]
            exc = float(seg_h.max()) if d == -1 else float(seg_l.min())
            return {"d": d, "k_gat": k_fim, "fech": float(m.cl[k_fim]), "exc": exc, "abertura": float(abertura),
                    "bloco": j + 1}
        dentro_ant = dentro
    return None


def trades_e1(m: Mercado, ev: dict, val: float, vah: float, entrada: str):
    """Monta o aviso (fatias, stop, alvo, filtros) e simula com e sem 1R. Devolve dict ou None (aviso não sai)."""
    d, fech = ev["d"], ev["fech"]
    stop = ev["exc"] * (1 + FOLGA_STOP) if d == -1 else ev["exc"] * (1 - FOLGA_STOP)
    alvo = val if d == -1 else vah
    if entrada == "fechamento":
        fatias = [(fech, 1.0)]
    else:
        borda = vah if d == -1 else val
        fatias = []
        for off, w in FATIAS_VENDA:
            p = borda * (1 + off) if d == -1 else borda * (1 - off)
            lado_ok = (p > fech) if d == -1 else (p < fech)
            antes_stop = (p < stop) if d == -1 else (p > stop)
            if lado_ok and antes_stop:
                fatias.append((p, w))
        if not fatias:
            return {"sai": False, "motivo": "sem fatia"}
        tw = sum(w for _, w in fatias)
        fatias = [(p, w / tw) for p, w in fatias]
    medio = sum(p * w for p, w in fatias)
    r_plan = abs(stop - medio) / medio
    if (d == -1 and stop <= medio) or (d == 1 and stop >= medio):
        return {"sai": False, "motivo": "stop do lado errado"}
    rr = abs(medio - alvo) / abs(stop - medio)
    larg = (vah - val) / medio
    base = {"sai": True, "r_plan": r_plan, "rr_plan": rr, "larg_pct": larg, "medio_plan": medio, "stop": stop,
            "alvo": alvo, "n_fatias": len(fatias)}
    if larg < 2 * r_plan:
        return {**base, "sai": False, "motivo": "largura < 2x stop"}
    if rr < RR_MIN or (d == -1 and alvo >= medio) or (d == 1 and alvo <= medio):
        return {**base, "sai": False, "motivo": "alvo < 2R"}
    k0 = ev["k_gat"] + 1
    merc = entrada == "fechamento"
    com = simular(m, d, fatias, stop, alvo, k0, merc, parcial=True)
    sem = simular(m, d, fatias, stop, alvo, k0, merc, parcial=False)
    base.update({"com": com, "sem": sem, "k0": k0})
    return base


def controle_direcao(m: Mercado, tr: dict, d: int, entrada: str) -> tuple[float | None, float | None]:
    """Resultado (mesma direção, direção oposta) da entrada única na 1ª execução, stop R_plan, alvo RR_plan."""
    com = tr["com"]
    if com is None:
        return None, None
    p = com["p_fill"]
    out = []
    for dd in (d, -d):
        stop = p * (1 - dd * tr["r_plan"])
        alvo = p * (1 + dd * tr["rr_plan"] * tr["r_plan"])
        if entrada == "fechamento":
            s = simular(m, dd, [(p, 1.0)], stop, alvo, tr["k0"], True, parcial=True)
        else:
            s = simular(m, dd, [(p, 1.0)], stop, alvo, tr["k0"], False, parcial=True, forcar_em=com["k_fill"])
        out.append(s["res_r"] if s else None)
    return out[0], out[1]


# ---------------------------------------------------------------------------------------------------- tipo de dia (F1)
def tipos_de_dia(m: Mercado, perfis, idx_de) -> pd.DataFrame:
    dnum = m.ts // DIA_MS
    dias_n = sorted(idx_de)
    # diário a partir dos perfis
    hi_d = {dn: perfis[idx_de[dn]].maxima for dn in dias_n}
    lo_d = {dn: perfis[idx_de[dn]].minima for dn in dias_n}
    cl_d = {dn: perfis[idx_de[dn]].fechamento for dn in dias_n}
    tr_d = {}
    for dn in dias_n:
        pc = cl_d.get(dn - 1)
        tr_d[dn] = max(hi_d[dn], pc) - min(lo_d[dn], pc) if pc is not None else hi_d[dn] - lo_d[dn]
    linhas = []
    hist_ib = {"asia": [], "america": []}
    for dn in dias_n:
        i = idx_de[dn]
        if i < 15 or (dn - 1) not in idx_de:
            continue
        trs = [tr_d[x] for x in range(dn - 14, dn) if x in tr_d]
        if len(trs) < 10:
            continue
        atr = float(np.mean(trs))
        ont = perfis[idx_de[dn - 1]]
        val, vah = ont.area_valor()
        a1 = (ont.maxima - ont.minima) / atr
        prev = perfis[max(0, i - 10):i]
        ctx = contexto(prev, P_FIXO) if len(prev) >= 10 else None
        data = pd.Timestamp(dn * DIA_MS, unit="ms", tz="UTC")
        fds = data.weekday() >= 5
        reg = {"dnum": dn, "data": data.strftime("%Y-%m-%d"), "atr": atr, "a1": a1, "val": val, "vah": vah}
        for ses, t_rel in (("asia", 0), ("america", 13 * HORA + 30 * 60_000)):
            t0 = dn * DIA_MS + t_rel
            k0 = m.idx(t0)
            k1 = m.idx(t0 + HORA - M5)
            if k0 is None or k1 is None or k1 - k0 != 11:
                reg[f"tipo_{ses}"] = "?"
                continue
            ab = m.op[k0]
            fe = m.cl[k1]
            mx, mn = float(m.hi[k0:k1 + 1].max()), float(m.lo[k0:k1 + 1].min())
            ib = (mx - mn) / atr
            e1 = abs(fe - ab) / (mx - mn) if mx > mn else 0.0
            h = hist_ib[ses][-60:]
            if len(h) >= 30:
                q1, q2 = np.quantile(h, [1 / 3, 2 / 3])
                terc = "baixo" if ib <= q1 else ("alto" if ib > q2 else "medio")
            else:
                terc = None
            hist_ib[ses].append(ib)
            fora = ab > vah or ab < val
            if fds:
                tipo = "F"
            elif terc is None:
                tipo = "?"
            elif a1 >= 1.8:
                tipo = "X"
            elif terc == "alto" and e1 >= 0.6:
                tipo = "D"
            elif fora and (mn > vah or mx < val) and terc in ("medio", "alto"):
                tipo = "A"
            elif fora and val <= fe <= vah:
                tipo = "V"
            elif a1 <= 0.6 and terc == "baixo" and ctx is not None and ctx.val <= fe <= ctx.vah:
                tipo = "C"
            elif not fora and terc in ("baixo", "medio") and e1 <= 0.6:
                tipo = "R"
            else:
                tipo = "N"
            reg.update({f"tipo_{ses}": tipo, f"ib_{ses}": ib, f"e1_{ses}": e1, f"terc_{ses}": terc})
        linhas.append(reg)
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------------------------------- estatística
def est(x) -> dict:
    x = np.asarray([v for v in x if v is not None and not np.isnan(v)], float)
    n = len(x)
    if n == 0:
        return {"n": 0, "media": np.nan, "se": np.nan, "acerto": np.nan}
    return {"n": n, "media": float(x.mean()), "se": float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan,
            "acerto": float((x > 0).mean())}


def f(x, casas=3):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.{casas}f}"


# ---------------------------------------------------------------------------------------------------- parte 1
def rodar_e1(m: Mercado, perfis, idx_de):
    t0 = time.time()
    bid = m.ts // BLOCO_MS
    # blocos: id -> (fechamento, índice do último candle de 5 min); só blocos completos (6 candles)
    ult = np.flatnonzero(np.diff(bid, append=bid[-1] + 1) != 0)
    prim = np.concatenate(([0], ult[:-1] + 1))
    blocos = {int(bid[u]): (float(m.cl[u]), int(u)) for p0, u in zip(prim, ult) if u - p0 == 5}
    rng = np.random.default_rng(SEMENTE)
    linhas, ctrl_area = [], []
    for dn in sorted(idx_de):
        data = pd.Timestamp(dn * DIA_MS, unit="ms", tz="UTC")
        ds = data.strftime("%Y-%m-%d")
        per = periodo_de(ds)
        if not per or data.weekday() >= 5 or (dn - 1) not in idx_de:
            continue
        i = idx_de[dn]
        ont = perfis[idx_de[dn - 1]]
        if len(ont.blocos) < 40:
            continue
        val, vah = ont.area_valor()
        p10 = perfis[max(0, i - 10):i]
        lo10, hi10 = min(p.minima for p in p10), max(p.maxima for p in p10)
        larg = vah - val
        centros = rng.uniform(lo10, hi10, size=(len(SESSOES), N_SORTEIOS))
        for si, (ses, t_rel) in enumerate(SESSOES.items()):
            t_ini = dn * DIA_MS + t_rel
            ev = evento_e1(m, blocos, t_ini, val, vah)
            if ev is not None:
                for entrada in ("fechamento", "reteste"):
                    tr = trades_e1(m, ev, val, vah, entrada)
                    reg = {"data": ds, "ano": data.year, "periodo": per, "sessao": ses, "entrada": entrada,
                           "lado": "compra" if ev["d"] == 1 else "venda", "val": val, "vah": vah,
                           "poc": ont.poc(), "abertura": ev["abertura"], "exc": ev["exc"], "bloco_gat": ev["bloco"],
                           "sai": tr["sai"], "motivo": tr.get("motivo", "")}
                    for kk in ("r_plan", "rr_plan", "larg_pct", "n_fatias"):
                        reg[kk] = tr.get(kk, np.nan)
                    if tr["sai"]:
                        com, sem = tr["com"], tr["sem"]
                        reg.update({"preencheu": com is not None,
                                    "res_r": com["res_r"] if com else np.nan,
                                    "res_r_sem1r": sem["res_r"] if sem else np.nan,
                                    "saida": com["saida"] if com else "", "tomou_1r": com["tomou_1r"] if com else False,
                                    "frac": com["frac"] if com else 0.0, "candles": com["candles"] if com else np.nan})
                        a, b = controle_direcao(m, tr, ev["d"], entrada)
                        reg.update({"ctrl_mesma": a, "ctrl_oposta": b})
                    linhas.append(reg)
            # controle A: área deslocada
            for s in range(N_SORTEIOS):
                c = centros[si, s]
                v2, h2 = c - larg / 2, c + larg / 2
                ev2 = evento_e1(m, blocos, t_ini, v2, h2)
                if ev2 is None:
                    continue
                for entrada in ("fechamento", "reteste"):
                    tr2 = trades_e1(m, ev2, v2, h2, entrada)
                    if tr2["sai"] and tr2["com"] is not None:
                        ctrl_area.append({"periodo": per, "sessao": ses, "entrada": entrada, "sorteio": s,
                                          "lado": "compra" if ev2["d"] == 1 else "venda",
                                          "res_r": tr2["com"]["res_r"]})
        if dn % 365 == 0:
            print(f"  {ds} eventos={len(linhas)} ctrl_area={len(ctrl_area)} ({time.time() - t0:.0f}s)")
    df = pd.DataFrame(linhas)
    ca = pd.DataFrame(ctrl_area)
    # controle de direção: 20 sorteios por moeda
    rng2 = np.random.default_rng(SEMENTE + 1)
    moedas = rng2.integers(0, 2, size=(len(df), N_SORTEIOS))
    for s in range(N_SORTEIOS):
        df[f"cd_{s}"] = np.where(moedas[:, s] == 0, df.get("ctrl_mesma"), df.get("ctrl_oposta"))
    df.to_csv(SAIDA_CSV, index=False)
    print(f"E1: {len(df)} linhas, controle de área {len(ca)} trades ({time.time() - t0:.0f}s)")
    return df, ca


def resumo_e1(df: pd.DataFrame, ca: pd.DataFrame) -> tuple[list[str], dict]:
    out = []
    veredito = {}
    out.append("## Parte 1 — TPO E1 (abriu fora do valor de ontem e voltou)\n")
    # funil
    out.append("### Funil (dias úteis 2020-01..2026-09)\n")
    out.append("| sessão | entrada | eventos (abriu fora e 2 blocos dentro) | aviso sai | largura < 2× stop | alvo < 2R | sem fatia | preencheu |")
    out.append("|---|---|---|---|---|---|---|---|")
    for ses in SESSOES:
        for ent in ("fechamento", "reteste"):
            s = df[(df.sessao == ses) & (df.entrada == ent)]
            out.append(f"| {ses} | {ent} | {len(s)} | {int(s.sai.sum())} | {int((s.motivo == 'largura < 2x stop').sum())} | "
                       f"{int((s.motivo == 'alvo < 2R').sum())} | {int((s.motivo == 'sem fatia').sum())} | "
                       f"{int(s.get('preencheu', pd.Series(dtype=bool)).fillna(False).astype(bool).sum())} |")
    out.append("")
    out.append("### Resultado por variante e período (R líquido por trade preenchido, com 1R e stop no médio)\n")
    out.append("EP = erro padrão da média. Controle D = direção sorteada (média de 20 sorteios, mesma entrada); "
               "controle A = área de valor deslocada ao acaso (20 sorteios, regra inteira refeita). "
               "Critério: líquido > 0 nos 3 períodos (n ≥ 30) e, em treino e validação, ≥ D + 2 EP e ≥ A + 2 EP.\n")
    out.append("| variante | período | n | acerto (>0) | média R ± EP | controle D | controle A (n) | ≥ D+2EP | ≥ A+2EP | sem 1R (média) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for ses in SESSOES:
        for ent in ("fechamento", "reteste"):
            nome = f"{ses} × {ent}"
            ok_all = True
            motivos = []
            for per, _, _ in PERIODOS:
                s = df[(df.sessao == ses) & (df.entrada == ent) & (df.periodo == per) & (df.sai == True)
                       & (df.get("preencheu") == True)]
                e = est(s.res_r.to_numpy(float))
                sem = est(s.res_r_sem1r.to_numpy(float))
                cds = [np.nanmean(pd.to_numeric(s[f"cd_{k}"], errors="coerce").to_numpy(float)) for k in range(N_SORTEIOS)] if len(s) else [np.nan]
                cd = float(np.nanmean(cds)) if len(s) else np.nan
                sa = ca[(ca.sessao == ses) & (ca.entrada == ent) & (ca.periodo == per)] if len(ca) else ca
                ea = est(sa.res_r.to_numpy(float)) if len(sa) else {"n": 0, "media": np.nan}
                acima_d = (e["media"] >= cd + 2 * e["se"]) if e["n"] > 1 and not np.isnan(cd) else False
                acima_a = (e["media"] >= ea["media"] + 2 * e["se"]) if e["n"] > 1 and ea["n"] else False
                out.append(f"| {nome} | {per} | {e['n']} | {f(e['acerto'] * 100 if e['n'] else np.nan, 1)}% | "
                           f"{f(e['media'])} ± {e['se']:.3f} | {f(cd)} | {f(ea['media'])} ({ea['n']}) | "
                           f"{'sim' if acima_d else 'não'} | {'sim' if acima_a else 'não'} | {f(sem['media'])} |"
                           if e["n"] > 1 else f"| {nome} | {per} | {e['n']} | - | - | {f(cd)} | {f(ea['media'])} ({ea['n']}) | - | - | - |")
                if e["n"] < MIN_N:
                    ok_all = False
                    motivos.append(f"{per}: n={e['n']} < 30 (inconclusivo)")
                elif not e["media"] > 0:
                    ok_all = False
                    motivos.append(f"{per}: líquido {e['media']:+.3f} ≤ 0")
                if per in ("treino", "validacao") and e["n"] >= MIN_N:
                    if not acima_d:
                        ok_all = False
                        motivos.append(f"{per}: não está 2 EP acima da direção sorteada")
                    if not acima_a:
                        ok_all = False
                        motivos.append(f"{per}: não está 2 EP acima da área deslocada")
            veredito[nome] = (ok_all, motivos)
    out.append("")
    out.append("### Por lado (todas as sessões e entradas separadas; média R líquida, n)\n")
    out.append("| variante | lado | treino | validação | holdout |")
    out.append("|---|---|---|---|---|")
    ok = df[(df.sai == True) & (df.get("preencheu") == True)]
    for ses in SESSOES:
        for ent in ("fechamento", "reteste"):
            for lado in ("compra", "venda"):
                cel = []
                for per, _, _ in PERIODOS:
                    e = est(ok[(ok.sessao == ses) & (ok.entrada == ent) & (ok.lado == lado) & (ok.periodo == per)].res_r.to_numpy(float))
                    cel.append(f"{f(e['media'])} ({e['n']})")
                out.append(f"| {ses} × {ent} | {lado} | " + " | ".join(cel) + " |")
    out.append("")
    out.append("### Ano a ano (média R líquida, n)\n")
    anos = sorted(ok.ano.unique()) if len(ok) else []
    out.append("| variante | " + " | ".join(str(a) for a in anos) + " |")
    out.append("|---|" + "---|" * len(anos))
    for ses in SESSOES:
        for ent in ("fechamento", "reteste"):
            cel = []
            for a in anos:
                e = est(ok[(ok.sessao == ses) & (ok.entrada == ent) & (ok.ano == a)].res_r.to_numpy(float))
                cel.append(f"{f(e['media'], 2)} ({e['n']})")
            out.append(f"| {ses} × {ent} | " + " | ".join(cel) + " |")
    out.append("")
    out.append("### Como saíram (todas as variantes, todos os períodos)\n")
    out.append("| variante | n | alvo | médio (zero a zero após 1R) | stop | tempo | tomou 1R | R planejado médio | RR planejado médio |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for ses in SESSOES:
        for ent in ("fechamento", "reteste"):
            s = ok[(ok.sessao == ses) & (ok.entrada == ent)]
            if not len(s):
                continue
            vc = s.saida.value_counts()
            out.append(f"| {ses} × {ent} | {len(s)} | {vc.get('alvo', 0)} | {vc.get('medio', 0)} | {vc.get('stop', 0)} | "
                       f"{vc.get('tempo', 0)} | {int(s.tomou_1r.sum())} | {s.r_plan.mean() * 100:.2f}% | {s.rr_plan.mean():.2f} |")
    out.append("")
    return out, veredito


# ---------------------------------------------------------------------------------------------------- parte 2
def rodar_f1(tipos: pd.DataFrame) -> tuple[list[str], dict]:
    df = pd.read_csv(TOQUES_EST2)
    df = df[df.composto.isin(["fixo10", "adapt"]) & df.tipo.isin(["VAL", "VAH"])].copy()
    df["dnum"] = df.ts_toque // DIA_MS
    mins = (df.ts_toque % DIA_MS) // 60_000
    df["sessao_tipo"] = np.where((mins >= 60) & (mins < 13 * 60 + 30), "asia",
                                 np.where(mins >= 14 * 60 + 30, "america", ""))
    tp = tipos.set_index("dnum")
    df["tipo_dia"] = [tp.at[d, f"tipo_{s}"] if (s and d in tp.index) else "" for d, s in zip(df.dnum, df.sessao_tipo)]
    df.to_csv(SAIDA_F1, index=False)
    # rótulos sorteados: por sessão, permuta entre os dias
    rng = np.random.default_rng(SEMENTE + 2)
    sorteados = []
    for s in range(N_SORTEIOS):
        mp = {}
        for ses in ("asia", "america"):
            lab = tipos[f"tipo_{ses}"].to_numpy()
            mp[ses] = dict(zip(tipos.dnum.to_numpy(), rng.permutation(lab)))
        sorteados.append([mp[s_][d] if s_ else "" for d, s_ in zip(df.dnum, df.sessao_tipo)])

    def liq(v: np.ndarray, mult: float):
        v = v[v != 0]
        if len(v) == 0:
            return np.nan, 0
        p = (v == 1).mean()
        return (mult + 1) * p - 1 - 0.06, len(v)

    out = ["## Parte 2 — Regime F1 (tipo de dia pela 1ª hora como filtro das bordas)\n"]
    out.append("Frequência dos tipos (dias úteis e fds, 2020–2026):\n")
    out.append("| sessão | " + " | ".join("FXDAVCRN?") + " |")
    out.append("|---|" + "---|" * 9)
    for ses in ("asia", "america"):
        vc = tipos[f"tipo_{ses}"].value_counts(normalize=True)
        out.append(f"| {ses} | " + " | ".join(f"{vc.get(t, 0) * 100:.0f}%" for t in "FXDAVCRN?") + " |")
    out.append("")
    out.append("Líquido em R por toque decidido (n decididos). Sem filtro = mesmas horas elegíveis (01:00–13:30 e "
               "14:30–24:00), todos os dias. Sorteado = média dos 20 e quantos dos 20 o filtrado supera.\n")
    out.append("| base | corrida | período | sem filtro (todas as horas) | sem filtro (horas elegíveis) | FILTRADO R/V | INVERTIDO A/D | sorteado (média) | filtrado > sorteados |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    veredito = {}
    eleg = df.sessao_tipo != ""
    for comp in ("fixo10", "adapt"):
        for tipo, col_dir in (("VAL", "compra"), ("VAH", "venda")):
            base = (df.composto == comp) & (df.tipo == tipo)
            for fmt, mult in (("11", 1.0), ("21", 2.0)):
                col = f"tr_r1_{fmt}"
                ok = True
                mot = []
                for per, _, _ in PERIODOS:
                    bp = base & (df.periodo == per)
                    l_all, n_all = liq(df.loc[bp, col].to_numpy(), mult)
                    l_el, n_el = liq(df.loc[bp & eleg, col].to_numpy(), mult)
                    l_f, n_f = liq(df.loc[bp & df.tipo_dia.isin(["R", "V"]), col].to_numpy(), mult)
                    l_i, n_i = liq(df.loc[bp & df.tipo_dia.isin(["A", "D"]), col].to_numpy(), mult)
                    ls = []
                    for s in range(N_SORTEIOS):
                        lab = pd.Series(sorteados[s], index=df.index)
                        ls.append(liq(df.loc[bp & lab.isin(["R", "V"]), col].to_numpy(), mult)[0])
                    ls = np.array(ls, float)
                    vence = int((l_f > ls).sum()) if not np.isnan(l_f) else 0
                    out.append(f"| {comp} {tipo} {col_dir} | {fmt[0]}:{fmt[1]} | {per} | {f(l_all)} ({n_all}) | {f(l_el)} ({n_el}) | "
                               f"{f(l_f)} ({n_f}) | {f(l_i)} ({n_i}) | {f(float(np.nanmean(ls)))} | {vence}/20 |")
                    if n_f < MIN_N:
                        ok = False
                        mot.append(f"{per}: filtrado n={n_f} < 30")
                    elif not l_f > 0:
                        ok = False
                        mot.append(f"{per}: filtrado {l_f:+.3f} ≤ 0")
                    if not (l_i < l_el):
                        ok = False
                        mot.append(f"{per}: invertido não é pior que o sem-filtro")
                    if per == "holdout" and vence < 19:
                        ok = False
                        mot.append(f"holdout: filtrado supera só {vence}/20 sorteados")
                veredito[f"{comp} {tipo} {fmt[0]}:{fmt[1]}"] = (ok, mot)
    out.append("")
    # informação: a regra dos tipos separa o resto do dia? (reação 1:1 por tipo, todas as linhas base juntas)
    out.append("Informação (não entra no veredito): líquido 1:1 por tipo de dia, composto fixo10, VAL+VAH juntos, todos os períodos.\n")
    out.append("| tipo | n decididos | líquido 1:1 |")
    out.append("|---|---|---|")
    b = (df.composto == "fixo10")
    for t in "RVCADXNF":
        l, n = liq(df.loc[b & (df.tipo_dia == t), "tr_r1_11"].to_numpy(), 1.0)
        out.append(f"| {t} | {n} | {f(l)} |")
    out.append("")
    return out, veredito


# ---------------------------------------------------------------------------------------------------- principal
def main():
    t0 = time.time()
    df5 = carregar()
    m = Mercado(df5)
    print(f"5m: {len(df5):,} candles ({time.time() - t0:.0f}s)")
    candles = df5[["timestamp", "open", "high", "low", "close", "volume"]].to_numpy(float)
    perfis = dias(candles)
    idx_de = {p.inicio // DIA_MS: i for i, p in enumerate(perfis)}
    print(f"perfis: {len(perfis)} ({time.time() - t0:.0f}s)")
    e1, ca = rodar_e1(m, perfis, idx_de)
    md1, v1 = resumo_e1(e1, ca)
    tipos = tipos_de_dia(m, perfis, idx_de)
    print(f"tipos de dia: {len(tipos)} ({time.time() - t0:.0f}s)")
    md2, v2 = rodar_f1(tipos)
    cab = ["# Estudo TPO E1 + Regime F1 — resultado\n",
           f"Gerado por `scripts/estudo_tpo_e1.py` em {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC. Regra exata e "
           "critério no docstring do script (escritos antes de rodar; nenhum parâmetro iterado).\n",
           "## Veredito pelo critério escrito antes\n"]
    for nome, (ok, mot) in v1.items():
        cab.append(f"- TPO E1 **{nome}**: {'APROVADA' if ok else 'reprovada'}" + ("" if ok else " — " + "; ".join(mot[:4])))
    for nome, (ok, mot) in v2.items():
        cab.append(f"- Regime F1 sobre **{nome}**: {'separa' if ok else 'não separa'}" + ("" if ok else " — " + "; ".join(mot[:4])))
    cab.append("")
    SAIDA_MD.write_text("\n".join(cab + md1 + md2), encoding="utf-8")
    print(f"resumo -> {SAIDA_MD} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
