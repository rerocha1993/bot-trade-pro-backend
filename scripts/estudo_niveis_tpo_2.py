# scripts/estudo_niveis_tpo_2.py
"""
SEGUNDO ESTUDO DOS NÍVEIS DE TPO — as hipóteses que o primeiro (scripts/estudo_niveis_tpo.py, 5 min) não cobriu.
BTCUSDT 15 min (Binance), 2020-01 a 2026-09. Critério escrito ANTES de rodar; nenhum parâmetro foi iterado.

Base comum (vale para H1..H5):
  - Composto = merge dos 10 dias anteriores (core/range_tradeiros.contexto com range_adaptativo=False, n_dias=10):
    VAL, VAH e POC conhecidos à meia-noite UTC do dia D. H1 também mede o merge ADAPTATIVO (contexto_adaptativo).
  - Controle: 6 níveis sorteados por dia, uniformes em [mínima, máxima] dos 10 dias anteriores (semente fixa).
  - Toque: candle de 15 min de D com low <= nível <= high e o fechamento de algum dos 16 candles anteriores (4 h)
    a >= 0,5% do nível. Só o PRIMEIRO toque assim de cada nível por dia. "Chegada" = lado do fechamento mais
    distante nas 4 h (acima / abaixo).
  - Direção do trade: VAL -> compra (sempre); VAH -> venda (sempre); POC e controle -> reação (chegou de cima ->
    compra; de baixo -> venda). O controle também é medido como "compra em nível sorteado" e "venda em nível
    sorteado" sem olhar a chegada (régua para VAL/VAH).
  - Reação: R = 1% e 2% do nível. Corrida 1:1 = anda R a favor antes de R contra; 2:1 = 2R a favor antes de 1R
    contra. Limite 192 candles (2 dias); sem decisão = neutro (fora de p). Pessimista: favor e contra no mesmo
    candle -> contra; o próprio candle do toque já conta para o stop (favor só a partir do candle seguinte).
  - Custo de ida e volta 0,06% = 0,06 R (R=1%) e 0,03 R (R=2%). Bruto 1:1 = 2p-1; 2:1 = 3p-1. Líquido = bruto - custo.
  - ★ = p da linha >= 2 EP acima da linha de controle correspondente (mesmo período, R e corrida); ▼ = 2 EP abaixo.
  - Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09 (H5: treino começa em
    2020-07-20, quando começa o long/short da Bybit).
  - CRITÉRIO DE APROVAÇÃO: líquido > 0 nos 3 períodos com >= 30 toques decididos em cada período.

H1 Tempo maior: VAL compra, VAH venda, POC reação, nos dois compostos (fixo 10 dias e adaptativo); também só nos
   dias em que o range é "válido" (ctx.valido: equilíbrio).
H2 Desvio × dentro (composto fixo): toque no VAL dividido em (a) DESVIO CONFIRMADO = algum dos 16 candles
   anteriores fechou ABAIXO do VAL e o candle do toque fechou de volta >= VAL — como a confirmação só existe no
   fechamento, a ENTRADA é no fechamento desse candle (R medido a partir dele, favor e contra desde o candle seguinte);
   (b) DENTRO = nenhum fechamento abaixo do VAL nas 4 h e chegada de cima, entrada no nível; (c) FORA = algum dos 16
   candles anteriores fechou abaixo do VAL, sem exigir reentrada, entrada no nível ((a) está contido em (c)).
   VAH espelhado. Controle com as MESMAS bandeiras e entradas em relação ao nível sorteado.
   Nota: a primeira rodada (20/10, 09:40) definia (a) com entrada no NÍVEL condicionada ao fechamento do mesmo
   candle — olhar o futuro. O artefato apareceu no controle (nível sorteado + "reentrou": líquido > 0 nos 3
   períodos, até +0,24 R). A regra foi corrigida ANTES de qualquer leitura das hipóteses e vale igual para controle e
   níveis; nada mais mudou.
H3 Toque virgem (composto fixo): nº de toques anteriores no nível desde o início de D-3 até o candle anterior ao
   toque (um toque conta quando o preço encosta no nível depois de ter fechado a >= 0,5% dele): 0 (virgem), 1, 2+.
   Controle quebrado igual.
H4 Escada (composto fixo): 5 limitadas em nível ± 0,25% (degraus de 0,125%), armadas a partir do candle do toque,
   preenchidas quando o candle alcança o preço (compra: low <= preço). Stop = médio × (1 - R), alvo = médio ×
   (1 + mult·R), recalculados a cada preenchimento. Favor não conta no candle em que houve preenchimento. Resultado
   em R do médio por unidade preenchida (e também por unidade cheia = × fração preenchida); custo 0,06% por unidade.
   Comparado com a entrada única no nível (H1) e com a escada em nível sorteado.
H5 Presos (composto fixo, desde 2020-07-20): long/short de contas da Bybit (1 h, hora fechada) contra a mediana dos
   30 dias anteriores: VAL com vendidos presos (lsr < mediana) × sem; VAH com comprados presos (lsr > mediana) × sem.
   Também OI subindo nas 6 h anteriores × caindo, e funding "do lado" (VAL: funding < mediana de 30 d; VAH: > mediana).
   Controle: compra/venda em nível sorteado com as mesmas bandeiras.

Saídas: data/estudo_niveis_tpo_2.csv (um toque por linha) e data/estudo_niveis_tpo_2_resumo.md.
"""
from __future__ import annotations

import json
import sys
import time
from bisect import bisect_right
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core.range_tradeiros import ParametrosRange, contexto, contexto_adaptativo  # noqa: E402
from core.tpo_sessao import DIA_MS, dias  # noqa: E402

CSV = RAIZ / "data" / "historico" / "BTCUSDT_binance_15m.csv"
LSR = RAIZ / "data" / "historico" / "lsr_bybit_1h.json"
OI = RAIZ / "data" / "historico" / "oi_bybit_1h.json"
FUNDING = RAIZ / "data" / "historico" / "funding_bybit.json"
SAIDA_CSV = RAIZ / "data" / "estudo_niveis_tpo_2.csv"
SAIDA_MD = RAIZ / "data" / "estudo_niveis_tpo_2_resumo.md"

