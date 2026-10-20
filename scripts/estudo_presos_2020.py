# scripts/estudo_presos_2020.py
"""
PRESOS NO FOOTPRINT, 2020–2026 (Fluxo D com o histórico inteiro da Bybit) e a COMBINAÇÃO TPO E2 + presos.
Dados: footprint por minuto da Bybit (BTCUSDT perpétuo linear, lado do agressor, faixas de US$ 20) em
dados/negocios/bybit/<dia>.jsonl.gz, baixado por scripts/baixar_negocios_bybit_periodo.py, 2020-03-25 a 2026-10-19.
CRITÉRIO ESCRITO ANTES DE RODAR; nenhum parâmetro iterado; holdout lido uma vez.

==================================================================================================== PARTE 1 — presos
Velas: conselho/fluxo.barras(minutos da Bybit, passo_s) com passo de 30 min e de 5 min (OHLC e footprint da Bybit).
Detecção: conselho/fluxo.presos(velas, passo_s=..., abandono_pct=0,005 em 30 min / 0,002 em 5 min); os demais cortes
  são os padrões do módulo (nó >= 3 × mediana das faixas da vela e >= 5 BTC, no terço extremo, vela fecha do outro
  lado da faixa; abandono = as 2 velas seguintes FECHAM >= abandono_pct além do nó). Evento = confirmado == True.
  Compradores presos (nó comprador no alto) -> VENDA no reteste; vendedores presos -> COMPRA. L = centro da faixa.
Ordem: uma limitada post-only em L, posta no fechamento da vela B+2 (quando o abandono fica conhecido), válida por
  24 h. Preenche só se um minuto ATRAVESSAR L (venda: máxima > L; compra: mínima < L).
Stop: além da vela dos presos + 0,10% (venda: máxima de B × 1,001; compra: mínima de B × 0,999), a mercado.
  R = |stop − L| / L (sem piso). Alvo = L ∓ 2R (limitada, só com o preço atravessando). Sem parcial em 1R.
Limite: a posição fecha a mercado no fechamento do minuto que completa 24 h desde o minuto do preenchimento.
Execução em minutos da Bybit, leitura pessimista: no minuto do preenchimento só o stop conta; stop e alvo no mesmo
  minuto = stop. Custos: maker 0,02% na entrada e no alvo; taker 0,055% + 0,02% de slippage no stop e no limite de
  tempo; funding linear da Bybit (data/historico/funding_bybit.json) em cada 00/08/16 UTC com a posição aberta
  (comprado paga taxa positiva). Resultado em R líquido por trade preenchido.
Buraco: evento cuja janela [início de B, fechamento de B+2 + 48 h] tem intervalo > 60 min sem minuto gravado sai do
  estudo (contado no funil). Período pela data da vela B: treino 2020-03-25..2023-12-31, validação 2024-01..2025-06,
  holdout 2025-07..2026-09 (eventos de outubro/2026 ficam fora).
Controles (mesma ordem, stop, alvo, limite, custo):
  (a) NÍVEL SORTEADO DA MESMA VELA: para cada evento, 20 níveis L' uniformes no terço extremo de B (o terço do nó);
      L' só vale se cumprir as mesmas condições de preso que o nó cumpriu, recalculadas para L' (venda: fechamento de
      B < L' − 10 e fechamentos de B+1 e B+2 <= L' × (1 − abandono); compra espelhada). Stop igual (o da vela B).
  (b) NÓ IGUAL NÃO ABANDONADO: mesmos nós (fluxo.presos) com confirmado == False; a ordem só é posta se o fechamento de
      B+2 estiver do lado certo de L (post-only: venda exige fechamento < L).
  (c) DIREÇÃO SORTEADA: no minuto e preço do preenchimento real, as duas direções com stop à mesma distância R e alvo
      a 2R (só o stop conta no minuto da entrada); esperança da moeda = média das duas. Também 20 sorteios do conjunto
      (cada trade com lado sorteado) para ver em quantos dos 20 o real fica acima.
APROVAÇÃO (por TF; compra+venda e cada lado separados): líquido médio > 0 nos 3 períodos com n >= 30 em cada (abaixo de
  30 = inconclusivo, nunca aprovado) E, em treino e validação, média >= (a) + 2 EP, >= (b) + 2 EP e >= (c) + 2 EP
  (EP = desvio/raiz(n) da estratégia; EP agrupado por dia mostrado ao lado, informativo).

==================================================================================================== PARTE 2 — TPO E2 + presos
Eventos da TPO E2 exatamente como em scripts/estudo_tpo_e2_e3.py (lidos de data/estudo_tpo_e2.csv, gerado por ele:
  cauda >= 0,30% e >= 60% do bloco de 30 min, fechamento no terço, nível do composto/ontem/naked no quartil de fora,
  "de longe", zona de 3 limitadas, stop na ponta do bloco + 0,10%, alvo no nível a >= 2R, 1R realiza 50% e stop no
  médio, teto 8 h / 20:00 UTC; execução em 5 min Binance, custo real, pessimista). Só blocos a partir de 2020-03-26.
PRESOS (P30, a linha principal): fluxo.presos nas velas de 30 min da Bybit no MESMO bloco ou no anterior, do lado da
  cauda (cauda de baixo = compra -> vendedores presos; cauda de cima = venda -> compradores presos). O abandono NÃO é
  exigido aqui: no fechamento do bloco ele ainda não aconteceu (exigir seria olhar o futuro); vale nó + absorção.
  P5 (informativo): presos de 5 min CONFIRMADOS (abandono de 0,2%) com B no bloco ou no anterior e confirmação até o
  fechamento do bloco.
Grupos: E2+P = borda + cauda + presos (a estratégia); (i) CAUDA NA BORDA SEM PRESOS = E2 sem presos; (ii) PRESOS SEM
  BORDA = blocos "sem_nivel" do estudo E2 (mesma cauda, nenhum nível) com presos; (iii) DIREÇÃO SORTEADA = coluna cd
  do estudo E2 (mesma hora e preço da 1ª execução, média de mesma e oposta).
APROVAÇÃO: a mesma da parte 1, com (i), (ii) e (iii) como controles.

Saídas: data/estudo_presos_2020.csv (trades da parte 1 e controles), data/estudo_presos_2020_e2.csv (eventos E2 com as
marcas de presos) e data/estudo_presos_2020_resumo.md (a seção "Conclusão" escrita à mão é preservada).
Uso: ./.venv/Scripts/python.exe scripts/estudo_presos_2020.py [--processos 6]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import date, datetime, timedelta, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from conselho import fluxo  # noqa: E402
from conselho.coletor_negocios import PASTA_NEGOCIOS  # noqa: E402

FUNDING = RAIZ / "data" / "historico" / "funding_bybit.json"
E2_CSV = RAIZ / "data" / "estudo_tpo_e2.csv"
SAIDA_CSV = RAIZ / "data" / "estudo_presos_2020.csv"
SAIDA_E2 = RAIZ / "data" / "estudo_presos_2020_e2.csv"
SAIDA_MD = RAIZ / "data" / "estudo_presos_2020_resumo.md"

INICIO = "2020-03-25"
FIM = "2026-10-19"
PERIODOS = [("treino", "2020-01-01", "2023-12-31"), ("validacao", "2024-01-01", "2025-06-30"),
            ("holdout", "2025-07-01", "2026-09-30")]
TFS = {"30m": (1800, 0.005), "5m": (300, 0.002)}
FOLGA = 0.001
RR = 2.0
VALIDADE_S = 24 * 3600
LIMITE_S = 24 * 3600
BURACO_S = 3600
N_SORTEIOS = 20
SEMENTE = 20261020
MAKER = 0.0002
TAKER = 0.00055 + 0.0002
P8H = 8 * 3600
MIN_N = 30


# ---------------------------------------------------------------------------------------------------- leitura
def _meses():
    d0 = date.fromisoformat(INICIO).replace(day=1)
    d1 = date.fromisoformat(FIM)
    out = []
    d = d0
    while d <= d1:
        nx = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append((d, nx))
        d = nx
    return out


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def processar_mes(args):
    """Carrega um mês (+ 1 dia de margem), devolve os minutos do mês e os eventos de presos com B no mês."""
    d0, d1 = args
    t0, t1 = _ts(d0), _ts(d1)
    regs = fluxo.carregar_minutos(["bybit"], t0, t1 + 86400 - 1)["bybit"]
    vistos, mins = set(), []
    for r in regs:
        t = int(r["ts"])
        if t in vistos:
            continue
        vistos.add(t)
        mins.append(r)
    if not mins:
        return None
    arr = np.array([(int(r["ts"]), float(r["abertura"]), float(r["maxima"]), float(r["minima"]), float(r["fechamento"]))
                    for r in mins if t0 <= int(r["ts"]) < t1], dtype=float).reshape(-1, 5)
    evs = {}
    for tf, (passo, ab) in TFS.items():
        velas = fluxo.barras({"bybit": mins}, passo_s=passo, preco_de="bybit")
        por_ts = {b["ts"]: b for b in velas}
        lst = []
        for e in fluxo.presos(velas, abandono_pct=ab, passo_s=passo):
            if not (t0 <= e["ts"] < t1):
                continue
            b = por_ts[e["ts"]]
            b1, b2 = por_ts.get(e["ts"] + passo), por_ts.get(e["ts"] + 2 * passo)
            lst.append({**e, "tf": tf, "hi": b["maxima"], "lo": b["minima"], "fe": b["fechamento"],
                        "cl1": b1["fechamento"] if b1 else np.nan, "cl2": b2["fechamento"] if b2 else np.nan})
        evs[tf] = lst
    return arr, evs


# ---------------------------------------------------------------------------------------------------- simulação
class Minutos:
    def __init__(self, arr: np.ndarray):
        o = np.argsort(arr[:, 0], kind="stable")
        arr = arr[o]
        self.ts = arr[:, 0].astype(np.int64)
        self.op, self.hi, self.lo, self.cl = arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4]
        gap = np.flatnonzero(np.diff(self.ts) > BURACO_S)
        self.gap_ini = self.ts[gap]          # último minuto antes de cada buraco
        self.gap_fim = self.ts[gap + 1]      # primeiro minuto depois
        f = json.load(open(FUNDING))["linear"]
        self.funding = {int(k) // 1000: float(v) for k, v in f.items()}

    def tem_buraco(self, a: int, z: int) -> bool:
        """Algum buraco (> 60 min sem minuto) cruza [a, z]?"""
        i = int(np.searchsorted(self.gap_fim, a, side="left"))
        return i < len(self.gap_ini) and self.gap_ini[i] <= z

    def fim_dado(self) -> int:
        return int(self.ts[-1])


def _sair(M: Minutos, d: int, p: float, stop: float, alvo: float, kf: int):
    """Da entrada em kf (só o stop conta em kf) até 24 h. Devolve (preço, tipo, k_saida) ou None (acabou o dado)."""
    ts = M.ts
    t_lim = ts[kf] + LIMITE_S
    ke = int(np.searchsorted(ts, t_lim, side="left"))
    if ke >= len(ts) and ts[-1] < t_lim - 60:
        return None
    hi, lo = M.hi[kf:ke], M.lo[kf:ke]
    st = (hi >= stop) if d == -1 else (lo <= stop)
    al = (lo < alvo) if d == -1 else (hi > alvo)
    al[0] = False
    s = int(np.argmax(st)) if st.any() else None
    a = int(np.argmax(al)) if al.any() else None
    if s is not None and (a is None or s <= a):
        return stop, "stop", kf + s
    if a is not None:
        return alvo, "alvo", kf + a
    return float(M.cl[ke - 1]), "tempo", ke - 1


def _resultado(M: Minutos, d: int, p: float, stop: float, saida, kf: int):
    preco, tipo, ks = saida
    r = abs(stop - p) / p
    pnl = d * (preco / p - 1) - MAKER - (MAKER if tipo == "alvo" else TAKER)
    t_a, t_z = int(M.ts[kf]), int(M.ts[ks])
    m = (t_a // P8H + 1) * P8H
    while m <= t_z:
        pnl -= d * M.funding.get(m, 0.0)
        m += P8H
    return {"res_r": pnl / r, "saida": tipo, "r_pct": r, "kf": kf, "horas": (t_z - t_a) / 3600}


def simular(M: Minutos, d: int, L: float, stop: float, t_ini: int):
    """Limitada em L válida 24 h a partir de t_ini; devolve dict ou None (não preencheu / sem dado)."""
    alvo = L + d * RR * abs(stop - L)
    i0 = int(np.searchsorted(M.ts, t_ini, side="left"))
    i1 = int(np.searchsorted(M.ts, t_ini + VALIDADE_S, side="left"))
    if i1 <= i0:
        return None
    seg = (M.hi[i0:i1] > L) if d == -1 else (M.lo[i0:i1] < L)
    if not seg.any():
        if i1 >= len(M.ts):
            return None
        return {"preencheu": False}
    kf = i0 + int(np.argmax(seg))
    sd = _sair(M, d, L, stop, alvo, kf)
    if sd is None:
        return None
    return {"preencheu": True, **_resultado(M, d, L, stop, sd, kf)}


def forcado(M: Minutos, d: int, p: float, r: float, kf: int):
    stop = p * (1 - d * r)
    alvo = p * (1 + d * RR * r)
    sd = _sair(M, d, p, stop, alvo, kf)
    return None if sd is None else _resultado(M, d, p, stop, sd, kf)["res_r"]


# ---------------------------------------------------------------------------------------------------- estatística
def periodo_de(t: int) -> str:
    s = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
    for nome, a, z in PERIODOS:
        if a <= s <= z:
            return nome
    return ""


def est(x, dias=None) -> dict:
    x = np.asarray(pd.to_numeric(pd.Series(list(x)), errors="coerce").dropna(), float)
    n = len(x)
    if n == 0:
        return {"n": 0, "media": np.nan, "se": np.nan, "se_dia": np.nan, "acerto": np.nan}
    se = float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan
    se_dia = np.nan
    if dias is not None and n > 1:
        df = pd.DataFrame({"x": x - x.mean(), "d": list(dias)[:n]})
        s = df.groupby("d").x.sum().to_numpy()
        se_dia = float(np.sqrt((s ** 2).sum()) / n)
    return {"n": n, "media": float(x.mean()), "se": se, "se_dia": se_dia, "acerto": float((x > 0).mean())}


def f(x, c=3):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{c}f}"


def pct(x):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.0f}%"


def veredito(linhas: dict) -> tuple[str, list]:
    """linhas[per] = (e, oks). REPROVADA se algum período com n >= 30 falha; INCONCLUSIVA se algum < 30."""
    falhas, curtos = [], []
    for per, _, _ in PERIODOS:
        e, oks = linhas[per]
        if e["n"] < MIN_N:
            curtos.append(f"{per}: n={e['n']} < 30")
            continue
        if not e["media"] > 0:
            falhas.append(f"{per}: líquido {f(e['media'])} <= 0")
        if per != "holdout" and not all(oks):
            falhas.append(f"{per}: não fica 2 EP acima de todos os controles")
    if falhas:
        return "REPROVADA", falhas + curtos
    if curtos:
        return "INCONCLUSIVA", curtos
    return "APROVADA", []


# ---------------------------------------------------------------------------------------------------- parte 1
def rodar_presos(M: Minutos, eventos: list):
    rng = np.random.default_rng(SEMENTE)
    linhas = []
    funil = {}
    for tf in TFS:
        passo, ab = TFS[tf]
        fu = funil.setdefault(tf, {"nos": 0, "confirmados": 0, "nao_abandonados": 0, "buraco": 0, "fora_periodo": 0,
                                   "nao_postas_b": 0, "sem_dado": 0})
        for e in eventos[tf]:
            fu["nos"] += 1
            per = periodo_de(e["ts"])
            if not per:
                fu["fora_periodo"] += 1
                continue
            if e["confirmado"] is None:
                continue
            t_conf = e["ts"] + 3 * passo
            if M.tem_buraco(e["ts"], t_conf + 2 * 86400):
                fu["buraco"] += 1
                continue
            d = -1 if e["lado"] == "compradores" else 1
            L = float(e["preco"])
            stop = e["hi"] * (1 + FOLGA) if d == -1 else e["lo"] * (1 - FOLGA)
            dia = datetime.fromtimestamp(e["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
            base = {"tf": tf, "periodo": per, "ano": dia[:4], "dia": dia, "ts_b": e["ts"],
                    "lado": "venda" if d == -1 else "compra", "nivel": L, "btc_no": e["btc"], "vezes": e["vezes"]}
            if e["confirmado"]:
                fu["confirmados"] += 1
                s = simular(M, d, L, stop, t_conf)
                if s is None:
                    fu["sem_dado"] += 1
                    continue
                reg = {**base, "grupo": "presos", **{k: v for k, v in s.items()}}
                if s["preencheu"]:
                    kf = s["kf"]
                    a = forcado(M, d, L, s["r_pct"], kf)
                    b = forcado(M, -d, L, s["r_pct"], kf)
                    reg.update({"cd_mesma": a, "cd_oposta": b})
                linhas.append(reg)
                # (a) nível sorteado no terço extremo da mesma vela
                amp = e["hi"] - e["lo"]
                lo3, hi3 = (e["hi"] - amp / 3, e["hi"]) if d == -1 else (e["lo"], e["lo"] + amp / 3)
                for j, Lr in enumerate(rng.uniform(lo3, hi3, N_SORTEIOS)):
                    if d == -1:
                        ok = e["fe"] < Lr - 10 and e["cl1"] <= Lr * (1 - ab) and e["cl2"] <= Lr * (1 - ab)
                    else:
                        ok = e["fe"] > Lr + 10 and e["cl1"] >= Lr * (1 + ab) and e["cl2"] >= Lr * (1 + ab)
                    if not ok:
                        continue
                    s2 = simular(M, d, float(Lr), stop, t_conf)
                    if s2 is None:
                        continue
                    linhas.append({**base, "grupo": "a_sorteado", "nivel": float(Lr), "sorteio": j, **s2})
            else:
                fu["nao_abandonados"] += 1
                c2 = e["cl2"]
                if not (isinstance(c2, float) and not math.isnan(c2)) or (d == -1 and not c2 < L) or (d == 1 and not c2 > L):
                    fu["nao_postas_b"] += 1
                    continue
                s = simular(M, d, L, stop, t_conf)
                if s is None:
                    continue
                linhas.append({**base, "grupo": "b_nao_abandonado", **s})
        print(f"  {tf}: {fu}", flush=True)
    df = pd.DataFrame(linhas)
    df["cd"] = 0.5 * (pd.to_numeric(df.get("cd_mesma"), errors="coerce") + pd.to_numeric(df.get("cd_oposta"), errors="coerce"))
    return df, funil


def sorteios_conjunto(s: pd.DataFrame, rng) -> np.ndarray:
    """20 sorteios do conjunto: cada trade com lado sorteado; devolve as 20 médias."""
    a = s.cd_mesma.to_numpy(float)
    b = s.cd_oposta.to_numpy(float)
    ok = ~(np.isnan(a) | np.isnan(b))
    a, b = a[ok], b[ok]
    if len(a) == 0:
        return np.array([])
    return np.array([np.where(rng.random(len(a)) < 0.5, a, b).mean() for _ in range(N_SORTEIOS)])


def resumo_presos(df: pd.DataFrame, funil: dict) -> tuple[list, dict]:
    rng = np.random.default_rng(SEMENTE + 1)
    out = ["## Parte 1 — presos no footprint (reteste do nível preso, stop além da vela + 0,10%, alvo 2R, 24 h)\n"]
    out.append("### Funil\n")
    out.append("| TF | nós (fluxo.presos) | fora dos períodos | buraco no dado | confirmados (abandono) | não abandonados | (b) não postos (post-only) |")
    out.append("|---|---|---|---|---|---|---|")
    for tf, fu in funil.items():
        out.append(f"| {tf} | {fu['nos']} | {fu['fora_periodo']} | {fu['buraco']} | {fu['confirmados']} | "
                   f"{fu['nao_abandonados']} | {fu['nao_postas_b']} |")
    out.append("")
    ok = df[df.preencheu == True]
    out.append("### Preenchimento e tamanho do R\n")
    out.append("| TF | grupo | ordens | preencheram | R mediano (% do preço) | custo mínimo em R (maker + taker no stop, mediana) |")
    out.append("|---|---|---|---|---|---|")
    for tf in TFS:
        for g in ("presos", "a_sorteado", "b_nao_abandonado"):
            s = df[(df.tf == tf) & (df.grupo == g)]
            p = ok[(ok.tf == tf) & (ok.grupo == g)]
            rm = float(p.r_pct.median()) if len(p) else np.nan
            out.append(f"| {tf} | {g} | {len(s)} | {len(p)} | {100 * rm:.3f}% | "
                       f"{(MAKER + TAKER) / rm if rm == rm and rm > 0 else float('nan'):.2f} |")
    out.append("")
    out.append("### Resultado (R líquido por trade preenchido)\n")
    out.append("(a) nível sorteado da mesma vela (20 por evento; n conta os sorteios); (b) nó igual não abandonado; "
               "(c) direção sorteada (esperança: média de mesma e oposta). EP = desvio/raiz(n); EPd = EP agrupado por "
               "dia (informativo). 20× = em quantos dos 20 sorteios do conjunto (lado sorteado) o real fica acima.\n")
    out.append("| TF | lado | período | n | acerto | média R ± EP | EPd | (a) (n) | (b) (n) | (c) | ≥a+2EP | ≥b+2EP | ≥c+2EP | real > sorteios |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    vered = {}
    for tf in TFS:
        for lado in (None, "compra", "venda"):
            linhas = {}
            for per, _, _ in PERIODOS:
                q = ok[(ok.tf == tf) & (ok.periodo == per)]
                if lado:
                    q = q[q.lado == lado]
                s, a, b = q[q.grupo == "presos"], q[q.grupo == "a_sorteado"], q[q.grupo == "b_nao_abandonado"]
                e = est(s.res_r, s.dia)
                ea, eb, ec = est(a.res_r), est(b.res_r), est(s.cd)
                oks = [e["n"] > 1 and not np.isnan(c) and e["media"] >= c + 2 * e["se"]
                       for c in (ea["media"], eb["media"], ec["media"])]
                srt = sorteios_conjunto(s, rng)
                acima = f"{int((e['media'] > srt).sum())}/{len(srt)}" if len(srt) else "-"
                out.append(f"| {tf} | {lado or 'compra+venda'} | {per} | {e['n']} | {pct(e['acerto'])} | "
                           f"{f(e['media'])} ± {f(e['se'])} | {f(e['se_dia'])} | {f(ea['media'])} ({ea['n']}) | "
                           f"{f(eb['media'])} ({eb['n']}) | {f(ec['media'])} | "
                           + " | ".join("sim" if o else "não" for o in oks) + f" | {acima} |")
                linhas[per] = (e, oks)
            vered[f"presos {tf} {lado or 'compra+venda'}"] = veredito(linhas)
    out.append("")
    out.append("### Ano a ano (presos, compra+venda)\n")
    out.append("| TF | ano | n | média R | compra n / média | venda n / média | (a) | (b) | (c) |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for tf in TFS:
        q = ok[ok.tf == tf]
        for ano in sorted(q.ano.unique()):
            y = q[q.ano == ano]
            s = y[y.grupo == "presos"]
            c, v = s[s.lado == "compra"], s[s.lado == "venda"]
            out.append(f"| {tf} | {ano} | {len(s)} | {f(est(s.res_r)['media'])} | {len(c)} / {f(est(c.res_r)['media'])} | "
                       f"{len(v)} / {f(est(v.res_r)['media'])} | {f(est(y[y.grupo == 'a_sorteado'].res_r)['media'])} | "
                       f"{f(est(y[y.grupo == 'b_nao_abandonado'].res_r)['media'])} | {f(est(s.cd)['media'])} |")
    out.append("")
    out.append("### Saídas (presos)\n")
    out.append("| TF | saída | n | média R | horas (mediana) |")
    out.append("|---|---|---|---|---|")
    for tf in TFS:
        s = ok[(ok.tf == tf) & (ok.grupo == "presos")]
        for sd, g in s.groupby("saida"):
            out.append(f"| {tf} | {sd} | {len(g)} | {f(g.res_r.mean())} | {g.horas.median():.1f} |")
    out.append("")
    return out, vered


# ---------------------------------------------------------------------------------------------------- parte 2
def marcar_e2(M: Minutos, eventos: list) -> pd.DataFrame:
    e2 = pd.read_csv(E2_CSV)
    e2["ts_bloco"] = [int(pd.Timestamp(dd, tz="UTC").timestamp() + round(h * 3600)) for dd, h in zip(e2.data, e2.hora)]
    p30 = {}
    for e in eventos["30m"]:
        p30.setdefault((e["ts"], e["lado"]), []).append(e)
    p5 = {}
    for e in eventos["5m"]:
        if e["confirmado"]:
            p5.setdefault(e["lado"], []).append(e["ts"])
    p5 = {k: np.array(sorted(v)) for k, v in p5.items()}
    t_min = _ts(date.fromisoformat("2020-03-26"))
    cobre, m30, m5 = [], [], []
    for tb, lado in zip(e2.ts_bloco, e2.lado):
        ok = tb - 1800 >= t_min and not M.tem_buraco(tb - 1800, tb + 1800)
        cobre.append(ok)
        lp = "vendedores" if lado == "compra" else "compradores"
        m30.append(ok and ((tb, lp) in p30 or (tb - 1800, lp) in p30))
        arr = p5.get(lp, np.array([]))
        i = np.searchsorted(arr, tb - 1800, side="left")
        m5.append(ok and i < len(arr) and arr[i] <= tb + 1800 - 900)
    e2["cobre_bybit"], e2["presos30"], e2["presos5"] = cobre, m30, m5
    return e2


def resumo_e2(e2: pd.DataFrame) -> tuple[list, dict]:
    rng = np.random.default_rng(SEMENTE + 2)
    out = ["## Parte 2 — TPO E2 (cauda na borda) + presos do lado da cauda\n"]
    base = e2[e2.cobre_bybit & (e2.sai == True)]
    out.append("### Funil (blocos com aviso E2/sem_nivel e footprint da Bybit, desde 2020-03-26)\n")
    out.append("| grupo | lado | avisos | preencheram | com presos 30 min | com presos 5 min confirmados |")
    out.append("|---|---|---|---|---|---|")
    for g in ("E2", "sem_nivel"):
        for lado in ("compra", "venda"):
            s = base[(base.grupo == g) & (base.lado == lado)]
            p = s[s.preencheu == True]
            out.append(f"| {g} | {lado} | {len(s)} | {len(p)} | {int(p.presos30.sum())} | {int(p.presos5.sum())} |")
    out.append("")
    ok = base[base.preencheu == True]
    vered = {}
    for marca, nome in (("presos30", "P30 (principal)"), ("presos5", "P5 (informativo)")):
        out.append(f"### Resultado {nome} — R líquido por trade (regra de gestão da E2)\n")
        out.append("(i) cauda na borda SEM presos; (ii) presos SEM borda (cauda sem nível + presos); (iii) direção "
                   "sorteada (cd do estudo E2).\n")
        out.append("| lado | período | n | acerto | média R ± EP | (i) (n) | (ii) (n) | (iii) | ≥i+2EP | ≥ii+2EP | ≥iii+2EP | real > sorteios |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for lado in (None, "compra", "venda"):
            linhas = {}
            for per, _, _ in PERIODOS:
                q = ok[ok.periodo == per]
                if lado:
                    q = q[q.lado == lado]
                s = q[(q.grupo == "E2") & q[marca]]
                ci = q[(q.grupo == "E2") & ~q[marca]]
                cii = q[(q.grupo == "sem_nivel") & q[marca]]
                e, ei, eii, eiii = est(s.res_r), est(ci.res_r), est(cii.res_r), est(s.cd)
                oks = [e["n"] > 1 and not np.isnan(c) and e["media"] >= c + 2 * e["se"]
                       for c in (ei["media"], eii["media"], eiii["media"])]
                srt = sorteios_conjunto(s, rng)
                acima = f"{int((e['media'] > srt).sum())}/{len(srt)}" if len(srt) else "-"
                out.append(f"| {lado or 'compra+venda'} | {per} | {e['n']} | {pct(e['acerto'])} | {f(e['media'])} ± "
                           f"{f(e['se'])} | {f(ei['media'])} ({ei['n']}) | {f(eii['media'])} ({eii['n']}) | "
                           f"{f(eiii['media'])} | " + " | ".join("sim" if o else "não" for o in oks) + f" | {acima} |")
                linhas[per] = (e, oks)
            vered[f"E2+{marca} {lado or 'compra+venda'}"] = veredito(linhas)
        out.append("")
    return out, vered


# ---------------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--processos", type=int, default=6)
    a = ap.parse_args(argv)
    t0 = time.time()
    arrs, eventos = [], {tf: [] for tf in TFS}
    with Pool(a.processos) as pool:
        for res in pool.imap(processar_mes, _meses()):
            if res is None:
                continue
            arr, evs = res
            arrs.append(arr)
            for tf in TFS:
                eventos[tf].extend(evs[tf])
            print(f"  mês {len(arrs)} minutos={len(arr)} eventos 30m={len(eventos['30m'])} 5m={len(eventos['5m'])} "
                  f"({time.time() - t0:.0f}s)", flush=True)
    M = Minutos(np.vstack(arrs))
    print(f"minutos: {len(M.ts)}; buracos > 60 min: {len(M.gap_ini)} ({time.time() - t0:.0f}s)", flush=True)
    df, funil = rodar_presos(M, eventos)
    df.to_csv(SAIDA_CSV, index=False)
    e2 = marcar_e2(M, eventos)
    e2.to_csv(SAIDA_E2, index=False)
    md1, v1 = resumo_presos(df, funil)
    md2, v2 = resumo_e2(e2)
    buracos = [(datetime.fromtimestamp(int(g), tz=timezone.utc).strftime("%Y-%m-%d %H:%M"), int(h - g) // 60)
               for g, h in zip(M.gap_ini, M.gap_fim)]
    cab = ["# Presos no footprint 2020–2026 e TPO E2 + presos\n",
           f"Gerado por `scripts/estudo_presos_2020.py` em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC (regra exata e "
           "critério no docstring, escritos antes de rodar; nenhum parâmetro iterado; holdout lido uma vez). Footprint "
           f"por minuto da Bybit BTCUSDT linear, {INICIO} a {FIM}: {len(M.ts)} minutos. Custo real, leitura pessimista "
           "em 1 min, funding linear (a tabela de funding termina em 2026-09-11; depois conta zero).\n",
           f"Buracos > 60 min sem minuto gravado: {len(buracos)} "
           + (("(" + "; ".join(f"{a} por {b} min" for a, b in buracos[:15]) + (" ..." if len(buracos) > 15 else "") + ")")
              if buracos else "") + "\n"]
    vered_md = ["## Veredito pelo critério\n"] + [f"- **{k}: {v}**" + (" — " + "; ".join(m) if m else "")
                                                 for k, (v, m) in {**v1, **v2}.items()] + [""]
    conclusao = ""
    if SAIDA_MD.exists():
        txt = SAIDA_MD.read_text(encoding="utf-8")
        i = txt.find("## Conclusão")
        if i >= 0:
            conclusao = txt[i:]
    SAIDA_MD.write_text("\n".join(cab + vered_md + md1 + md2) + ("\n" + conclusao if conclusao else ""), encoding="utf-8")
    for k, (v, m) in {**v1, **v2}.items():
        print(f"{k}: {v} {m}")
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
