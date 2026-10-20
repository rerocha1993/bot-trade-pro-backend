# scripts/estudo_niveis_tpo.py
"""
ESTUDO DE QUALIDADE DOS NÍVEIS DE TPO (BTCUSDT 5m, Binance, 2020-01 a 2026-09).

Não é backtest de estratégia: mede, nível por nível, se o preço REAGE mais que o acaso quando toca o nível
pela primeira vez vindo de longe. A régua é um conjunto de níveis sorteados (6 por dia) medidos do mesmo jeito.

Níveis (todos conhecidos ANTES do toque):
  a) dia anterior (D-1): POC, VAH, VAL, máxima, mínima; máxima/mínima/POC de cada sessão (asia, europa, america)
  b) sessões de HOJE já encerradas: Ásia de D vale a partir das 08:00 UTC; Europa de D a partir das 13:30 UTC
  c) naked POCs diários (POC de dias <= D-2 não tocados por nenhum dia até D-1), os 5 mais próximos do fechamento de D-1
  d) semana-calendário anterior (seg–dom, merge): POC, VAH, VAL, máxima, mínima; mês-calendário anterior (merge):
     POC, VAH, VAL; ano (merge dos últimos 365 dias até D-1): POC, VAH, VAL
  e) aberturas: do dia D, da semana corrente (segunda 00:00 UTC), do mês corrente
  f) CONTROLE: 6 níveis sorteados por dia, uniformes em [mínima, máxima] dos 5 dias anteriores (semente fixa)

Toque: candle de 5 min do dia D em que low <= nível <= high, com o fechamento de algum dos 12 candles anteriores (1h)
a >= 0,5% do nível. Só o primeiro toque assim de cada nível por dia (após o horário em que o nível passa a valer).
Lado: o fechamento mais distante entre os 12 anteriores estava acima -> suporte (reação esperada = alta);
abaixo -> resistência (reação esperada = queda).

Reação: R = 0,3% e 0,6% do nível. Corrida 1:1: a partir do candle seguinte ao toque, anda R a favor antes de andar R
contra? Corrida 2:1: 2R a favor antes de 1R contra. Limite de 48 candles (4h); sem decisão = neutro.
Pessimista: se favor e contra cabem no mesmo candle, conta contra; se o PRÓPRIO candle do toque já atravessa o nível em R,
conta contra (a limitada no nível teria sido executada e estopada).

Custo de ida e volta: 0,06% (= 0,2 R para R=0,3%; 0,1 R para R=0,6%).
Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09. Sem iteração de parâmetros.

Saídas: data/estudo_niveis_tpo.csv (um toque por linha) e data/estudo_niveis_tpo_resumo.md (tabelas).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from conselho.tpo import DIA_MS, Perfil, dias, merge, naked_pocs, sessoes  # noqa: E402

CSV = RAIZ / "data" / "historico" / "BTCUSDT_binance_5m.csv"
SAIDA_CSV = RAIZ / "data" / "estudo_niveis_tpo.csv"
SAIDA_MD = RAIZ / "data" / "estudo_niveis_tpo_resumo.md"

INICIO_DADOS_MS = int(pd.Timestamp("2019-01-01", tz="UTC").timestamp() * 1000)   # lookback do merge anual
INICIO_ESTUDO_MS = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp() * 1000)
PERIODOS = [
    ("treino", "2020-01-01", "2023-12-31"),
    ("validacao", "2024-01-01", "2025-06-30"),
    ("holdout", "2025-07-01", "2026-09-30"),
]
LONGE_PCT = 0.005
JANELA_LONGE = 12
LIMITE = 48
RS = {"03": 0.003, "06": 0.006}
CUSTO = 0.0006
SEMENTE = 20261020
N_CONTROLE = 6
N_NAKED = 5
MIN_DEC = 30  # mínimo de toques decididos por período para a leitura de consistência

ORDEM_TIPOS = [
    "controle",
    "d1_POC", "d1_VAH", "d1_VAL", "d1_max", "d1_min",
    "d1_asia_POC", "d1_asia_max", "d1_asia_min",
    "d1_europa_POC", "d1_europa_max", "d1_europa_min",
    "d1_america_POC", "d1_america_max", "d1_america_min",
    "hoje_asia_POC", "hoje_asia_max", "hoje_asia_min",
    "hoje_europa_POC", "hoje_europa_max", "hoje_europa_min",
    "naked_POC",
    "sem_POC", "sem_VAH", "sem_VAL", "sem_max", "sem_min",
    "mes_POC", "mes_VAH", "mes_VAL",
    "ano_POC", "ano_VAH", "ano_VAL",
    "abert_dia", "abert_semana", "abert_mes",
]


# ---------------------------------------------------------------------------------------------------- dados
def carregar():
    df = pd.read_csv(CSV)
    df = df[df["timestamp"] >= INICIO_DADOS_MS].reset_index(drop=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def sessao_do_minuto(m: int) -> str:
    if m < 8 * 60:
        return "asia"
    if m < 13 * 60 + 30:
        return "europa"
    if m < 20 * 60:
        return "america"
    return "noite"


def segunda_de(dnum: int) -> int:
    """Número do dia (desde 1970-01-01, quinta) da segunda-feira da semana de `dnum`."""
    return dnum - ((dnum + 3) % 7)


def mes_de(dnum: int) -> tuple[int, int]:
    t = pd.Timestamp(dnum * DIA_MS, unit="ms", tz="UTC")
    return t.year, t.month


def primeiro_dia_do_mes(ano: int, mes: int) -> int:
    return int(pd.Timestamp(year=ano, month=mes, day=1, tz="UTC").timestamp() * 1000) // DIA_MS


# ---------------------------------------------------------------------------------------------------- níveis
class Niveis:
    """Monta a lista de níveis de cada dia D usando só perfis de dias anteriores (e sessões de D já fechadas)."""

    def __init__(self, perfis: list[Perfil], ts: np.ndarray, op: np.ndarray):
        self.por_dia = {p.inicio // DIA_MS: p for p in perfis}
        self.perfis = perfis
        self.idx_de = {p.inicio // DIA_MS: i for i, p in enumerate(perfis)}
        self.ts = ts
        self.op = op
        self.dnum = ts // DIA_MS
        self.rng = np.random.default_rng(SEMENTE)
        self._semana = {}
        self._mes = {}
        self.naked: list[dict] = []     # POCs de dias <= D-2 não tocados até D-1
        self._naked_ate = None

    # naked POCs, incremental (equivalente a naked_pocs(perfis, ate=i), verificado em verificar_naked)
    def _avancar_naked(self, i: int):
        """Deixa self.naked = naked_pocs(perfis, ate=i)."""
        if self._naked_ate is None:
            self._naked_ate = 1
            self.naked = []
        while self._naked_ate < i:
            j = self._naked_ate  # perfil j passa a ser "anterior": entra o POC de j-1 e filtra-se pelo range de j
            pj = self.perfis[j]
            self.naked.append({"preco": self.perfis[j - 1].poc(), "dia_ms": self.perfis[j - 1].inicio})
            self.naked = [x for x in self.naked if not (pj.minima <= x["preco"] <= pj.maxima)]
            self._naked_ate = j + 1

    def verificar_naked(self, i: int):
        self._avancar_naked(i)
        ref = naked_pocs(self.perfis, ate=i)
        assert [x["preco"] for x in ref] == [x["preco"] for x in self.naked], f"naked divergente em i={i}"

    def _perfis_entre(self, d0: int, d1: int) -> list[Perfil]:
        return [self.por_dia[d] for d in range(d0, d1 + 1) if d in self.por_dia]

    def semana_anterior(self, dnum: int):
        seg = segunda_de(dnum)
        if seg not in self._semana:
            ps = self._perfis_entre(seg - 7, seg - 1)
            self._semana[seg] = merge(ps) if ps else None
        return self._semana[seg]

    def mes_anterior(self, dnum: int):
        ano, mes = mes_de(dnum)
        chave = (ano, mes)
        if chave not in self._mes:
            a0 = primeiro_dia_do_mes(ano, mes)
            ano_p, mes_p = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
            ps = self._perfis_entre(primeiro_dia_do_mes(ano_p, mes_p), a0 - 1)
            self._mes[chave] = merge(ps) if ps else None
        return self._mes[chave]

    def abertura_desde(self, dnum0: int) -> float | None:
        k = int(np.searchsorted(self.dnum, dnum0))
        return float(self.op[k]) if k < len(self.op) else None

    def do_dia(self, dnum: int) -> list[tuple[str, float, int]] | None:
        """Lista (tipo, preço, minuto a partir do qual vale). None se faltar o dia anterior."""
        if dnum - 1 not in self.por_dia or dnum not in self.por_dia:
            return None
        out = []
        p1 = self.por_dia[dnum - 1]
        nv = p1.niveis()
        out += [("d1_POC", nv["POC"], 0), ("d1_VAH", nv["VAH"], 0), ("d1_VAL", nv["VAL"], 0),
                ("d1_max", nv["maxima"], 0), ("d1_min", nv["minima"], 0)]
        for nome, s in sessoes(p1).items():
            out += [(f"d1_{nome}_POC", s.poc(), 0), (f"d1_{nome}_max", s.maxima, 0), (f"d1_{nome}_min", s.minima, 0)]
        # sessões de hoje, já fechadas
        sh = sessoes(self.por_dia[dnum])
        if "asia" in sh:
            s = sh["asia"]
            out += [("hoje_asia_POC", s.poc(), 480), ("hoje_asia_max", s.maxima, 480), ("hoje_asia_min", s.minima, 480)]
        if "europa" in sh:
            s = sh["europa"]
            out += [("hoje_europa_POC", s.poc(), 810), ("hoje_europa_max", s.maxima, 810), ("hoje_europa_min", s.minima, 810)]
        # naked POCs
        i = self.idx_de[dnum]
        self._avancar_naked(i)
        fech = p1.fechamento
        for x in sorted(self.naked, key=lambda x: abs(x["preco"] - fech))[:N_NAKED]:
            out.append(("naked_POC", x["preco"], 0))
        # semana anterior
        ps = self.semana_anterior(dnum)
        if ps is not None:
            nv = ps.niveis()
            out += [("sem_POC", nv["POC"], 0), ("sem_VAH", nv["VAH"], 0), ("sem_VAL", nv["VAL"], 0),
                    ("sem_max", nv["maxima"], 0), ("sem_min", nv["minima"], 0)]
        pm = self.mes_anterior(dnum)
        if pm is not None:
            val, vah = pm.area_valor()
            out += [("mes_POC", pm.poc(), 0), ("mes_VAH", vah, 0), ("mes_VAL", val, 0)]
        pa = self._perfis_entre(dnum - 365, dnum - 1)
        if len(pa) >= 300:
            pa = merge(pa)
            val, vah = pa.area_valor()
            out += [("ano_POC", pa.poc(), 0), ("ano_VAH", vah, 0), ("ano_VAL", val, 0)]
        # aberturas
        out.append(("abert_dia", self.por_dia[dnum].abertura, 0))
        ab = self.abertura_desde(segunda_de(dnum))
        if ab is not None:
            out.append(("abert_semana", ab, 0))
        ano, mes = mes_de(dnum)
        ab = self.abertura_desde(primeiro_dia_do_mes(ano, mes))
        if ab is not None:
            out.append(("abert_mes", ab, 0))
        # controle: 6 sorteados em [mínima, máxima] dos 5 dias anteriores
        p5 = self._perfis_entre(dnum - 5, dnum - 1)
        lo = min(p.minima for p in p5)
        hi = max(p.maxima for p in p5)
        for v in self.rng.uniform(lo, hi, N_CONTROLE):
            out.append(("controle", float(v), 0))
        return out


# ---------------------------------------------------------------------------------------------------- toques
def reacao(hi: np.ndarray, lo: np.ndarray, k: int, nivel: float, lado: str, r: float, mult: float,
           stop_no_toque: bool = True, direcao: str = "reacao"):
    """
    +1 alvo (mult*R) antes do stop (R), -1 contra, 0 sem decisão em LIMITE candles.
    direcao="reacao": suporte -> alta; "continuacao": suporte -> queda (atravessa o nível).
    stop_no_toque=True: o próprio candle do toque já conta para o stop (pessimista); False = regra literal
    (tudo a partir do candle seguinte).
    """
    fim = k + LIMITE + 1
    k0 = k if stop_no_toque else k + 1
    alta = (lado == "suporte") == (direcao == "reacao")
    if alta:
        favor = nivel * (1 + mult * r)
        contra = nivel * (1 - r)
        f = np.flatnonzero(hi[k + 1:fim] >= favor)
        c = np.flatnonzero(lo[k0:fim] <= contra)
    else:
        favor = nivel * (1 - mult * r)
        contra = nivel * (1 + r)
        f = np.flatnonzero(lo[k + 1:fim] <= favor)
        c = np.flatnonzero(hi[k0:fim] >= contra)
    if c.size:
        c = c + (k0 - k)
    fi = int(f[0]) + 1 if f.size else None
    ci = int(c[0]) if c.size else None
    if fi is None and ci is None:
        return 0, None
    if ci is None:
        return 1, fi
    if fi is None:
        return -1, ci
    return (1, fi) if fi < ci else (-1, ci)


def rodar():
    t0 = time.time()
    df = carregar()
    ts = df["timestamp"].to_numpy(np.int64)
    op = df["open"].to_numpy(float)
    hi = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    cl = df["close"].to_numpy(float)
    candles = df[["timestamp", "open", "high", "low", "close", "volume"]].to_numpy(float)
    print(f"candles: {len(df):,} de {pd.Timestamp(ts[0], unit='ms')} a {pd.Timestamp(ts[-1], unit='ms')}")

    perfis = dias(candles)
    print(f"perfis diários: {len(perfis)} ({time.time() - t0:.0f}s)")
    niv = Niveis(perfis, ts, op)
    for i in (5, 400, 1200):
        if i < len(perfis):
            niv.verificar_naked(i)

    dnum = ts // DIA_MS
    minuto = ((ts % DIA_MS) // 60000).astype(int)
    dias_estudo = [d for d in sorted(niv.por_dia) if d * DIA_MS >= INICIO_ESTUDO_MS]
    linhas = []
    n_dias = 0
    for d in dias_estudo:
        a = int(np.searchsorted(dnum, d))
        b = int(np.searchsorted(dnum, d + 1))
        if a < JANELA_LONGE or b + LIMITE + 1 > len(ts) or b - a < 100:
            continue
        niveis = niv.do_dia(d)
        if not niveis:
            continue
        n_dias += 1
        n = b - a
        W = sliding_window_view(cl[a - JANELA_LONGE:b - 1], JANELA_LONGE)  # W[i] = fechamentos dos 12 candles antes de a+i
        assert W.shape[0] == n
        mins = minuto[a:b]
        data = pd.Timestamp(d * DIA_MS, unit="ms", tz="UTC")
        fds = data.dayofweek >= 5
        for tipo, L, valido_min in niveis:
            toca = (lo[a:b] <= L) & (hi[a:b] >= L)
            valido = mins >= valido_min
            dif = (W - L) / L
            longe = np.abs(dif).max(axis=1) >= LONGE_PCT
            ok = toca & valido & longe
            if not ok.any():
                continue
            i = int(np.argmax(ok))
            k = a + i
            previos = int((toca & valido)[:i].sum())
            j = int(np.argmax(np.abs(dif[i])))
            lado = "suporte" if dif[i][j] > 0 else "resistencia"
            linha = {
                "data": data.strftime("%Y-%m-%d"), "dia_semana": int(data.dayofweek), "fim_de_semana": bool(fds),
                "tipo": tipo, "nivel": round(L, 2), "lado": lado, "ts_toque": int(ts[k]),
                "hora_utc": int(mins[i] // 60), "sessao": sessao_do_minuto(int(mins[i])),
                "dist_1h_pct": round(abs(dif[i][j]) * 100, 3), "toques_previos_dia": previos,
                "fech_toque_pct": round((cl[k] - L) / L * 100, 3),
            }
            for rk, r in RS.items():
                for fmt, mult in (("11", 1.0), ("21", 2.0)):
                    res, nb = reacao(hi, lo, k, L, lado, r, mult)
                    linha[f"r{rk}_{fmt}"] = res
                    linha[f"r{rk}_{fmt}_candles"] = nb if nb is not None else -1
                    # regra literal da especificação: stop só a partir do candle seguinte
                    linha[f"r{rk}_{fmt}_sp"] = reacao(hi, lo, k, L, lado, r, mult, stop_no_toque=False)[0]
                    # continuação (atravessar o nível), mesma pessimismo — hipótese pós-hoc
                    linha[f"c{rk}_{fmt}"] = reacao(hi, lo, k, L, lado, r, mult, direcao="continuacao")[0]
                linha[f"stop_no_toque_{rk}"] = bool(
                    (lo[k] <= L * (1 - r)) if lado == "suporte" else (hi[k] >= L * (1 + r)))
            linhas.append(linha)
        if n_dias % 365 == 0:
            print(f"  {data.date()} dias={n_dias} toques={len(linhas)} ({time.time() - t0:.0f}s)")

    out = pd.DataFrame(linhas)
    out["periodo"] = ""
    for nome, a, z in PERIODOS:
        m = (out["data"] >= a) & (out["data"] <= z)
        out.loc[m, "periodo"] = nome
    out = out[out["periodo"] != ""].reset_index(drop=True)
    SAIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(SAIDA_CSV, index=False)
    print(f"toques: {len(out):,} em {n_dias} dias -> {SAIDA_CSV} ({time.time() - t0:.0f}s)")
    escrever_resumo(out)
    print(f"resumo -> {SAIDA_MD} ({time.time() - t0:.0f}s)")


# ---------------------------------------------------------------------------------------------------- resumo
def estat(df: pd.DataFrame, col: str, custo_r: float, mult: float) -> dict:
    v = df[col].to_numpy()
    n = len(v)
    dec = int((v != 0).sum())
    w = int((v == 1).sum())
    if dec == 0:
        return {"n": n, "dec": dec, "p": np.nan, "se": np.nan, "bruto": np.nan, "liq": np.nan}
    p = w / dec
    se = float(np.sqrt(p * (1 - p) / dec))
    bruto = (mult + 1) * p - 1
    return {"n": n, "dec": dec, "p": p, "se": se, "bruto": bruto, "liq": bruto - custo_r}


REGRAS = {"principal": ("r", ""), "literal": ("r", "_sp"), "continuacao": ("c", "")}


def coluna(regra: str, rk: str, fmt: str) -> str:
    pre, suf = REGRAS[regra]
    return f"{pre}{rk}_{fmt}{suf}"


def tabela_periodo(df: pd.DataFrame, rk: str, periodo: str, regra: str = "principal") -> tuple[pd.DataFrame, dict]:
    """Linhas tipo×lado com n, p e líquido nas duas corridas; ★ = melhor que o controle por >= 2 EP, ▼ = pior."""
    custo_r = CUSTO / RS[rk]
    sub = df[df["periodo"] == periodo]
    regs = []
    ctrl = {}
    for lado in ("suporte", "resistencia"):
        c = sub[(sub["tipo"] == "controle") & (sub["lado"] == lado)]
        ctrl[lado] = {"11": estat(c, coluna(regra, rk, "11"), custo_r, 1.0),
                      "21": estat(c, coluna(regra, rk, "21"), custo_r, 2.0)}
    for tipo in ORDEM_TIPOS:
        for lado in ("suporte", "resistencia"):
            s = sub[(sub["tipo"] == tipo) & (sub["lado"] == lado)]
            if len(s) == 0:
                continue
            e11 = estat(s, coluna(regra, rk, "11"), custo_r, 1.0)
            e21 = estat(s, coluna(regra, rk, "21"), custo_r, 2.0)
            reg = {"periodo": periodo, "R": rk, "tipo": tipo, "lado": lado, "n": e11["n"], "dec11": e11["dec"],
                   "p11": e11["p"], "se11": e11["se"], "liq11": e11["liq"], "dec21": e21["dec"], "p21": e21["p"],
                   "se21": e21["se"], "liq21": e21["liq"], "sig11": "", "sig21": ""}
            if tipo != "controle":
                for fmt, e in (("11", e11), ("21", e21)):
                    c = ctrl[lado][fmt]
                    if np.isnan(e["p"]) or np.isnan(c["p"]):
                        continue
                    sep = float(np.sqrt(e["se"] ** 2 + c["se"] ** 2))
                    if sep > 0 and e["p"] - c["p"] >= 2 * sep:
                        reg[f"sig{fmt}"] = "★"
                    elif sep > 0 and c["p"] - e["p"] >= 2 * sep:
                        reg[f"sig{fmt}"] = "▼"
            regs.append(reg)
    return pd.DataFrame(regs), ctrl


def fmt_p(p, se):
    return "-" if np.isnan(p) else f"{p * 100:.1f}±{se * 100:.1f}"


def fmt_r(x):
    return "-" if (x is None or np.isnan(x)) else f"{x:+.3f}"


def md_tabela(t: pd.DataFrame) -> str:
    linhas = ["| tipo | lado | n | dec | reação 1:1 % | líq 1:1 (R) | reação 2:1 % | líq 2:1 (R) |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for _, r in t.iterrows():
        linhas.append(f"| {r['tipo']} | {r['lado'][:3]} | {r['n']} | {r['dec11']} | {fmt_p(r['p11'], r['se11'])}{r['sig11']} | "
                      f"{fmt_r(r['liq11'])} | {fmt_p(r['p21'], r['se21'])}{r['sig21']} | {fmt_r(r['liq21'])} |")
    return "\n".join(linhas)


def todas_as_tabelas(df: pd.DataFrame, regra: str) -> pd.DataFrame:
    return pd.concat([tabela_periodo(df, rk, nome, regra)[0] for rk in RS for nome, _, _ in PERIODOS], ignore_index=True)


def consistencia(todas: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por tipo×lado×R×corrida com o líquido nos 3 períodos (só com >= MIN_DEC decididos em cada um)."""
    cons = []
    for rk in RS:
        for fmt in ("11", "21"):
            t = todas[todas["R"] == rk]
            for (tipo, lado), g in t.groupby(["tipo", "lado"]):
                if tipo == "controle":
                    continue
                g = g.set_index("periodo")
                if any(p not in g.index for p, _, _ in PERIODOS):
                    continue
                liqs = [float(g.loc[p, f"liq{fmt}"]) for p, _, _ in PERIODOS]
                decs = [int(g.loc[p, f"dec{fmt}"]) for p, _, _ in PERIODOS]
                sigs = [str(g.loc[p, f"sig{fmt}"]) for p, _, _ in PERIODOS]
                if any(np.isnan(x) for x in liqs) or min(decs) < MIN_DEC:
                    continue
                cons.append({"R": rk, "corrida": "1:1" if fmt == "11" else "2:1", "tipo": tipo, "lado": lado,
                             "n": int(g["n"].sum()), "treino": liqs[0], "validacao": liqs[1], "holdout": liqs[2],
                             "sigs": "".join(sigs), "min": min(liqs), "positivo_3": all(x > 0 for x in liqs)})
    return pd.DataFrame(cons)