INICIO_DADOS_MS = int(pd.Timestamp("2019-11-01", tz="UTC").timestamp() * 1000)
INICIO_ESTUDO_MS = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
INICIO_LSR = "2020-07-20"
PERIODOS = [
    ("treino", "2020-01-01", "2023-12-31"),
    ("validacao", "2024-01-01", "2025-06-30"),
    ("holdout", "2025-07-01", "2026-09-30"),
]
HORA_MS = 3_600_000
LONGE_PCT = 0.005
JANELA_LONGE = 16          # candles de 15 min = 4 h (= 8 blocos de 30 min, janela do "desvio" da H2)
LIMITE = 192               # candles de 15 min = 2 dias
RS = {"1": 0.01, "2": 0.02}
FMTS = (("11", 1.0), ("21", 2.0))
CUSTO = 0.0006
SEMENTE = 20261020
N_CONTROLE = 6
MIN_DEC = 30
DIAS_TOQUES_PREVIOS = 3
ESCADA_OFFS = np.linspace(0.0025, -0.0025, 5)   # compra: do degrau mais alto para o mais baixo
JANELA_MEDIANA_MS = 30 * 24 * HORA_MS
P_FIXO = ParametrosRange(range_adaptativo=False, n_dias=10)
P_ADAPT = ParametrosRange()
COMPOSTOS = ("fixo10", "adapt")


# ---------------------------------------------------------------------------------------------------- dados
def carregar() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df = df[df["timestamp"] >= INICIO_DADOS_MS]
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


class Serie:
    """Série temporal {ts_ms: valor} com 'último valor conhecido em t' e mediana dos 30 dias anteriores."""

    def __init__(self, caminho: Path, chave: str | None = None, min_pontos: int = 24 * 7):
        d = json.load(open(caminho))
        if chave:
            d = d[chave]
        pares = sorted((int(k), float(v)) for k, v in d.items())
        self.ts = [p[0] for p in pares]
        self.v = np.array([p[1] for p in pares], float)
        self.min_pontos = min_pontos
        self._cache: dict[int, float] = {}

    def em(self, t: int) -> float:
        i = bisect_right(self.ts, t) - 1
        return float(self.v[i]) if i >= 0 else np.nan

    def mediana(self, t: int) -> float:
        i = bisect_right(self.ts, t)
        if i in self._cache:
            return self._cache[i]
        j = bisect_right(self.ts, t - JANELA_MEDIANA_MS)
        m = float(np.median(self.v[j:i])) if i - j >= self.min_pontos else np.nan
        self._cache[i] = m
        return m


# ---------------------------------------------------------------------------------------------------- reações
def reacao(hi: np.ndarray, lo: np.ndarray, k: int, nivel: float, direcao: int, r: float, mult: float,
           desde_seguinte: bool = False):
    """+1 alvo (mult*R) antes do stop (R), -1 contra, 0 sem decisão. direcao +1 = compra, -1 = venda.
    Pessimista: o candle do toque já conta para o stop; favor só a partir do seguinte; empate no candle -> contra.
    desde_seguinte=True: entrada no FECHAMENTO do candle k (preço = `nivel`), stop e alvo só a partir de k+1."""
    fim = k + LIMITE + 1
    k0 = k + 1 if desde_seguinte else k
    if direcao == 1:
        favor, contra = nivel * (1 + mult * r), nivel * (1 - r)
        f = np.flatnonzero(hi[k + 1:fim] >= favor)
        c = np.flatnonzero(lo[k0:fim] <= contra)
    else:
        favor, contra = nivel * (1 - mult * r), nivel * (1 + r)
        f = np.flatnonzero(lo[k + 1:fim] <= favor)
        c = np.flatnonzero(hi[k0:fim] >= contra)
    fi = int(f[0]) + 1 if f.size else None
    ci = int(c[0]) + (k0 - k) if c.size else None
    if fi is None and ci is None:
        return 0, None
    if ci is None:
        return 1, fi
    if fi is None:
        return -1, ci
    return (1, fi) if fi < ci else (-1, ci)


def escada(hi: np.ndarray, lo: np.ndarray, k: int, nivel: float, direcao: int, r: float, mult: float):
    """
    5 limitadas em nível ± 0,25%, armadas no candle do toque. Devolve (resultado em R do médio por unidade
    preenchida: +mult, -1 ou 0 sem decisão; fração preenchida; candles até a decisão).
    Stop = médio*(1-R) e alvo = médio*(1+mult*R) recalculados a cada preenchimento; no candle com preenchimento
    o alvo não conta (não se sabe se a máxima veio antes); stop e alvo no mesmo candle -> stop.
    """
    fim = min(k + LIMITE + 1, len(hi))
    h, l = hi[k:fim], lo[k:fim]
    if direcao == 1:
        precos = nivel * (1 + ESCADA_OFFS)
        quando = [(int(np.argmax(l <= p)) if (l <= p).any() else None) for p in precos]
    else:
        precos = nivel * (1 - ESCADA_OFFS)
        quando = [(int(np.argmax(h >= p)) if (h >= p).any() else None) for p in precos]
    tempos = sorted({t for t in quando if t is not None})
    if not tempos:
        return 0.0, 0.0, None
    n_fill = 0
    for s, t in enumerate(tempos):
        cheios = [p for p, q in zip(precos, quando) if q is not None and q <= t]
        n_fill = len(cheios)
        medio = float(np.mean(cheios))
        t_fim = tempos[s + 1] if s + 1 < len(tempos) else len(h)
        seg_h, seg_l = h[t:t_fim], l[t:t_fim]
        if direcao == 1:
            stop, alvo = medio * (1 - r), medio * (1 + mult * r)
            cs = np.flatnonzero(seg_l <= stop)
            fs = np.flatnonzero(seg_h[1:] >= alvo) + 1
        else:
            stop, alvo = medio * (1 + r), medio * (1 - mult * r)
            cs = np.flatnonzero(seg_h >= stop)
            fs = np.flatnonzero(seg_l[1:] <= alvo) + 1
        ci = int(cs[0]) if cs.size else None
        fi = int(fs[0]) if fs.size else None
        if ci is None and fi is None:
            continue
        if fi is None or (ci is not None and ci <= fi):
            return -1.0, n_fill / 5, t + ci
        return mult, n_fill / 5, t + fi
    return 0.0, n_fill / 5, None


