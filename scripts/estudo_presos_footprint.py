# scripts/estudo_presos_footprint.py
"""
FLUXO D — "Nódulo abandonado" (presos pelo footprint). docs/especialistas/plano_gestao.md 2.5 e passo 2 da seção 4;
regra em docs/especialistas/fluxo.md 5.1 e docs/tradeiros/presos_footprint.md 5.3–5.4.
Negócios reais da Bybit (BTCUSDT linear, lado do agressor), dados/trades_bybit, 10/08 a 08/09/2026.
CRITÉRIO ESCRITO ANTES DE RODAR; nenhum parâmetro iterado.

Redução: cada negócio vira (minuto, nível de 20 USD = floor(preço/20)*20, lado) com notional em USD = size × price;
por minuto também OHLC e delta (compra − venda). O bruto não é guardado (só a redução, opcionalmente em --cache).
Barras de 5 min e 30 min reagregadas dos minutos. Preço do nível L = centro da faixa (piso + 10).

Detecção (COMPRADOR preso; o vendedor preso é o espelho exato):
  1. Nódulo na barra B: nível L com vol_buy(L) ≥ 3 × mediana de vol_buy dos níveis negociados de B, ≥ p90 de vol_buy
     por nível das 48 barras ANTERIORES (todos os níveis negociados), ≥ 500 mil USD (piso absoluto, plano 2.5),
     L no terço superior do range de B, delta(L) > 0. Vários níveis: fica o de maior vol_buy (1 por barra e lado).
  2. Absorvido: fech(B) ≤ L × (1 − 0,05%).
  3. Abandonado: as 2 barras seguintes FECHAM ≥ 0,3% (5 min) / ≥ 0,5% (30 min) abaixo de L e nenhuma negocia acima da
     máxima de B (plano 2.5: "as 2 barras seguintes fecham").
  4. Reteste: depois do fechamento de B+2, o primeiro minuto que encosta na zona L ± 0,05% vindo de baixo (máxima ≥
     L × (1 − 0,05%) com o preço antes abaixo da zona). Tem de ser a partir do início de B+4 (≥ 2 barras depois do
     abandono) e até 24 h depois do fechamento de B; se a primeira volta veio antes, não há evento.
  5. Confirmação (versão medida do plano): dentro de 30 min desde o toque, o primeiro minuto na zona que fecha abaixo
     da própria abertura com delta do minuto ≤ 0; se o stop for tocado antes, não há entrada.
  6. Entrada: a mercado no fechamento desse minuto (taker 0,055% + slippage 0,02%). Stop = máxima de B + 0,10%, a
     mercado (taker + slippage). Sessão: entrada em dia útil entre 08:00 e 20:00 UTC (Europa e América); fora disso,
     o aviso não sai. Veto de macro não aplicado (não há tabela de eventos).
Variantes (2 × 2 TF):
  - P (plano 2.5): stop ≥ 0,40% do preço de entrada senão não sai; alvo = fechamento de barra mais baixo entre B+1 e a
    barra anterior à do reteste, exigido ≥ 2R senão não sai; no 1R realiza 50% (limitada, maker) e o stop vai ao preço
    de entrada; resto no alvo (limitada, maker), na entrada ou no prazo.
  - T (Tradeiros, fluxo.md 5.1): sem piso de stop; alvo único = 1R (limitada, maker), sai inteiro.
  Prazo: 2 h desde a entrada; sem resolução, sai a mercado no fechamento do minuto. Funding linear Bybit cobrado nos
  minutos 00/08/16 UTC com posição aberta. Pessimista: stop e favor no mesmo minuto = stop; no minuto do 1R, se ele
  também tocou a entrada, o resto sai na entrada; limitadas só com o preço atravessando.
Controles (mesma mecânica de reteste, confirmação, stop, alvo, sessão e custo):
  (a) nível sorteado da MESMA barra B (só barras com evento real): 20 sorteios por evento entre os níveis do terço
      superior de B que NÃO são nódulo e cumprem o absorvido; abandono e reteste refeitos para o nível sorteado.
  (b) nódulo igual NÃO preso: cumpre (1) mas falha (2) ou (3); reteste/entrada/stop/alvo iguais.
  (c) direção sorteada: mesma entrada (minuto e preço), moeda decide o lado, stop à mesma distância, alvo ao mesmo
      múltiplo de R; 20 sorteios.
Janelas: J1 10–19/08, J2 20–29/08, J3 30/08–08/09/2026 (pela data da barra B).
APROVAÇÃO (por TF × variante):
  - ≥ 40 trades por lado nos 30 dias (senão inconclusivo, nunca aprovado);
  - líquido médio > 0 em J1, J2 e J3 **e** nas duas direções (30 dias);
  - taxa de 1R antes do stop ≥ controle (a) + 10 pontos em J1, J2 e J3;
  - média ≥ controle (a) + 2 EP e ≥ controle (c) + 2 EP em J1 e J2 (EP = desvio/√n da variante).
Só se alguma combinação passar: baixar 60–90 dias de regimes diferentes desde 2020 (core/bybit_trades_fetcher.py),
reduzir na hora e repetir. Se reprovar, a coleta não é gasta (plano, seção 4, passo 2).

Saídas: data/estudo_presos_footprint.csv (trades e controles) e data/estudo_presos_footprint_resumo.md.
Uso: ./.venv/Scripts/python.exe scripts/estudo_presos_footprint.py [--cache DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "dados" / "trades_bybit"
FUNDING = RAIZ / "data" / "historico" / "funding_bybit.json"
SAIDA_CSV = RAIZ / "data" / "estudo_presos_footprint.csv"
SAIDA_MD = RAIZ / "data" / "estudo_presos_footprint_resumo.md"

NIVEL = 20.0
TFS = {"5m": (5, 0.003), "30m": (30, 0.005)}
MULT_MED = 3.0
P90_BARRAS = 48
PISO_USD = 500_000.0
ZONA = 0.0005
FOLGA_STOP = 0.001
JANELA_RETESTE_MIN = 24 * 60
CONFIRMA_MIN = 30
PRAZO_MIN = 120
PISO_STOP = 0.004
RR_MIN = 2.0
MAKER = 0.0002
TAKER = 0.00055 + 0.0002
N_SORTEIOS = 20
SEMENTE = 20261020
MIN_LADO = 40
JANELAS = [("J1", "2026-08-10", "2026-08-19"), ("J2", "2026-08-20", "2026-08-29"), ("J3", "2026-08-30", "2026-09-08")]
MS_MIN = 60_000


# ---------------------------------------------------------------------------------------------------- redução
def reduzir_dia(caminho: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_csv(caminho, usecols=["timestamp", "side", "size", "price"])
    d["minuto"] = (d["timestamp"] * 1000).astype(np.int64) // MS_MIN
    d["usd"] = d["size"] * d["price"]
    d["nivel"] = (np.floor(d["price"] / NIVEL) * NIVEL).astype(np.int64)
    compra = d["side"].str.lower() == "buy"
    d["vb"] = np.where(compra, d["usd"], 0.0)
    d["vs"] = np.where(compra, 0.0, d["usd"])
    niv = d.groupby(["minuto", "nivel"], sort=True)[["vb", "vs"]].sum().reset_index()
    g = d.groupby("minuto", sort=True)
    mins = pd.DataFrame({"open": g["price"].first(), "high": g["price"].max(), "low": g["price"].min(),
                         "close": g["price"].last(), "delta": g["vb"].sum() - g["vs"].sum()}).reset_index()
    return mins, niv


def carregar(cache: Path | None):
    arqs = sorted(PASTA.glob("BTCUSDT*.csv.gz"))
    ms, ns = [], []
    for a in arqs:
        cm = cache / f"{a.stem}.min.pkl" if cache else None
        cn = cache / f"{a.stem}.niv.pkl" if cache else None
        if cm and cm.exists() and cn.exists():
            mi, ni = pd.read_pickle(cm), pd.read_pickle(cn)
        else:
            mi, ni = reduzir_dia(a)
            if cache:
                cache.mkdir(parents=True, exist_ok=True)
                mi.to_pickle(cm)
                ni.to_pickle(cn)
        ms.append(mi)
        ns.append(ni)
        print(f"  {a.name}: {len(mi)} min, {len(ni)} (min,nível)")
    mins = pd.concat(ms, ignore_index=True).drop_duplicates("minuto").sort_values("minuto")
    niv = pd.concat(ns, ignore_index=True).groupby(["minuto", "nivel"])[["vb", "vs"]].sum().reset_index()
    # minutos contíguos
    todos = np.arange(mins.minuto.min(), mins.minuto.max() + 1)
    mins = mins.set_index("minuto").reindex(todos)
    mins["close"] = mins["close"].ffill()
    for c in ("open", "high", "low"):
        mins[c] = mins[c].fillna(mins["close"])
    mins["delta"] = mins["delta"].fillna(0.0)
    mins.index.name = "minuto"
    return mins.reset_index(), niv


# ---------------------------------------------------------------------------------------------------- mercado de minutos
class Minutos:
    def __init__(self, mins: pd.DataFrame):
        self.m = mins["minuto"].to_numpy(np.int64)
        self.m0 = int(self.m[0])
        self.op = mins["open"].to_numpy(float)
        self.hi = mins["high"].to_numpy(float)
        self.lo = mins["low"].to_numpy(float)
        self.cl = mins["close"].to_numpy(float)
        self.dl = mins["delta"].to_numpy(float)
        d = json.load(open(FUNDING))["linear"]
        self.funding = {int(k) // MS_MIN: float(v) for k, v in d.items()}

    def i(self, minuto: int) -> int:
        return int(minuto - self.m0)


def simular(mk: Minutos, d: int, k_e: int, entrada: float, stop: float, alvo: float, parcial: bool) -> dict | None:
    """Entrada a mercado no fechamento do minuto k_e. d=+1 compra, -1 venda. Devolve resultado em R líquido."""
    hi, lo, cl = mk.hi, mk.lo, mk.cl
    n = len(hi)
    r_abs = abs(stop - entrada)
    n1 = entrada + d * r_abs
    aberto = 1.0
    saidas = []
    fund = 0.0
    tomou = False
    stop_cur = stop
    saida = None
    k = k_e + 1
    while k < n:
        if (mk.m[k] % (8 * 60)) == 0:
            fund -= d * mk.funding.get(int(mk.m[k]), 0.0) * aberto
        if (d == 1 and lo[k] <= stop_cur) or (d == -1 and hi[k] >= stop_cur):
            saidas.append((aberto, stop_cur, "mkt"))
            saida = "entrada" if tomou else "stop"
            break
        atravessa = (lambda p: hi[k] > p) if d == 1 else (lambda p: lo[k] < p)
        if parcial:
            if not tomou and atravessa(n1):
                saidas.append((0.5, n1, "lim"))
                aberto = 0.5
                tomou = True
                stop_cur = entrada
                if (d == 1 and lo[k] <= entrada) or (d == -1 and hi[k] >= entrada):
                    saidas.append((aberto, entrada, "mkt"))
                    saida = "entrada"
                    break
            if tomou and atravessa(alvo):
                saidas.append((aberto, alvo, "lim"))
                saida = "alvo"
                break
        else:
            if atravessa(n1):
                saidas.append((1.0, n1, "lim"))
                tomou = True
                saida = "alvo"
                break
        if k - k_e >= PRAZO_MIN:
            saidas.append((aberto, float(cl[k]), "mkt"))
            saida = "prazo"
            break
        k += 1
    else:
        return None
    pnl = -TAKER + fund
    for w, p, tp in saidas:
        pnl += w * (d * (p / entrada - 1) - (MAKER if tp == "lim" else TAKER))
    r_pct = r_abs / entrada
    return {"res_r": pnl / r_pct, "tomou_1r": tomou, "saida": saida, "r_pct": r_pct, "minutos": k - k_e}


# ---------------------------------------------------------------------------------------------------- barras
def barras(mins: pd.DataFrame, niv: pd.DataFrame, tf: int):
    b = mins.minuto.to_numpy(np.int64) // tf
    g = pd.DataFrame({"bar": b, "open": mins.open, "high": mins.high, "low": mins.low, "close": mins.close})
    gb = g.groupby("bar")
    bars = pd.DataFrame({"open": gb.open.first(), "high": gb.high.max(), "low": gb.low.min(),
                         "close": gb.close.last(), "n": gb.size()})
    bars = bars[bars.n == tf].copy()
    nv = niv.assign(bar=niv.minuto // tf).groupby(["bar", "nivel"])[["vb", "vs"]].sum().reset_index()
    return bars, nv


def detectar(bars: pd.DataFrame, nv: pd.DataFrame, tf: int, dist: float, rng) -> list[dict]:
    """Candidatos por barra: nódulos (presos e não presos) e os níveis do controle (a)."""
    bar_ids = bars.index.to_numpy(np.int64)
    pos = {int(b): i for i, b in enumerate(bar_ids)}
    hi, lo, cl = bars.high.to_numpy(float), bars.low.to_numpy(float), bars.close.to_numpy(float)
    grupos = {int(k): v for k, v in nv.groupby("bar")}
    hist_b, hist_s = [], []      # arrays de vol por nível das barras anteriores
    eventos = []
    for i, b in enumerate(bar_ids):
        gnv = grupos.get(int(b))
        if gnv is None:
            hist_b.append(np.array([]))
            hist_s.append(np.array([]))
            continue
        L = gnv.nivel.to_numpy(float) + NIVEL / 2
        vb, vs = gnv.vb.to_numpy(float), gnv.vs.to_numpy(float)
        if len(hist_b) >= P90_BARRAS and i + 2 < len(bar_ids) and bar_ids[i + 2] == b + 2:
            pb = np.percentile(np.concatenate(hist_b[-P90_BARRAS:]), 90)
            ps = np.percentile(np.concatenate(hist_s[-P90_BARRAS:]), 90)
            rg = hi[i] - lo[i]
            for lado, vol, delta_ok, terco, p90 in (
                    ("compra_presa", vb, (vb - vs) > 0, L >= lo[i] + 2 / 3 * rg, pb),
                    ("venda_presa", vs, (vs - vb) > 0, L <= lo[i] + 1 / 3 * rg, ps)):
                med = np.median(vol)
                nod = (vol >= MULT_MED * med) & (vol >= p90) & (vol >= PISO_USD) & delta_ok & terco & (rg > 0)
                if not nod.any():
                    continue
                j = int(np.flatnonzero(nod)[np.argmax(vol[nod])])
                Lj = float(L[j])
                d_trade = -1 if lado == "compra_presa" else 1      # vende contra comprador preso
                abs_ok, aband_ok = absorvido_abandonado(hi, lo, cl, i, Lj, d_trade, dist)
                base = {"bar": int(b), "i": i, "lado": lado, "d": d_trade, "L": Lj, "vol": float(vol[j]),
                        "bar_hi": float(hi[i]), "bar_lo": float(lo[i])}
                if abs_ok and aband_ok:
                    eventos.append({**base, "grupo": "D"})
                    # controle (a): níveis do mesmo terço, sem nódulo, que cumprem o absorvido
                    cand = np.flatnonzero(terco & ~nod & ((cl[i] <= L * (1 - ZONA)) if d_trade == -1 else (cl[i] >= L * (1 + ZONA))))
                    if cand.size:
                        for s, jj in enumerate(rng.choice(cand, size=N_SORTEIOS, replace=True)):
                            La = float(L[jj])
                            ab2, an2 = absorvido_abandonado(hi, lo, cl, i, La, d_trade, dist)
                            if ab2 and an2:
                                eventos.append({**base, "L": La, "vol": float(vol[jj]), "grupo": "a", "sorteio": s})
                else:
                    eventos.append({**base, "grupo": "b"})
        hist_b.append(vb)
        hist_s.append(vs)
    return eventos


def absorvido_abandonado(hi, lo, cl, i, L, d, dist):
    if d == -1:    # compradores presos: fecha abaixo de L, as 2 seguintes fecham >= dist abaixo e não passam a máxima de B
        ab = cl[i] <= L * (1 - ZONA)
        an = all(cl[i + j] <= L * (1 - dist) and hi[i + j] <= hi[i] for j in (1, 2))
    else:
        ab = cl[i] >= L * (1 + ZONA)
        an = all(cl[i + j] >= L * (1 + dist) and lo[i + j] >= lo[i] for j in (1, 2))
    return bool(ab), bool(an)


def operar(mk: Minutos, ev: dict, bars: pd.DataFrame, tf: int) -> dict | None:
    """Reteste, confirmação, entrada e as duas variantes. None se não houver entrada."""
    d, L, b = ev["d"], ev["L"], ev["bar"]
    zlo, zhi = L * (1 - ZONA), L * (1 + ZONA)
    fim_b2 = (b + 3) * tf                  # primeiro minuto depois de B+2
    ini_janela = (b + 4) * tf              # início de B+4
    lim = (b + 1) * tf + JANELA_RETESTE_MIN
    k = mk.i(fim_b2)
    kmax = min(mk.i(lim), len(mk.hi) - 1)
    hi, lo, cl, op, dl = mk.hi, mk.lo, mk.cl, mk.op, mk.dl
    # precisa estar do lado de fora da zona antes do toque
    fora = False
    k_toque = None
    while k <= kmax:
        if d == -1:
            if not fora and cl[k] < zlo and hi[k] < zlo:
                fora = True
            elif fora and hi[k] >= zlo:
                k_toque = k
                break
        else:
            if not fora and cl[k] > zhi and lo[k] > zhi:
                fora = True
            elif fora and lo[k] <= zhi:
                k_toque = k
                break
        k += 1
    if k_toque is None or mk.m[k_toque] < ini_janela:
        return None
    stop = ev["bar_hi"] * (1 + FOLGA_STOP) if d == -1 else ev["bar_lo"] * (1 - FOLGA_STOP)
    k_e = None
    for k in range(k_toque, min(k_toque + CONFIRMA_MIN, len(hi))):
        if (d == -1 and hi[k] >= stop) or (d == 1 and lo[k] <= stop):
            return None
        na_zona = lo[k] <= zhi and hi[k] >= zlo
        if na_zona and ((d == -1 and cl[k] < op[k] and dl[k] <= 0) or (d == 1 and cl[k] > op[k] and dl[k] >= 0)):
            k_e = k
            break
    if k_e is None:
        return None
    t = pd.Timestamp(int(mk.m[k_e]) * MS_MIN, unit="ms", tz="UTC")
    if t.weekday() >= 5 or not (8 <= t.hour < 20):
        return None
    entrada = float(cl[k_e])
    if (d == -1 and stop <= entrada) or (d == 1 and stop >= entrada):
        return None
    r_pct = abs(stop - entrada) / entrada
    # alvo P: fechamento de barra mais extremo entre B+1 e a barra anterior à do reteste
    bar_ret = int(mk.m[k_toque]) // tf
    seg = bars.loc[(bars.index >= b + 1) & (bars.index < bar_ret), "close"]
    alvo_p = float(seg.min()) if d == -1 else float(seg.max())
    rr_p = (entrada - alvo_p) / (stop - entrada) if d == -1 else (alvo_p - entrada) / (entrada - stop)
    out = {"k_e": k_e, "entrada": entrada, "stop": stop, "r_pct": r_pct, "rr_p": rr_p,
           "data_b": pd.Timestamp(b * tf * MS_MIN, unit="ms", tz="UTC").strftime("%Y-%m-%d"),
           "hora_e": t.strftime("%Y-%m-%d %H:%M")}
    out["T"] = simular(mk, d, k_e, entrada, stop, entrada + d * abs(stop - entrada), parcial=False)
    if r_pct >= PISO_STOP and rr_p >= RR_MIN:
        out["P"] = simular(mk, d, k_e, entrada, stop, alvo_p, parcial=True)
    else:
        out["P"] = None
        out["motivo_p"] = "stop < 0,4%" if r_pct < PISO_STOP else "alvo < 2R"
    # controle (c): as duas direções com a mesma geometria
    for var, rr, parcial in (("T", 1.0, False), ("P", rr_p, True)):
        if out[var] is None:
            continue
        for nome, dd in (("mesma", d), ("oposta", -d)):
            st = entrada * (1 - dd * r_pct)
            al = entrada * (1 + dd * rr * r_pct)
            s = simular(mk, dd, k_e, entrada, st, al, parcial=parcial)
            out[f"c_{var}_{nome}"] = s["res_r"] if s else np.nan
    return out


# ---------------------------------------------------------------------------------------------------- estatística
def est(x) -> dict:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n == 0:
        return {"n": 0, "media": np.nan, "se": np.nan}
    return {"n": n, "media": float(x.mean()), "se": float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan}


def fr(x, c=3):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.{c}f}"


def janela_de(data: str) -> str:
    for nome, a, z in JANELAS:
        if a <= data <= z:
            return nome
    return ""


# ---------------------------------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=None)
    args = ap.parse_args()
    t0 = time.time()
    mins, niv = carregar(args.cache)
    mk = Minutos(mins)
    print(f"minutos: {len(mins):,}; (min,nível): {len(niv):,} ({time.time() - t0:.0f}s)")
    rng = np.random.default_rng(SEMENTE)
    linhas = []
    for tf_nome, (tf, dist) in TFS.items():
        bars, nv = barras(mins, niv, tf)
        evs = detectar(bars, nv, tf, dist, rng)
        print(f"{tf_nome}: {len(bars)} barras, candidatos D={sum(e['grupo'] == 'D' for e in evs)} "
              f"a={sum(e['grupo'] == 'a' for e in evs)} b={sum(e['grupo'] == 'b' for e in evs)} ({time.time() - t0:.0f}s)")
        for ev in evs:
            op = operar(mk, ev, bars, tf)
            reg = {"tf": tf_nome, "grupo": ev["grupo"], "sorteio": ev.get("sorteio", -1), "lado": ev["lado"],
                   "bar": ev["bar"], "L": ev["L"], "vol_usd": ev["vol"]}
            if op is None:
                reg["entrou"] = False
                linhas.append(reg)
                continue
            reg.update({"entrou": True, "data_b": op["data_b"], "janela": janela_de(op["data_b"]),
                        "hora_entrada": op["hora_e"], "entrada": op["entrada"], "stop": op["stop"],
                        "r_pct": op["r_pct"], "rr_p": op["rr_p"], "motivo_p": op.get("motivo_p", "")})
            for var in ("T", "P"):
                s = op[var]
                reg[f"{var}_res"] = s["res_r"] if s else np.nan
                reg[f"{var}_1r"] = s["tomou_1r"] if s else np.nan
                reg[f"{var}_saida"] = s["saida"] if s else ""
                reg[f"c_{var}_mesma"] = op.get(f"c_{var}_mesma", np.nan)
                reg[f"c_{var}_oposta"] = op.get(f"c_{var}_oposta", np.nan)
            linhas.append(reg)
    df = pd.DataFrame(linhas)
    rng2 = np.random.default_rng(SEMENTE + 1)
    moedas = rng2.integers(0, 2, size=(len(df), N_SORTEIOS))
    for var in ("T", "P"):
        if f"c_{var}_mesma" in df:
            for s in range(N_SORTEIOS):
                df[f"cd_{var}_{s}"] = np.where(moedas[:, s] == 0, df[f"c_{var}_mesma"], df[f"c_{var}_oposta"])
    df.to_csv(SAIDA_CSV, index=False)
    print(f"linhas: {len(df)} -> {SAIDA_CSV} ({time.time() - t0:.0f}s)")
    escrever(df)
    print(f"resumo -> {SAIDA_MD} ({time.time() - t0:.0f}s)")


def escrever(df: pd.DataFrame):
    ent = df[df.entrou == True]
    out = ["# Estudo Fluxo D — nódulo abandonado (presos pelo footprint) — resultado\n",
           f"Gerado por `scripts/estudo_presos_footprint.py` em {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC. "
           "Regra e critério no docstring (escritos antes de rodar; nenhum parâmetro iterado). Negócios da Bybit "
           "BTCUSDT linear, 10/08–08/09/2026.\n"]
    ver = []
    tab = ["| TF | variante | grupo | janela | n | 1R antes do stop | média R ± EP | controle (c) direção |",
           "|---|---|---|---|---|---|---|---|"]
    lados = ["| TF | variante | grupo | lado | n | 1R antes do stop | média R |", "|---|---|---|---|---|---|---|"]
    funil = ["| TF | candidatos D (nódulo+absorvido+abandonado) | com entrada | entrada P (stop ≥ 0,4% e alvo ≥ 2R) | controle (a) entradas | controle (b) candidatos | (b) entradas |",
             "|---|---|---|---|---|---|---|"]
    for tf in TFS:
        sdf = df[df.tf == tf]
        funil.append(f"| {tf} | {(sdf.grupo == 'D').sum()} | {((sdf.grupo == 'D') & (sdf.entrou == True)).sum()} | "
                     f"{((sdf.grupo == 'D') & (sdf.entrou == True) & sdf.get('P_res', pd.Series(dtype=float)).notna()).sum()} | "
                     f"{((sdf.grupo == 'a') & (sdf.entrou == True)).sum()} | {(sdf.grupo == 'b').sum()} | "
                     f"{((sdf.grupo == 'b') & (sdf.entrou == True)).sum()} |")
        for var in ("P", "T"):
            col = f"{var}_res"
            ok = True
            mot = []
            dd = ent[(ent.tf == tf) & (ent.grupo == "D") & ent[col].notna()]
            aa = ent[(ent.tf == tf) & (ent.grupo == "a") & ent[col].notna()]
            bb = ent[(ent.tf == tf) & (ent.grupo == "b") & ent[col].notna()]
            for lado in ("compra_presa", "venda_presa"):
                s = dd[dd.lado == lado]
                e = est(s[col])
                tx = s[f"{var}_1r"].astype(float).mean() if len(s) else np.nan
                lados.append(f"| {tf} | {var} | D | {lado} | {e['n']} | {fr(tx * 100 if len(s) else np.nan, 1)}% | {fr(e['media'])} |")
                for g, gg in (("a", aa), ("b", bb)):
                    s2 = gg[gg.lado == lado]
                    e2 = est(s2[col])
                    tx2 = s2[f"{var}_1r"].astype(float).mean() if len(s2) else np.nan
                    lados.append(f"| {tf} | {var} | {g} | {lado} | {e2['n']} | {fr(tx2 * 100 if len(s2) else np.nan, 1)}% | {fr(e2['media'])} |")
                if e["n"] < MIN_LADO:
                    ok = False
                    mot.append(f"{lado}: n={e['n']} < 40 (inconclusivo)")
                elif not e["media"] > 0:
                    ok = False
                    mot.append(f"{lado}: líquido {e['media']:+.3f} ≤ 0")
            for jn, _, _ in JANELAS + [("30 dias", "", "")]:
                if jn == "30 dias":
                    sd, sa, sb = dd, aa, bb
                else:
                    sd, sa, sb = dd[dd.janela == jn], aa[aa.janela == jn], bb[bb.janela == jn]
                e, ea, eb = est(sd[col]), est(sa[col]), est(sb[col])
                tx = sd[f"{var}_1r"].astype(float).mean() if len(sd) else np.nan
                txa = sa[f"{var}_1r"].astype(float).mean() if len(sa) else np.nan
                txb = sb[f"{var}_1r"].astype(float).mean() if len(sb) else np.nan
                cds = [pd.to_numeric(sd[f"cd_{var}_{k}"], errors="coerce").mean() for k in range(N_SORTEIOS)] if len(sd) else [np.nan]
                cd = float(np.nanmean(cds)) if len(sd) else np.nan
                se = e["se"] if not np.isnan(e["se"]) else 0.0
                tab.append(f"| {tf} | {var} | D | {jn} | {e['n']} | {fr(tx * 100 if len(sd) else np.nan, 1)}% | "
                           f"{fr(e['media'])} ± {se:.3f} | {fr(cd)} |")
                tab.append(f"| {tf} | {var} | (a) nível sorteado | {jn} | {ea['n']} | {fr(txa * 100 if len(sa) else np.nan, 1)}% | {fr(ea['media'])} | |")
                tab.append(f"| {tf} | {var} | (b) não preso | {jn} | {eb['n']} | {fr(txb * 100 if len(sb) else np.nan, 1)}% | {fr(eb['media'])} | |")
                if jn == "30 dias":
                    continue
                if e["n"] == 0 or not e["media"] > 0:
                    ok = False
                    mot.append(f"{jn}: líquido {fr(e['media'])} (n={e['n']})")
                if not (len(sd) and len(sa) and tx >= txa + 0.10):
                    ok = False
                    mot.append(f"{jn}: 1R {fr(tx * 100 if len(sd) else np.nan, 1)}% < (a) {fr(txa * 100 if len(sa) else np.nan, 1)}% + 10")
                if jn in ("J1", "J2"):
                    if not (e["n"] > 1 and ea["n"] and e["media"] >= ea["media"] + 2 * se):
                        ok = False
                        mot.append(f"{jn}: não está 2 EP acima de (a)")
                    if not (e["n"] > 1 and not np.isnan(cd) and e["media"] >= cd + 2 * se):
                        ok = False
                        mot.append(f"{jn}: não está 2 EP acima de (c)")
            ver.append((tf, var, ok, mot))
    out.append("## Veredito pelo critério escrito antes\n")
    for tf, var, ok, mot in ver:
        out.append(f"- **{tf} × {var}**: {'APROVADA' if ok else 'reprovada'}" + ("" if ok else " — " + "; ".join(mot[:5])))
    out.append("")
    out.append("## Funil\n")
    out += funil + [""]
    out.append("## Por janela (R líquido por trade; controle (c) = média de 20 sorteios de direção na mesma entrada)\n")
    out.append("P = plano 2.5 (stop ≥ 0,4%, alvo ≥ 2R, 50% no 1R, stop na entrada). T = Tradeiros (alvo 1R, sai inteiro). "
               "(a) = nível sorteado da mesma barra, 20 sorteios por evento (n conta todos os sorteios). (b) = nódulo igual "
               "não preso.\n")
    out += tab + [""]
    out.append("## Por lado (30 dias)\n")
    out += lados + [""]
    out.append("## Como saíram (grupo D)\n")
    out.append("| TF | variante | n | alvo | entrada (zero a zero) | stop | prazo | stop médio % | RR do alvo P médio |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for tf in TFS:
        for var in ("P", "T"):
            s = ent[(ent.tf == tf) & (ent.grupo == "D") & ent[f"{var}_res"].notna()]
            if not len(s):
                continue
            vc = s[f"{var}_saida"].value_counts()
            out.append(f"| {tf} | {var} | {len(s)} | {vc.get('alvo', 0)} | {vc.get('entrada', 0)} | {vc.get('stop', 0)} | "
                       f"{vc.get('prazo', 0)} | {s.r_pct.mean() * 100:.2f}% | {s.rr_p.mean():.2f} |")
    out.append("")
    SAIDA_MD.write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
