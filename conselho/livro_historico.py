"""
Leitura do histórico do livro de ordens gravado por ``conselho.coletor_livro``.

- ``carregar_dia`` / ``carregar_periodo``: registros (dicts) de uma exchange.
- ``matriz``: transforma registros em arrays numpy tempo × faixa, por lado.
- ``carregar_matrizes``: um dia inteiro, {exchange: {"bids": M, "asks": M, "ts": ..., "mid": ...}}.
- ``paredes``: faixas de um snapshot com quantidade >= fator × mediana das faixas
  à MESMA distância do mid nas últimas 24 h (histórico da mesma exchange).
- ``serie_overlay``: as "nuvens" do TRDR (Order Book Depth Overlay) num período: por passo de tempo, a soma
  por categoria de distância (0–1%, 1–2,5%, 2,5–5%, 5–10%, 10–25%) das exchanges escolhidas, a razão
  bids/asks e o lado com vantagem. Registros antigos (sem ``cat_*``) entram aproximados pelas faixas de 0,1%.
- ``top_agregado``: os Top Levels (10 maiores níveis por lado) somados entre exchanges no mesmo preço
  arredondado a 0,05%.

Só leitura de arquivos locais; nada aqui toca a internet.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

import numpy as np

from conselho.coletor_livro import (
    CATEGORIAS_PCT, EXCHANGES, N_CATEGORIAS, N_FAIXAS, N_TOP, PASTA_DADOS, ROTULOS_CATEGORIAS,
    caminho_do_dia, categorias_alcancadas, preco_da_faixa,
)

LADOS = ("bids", "asks")
JANELA_24H_S = 24 * 3600
PASSO_OVERLAY_S = 300        # um ponto por candle de 5 min
GRADE_TOP_PCT = 0.0005       # top levels de exchanges diferentes no mesmo preço a 0,05% viram um só
TOLERANCIA_TOP_S = 180       # snapshot até 3 min antes do instante pedido ainda vale


# ----------------------------------------------------------------- leitura
def _ler_jsonl_gz(caminho: str) -> List[Dict]:
    """Lê um .jsonl.gz (vários membros gzip concatenados). Linhas corrompidas são puladas."""
    if not os.path.exists(caminho):
        return []
    out: List[Dict] = []
    with gzip.open(caminho, "rb") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                out.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
    return out


def dias_disponiveis(exchange: str, raiz: str = PASTA_DADOS) -> List[str]:
    """Dias (AAAA-MM-DD) com arquivo gravado para a exchange, em ordem."""
    pasta = os.path.join(raiz, exchange)
    arquivos = glob.glob(os.path.join(pasta, "*.jsonl.gz"))
    return sorted(os.path.basename(a)[:-len(".jsonl.gz")] for a in arquivos)


def carregar_dia(exchange: str, dia: str, raiz: str = PASTA_DADOS) -> List[Dict]:
    """Registros de um dia UTC (AAAA-MM-DD) de uma exchange, ordenados por ts."""
    regs = _ler_jsonl_gz(caminho_do_dia(exchange, dia, raiz))
    regs.sort(key=lambda r: r.get("ts", 0))
    return regs


def carregar_periodo(exchange: str, ts_inicio: float, ts_fim: float, raiz: str = PASTA_DADOS) -> List[Dict]:
    """Registros com ts em [ts_inicio, ts_fim], atravessando os arquivos diários necessários."""
    d0 = datetime.fromtimestamp(ts_inicio, tz=timezone.utc).date()
    d1 = datetime.fromtimestamp(ts_fim, tz=timezone.utc).date()
    regs: List[Dict] = []
    d = d0
    while d <= d1:
        regs.extend(carregar_dia(exchange, d.strftime("%Y-%m-%d"), raiz))
        d += timedelta(days=1)
    regs = [r for r in regs if ts_inicio <= r.get("ts", -1) <= ts_fim]
    regs.sort(key=lambda r: r.get("ts", 0))
    return regs


# ----------------------------------------------------------------- matrizes
def matriz(registros: Iterable[Dict], n_faixas: int = N_FAIXAS) -> Dict[str, np.ndarray]:
    """
    Converte registros em arrays: ``ts`` (T,), ``mid`` (T,), ``bids`` (T, n), ``asks`` (T, n).

    Linha t = snapshot t; coluna i = faixa i (distância [i, i+1) × 0,1% do mid).
    Registros com número diferente de faixas são ajustados (corte ou zero à direita).
    """
    regs = list(registros)
    T = len(regs)
    ts = np.zeros(T, dtype=np.int64)
    mid = np.zeros(T, dtype=np.float64)
    lados = {lado: np.zeros((T, n_faixas), dtype=np.float64) for lado in LADOS}
    for t, r in enumerate(regs):
        ts[t] = int(r.get("ts", 0))
        mid[t] = float(r.get("mid", 0.0))
        for lado in LADOS:
            v = r.get(lado) or []
            k = min(len(v), n_faixas)
            if k:
                lados[lado][t, :k] = v[:k]
    return {"ts": ts, "mid": mid, **lados}


def carregar_matrizes(dia: str, raiz: str = PASTA_DADOS,
                      exchanges: Iterable[str] = EXCHANGES) -> Dict[str, Dict[str, np.ndarray]]:
    """Um dia inteiro: {exchange: matriz(...)}. Exchanges sem arquivo entram com T = 0."""
    return {ex: matriz(carregar_dia(ex, dia, raiz)) for ex in exchanges}


# ----------------------------------------------------------------- paredes
def mediana_por_faixa(historico: Iterable[Dict], ts_ref: Optional[float] = None,
                      janela_s: float = JANELA_24H_S, n_faixas: int = N_FAIXAS) -> Dict[str, np.ndarray]:
    """
    Mediana, por faixa, das quantidades nos snapshots do histórico com ts em
    [ts_ref - janela_s, ts_ref). Sem ts_ref usa todo o histórico. Devolve {"bids": (n,), "asks": (n,)}.
    Sem snapshots na janela devolve NaN (nenhuma parede pode ser marcada).
    """
    regs = list(historico)
    if ts_ref is not None:
        regs = [r for r in regs if ts_ref - janela_s <= r.get("ts", -1) < ts_ref]
    if not regs:
        return {lado: np.full(n_faixas, np.nan) for lado in LADOS}
    m = matriz(regs, n_faixas)
    return {lado: np.median(m[lado], axis=0) for lado in LADOS}


def paredes(snapshot: Dict, historico: Iterable[Dict], fator: float = 3.0,
            janela_s: float = JANELA_24H_S, minimo_snapshots: int = 10) -> Dict[str, List[Dict]]:
    """
    Marca as faixas do ``snapshot`` cuja quantidade é >= ``fator`` × mediana das faixas à mesma
    distância do mid nas últimas ``janela_s`` segundos do ``historico`` (mesma exchange).

    Devolve {"bids": [...], "asks": [...]}, cada item:
        {"faixa": i, "distancia_pct": (i+0.5)*faixa_pct*100, "preco": centro da faixa,
         "qtd": BTC na faixa, "mediana": mediana 24 h, "razao": qtd/mediana}
    Com menos de ``minimo_snapshots`` no histórico da janela, não marca nada (lista vazia):
    sem base de comparação não há parede, só ruído.
    """
    n = len(snapshot.get("bids") or [])
    faixa_pct = float(snapshot.get("faixa_pct", 0.001))
    mid = float(snapshot.get("mid", 0.0))
    ts_ref = snapshot.get("ts")
    regs = [r for r in historico
            if ts_ref is None or (ts_ref - janela_s <= r.get("ts", -1) < ts_ref)]
    saida: Dict[str, List[Dict]] = {lado: [] for lado in LADOS}
    if len(regs) < minimo_snapshots or n == 0:
        return saida
    medianas = mediana_por_faixa(regs, None, janela_s, n)
    for lado in LADOS:
        qtds = np.asarray(snapshot.get(lado) or [], dtype=np.float64)
        med = medianas[lado]
        for i in range(min(len(qtds), n)):
            q, m = float(qtds[i]), float(med[i])
            if not np.isfinite(m) or m <= 0 or q <= 0:
                continue
            if q >= fator * m:
                saida[lado].append({
                    "faixa": i,
                    "distancia_pct": round((i + 0.5) * faixa_pct * 100, 3),
                    "preco": round(preco_da_faixa(mid, lado, i, faixa_pct), 2),
                    "qtd": round(q, 6),
                    "mediana": round(m, 6),
                    "razao": round(q / m, 2),
                })
        saida[lado].sort(key=lambda x: -x["razao"])
    return saida


# ----------------------------------------------------------------- nuvens (overlay do TRDR)
def ultimo_ts(exchanges: Iterable[str] = EXCHANGES, raiz: str = PASTA_DADOS) -> Optional[int]:
    """Maior ts gravado entre as exchanges (olha só o último arquivo diário de cada uma). None sem dados."""
    maior: Optional[int] = None
    for ex in exchanges:
        dias = dias_disponiveis(ex, raiz)
        if not dias:
            continue
        regs = carregar_dia(ex, dias[-1], raiz)
        if regs:
            t = int(regs[-1].get("ts", 0))
            maior = t if maior is None else max(maior, t)
    return maior


def _alcance_aproximado(registro: Dict, lado: str) -> float:
    """Registro antigo: alcance estimado pela última faixa de 0,1% com quantidade (do mid, até 5%)."""
    v = registro.get(lado) or []
    faixa = float(registro.get("faixa_pct", 0.001))
    ultima = max((i for i, q in enumerate(v) if q and q > 0), default=-1)
    return round((ultima + 1) * faixa, 9)


def categorias_do_registro(registro: Dict) -> Dict:
    """
    Totais por categoria do TRDR de UM registro, por lado, e quais categorias o livro dele alcança.

    Registro novo (com ``cat_bids``/``cat_asks``): usa o que foi gravado (medido do melhor bid/ask).
    Registro antigo: aproxima somando as faixas de 0,1% (medidas do mid, só até 5%) e marca ``aproximado``;
    as categorias 5–10% e 10–25% ficam em zero e nunca contam como alcançadas.
    Devolve {"bids": [5], "asks": [5], "alcance": {"bids": [bool×5], "asks": [bool×5]}, "aproximado": bool}.
    """
    if registro.get("cat_bids") is not None and registro.get("cat_asks") is not None:
        return {
            "bids": [float(x) for x in registro["cat_bids"]][:N_CATEGORIAS],
            "asks": [float(x) for x in registro["cat_asks"]][:N_CATEGORIAS],
            "alcance": {lado: categorias_alcancadas(registro, lado) for lado in LADOS},
            "aproximado": False,
        }
    faixa = float(registro.get("faixa_pct", 0.001))
    saida: Dict = {"alcance": {}, "aproximado": True}
    for lado in LADOS:
        cats = [0.0] * N_CATEGORIAS
        for i, q in enumerate(registro.get(lado) or []):
            d = round(i * faixa, 9)          # 25 × 0,001 tem de cair em 0,025, não em 0,02499…
            for k in range(N_CATEGORIAS):
                if CATEGORIAS_PCT[k] <= d < CATEGORIAS_PCT[k + 1]:
                    cats[k] += float(q or 0.0)
                    break
        saida[lado] = cats
        alc = _alcance_aproximado(registro, lado)
        saida["alcance"][lado] = [alc >= CATEGORIAS_PCT[k + 1] for k in range(N_CATEGORIAS)]
    return saida


def _media(valores: List[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0


def serie_overlay(ts_inicio: float, ts_fim: float, exchanges: Iterable[str] = EXCHANGES,
                  raiz: str = PASTA_DADOS, passo_s: int = PASSO_OVERLAY_S, amostra: str = "media",
                  so_alcance: bool = False) -> Dict:
    """
    Série do Order Book Depth Overlay num período, somando as ``exchanges`` escolhidas.

    Os snapshots são agrupados em passos de ``passo_s`` segundos (``ts // passo_s * passo_s``, alinhado ao
    início do candle); dentro de um passo, cada exchange entra com a MÉDIA dos seus snapshots (``amostra="media"``)
    ou só com o ÚLTIMO, o do fechamento do candle (``amostra="fechamento"``, como o TRDR: a razão só vale se ficou
    até o fechamento, o que filtra ordem que aparece e some); entre exchanges, soma. Com ``so_alcance``, uma
    exchange só entra na categoria que o livro dela alcança nos dois lados (a Binance pára perto de 1%: sem isso, a
    faixa de 1–2,5% recebe um pedaço cortado e desigual dela). Para cada ponto:
        ts, mid (média dos mids das exchanges presentes), bids[5], asks[5] (BTC por categoria),
        razao[5] (bids/asks; None sem asks), forca[5] ((b-a)/(b+a) em [-1, 1]; 0 sem nada),
        vantagem[5] ('bids' | 'asks' | None), cobertura[5] (exchanges que alcançam a categoria nos dois lados),
        exchanges (presentes no passo), aproximado (algum registro antigo entrou),
        total_bids, total_asks, forca_total.
    ``fontes`` resume cada exchange: snapshots, primeiro/último ts, alcance do último registro, quantos aproximados.
    """
    exs = [e for e in exchanges]
    passo = max(1, int(passo_s))
    por_passo: Dict[int, Dict[str, List[Dict]]] = {}
    fontes: Dict[str, Dict] = {}
    for ex in exs:
        regs = carregar_periodo(ex, ts_inicio, ts_fim, raiz)
        aproximados = 0
        for r in regs:
            c = categorias_do_registro(r)
            aproximados += int(c["aproximado"])
            chave = (int(r.get("ts", 0)) // passo) * passo
            por_passo.setdefault(chave, {}).setdefault(ex, []).append({**c, "mid": float(r.get("mid", 0.0))})
        ult = regs[-1] if regs else None
        fontes[ex] = {
            "snapshots": len(regs),
            "primeiro_ts": int(regs[0]["ts"]) if regs else None,
            "ultimo_ts": int(ult["ts"]) if ult else None,
            "alcance_bids_pct": (float(ult["alcance_bids_pct"]) if ult and ult.get("alcance_bids_pct") is not None
                                 else (_alcance_aproximado(ult, "bids") if ult else None)),
            "alcance_asks_pct": (float(ult["alcance_asks_pct"]) if ult and ult.get("alcance_asks_pct") is not None
                                 else (_alcance_aproximado(ult, "asks") if ult else None)),
            "aproximados": aproximados,
        }

    pontos: List[Dict] = []
    for chave in sorted(por_passo):
        por_ex = por_passo[chave]
        bids = [0.0] * N_CATEGORIAS
        asks = [0.0] * N_CATEGORIAS
        cobertura: List[List[str]] = [[] for _ in range(N_CATEGORIAS)]
        mids: List[float] = []
        aproximado = False
        for ex in exs:
            itens = por_ex.get(ex)
            if not itens:
                continue
            if amostra == "fechamento":
                itens = itens[-1:]
            mids.append(_media([i["mid"] for i in itens]))
            aproximado = aproximado or any(i["aproximado"] for i in itens)
            for k in range(N_CATEGORIAS):
                alcanca = all(i["alcance"]["bids"][k] and i["alcance"]["asks"][k] for i in itens)
                if alcanca:
                    cobertura[k].append(ex)
                elif so_alcance:
                    continue
                bids[k] += _media([i["bids"][k] for i in itens])
                asks[k] += _media([i["asks"][k] for i in itens])
        razao = [(bids[k] / asks[k]) if asks[k] > 0 else None for k in range(N_CATEGORIAS)]
        forca = [((bids[k] - asks[k]) / (bids[k] + asks[k])) if (bids[k] + asks[k]) > 0 else 0.0
                 for k in range(N_CATEGORIAS)]
        tb, ta = sum(bids), sum(asks)
        pontos.append({
            "ts": int(chave),
            "mid": round(_media(mids), 2),
            "bids": [round(x, 4) for x in bids],
            "asks": [round(x, 4) for x in asks],
            "razao": [None if r is None else round(r, 4) for r in razao],
            "forca": [round(f, 4) for f in forca],
            "vantagem": ["bids" if f > 0 else "asks" if f < 0 else None for f in forca],
            "cobertura": cobertura,
            "exchanges": [ex for ex in exs if por_ex.get(ex)],
            "aproximado": aproximado,
            "total_bids": round(tb, 4),
            "total_asks": round(ta, 4),
            "forca_total": round((tb - ta) / (tb + ta), 4) if (tb + ta) > 0 else 0.0,
        })
    return {
        "passo_s": passo,
        "categorias": [{"lo": CATEGORIAS_PCT[k], "hi": CATEGORIAS_PCT[k + 1], "rotulo": ROTULOS_CATEGORIAS[k]}
                       for k in range(N_CATEGORIAS)],
        "pontos": pontos,
        "fontes": fontes,
    }


def _top_do_registro(registro: Dict, lado: str, n: int = N_TOP) -> Dict:
    """Top levels de um registro; antigo (sem ``top_*``) usa as n maiores faixas de 0,1% (centro da faixa)."""
    top = registro.get(f"top_{lado}")
    if top is not None:
        return {"niveis": [(float(p), float(q)) for p, q in top if q], "aproximado": False}
    mid = float(registro.get("mid", 0.0))
    faixa = float(registro.get("faixa_pct", 0.001))
    v = [(float(q or 0.0), i) for i, q in enumerate(registro.get(lado) or [])]
    v.sort(key=lambda x: -x[0])
    return {"niveis": [(preco_da_faixa(mid, lado, i, faixa), q) for q, i in v[:n] if q > 0], "aproximado": True}


def snapshot_mais_recente(exchange: str, ts: Optional[float], raiz: str = PASTA_DADOS,
                          tolerancia_s: float = TOLERANCIA_TOP_S) -> Optional[Dict]:
    """Último registro da exchange com ts <= ``ts`` e a até ``tolerancia_s`` dele. ``ts`` None = o último gravado."""
    if ts is None:
        dias = dias_disponiveis(exchange, raiz)
        if not dias:
            return None
        regs = carregar_dia(exchange, dias[-1], raiz)
        return regs[-1] if regs else None
    regs = carregar_periodo(exchange, ts - tolerancia_s, ts, raiz)
    return regs[-1] if regs else None


def top_agregado(ts: Optional[float] = None, exchanges: Iterable[str] = EXCHANGES, raiz: str = PASTA_DADOS,
                 n: int = N_TOP, grade_pct: float = GRADE_TOP_PCT,
                 tolerancia_s: float = TOLERANCIA_TOP_S) -> Dict:
    """
    Order Book Top Levels agregados: junta os top levels do snapshot mais recente (até ``ts``) de cada
    exchange, soma os que caem no mesmo preço arredondado à grade de ``grade_pct`` do mid e devolve os ``n``
    maiores por lado: [{"preco", "qtd", "exchanges": [...]}], do maior para o menor.
    Registros antigos entram com as maiores faixas de 0,1% e marcam ``aproximado``.
    """
    usados: Dict[str, Dict] = {}
    for ex in exchanges:
        r = snapshot_mais_recente(ex, ts, raiz, tolerancia_s)
        if r is not None:
            usados[ex] = r
    if not usados:
        return {"ts": None, "mid": None, "bids": [], "asks": [], "exchanges": [], "aproximado": False}
    mid = _media([float(r.get("mid", 0.0)) for r in usados.values()])
    grade = max(mid * grade_pct, 1e-9)
    aproximado = False
    saida: Dict = {}
    for lado in LADOS:
        grupos: Dict[int, Dict] = {}
        for ex, r in usados.items():
            t = _top_do_registro(r, lado, n)
            aproximado = aproximado or t["aproximado"]
            for p, q in t["niveis"]:
                chave = int(round(p / grade))
                g = grupos.setdefault(chave, {"soma_pq": 0.0, "qtd": 0.0, "exchanges": []})
                g["soma_pq"] += p * q
                g["qtd"] += q
                if ex not in g["exchanges"]:
                    g["exchanges"].append(ex)
        niveis = [{"preco": round(g["soma_pq"] / g["qtd"], 2), "qtd": round(g["qtd"], 4), "exchanges": g["exchanges"]}
                  for g in grupos.values() if g["qtd"] > 0]
        niveis.sort(key=lambda x: -x["qtd"])
        saida[lado] = niveis[:n]
    return {
        "ts": max(int(r.get("ts", 0)) for r in usados.values()),
        "mid": round(mid, 2),
        "bids": saida["bids"],
        "asks": saida["asks"],
        "exchanges": list(usados),
        "aproximado": aproximado,
    }


# ----------------------------------------------------------------- mapa de calor (heatmap de liquidez)
FATOR_MIN_CALOR = 2.0        # a faixa só acende com pelo menos 2x o normal daquela distância
FATOR_LOCAL_MIN = 3.0        # ... ou com pelo menos 3x as faixas vizinhas (±VIZINHAS) no mesmo instante
VIZINHAS = 5                 # 5 faixas da grade para cada lado (~0,5%)
BTC_MIN_CALOR = 2.0          # e com pelo menos 2 BTC somados na célula (corta ruído de livro raso)
MIN_SNAPSHOTS_BASE = 20      # sem 20 snapshots de base, a exchange não entra (não há "normal" para comparar)


def mapa_calor(ts_inicio: float, ts_fim: float, exchanges: Iterable[str] = EXCHANGES, raiz: str = PASTA_DADOS,
               passo_s: int = PASSO_OVERLAY_S, fator_min: float = FATOR_MIN_CALOR, btc_min: float = BTC_MIN_CALOR,
               janela_base_s: float = JANELA_24H_S, grade_usd: Optional[float] = None) -> Dict:
    """
    Heatmap de liquidez do livro (estilo Bookmap/TRDR): só acende onde há ordens acima do normal.

    Para cada exchange e lado, o NORMAL de cada faixa de 0,1% é a mediana da quantidade naquela mesma distância do
    mid, nos snapshots de [ts_inicio − janela_base_s, ts_fim]. Em cada coluna de ``passo_s`` segundos a quantidade é
    a MÉDIA dos snapshots da coluna: parede que pisca (spoof) fica diluída, parede que fica parada aparece inteira.
    As faixas das exchanges vão para uma grade absoluta de preço (0,1% do preço, arredondado a US$ 10) e somam;
    a intensidade da célula é soma(quantidade) / soma(normal). Só saem células com intensidade >= ``fator_min`` e
    quantidade >= ``btc_min``.

    Devolve {"passo_s", "grade_usd", "fator_min", "btc_min", "exchanges", "base": {ex: snapshots},
             "colunas": [{"ts", "mid", "celulas": [[preco_baixo, preco_alto, lado (0 bids / 1 asks), btc, intensidade,
                                                     intensidade_local]]}]}
    intensidade = contra o histórico na mesma distância; intensidade_local = contra as faixas vizinhas no mesmo instante.
    Sai a célula que passa em qualquer uma das duas (``fator_min`` ou FATOR_LOCAL_MIN).
    Faixas que a exchange não alcança (quantidade sempre 0) não têm normal e nunca acendem.
    ``grade_usd`` fixa a grade (o painel junta vários dias e precisa da mesma grade em todos).
    """
    exs = list(exchanges)
    passo = max(1, int(passo_s))
    dados: Dict[str, Dict] = {}
    base_n: Dict[str, int] = {}
    for ex in exs:
        regs = carregar_periodo(ex, ts_inicio - janela_base_s, ts_fim, raiz)
        base_n[ex] = len(regs)
        if len(regs) < MIN_SNAPSHOTS_BASE:
            continue
        m = matriz(regs)
        normal = {lado: np.median(m[lado], axis=0) for lado in LADOS}
        sel = m["ts"] >= ts_inicio
        dados[ex] = {"ts": m["ts"][sel], "mid": m["mid"][sel], "bids": m["bids"][sel], "asks": m["asks"][sel],
                     "normal": normal, "faixa_pct": float(regs[-1].get("faixa_pct", 0.001))}
    if not dados:
        return {"passo_s": passo, "grade_usd": None, "fator_min": fator_min, "btc_min": btc_min, "exchanges": exs,
                "base": base_n, "colunas": []}

    mids = np.concatenate([d["mid"] for d in dados.values() if len(d["mid"])]) if any(len(d["mid"]) for d in dados.values()) else np.array([])
    ref = float(np.median(mids)) if len(mids) else 0.0
    grade = float(grade_usd) if grade_usd else (max(1.0, round(ref * 0.001 / 10.0) * 10.0) if ref else 1.0)

    # coluna -> lado -> bin da grade -> [btc, normal]
    colunas: Dict[int, Dict] = {}
    for ex, d in dados.items():
        chaves = (d["ts"] // passo) * passo
        for chave in np.unique(chaves):
            linhas = chaves == chave
            mid = float(np.mean(d["mid"][linhas]))
            col = colunas.setdefault(int(chave), {"mids": [], "bins": {0: {}, 1: {}}})
            col["mids"].append(mid)
            for k, lado in enumerate(LADOS):
                qtd = d[lado][linhas].mean(axis=0)
                normal = d["normal"][lado]
                for i in np.nonzero((qtd > 0) & (normal > 0))[0]:
                    preco = preco_da_faixa(mid, lado, int(i), d["faixa_pct"])
                    b = int(preco // grade)
                    acc = col["bins"][k].setdefault(b, [0.0, 0.0])
                    acc[0] += float(qtd[i])
                    acc[1] += float(normal[i])

    saida = []
    for chave in sorted(colunas):
        col = colunas[chave]
        celulas = []
        for k in (0, 1):
            bins = col["bins"][k]
            for b, (btc, normal) in bins.items():
                if normal <= 0 or btc < btc_min:
                    continue
                inten = btc / normal
                # intensidade LOCAL: contra as faixas vizinhas do mesmo lado neste instante (é o que o olho vê como
                # "parede" perto do preço, onde o livro é sempre cheio e a régua histórica quase nunca passa de 2x)
                viz = [bins[j][0] for j in range(b - VIZINHAS, b + VIZINHAS + 1) if j != b and j in bins and bins[j][0] > 0]
                local = btc / float(np.median(viz)) if viz else 0.0
                if inten >= fator_min or local >= FATOR_LOCAL_MIN:
                    celulas.append([round(b * grade, 2), round((b + 1) * grade, 2), k, round(btc, 3), round(inten, 2),
                                    round(local, 2)])
        saida.append({"ts": chave, "mid": round(float(np.mean(col["mids"])), 2), "celulas": celulas})
    return {"passo_s": passo, "grade_usd": grade, "fator_min": fator_min, "btc_min": btc_min, "exchanges": exs,
            "base": base_n, "colunas": saida}