def toques_anteriores(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray, a0: int, k: int, nivel: float) -> int:
    """Toques no nível em [a0, k): um toque conta quando o candle encosta no nível depois de o preço ter fechado a
    >= LONGE_PCT dele (desde o toque anterior). O estado inicial é 'longe'."""
    if k <= a0:
        return 0
    h, l, c = hi[a0:k], lo[a0:k], cl[a0:k]
    toca = (l <= nivel) & (h >= nivel)
    longe = np.abs(c - nivel) / nivel >= LONGE_PCT
    idx = np.arange(len(toca))
    ult_longe = np.maximum.accumulate(np.where(longe, idx, -1))
    ult_toque = np.maximum.accumulate(np.where(toca, idx, -1))
    ult_longe_antes = np.concatenate(([0], ult_longe[:-1]))      # estado inicial: longe
    ult_toque_antes = np.concatenate(([-1], ult_toque[:-1]))
    evento = toca & (ult_longe_antes >= ult_toque_antes)
    return int(evento.sum())


# ---------------------------------------------------------------------------------------------------- estudo
def rodar():
    t0 = time.time()
    df = carregar()
    ts = df["timestamp"].to_numpy(np.int64)
    hi = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    cl = df["close"].to_numpy(float)
    candles = df[["timestamp", "open", "high", "low", "close", "volume"]].to_numpy(float)
    print(f"candles 15m: {len(df):,} de {pd.Timestamp(ts[0], unit='ms')} a {pd.Timestamp(ts[-1], unit='ms')}")

    perfis = dias(candles)
    idx_de = {p.inicio // DIA_MS: i for i, p in enumerate(perfis)}
    print(f"perfis diários: {len(perfis)} ({time.time() - t0:.0f}s)")
    lsr, oi = Serie(LSR), Serie(OI)
    fund = Serie(FUNDING, "linear", min_pontos=60)
    rng = np.random.default_rng(SEMENTE)

    dnum = ts // DIA_MS
    linhas = []
    n_dias = 0
    for d in sorted(idx_de):
        if d * DIA_MS < INICIO_ESTUDO_MS:
            continue
        a = int(np.searchsorted(dnum, d))
        b = int(np.searchsorted(dnum, d + 1))
        if a < JANELA_LONGE or b + LIMITE + 1 > len(ts) or b - a < 60:
            continue
        i = idx_de[d]
        prev = perfis[max(0, i - P_ADAPT.max_dias):i]
        if len(prev) < P_FIXO.n_dias:
            continue
        ctx_f = contexto(prev, P_FIXO)
        ctx_a = contexto_adaptativo(prev, P_ADAPT)
        niveis: list[tuple[str, str, float, object]] = []
        for nome, ctx in (("fixo10", ctx_f), ("adapt", ctx_a)):
            if ctx is None or not (ctx.vah > ctx.val):
                continue
            niveis += [(nome, "VAL", ctx.val, ctx), (nome, "VAH", ctx.vah, ctx), (nome, "POC", ctx.poc, ctx)]
        p10 = prev[-10:]
        lo10, hi10 = min(p.minima for p in p10), max(p.maxima for p in p10)
        for v in rng.uniform(lo10, hi10, N_CONTROLE):
            niveis.append(("-", "controle", float(v), ctx_f))
        n_dias += 1
        n = b - a
        W = sliding_window_view(cl[a - JANELA_LONGE:b - 1], JANELA_LONGE)   # W[i] = 16 fechamentos antes de a+i
        assert W.shape[0] == n
        a0 = int(np.searchsorted(dnum, d - DIAS_TOQUES_PREVIOS))
        data = pd.Timestamp(d * DIA_MS, unit="ms", tz="UTC")
        for composto, tipo, L, ctx in niveis:
            toca = (lo[a:b] <= L) & (hi[a:b] >= L)
            dif = (W - L) / L
            longe = np.abs(dif).max(axis=1) >= LONGE_PCT
            ok = toca & longe
            if not ok.any():
                continue
            ii = int(np.argmax(ok))
            k = a + ii
            j = int(np.argmax(np.abs(dif[ii])))
            chegada = "acima" if dif[ii][j] > 0 else "abaixo"
            if tipo == "VAL":
                direcao = 1
            elif tipo == "VAH":
                direcao = -1
            else:
                direcao = 1 if chegada == "acima" else -1
            t_toque = int(ts[k])
            lsr_v, lsr_m = lsr.em(t_toque - HORA_MS), lsr.mediana(t_toque - HORA_MS)
            oi_ag, oi_6h = oi.em(t_toque - HORA_MS), oi.em(t_toque - 7 * HORA_MS)
            fu_v, fu_m = fund.em(t_toque), fund.mediana(t_toque)
            linha = {
                "data": data.strftime("%Y-%m-%d"), "composto": composto, "tipo": tipo, "nivel": round(L, 2),
                "ts_toque": t_toque, "hora_utc": int(((t_toque % DIA_MS) // 60000) // 60), "chegada": chegada,
                "direcao": direcao, "dist_4h_pct": round(abs(dif[ii][j]) * 100, 3),
                "fechou_abaixo_8b": bool((W[ii] < L).any()), "fechou_acima_8b": bool((W[ii] > L).any()),
                "fech_toque": float(cl[k]),
                "toques_previos": toques_anteriores(hi, lo, cl, a0, k, L),
                "ctx_valido": bool(ctx.valido) if ctx is not None else False,
                "ctx_dias": int(ctx.dias) if ctx is not None else 0,
                "ctx_largura_pct": round((ctx.vah - ctx.val) / ctx.poc * 100, 3) if ctx is not None else np.nan,
                "lsr": lsr_v, "lsr_med": lsr_m, "oi_6h": (oi_ag / oi_6h - 1) if oi_ag > 0 and oi_6h > 0 else np.nan,
                "funding": fu_v, "funding_med": fu_m,
            }
            for rk, r in RS.items():
                for fmt, mult in FMTS:
                    linha[f"up_r{rk}_{fmt}"] = reacao(hi, lo, k, L, 1, r, mult)[0]
                    linha[f"dn_r{rk}_{fmt}"] = reacao(hi, lo, k, L, -1, r, mult)[0]
                    # entrada no fechamento do candle do toque (H2a: desvio confirmado), favor e contra desde k+1
                    linha[f"fcu_r{rk}_{fmt}"] = reacao(hi, lo, k, float(cl[k]), 1, r, mult, desde_seguinte=True)[0]
                    linha[f"fcd_r{rk}_{fmt}"] = reacao(hi, lo, k, float(cl[k]), -1, r, mult, desde_seguinte=True)[0]
                    res, fr, nb = escada(hi, lo, k, L, direcao, r, mult)
                    linha[f"esc_r{rk}_{fmt}"] = res
                    linha[f"esc_r{rk}_{fmt}_fr"] = fr
                    linha[f"esc_r{rk}_{fmt}_candles"] = nb if nb is not None else -1
            linhas.append(linha)
        if n_dias % 365 == 0:
            print(f"  {data.date()} dias={n_dias} toques={len(linhas)} ({time.time() - t0:.0f}s)")

    out = pd.DataFrame(linhas)
    out["periodo"] = ""
    for nome, a, z in PERIODOS:
        m = (out["data"] >= a) & (out["data"] <= z)
        out.loc[m, "periodo"] = nome
    out = out[out["periodo"] != ""].reset_index(drop=True)
    # colunas derivadas: reação (pela chegada) e trade (pela direção fixada)
    for rk in RS:
        for fmt, _ in FMTS:
            up, dn = out[f"up_r{rk}_{fmt}"], out[f"dn_r{rk}_{fmt}"]
            out[f"bn_r{rk}_{fmt}"] = np.where(out["chegada"] == "acima", up, dn)
            out[f"tr_r{rk}_{fmt}"] = np.where(out["direcao"] == 1, up, dn)
    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(SAIDA_CSV, index=False)
    print(f"toques: {len(out):,} em {n_dias} dias -> {SAIDA_CSV} ({time.time() - t0:.0f}s)")
    escrever_resumo(out)
    print(f"resumo -> {SAIDA_MD} ({time.time() - t0:.0f}s)")


# ---------------------------------------------------------------------------------------------------- estatística
def estat_p(v: np.ndarray, custo_r: float, mult: float) -> dict:
    n = len(v)
    dec = int((v != 0).sum())
    w = int((v == 1).sum())
    if dec == 0:
        return {"n": n, "dec": dec, "p": np.nan, "se": np.nan, "bruto": np.nan, "liq": np.nan}
    p = w / dec
    se = float(np.sqrt(p * (1 - p) / dec))
    bruto = (mult + 1) * p - 1
    return {"n": n, "dec": dec, "p": p, "se": se, "bruto": bruto, "liq": bruto - custo_r}


def estat_media(x: np.ndarray) -> dict:
    n = len(x)
    if n == 0:
        return {"n": 0, "media": np.nan, "se": np.nan}
    return {"n": n, "media": float(np.mean(x)), "se": float(np.std(x, ddof=1) / np.sqrt(n)) if n > 1 else np.nan}


def fmt_p(p, se):
    return "-" if (p is None or np.isnan(p)) else f"{p * 100:.1f}±{se * 100:.1f}"


def fmt_r(x):
    return "-" if (x is None or np.isnan(x)) else f"{x:+.3f}"


def sinal(e: dict, c: dict | None) -> str:
    if c is None or np.isnan(e["p"]) or np.isnan(c["p"]):
        return ""
    sep = float(np.sqrt(e["se"] ** 2 + c["se"] ** 2))
    if sep > 0 and e["p"] - c["p"] >= 2 * sep:
        return "★"
    if sep > 0 and c["p"] - e["p"] >= 2 * sep:
        return "▼"
    return ""


def sinal_media(e: dict, c: dict | None) -> str:
    if c is None or np.isnan(e["media"]) or np.isnan(c["media"]) or np.isnan(e["se"]) or np.isnan(c["se"]):
        return ""
    sep = float(np.sqrt(e["se"] ** 2 + c["se"] ** 2))
    if sep > 0 and e["media"] - c["media"] >= 2 * sep:
        return "★"
    if sep > 0 and c["media"] - e["media"] >= 2 * sep:
        return "▼"
    return ""


# ---------------------------------------------------------------------------------------------------- linhas das hipóteses
# cada linha: (rótulo, máscara, prefixo da coluna de resultado ['up','dn','bn','tr'], rótulo da linha de controle ou None)
def linhas_h1(df: pd.DataFrame, composto: str) -> list[tuple]:
    ctrl = df["tipo"] == "controle"
    c = df["composto"] == composto
    acima, abaixo = df["chegada"] == "acima", df["chegada"] == "abaixo"
    return [
        ("controle: compra em nível sorteado", ctrl, "up", None),
        ("controle: venda em nível sorteado", ctrl, "dn", None),
        ("controle: reação de cima (compra)", ctrl & acima, "up", None),
        ("controle: reação de baixo (venda)", ctrl & abaixo, "dn", None),
        ("VAL compra", c & (df["tipo"] == "VAL"), "up", "controle: compra em nível sorteado"),
        ("VAH venda", c & (df["tipo"] == "VAH"), "dn", "controle: venda em nível sorteado"),
        ("POC reação de cima (compra)", c & (df["tipo"] == "POC") & acima, "up", "controle: reação de cima (compra)"),
        ("POC reação de baixo (venda)", c & (df["tipo"] == "POC") & abaixo, "dn", "controle: reação de baixo (venda)"),
        ("VAL compra, só range válido", c & (df["tipo"] == "VAL") & df["ctx_valido"], "up", "controle: compra em nível sorteado"),
        ("VAH venda, só range válido", c & (df["tipo"] == "VAH") & df["ctx_valido"], "dn", "controle: venda em nível sorteado"),
    ]


def linhas_h2(df: pd.DataFrame) -> list[tuple]:
    ctrl = df["tipo"] == "controle"
    c = df["composto"] == "fixo10"
    acima, abaixo = df["chegada"] == "acima", df["chegada"] == "abaixo"
    reentrou_cima = df["fech_toque"] >= df["nivel"]      # fechou de volta acima do nível (VAL) -> entrada no fechamento
    reentrou_baixo = df["fech_toque"] <= df["nivel"]     # fechou de volta abaixo do nível (VAH) -> entrada no fechamento
    fa, fc = df["fechou_abaixo_8b"], df["fechou_acima_8b"]
    val, vah = c & (df["tipo"] == "VAL"), c & (df["tipo"] == "VAH")
    return [
        ("controle compra (a) fechou abaixo e reentrou [entrada no fechamento]", ctrl & fa & reentrou_cima, "fcu", None),
        ("controle compra (b) de cima sem fechar abaixo", ctrl & ~fa & acima, "up", None),
        ("controle compra (c) fechou abaixo nas 4 h, entrada no nível", ctrl & fa, "up", None),
        ("controle venda (a) fechou acima e reentrou [entrada no fechamento]", ctrl & fc & reentrou_baixo, "fcd", None),
        ("controle venda (b) de baixo sem fechar acima", ctrl & ~fc & abaixo, "dn", None),
        ("controle venda (c) fechou acima nas 4 h, entrada no nível", ctrl & fc, "dn", None),
        ("VAL compra (a) DESVIO confirmado [entrada no fechamento]", val & fa & reentrou_cima, "fcu",
         "controle compra (a) fechou abaixo e reentrou [entrada no fechamento]"),
        ("VAL compra (b) DENTRO: de cima sem fechar abaixo", val & ~fa & acima, "up", "controle compra (b) de cima sem fechar abaixo"),
        ("VAL compra (c) FORA: fechou abaixo nas 4 h, entrada no nível", val & fa, "up", "controle compra (c) fechou abaixo nas 4 h, entrada no nível"),
        ("VAH venda (a) DESVIO confirmado [entrada no fechamento]", vah & fc & reentrou_baixo, "fcd",
         "controle venda (a) fechou acima e reentrou [entrada no fechamento]"),
        ("VAH venda (b) DENTRO: de baixo sem fechar acima", vah & ~fc & abaixo, "dn", "controle venda (b) de baixo sem fechar acima"),
        ("VAH venda (c) FORA: fechou acima nas 4 h, entrada no nível", vah & fc, "dn", "controle venda (c) fechou acima nas 4 h, entrada no nível"),
    ]


def linhas_h3(df: pd.DataFrame) -> list[tuple]:
    ctrl = df["tipo"] == "controle"
    c = df["composto"] == "fixo10"
    tp = df["toques_previos"]
    cats = [("0 (virgem)", tp == 0), ("1 (2º toque)", tp == 1), ("2+ (3º toque ou mais)", tp >= 2)]
    out = []
    for nome, m in cats:
        out += [(f"controle compra, toques {nome}", ctrl & m, "up", None),
                (f"controle venda, toques {nome}", ctrl & m, "dn", None),
                (f"controle reação, toques {nome}", ctrl & m, "bn", None)]
    for nome, m in cats:
        out += [(f"VAL compra, toques {nome}", c & (df["tipo"] == "VAL") & m, "up", f"controle compra, toques {nome}"),
                (f"VAH venda, toques {nome}", c & (df["tipo"] == "VAH") & m, "dn", f"controle venda, toques {nome}"),
                (f"POC reação, toques {nome}", c & (df["tipo"] == "POC") & m, "bn", f"controle reação, toques {nome}")]
    return out


def linhas_h4(df: pd.DataFrame) -> list[tuple]:
    ctrl = df["tipo"] == "controle"
    c = df["composto"] == "fixo10"
    compra, venda = df["direcao"] == 1, df["direcao"] == -1
    return [
        ("controle compra (reação de cima)", ctrl & compra, "tr", None),
        ("controle venda (reação de baixo)", ctrl & venda, "tr", None),
        ("VAL compra", c & (df["tipo"] == "VAL"), "tr", "controle compra (reação de cima)"),
        ("VAH venda", c & (df["tipo"] == "VAH"), "tr", "controle venda (reação de baixo)"),
        ("POC compra (reação de cima)", c & (df["tipo"] == "POC") & compra, "tr", "controle compra (reação de cima)"),
        ("POC venda (reação de baixo)", c & (df["tipo"] == "POC") & venda, "tr", "controle venda (reação de baixo)"),
    ]


def linhas_h5(df: pd.DataFrame) -> list[tuple]:
    ctrl = df["tipo"] == "controle"
    c = df["composto"] == "fixo10"
    val, vah = c & (df["tipo"] == "VAL"), c & (df["tipo"] == "VAH")
    tem_lsr = df["lsr"].notna() & df["lsr_med"].notna()
    vend_presos, comp_presos = tem_lsr & (df["lsr"] < df["lsr_med"]), tem_lsr & (df["lsr"] > df["lsr_med"])
    sem_vend, sem_comp = tem_lsr & ~(df["lsr"] < df["lsr_med"]), tem_lsr & ~(df["lsr"] > df["lsr_med"])
    tem_oi = df["oi_6h"].notna()
    oi_sobe, oi_cai = tem_oi & (df["oi_6h"] > 0), tem_oi & (df["oi_6h"] <= 0)
    tem_fu = df["funding"].notna() & df["funding_med"].notna()
    fu_val, fu_val_nao = tem_fu & (df["funding"] < df["funding_med"]), tem_fu & ~(df["funding"] < df["funding_med"])
    fu_vah, fu_vah_nao = tem_fu & (df["funding"] > df["funding_med"]), tem_fu & ~(df["funding"] > df["funding_med"])
    out = []
    for nome, mv, mh in (("lsr: presos contra", vend_presos, comp_presos), ("lsr: sem presos", sem_vend, sem_comp),
                         ("OI 6h subindo", oi_sobe, oi_sobe), ("OI 6h caindo", oi_cai, oi_cai),
                         ("funding do lado", fu_val, fu_vah), ("funding não", fu_val_nao, fu_vah_nao)):
        out += [(f"controle compra, {nome}", ctrl & mv, "up", None),
                (f"controle venda, {nome}", ctrl & mh, "dn", None)]
    for nome, mv, mh in (("lsr: vendidos presos", vend_presos, None), ("lsr: sem vendidos presos", sem_vend, None),
                         ("OI 6h subindo", oi_sobe, None), ("OI 6h caindo", oi_cai, None),
                         ("funding do lado", fu_val, None), ("funding não", fu_val_nao, None)):
        ref = {"lsr: vendidos presos": "lsr: presos contra", "lsr: sem vendidos presos": "lsr: sem presos"}.get(nome, nome)
        out.append((f"VAL compra, {nome}", val & mv, "up", f"controle compra, {ref}"))
    for nome, mh in (("lsr: comprados presos", comp_presos), ("lsr: sem comprados presos", sem_comp),
                     ("OI 6h subindo", oi_sobe), ("OI 6h caindo", oi_cai),
                     ("funding do lado", fu_vah), ("funding não", fu_vah_nao)):
        ref = {"lsr: comprados presos": "lsr: presos contra", "lsr: sem comprados presos": "lsr: sem presos"}.get(nome, nome)
        out.append((f"VAH venda, {nome}", vah & mh, "dn", f"controle venda, {ref}"))
    return out


# ---------------------------------------------------------------------------------------------------- tabelas
def tabela_p(df: pd.DataFrame, linhas: list[tuple], rk: str, periodo: str) -> list[dict]:
    custo_r = CUSTO / RS[rk]
    sub = df["periodo"] == periodo
    ests: dict[str, dict] = {}
    regs = []
    for rotulo, m, pref, ref in linhas:
        s = df[sub & m]
        e = {fmt: estat_p(s[f"{pref}_r{rk}_{fmt}"].to_numpy(), custo_r, mult) for fmt, mult in FMTS}
        ests[rotulo] = e
        reg = {"periodo": periodo, "R": rk, "linha": rotulo, "ref": ref, "n": e["11"]["n"]}
        for fmt, _ in FMTS:
            c = ests.get(ref, {}).get(fmt) if ref else None
            reg.update({f"dec{fmt}": e[fmt]["dec"], f"p{fmt}": e[fmt]["p"], f"se{fmt}": e[fmt]["se"],
                        f"liq{fmt}": e[fmt]["liq"], f"sig{fmt}": sinal(e[fmt], c)})
        regs.append(reg)
    return regs


def md_tabela_p(regs: list[dict]) -> str:
    out = ["| linha | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for r in regs:
        out.append(f"| {r['linha']} | {r['n']} | {r['dec11']} | {fmt_p(r['p11'], r['se11'])}{r['sig11']} | {fmt_r(r['liq11'])} | "
                   f"{fmt_p(r['p21'], r['se21'])}{r['sig21']} | {fmt_r(r['liq21'])} |")
    return "\n".join(out)


def tabela_escada(df: pd.DataFrame, linhas: list[tuple], rk: str, periodo: str) -> list[dict]:
    custo_r = CUSTO / RS[rk]
    sub = df["periodo"] == periodo
    ests: dict[str, dict] = {}
    regs = []
    for rotulo, m, pref, ref in linhas:
        s = df[sub & m]
        e = {}
        for fmt, mult in FMTS:
            res = s[f"esc_r{rk}_{fmt}"].to_numpy(float)
            fr = s[f"esc_r{rk}_{fmt}_fr"].to_numpy(float)
            dec = res != 0
            liq_norm = res[dec] - custo_r                       # R do médio, por unidade preenchida
            liq_cheia = (res[dec] - custo_r) * fr[dec]           # por unidade cheia
            uni = s[f"{pref}_r{rk}_{fmt}"].to_numpy()
            udec = uni != 0
            liq_uni = np.where(uni[udec] == 1, mult, -1.0) - custo_r
            e[fmt] = {"n": len(s), "dec": int(dec.sum()), "fr": float(fr.mean()) if len(fr) else np.nan,
                      "norm": estat_media(liq_norm), "cheia": estat_media(liq_cheia), "uni": estat_media(liq_uni),
                      "udec": int(udec.sum())}
        ests[rotulo] = e
        reg = {"periodo": periodo, "R": rk, "linha": rotulo, "ref": ref, "n": e["11"]["n"], "fr": e["11"]["fr"]}
        for fmt, _ in FMTS:
            c = ests.get(ref, {}).get(fmt) if ref else None
            reg.update({f"dec{fmt}": e[fmt]["dec"], f"norm{fmt}": e[fmt]["norm"]["media"], f"normse{fmt}": e[fmt]["norm"]["se"],
                        f"cheia{fmt}": e[fmt]["cheia"]["media"], f"uni{fmt}": e[fmt]["uni"]["media"],
                        f"sig{fmt}": sinal_media(e[fmt]["norm"], c["norm"] if c else None),
                        f"liq{fmt}": e[fmt]["norm"]["media"]})
        regs.append(reg)
    return regs


def md_tabela_escada(regs: list[dict]) -> str:
    out = ["| linha | n | preench. média | dec 1:1 | escada 1:1 (R do médio) | × cheia | única 1:1 | dec 2:1 | escada 2:1 (R do médio) | × cheia | única 2:1 |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in regs:
        cel = [r["linha"], str(r["n"]), "-" if np.isnan(r["fr"]) else f"{r['fr'] * 100:.0f}%"]
        for fmt in ("11", "21"):
            se = r[f"normse{fmt}"]
            cel += [str(r[f"dec{fmt}"]),
                    f"{fmt_r(r[f'norm{fmt}'])}±{se:.3f}{r[f'sig{fmt}']}" if not np.isnan(se) else fmt_r(r[f"norm{fmt}"]),
                    fmt_r(r[f"cheia{fmt}"]), fmt_r(r[f"uni{fmt}"])]
        out.append("| " + " | ".join(cel) + " |")
    return "\n".join(out)


def consistencia(todas: list[dict], periodos: list) -> pd.DataFrame:
    """Uma linha por linha-de-hipótese × R × corrida com o líquido nos 3 períodos (>= MIN_DEC decididos em cada)."""
    t = pd.DataFrame(todas)
    cons = []
    for rk in RS:
        for fmt, _ in FMTS:
            for rotulo, g in t[t["R"] == rk].groupby("linha", sort=False):
                if g["ref"].iloc[0] is None or str(rotulo).startswith("controle"):
                    continue
                g = g.set_index("periodo")
                if any(p not in g.index for p, _, _ in periodos):
                    continue
                liqs = [float(g.loc[p, f"liq{fmt}"]) for p, _, _ in periodos]
                decs = [int(g.loc[p, f"dec{fmt}"]) for p, _, _ in periodos]
                sigs = [str(g.loc[p, f"sig{fmt}"]) for p, _, _ in periodos]
                if any(np.isnan(x) for x in liqs) or min(decs) < MIN_DEC:
                    continue
                cons.append({"R": rk, "corrida": "1:1" if fmt == "11" else "2:1", "linha": rotulo, "n": int(g["n"].sum()),
                             "treino": liqs[0], "validacao": liqs[1], "holdout": liqs[2], "sigs": "".join(sigs),
                             "min": min(liqs), "positivo_3": all(x > 0 for x in liqs)})
    return pd.DataFrame(cons)


def md_consistencia(cons: pd.DataFrame, top: int = 5) -> list[str]:
    if not len(cons):
        return ["(nenhuma linha com ≥ 30 decididos nos 3 períodos)\n"]
    pos = cons[cons["positivo_3"]].sort_values("min", ascending=False)
    partes = [f"**Líquido positivo nos 3 períodos: {len(pos)} de {len(cons)} combinações linha×R×corrida.**\n"]
    cab = "| R | corrida | linha | n | treino | validação | holdout | min | ★▼ |\n|---|---|---|---:|---:|---:|---:|---:|---|"
    if len(pos):
        partes.append(cab)
        for _, r in pos.iterrows():
            partes.append(f"| {RS[r['R']] * 100:.0f}% | {r['corrida']} | {r['linha']} | {r['n']} | {fmt_r(r['treino'])} | "
                          f"{fmt_r(r['validacao'])} | {fmt_r(r['holdout'])} | {fmt_r(r['min'])} | {r['sigs']} |")
        partes.append("")
    partes.append(f"Top {top} por pior período:\n")
    partes.append(cab)
    for _, r in cons.sort_values("min", ascending=False).head(top).iterrows():
        partes.append(f"| {RS[r['R']] * 100:.0f}% | {r['corrida']} | {r['linha']} | {r['n']} | {fmt_r(r['treino'])} | "
                      f"{fmt_r(r['validacao'])} | {fmt_r(r['holdout'])} | {fmt_r(r['min'])} | {r['sigs']} |")
    partes.append("")
    return partes


# ---------------------------------------------------------------------------------------------------- resumo
CONCLUSAO = """\
(prosa escrita depois de rodar; nenhum parâmetro foi alterado depois de ver o holdout — a única mudança foi a correção
do olhar-futuro da H2a, descrita na regra, aplicada igual ao controle)

1. **Nenhuma das cinco hipóteses passa.** De 117 combinações linha×R×corrida com amostra, 3 deram líquido > 0 nos 3
   períodos (2 na H2, 1 na H5) e nenhuma ficou 2 EP acima do controle sorteado em período algum; com 117 testes,
   3 positivas é o esperado do acaso.
2. **H1 (15 min, R 1–2%, 2 dias): VAL/VAH/POC do composto de 10 dias = nível sorteado** (0 de 16). O composto adaptativo
   quase sempre vira o perfil de ontem (1 dia em metade dos dias, 2,0 em média) e também dá 0 de 24. O range "válido"
   pelo critério de equilíbrio existe em só 10% dos dias (n 11–40 por período: sem leitura). Vender a VAH é pior que
   comprar o VAL em todo período, e a mesma assimetria está no controle (viés de alta de 2020–23), não no nível.
3. **H2 (desvio × dentro): sem vantagem.** A primeira rodada tinha olhar-futuro na "reentrada" e o controle sorteado
   ficou positivo nos 3 períodos (artefato); corrigida, o desvio confirmado tem 71/26/20 toques no VAL (amostra
   insuficiente) e no holdout reagiu em 25% (▼). "Dentro" dá −0,010/−0,054/−0,159 R no melhor formato.
4. A única linha com 3 períodos positivos é **"VAL com fechamento abaixo nas 4 h, entrada no nível"** em 2 dos 4
   formatos (R=1% 2:1: +0,033/+0,162/+0,111; R=2% 1:1: +0,085/+0,027/+0,149), n = 225, sem ★ (0,6–1,5 EP acima do
   controle) e com os outros 2 formatos negativos. É candidato a um reteste pré-registrado em dados novos, não aprovação.
5. **H3 (toque virgem): 0 de 12.** O 1º toque tem 64/25/18 toques no VAL (sem leitura); 2º e 3º+ não diferem do controle
   com o mesmo número de toques; não aparece o gradiente "cada toque enfraquece a borda".
6. **H4 (escada de 5 limitadas em ±0,25%): é a mesma operação que a entrada única** quando R é 1–2%: 99–100% dos toques
   com o mesmo resultado em 1:1, preenchimento médio 95–98%, 0 de 16. A zona é estreita demais para o R; a tese das
   fatias largas (1,5 ATR, 11/09) não foi testada aqui.
7. **H5 (presos): lsr contra a mediana não separa** VAL nem VAH (vendidos presos no VAL, R=1% 1:1: −0,014/−0,097/−0,239 R;
   comprados presos na VAH: −0,175/−0,323/+0,107). OI subindo e funding "do lado" também não; a única linha positiva
   (VAL com funding NÃO do lado, R=2% 1:1) é o complemento da hipótese, 1 em 36, sem ★.
8. Leitura geral: o controle mostra o drift (compra em nível sorteado 47–52% de reação, venda 41–51%) e cada linha de
   nível acompanha o controle do mesmo lado. Resultado negativo é resultado: não ligar nada disso sem hipótese nova.
"""


def escrever_resumo(df: pd.DataFrame):
    partes = ["# Estudo 2 dos níveis de TPO — composto, desvio, toque virgem, escada e presos (BTCUSDT 15m, 2020-01 a 2026-09)\n",
              "Gerado por `scripts/estudo_niveis_tpo_2.py`. Um toque por linha em `data/estudo_niveis_tpo_2.csv`. "
              "Complementa `data/estudo_niveis_tpo_resumo.md` (5 min), que deu 0 de 180.\n",
              "## Regra exata\n", "```\n" + (__doc__ or "").strip() + "\n```\n"]

    nd = df.groupby("periodo")["data"].nunique()
    partes.append("## Volume\n")
    partes.append("| período | dias | toques (todos) | VAL/VAH/POC fixo10 | VAL/VAH/POC adapt | controle |\n|---|---:|---:|---:|---:|---:|")
    for nome, _, _ in PERIODOS:
        s = df[df["periodo"] == nome]
        partes.append(f"| {nome} | {nd.get(nome, 0)} | {len(s)} | {int((s['composto'] == 'fixo10').sum())} | "
                      f"{int((s['composto'] == 'adapt').sum())} | {int((s['tipo'] == 'controle').sum())} |")
    partes.append("")
    fx = df[df["composto"] == "fixo10"]
    partes.append(f"- Composto fixo: largura média do valor {fx['ctx_largura_pct'].mean():.2f}% do POC; range válido (equilíbrio) em "
                  f"{fx.groupby('data')['ctx_valido'].first().mean() * 100:.0f}% dos dias. "
                  f"Composto adaptativo: {df[df['composto'] == 'adapt'].groupby('data')['ctx_dias'].first().mean():.1f} dias em média.")
    for rk in RS:
        neu = (df[f"tr_r{rk}_11"] == 0).mean() * 100
        neu2 = (df[f"tr_r{rk}_21"] == 0).mean() * 100
        partes.append(f"- R={RS[rk] * 100:.0f}%: sem decisão em 2 dias: {neu:.1f}% (1:1), {neu2:.1f}% (2:1); "
                      f"escada: fração preenchida média {df[f'esc_r{rk}_11_fr'].mean() * 100:.0f}%.")
    partes.append("")

    # ---- hipóteses
    hip = []   # (nome, linhas, periodos, tipo_tabela, df)
    for comp in COMPOSTOS:
        hip.append((f"H1 Tempo maior — composto {comp}", linhas_h1(df, comp), PERIODOS, "p", df))
    hip.append(("H2 Desvio × dentro (composto fixo10)", linhas_h2(df), PERIODOS, "p", df))
    hip.append(("H3 Toque virgem (composto fixo10)", linhas_h3(df), PERIODOS, "p", df))
    hip.append(("H4 Escada de 5 limitadas (composto fixo10)", linhas_h4(df), PERIODOS, "esc", df))
    df5 = df[df["data"] >= INICIO_LSR]
    per5 = [("treino", INICIO_LSR, "2023-12-31")] + PERIODOS[1:]
    hip.append((f"H5 Presos (composto fixo10, desde {INICIO_LSR})", linhas_h5(df5), per5, "p", df5))

    veredito = []
    corpo = []
    for nome, linhas, pers, tipo, d in hip:
        todas = []
        corpo.append(f"## {nome}\n")
        for rk in RS:
            corpo.append(f"### R = {RS[rk] * 100:.0f}% (custo {CUSTO / RS[rk]:.2f} R por toque)\n")
            for pnome, _, _ in pers:
                regs = tabela_p(d, linhas, rk, pnome) if tipo == "p" else tabela_escada(d, linhas, rk, pnome)
                todas += regs
                corpo.append(f"#### {pnome}\n")
                corpo.append(md_tabela_p(regs) if tipo == "p" else md_tabela_escada(regs))
                corpo.append("")
        cons = consistencia(todas, pers)
        corpo.append(f"### Consistência nos 3 períodos — {nome}\n")
        corpo.append(f"Só linhas com ≥ {MIN_DEC} decididos em cada período. `min` = pior período. "
                     + ("Líquido = média em R do médio por unidade preenchida." if tipo == "esc" else "") + "\n")
        corpo += md_consistencia(cons)
        npos = int(cons["positivo_3"].sum()) if len(cons) else 0
        melhor = cons.sort_values("min", ascending=False).head(1) if len(cons) else None
        txt = ""
        if melhor is not None and len(melhor):
            m = melhor.iloc[0]
            txt = (f" Melhor pior-período: {m['linha']} R={RS[m['R']] * 100:.0f}% {m['corrida']} "
                   f"({fmt_r(m['treino'])} / {fmt_r(m['validacao'])} / {fmt_r(m['holdout'])} R).")
        est = sum(1 for r in todas if not str(r["linha"]).startswith("controle") for f in ("11", "21") if r[f"sig{f}"] == "★")
        set_ = sum(1 for r in todas if not str(r["linha"]).startswith("controle") for f in ("11", "21") if r[f"sig{f}"] == "▼")
        ntest = sum(1 for r in todas if not str(r["linha"]).startswith("controle") for f in ("11", "21"))
        veredito.append(f"- **{nome}**: **{npos} de {len(cons)}** combinações com líquido > 0 nos 3 períodos "
                        f"(≥ {MIN_DEC} decididos por período).{txt} ★ {est} / ▼ {set_} em {ntest} testes contra o controle.")

    partes.append("## Veredito pelo critério escrito antes\n")
    partes += veredito
    partes.append("")
    partes.append("## Conclusão\n")
    partes.append(CONCLUSAO)
    partes.append("")
    partes += corpo

    # controle como referência
    partes.append("## Controle (níveis sorteados) por período — compra e venda sem olhar a chegada\n")
    partes.append("| R | período | direção | n | dec | reação 1:1 % | líq 1:1 | reação 2:1 % | líq 2:1 |\n|---|---|---|---:|---:|---:|---:|---:|---:|")
    for rk in RS:
        for pnome, _, _ in PERIODOS:
            regs = tabela_p(df, linhas_h1(df, "fixo10")[:2], rk, pnome)
            for r in regs:
                partes.append(f"| {RS[rk] * 100:.0f}% | {pnome} | {r['linha'].split(': ')[1]} | {r['n']} | {r['dec11']} | "
                              f"{fmt_p(r['p11'], r['se11'])} | {fmt_r(r['liq11'])} | {fmt_p(r['p21'], r['se21'])} | {fmt_r(r['liq21'])} |")
    partes.append("")
    SAIDA_MD.write_text("\n".join(partes), encoding="utf-8")


if __name__ == "__main__":
    rodar()