def md_consistencia(cons: pd.DataFrame, titulo: str, top: int = 5) -> list[str]:
    partes = [f"### {titulo}\n"]
    if not len(cons):
        partes.append("(sem linhas)\n")
        return partes
    pos = cons[cons["positivo_3"]].sort_values("min", ascending=False)
    partes.append(f"**Líquido positivo nos 3 períodos: {len(pos)} combinações (tipo×lado×R×corrida) de {len(cons)}.**\n")
    cab = "| R | corrida | tipo | lado | n | treino | validação | holdout | min | ★▼ |\n|---|---|---|---|---:|---:|---:|---:|---:|---|"
    if len(pos):
        partes.append(cab)
        for _, r in pos.iterrows():
            partes.append(f"| {RS[r['R']] * 100:.1f}% | {r['corrida']} | {r['tipo']} | {r['lado'][:3]} | {r['n']} | {fmt_r(r['treino'])} | "
                          f"{fmt_r(r['validacao'])} | {fmt_r(r['holdout'])} | {fmt_r(r['min'])} | {r['sigs']} |")
        partes.append("")
    for rk in RS:
        partes.append(f"Top {top} por pior período, R = {RS[rk] * 100:.1f}%:\n")
        partes.append(cab)
        for _, r in cons[cons["R"] == rk].sort_values("min", ascending=False).head(top).iterrows():
            partes.append(f"| {RS[r['R']] * 100:.1f}% | {r['corrida']} | {r['tipo']} | {r['lado'][:3]} | {r['n']} | {fmt_r(r['treino'])} | "
                          f"{fmt_r(r['validacao'])} | {fmt_r(r['holdout'])} | {fmt_r(r['min'])} | {r['sigs']} |")
        partes.append("")
    return partes


def md_painel(todas: pd.DataFrame, rk: str) -> list[str]:
    """Painel compacto: tipo×lado, líquido 1:1 e 2:1 nos três períodos (t/v/h) com ★/▼ contra o controle."""
    t = todas[todas["R"] == rk]
    partes = ["| tipo | lado | n | líq 1:1 treino | val | hold | líq 2:1 treino | val | hold |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for tipo in ORDEM_TIPOS:
        for lado in ("suporte", "resistencia"):
            g = t[(t["tipo"] == tipo) & (t["lado"] == lado)].set_index("periodo")
            if not len(g):
                continue
            cel = []
            for fmt in ("11", "21"):
                for p, _, _ in PERIODOS:
                    if p in g.index:
                        cel.append(f"{fmt_r(g.loc[p, f'liq{fmt}'])}{g.loc[p, f'sig{fmt}']} ({g.loc[p, f'dec{fmt}']})")
                    else:
                        cel.append("-")
            partes.append(f"| {tipo} | {lado[:3]} | {int(g['n'].sum())} | " + " | ".join(cel) + " |")
    return partes


def escrever_resumo(df: pd.DataFrame):
    partes = []
    partes.append("# Estudo de qualidade dos níveis de TPO — BTCUSDT 5m (Binance), 2020-01 a 2026-09\n")
    partes.append("Gerado por `scripts/estudo_niveis_tpo.py`. Um toque por linha em `data/estudo_niveis_tpo.csv`.\n")
    partes.append("## Regra exata\n")
    partes.append(
        "- Dados: candles de 5 min UTC; perfis diários de TPO por `core/tpo_sessao.py` (blocos de 30 min, faixa de 0,1% do preço).\n"
        "- Níveis do dia D (todos conhecidos antes do toque): D-1 → POC, VAH, VAL, máxima, mínima e máx/mín/POC das sessões "
        "asia (00–08 UTC), europa (08–13:30), america (13:30–20); sessões de HOJE já fechadas → Ásia de D vale a partir das 08:00, "
        "Europa de D a partir das 13:30; naked POCs (POC de dias ≤ D-2 nunca tocados até D-1, os 5 mais próximos do fechamento de D-1); "
        "semana-calendário anterior (seg–dom, merge) → POC, VAH, VAL, máx, mín; mês-calendário anterior (merge) → POC, VAH, VAL; "
        "ano (merge dos últimos 365 dias até D-1) → POC, VAH, VAL; aberturas do dia D, da semana corrente (segunda 00:00 UTC) e do mês corrente.\n"
        f"- Controle: {N_CONTROLE} níveis sorteados por dia (uniforme em [mínima, máxima] dos 5 dias anteriores, semente {SEMENTE}), medidos igual.\n"
        f"- Toque: candle de D com low ≤ nível ≤ high e o fechamento de algum dos {JANELA_LONGE} candles anteriores a ≥ {LONGE_PCT * 100:.1f}% do nível. "
        "Só o primeiro toque assim de cada nível por dia, respeitando a hora em que o nível passa a valer. Lado pelo fechamento mais distante "
        "da última hora: acima → suporte (reação esperada = alta), abaixo → resistência (reação = queda). `toques_previos_dia` no CSV conta "
        "candles anteriores do dia que encostaram no nível sem vir de longe.\n"
        f"- Reação: R = 0,3% e 0,6% do nível. Corrida 1:1 = a partir do candle seguinte ao toque, anda R a favor antes de R contra; "
        f"2:1 = 2R a favor antes de 1R contra. Limite {LIMITE} candles (4h); sem decisão = neutro (fora de p). "
        "Pessimista: favor e contra no mesmo candle → contra; se o próprio candle do toque já atravessou o nível em R → contra.\n"
        f"- p = reações / decididos; EP = sqrt(p(1-p)/decididos). Bruto por toque: 1:1 = 2p−1; 2:1 = 3p−1. Líquido = bruto − custo de ida e volta "
        f"{CUSTO * 100:.2f}% em R ({CUSTO / RS['03']:.1f} R para R=0,3%; {CUSTO / RS['06']:.1f} R para R=0,6%).\n"
        "- ★ = p do nível ≥ 2 EP acima do controle do mesmo lado/período/corrida; ▼ = ≥ 2 EP abaixo.\n"
        "- Períodos: treino 2020-01..2023-12, validação 2024-01..2025-06, holdout 2025-07..2026-09. Nenhum parâmetro foi iterado.\n"
    )
    nd = df.groupby("periodo")["data"].nunique()
    partes.append("## Volume\n")
    partes.append("| período | dias | toques | toques/dia |\n|---|---:|---:|---:|")
    for nome, _, _ in PERIODOS:
        n = int((df["periodo"] == nome).sum())
        partes.append(f"| {nome} | {nd.get(nome, 0)} | {n} | {n / max(nd.get(nome, 1), 1):.1f} |")
    partes.append("")

    todas = todas_as_tabelas(df, "principal")
    todas_sp = todas_as_tabelas(df, "literal")
    todas_c = todas_as_tabelas(df, "continuacao")
    cons_p, cons_sp, cons_c = consistencia(todas), consistencia(todas_sp), consistencia(todas_c)
    partes.append("## Veredito\n")
    for nome, c in (("regra principal (pessimista)", cons_p), ("regra literal da especificação", cons_sp),
                    ("continuação (pós-hoc)", cons_c)):
        npos = int(c["positivo_3"].sum()) if len(c) else 0
        melhor = c.sort_values("min", ascending=False).head(1)
        txt = ""
        if len(melhor):
            m = melhor.iloc[0]
            txt = (f" Melhor pior-período: {m['tipo']}/{m['lado'][:3]} R={RS[m['R']] * 100:.1f}% {m['corrida']} "
                   f"({fmt_r(m['treino'])} / {fmt_r(m['validacao'])} / {fmt_r(m['holdout'])} R).")
        partes.append(f"- {nome}: **{npos} de {len(c)}** combinações tipo×lado×R×corrida com líquido positivo nos 3 períodos "
                      f"(mín. {MIN_DEC} decididos por período).{txt}")
    partes.append("")

    partes.append("## Regra principal (pessimista) — tabelas completas por período\n")
    for rk in RS:
        partes.append(f"### R = {RS[rk] * 100:.1f}% (custo {CUSTO / RS[rk]:.1f} R por toque)\n")
        for nome, _, _ in PERIODOS:
            t, _ = tabela_periodo(df, rk, nome, "principal")
            partes.append(f"#### {nome}\n")
            partes.append(md_tabela(t))
            partes.append("")

    partes.append("## Painéis compactos: líquido por toque (R) nos três períodos, (n decididos)\n")
    partes.append("★/▼ = p do nível ≥ 2 EP acima/abaixo do controle do mesmo lado, período e corrida.\n")
    for regra, tt, titulo in (("principal", todas, "Regra principal (stop já conta no candle do toque)"),
                              ("literal", todas_sp, "Regra literal da especificação (tudo a partir do candle seguinte)"),
                              ("continuacao", todas_c, "CONTINUAÇÃO (atravessar o nível) — hipótese pós-hoc, mesma pessimismo")):
        for rk in RS:
            partes.append(f"### {titulo} — R = {RS[rk] * 100:.1f}%\n")
            partes += md_painel(tt, rk)
            partes.append("")

    partes.append("## Consistência nos três períodos (líquido por toque, em R)\n")
    partes.append(f"Só tipo×lado com ≥ {MIN_DEC} toques decididos em cada período. `min` = pior período.\n")
    partes += md_consistencia(cons_p, "Regra principal")
    partes += md_consistencia(cons_sp, "Regra literal da especificação")
    partes += md_consistencia(cons_c, "Continuação (pós-hoc)")

    # controle como referência
    partes.append("## Controle (níveis sorteados) por período\n")
    partes.append("| R | período | lado | n | dec | reação 1:1 % | líq 1:1 | reação 2:1 % | líq 2:1 |\n|---|---|---|---:|---:|---:|---:|---:|---:|")
    for _, r in todas[todas["tipo"] == "controle"].iterrows():
        partes.append(f"| {RS[r['R']] * 100:.1f}% | {r['periodo']} | {r['lado'][:3]} | {r['n']} | {r['dec11']} | {fmt_p(r['p11'], r['se11'])} | "
                      f"{fmt_r(r['liq11'])} | {fmt_p(r['p21'], r['se21'])} | {fmt_r(r['liq21'])} |")
    partes.append("")

    # estrelas: contagem por tipo×lado
    partes.append("## Diferença do sorteio (contagem de ★ / ▼ em 3 períodos × 2 R × 2 corridas = 12 testes)\n")
    est = todas[todas["tipo"] != "controle"].groupby(["tipo", "lado"]).agg(
        n=("n", "sum"), estrelas=("sig11", lambda s: int((s == "★").sum())), setas=("sig11", lambda s: int((s == "▼").sum())),
        estrelas21=("sig21", lambda s: int((s == "★").sum())), setas21=("sig21", lambda s: int((s == "▼").sum()))).reset_index()
    est["★"] = est["estrelas"] + est["estrelas21"]
    est["▼"] = est["setas"] + est["setas21"]
    partes.append("| tipo | lado | n total | ★ | ▼ |\n|---|---|---:|---:|---:|")
    for _, r in est.sort_values(["★", "n"], ascending=False).iterrows():
        partes.append(f"| {r['tipo']} | {r['lado'][:3]} | {r['n']} | {r['★']} | {r['▼']} |")
    iguais = est[(est["★"] == 0) & (est["▼"] == 0)]
    partes.append("")
    partes.append(f"**Sem nenhuma diferença do sorteio em 12 testes:** {len(iguais)} de {len(est)} tipo×lado: " +
                  ", ".join(f"{r['tipo']}/{r['lado'][:3]}" for _, r in iguais.iterrows()) + "\n")

    # por sessão do toque e fim de semana (todos os períodos juntos; só tipos com n >= 200)
    custo03 = CUSTO / RS["03"]
    grandes = df.groupby("tipo").size()
    grandes = set(grandes[grandes >= 200].index)
    partes.append("## Por sessão do toque (três períodos juntos, R=0,3%, tipos com n ≥ 200)\n")
    partes.append("| tipo | lado | sessão | n | dec | reação 1:1 % | líq 1:1 | reação 2:1 % | líq 2:1 |\n|---|---|---|---:|---:|---:|---:|---:|---:|")
    for tipo in ORDEM_TIPOS:
        if tipo not in grandes:
            continue
        for lado in ("suporte", "resistencia"):
            for ses in ("asia", "europa", "america", "noite"):
                s = df[(df["tipo"] == tipo) & (df["lado"] == lado) & (df["sessao"] == ses)]
                if len(s) < 30:
                    continue
                e11 = estat(s, "r03_11", custo03, 1.0)
                e21 = estat(s, "r03_21", custo03, 2.0)
                partes.append(f"| {tipo} | {lado[:3]} | {ses} | {e11['n']} | {e11['dec']} | {fmt_p(e11['p'], e11['se'])} | "
                              f"{fmt_r(e11['liq'])} | {fmt_p(e21['p'], e21['se'])} | {fmt_r(e21['liq'])} |")
    partes.append("")
    partes.append("## Fim de semana × dia útil (três períodos juntos, R=0,3%, tipos com n ≥ 200)\n")
    partes.append("| tipo | lado | fds | n | dec | reação 1:1 % | líq 1:1 | reação 2:1 % | líq 2:1 |\n|---|---|---|---:|---:|---:|---:|---:|---:|")
    for tipo in ORDEM_TIPOS:
        if tipo not in grandes:
            continue
        for lado in ("suporte", "resistencia"):
            for fds in (False, True):
                s = df[(df["tipo"] == tipo) & (df["lado"] == lado) & (df["fim_de_semana"] == fds)]
                if len(s) < 30:
                    continue
                e11 = estat(s, "r03_11", custo03, 1.0)
                e21 = estat(s, "r03_21", custo03, 2.0)
                partes.append(f"| {tipo} | {lado[:3]} | {'sim' if fds else 'não'} | {e11['n']} | {e11['dec']} | "
                              f"{fmt_p(e11['p'], e11['se'])} | {fmt_r(e11['liq'])} | {fmt_p(e21['p'], e21['se'])} | {fmt_r(e21['liq'])} |")
    partes.append("")

    # diagnóstico: stops no próprio candle do toque e neutros
    partes.append("## Diagnóstico\n")
    for rk in RS:
        st = df[f"stop_no_toque_{rk}"].mean() * 100
        neu11 = (df[f"r{rk}_11"] == 0).mean() * 100
        neu21 = (df[f"r{rk}_21"] == 0).mean() * 100
        partes.append(f"- R={RS[rk] * 100:.1f}%: stop já no candle do toque em {st:.1f}% dos toques; sem decisão em 4h: "
                      f"{neu11:.1f}% (1:1), {neu21:.1f}% (2:1).")
    partes.append(f"- Distância média percorrida na última hora até o toque: {df['dist_1h_pct'].mean():.2f}% "
                  f"(mediana {df['dist_1h_pct'].median():.2f}%).")
    partes.append("")
    SAIDA_MD.write_text("\n".join(partes), encoding="utf-8")


if __name__ == "__main__":
    rodar()
