# core/elliott_pro/mestre.py
"""
Contagem MESTRE (graus grandes, desde 2011) e aninhamento fractal.

Graus (ZigZag por PERCENTUAL do preço, no semanal ou diário):
    ciclo          reversões >= 40%   (ondas de anos: 2011-2013, 2015-2017, 2018-2021, 2022-2025...)
    primario       reversões >= 22%   (ondas de meses a 1-2 anos)
    intermediario  reversões >= 12%   (ondas de semanas a meses)

Aninhamento: o grau menor é contado SOMENTE dentro da onda em curso do grau maior (a partir do último
pivô confirmado do grau maior). É assim que "uma onda 3 maior contém 1-2-3-4-5 menores".

Travar: o usuário escolhe um cenário de um grau e ele vira o trilho (tabela elliott_contagens_validadas,
status 'travada'). Enquanto o preço não cruzar a invalidação, o viés do trilho entra no alinhamento
multi-grau como grau "mestre"; se cruzar, a trava é marcada 'invalidada' e o bot volta ao modo livre.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import numpy as np

from core.utils_indicadores import atr as calc_atr
from .pivots import Pivot
from .scenarios import ScenarioEngine

GRAUS_MESTRE = {"ciclo": 0.40, "primario": 0.22, "intermediario": 0.12}


def zigzag_pct(ohlcv: Sequence, pct: float) -> List[Pivot]:
    """ZigZag por reversão percentual sobre high/low. Último pivô é provisório."""
    n = len(ohlcv)
    if n < 3:
        return []
    highs = np.array([float(c[2]) for c in ohlcv])
    lows = np.array([float(c[3]) for c in ohlcv])
    ts = [int(c[0]) for c in ohlcv]
    pivots: List[Pivot] = []
    hi_i, lo_i = 0, 0
    direcao = None
    start = n
    for i in range(1, n):
        if highs[i] > highs[hi_i]:
            hi_i = i
        if lows[i] < lows[lo_i]:
            lo_i = i
        if highs[hi_i] >= lows[lo_i] * (1 + pct):
            if hi_i > lo_i:
                direcao = "up"; pivots.append(Pivot(lo_i, ts[lo_i], float(lows[lo_i]), "L")); ext = hi_i
            else:
                direcao = "down"; pivots.append(Pivot(hi_i, ts[hi_i], float(highs[hi_i]), "H")); ext = lo_i
            start = i + 1
            break
    if direcao is None:
        return []
    for i in range(start, n):
        if direcao == "up":
            if highs[i] > highs[ext]:
                ext = i
            elif lows[i] <= highs[ext] * (1 - pct):
                pivots.append(Pivot(ext, ts[ext], float(highs[ext]), "H")); direcao = "down"; ext = i
        else:
            if lows[i] < lows[ext]:
                ext = i
            elif highs[i] >= lows[ext] * (1 + pct):
                pivots.append(Pivot(ext, ts[ext], float(lows[ext]), "L")); direcao = "up"; ext = i
    if direcao == "up":
        pivots.append(Pivot(ext, ts[ext], float(highs[ext]), "H", confirmado=False))
    else:
        pivots.append(Pivot(ext, ts[ext], float(lows[ext]), "L", confirmado=False))
    return pivots


def _data(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def analisar_grau(ohlcv: Sequence, pct: float, nome: str) -> Dict:
    piv = zigzag_pct(ohlcv, pct)
    preco = float(ohlcv[-1][4])
    limiar = preco * pct
    a = calc_atr(ohlcv, 14) or limiar / 4
    eng = ScenarioEngine(piv, preco, limiar, a, max_pivots=60)
    res = eng.analisar()
    res["grau"] = nome
    res["pct"] = pct
    res["pivots"] = [{**p.dict(), "data": _data(p.ts)} for p in piv]
    for c in res["cenarios"]:
        for o in c.get("ondas", []):
            o["data_inicio"], o["data_fim"] = _data(o["ts_inicio"]), _data(o["ts_fim"])
    return res


TF_POR_GRAU = {"ciclo": "1w", "primario": "1d", "intermediario": "4h"}


def contagem_mestre(series: Dict[str, Sequence], graus: Dict[str, float] = None) -> Dict:
    """
    series: {'1w': candles desde 2011, '1d': candles, '4h': candles} (o que faltar é substituído pelo maior disponível).
    Grau ciclo no semanal desde o início; cada grau seguinte é analisado no seu timeframe SÓ a partir do último
    pivô confirmado do grau anterior (a onda maior em curso). Se a onda em curso ainda for curta, usa um timeframe menor.
    """
    graus = graus or GRAUS_MESTRE
    disponiveis = {tf: [list(map(float, c[:6])) for c in s] for tf, s in series.items() if s}
    if not disponiveis:
        raise ValueError("nenhuma série informada")
    ordem = ["1w", "1d", "4h", "1h"]
    base = disponiveis.get("1w") or disponiveis[next(iter(disponiveis))]
    saida = {"inicio": _data(int(base[0][0])), "fim": _data(int(base[-1][0])), "preco": base[-1][4], "graus": {}}
    ancoras = [int(base[0][0])]          # candidatas de âncora (do mais recente para o mais antigo)
    for nome, pct in graus.items():
        tf_pref = TF_POR_GRAU.get(nome, "1d")
        candidatos = [tf for tf in ordem[ordem.index(tf_pref):] if tf in disponiveis] or list(disponiveis)
        res = None
        # tenta a âncora mais recente (onda maior em curso); se a subcontagem não tiver estrutura, recua um pivô
        for ancora_ts in ancoras:
            for tf in candidatos:
                serie = [c for c in disponiveis[tf] if c[0] >= ancora_ts]
                if len(serie) < 40:
                    continue
                r = analisar_grau(serie, pct, nome)
                if r.get("n_cenarios", 0) >= 1 and len(r.get("pivots", [])) >= 4:
                    res = r
                    res["timeframe"] = tf
                    res["desde"] = _data(int(serie[0][0]))
                    break
            if res:
                break
        if res is None:
            saida["graus"][nome] = {"erro": "onda maior em curso ainda sem subestrutura", "fase": "indefinido", "cenarios": [], "pivots": []}
            continue
        saida["graus"][nome] = res
        conf = [p for p in res["pivots"] if p["confirmado"]]
        ancoras = [p["ts"] for p in conf[::-1][:4]] or ancoras
    return saida


def verificar_trava(trava: Dict, preco: float) -> Dict:
    """trava: dict salvo ao travar (vies, invalidacao, alvos). Devolve status atualizado."""
    inv = trava.get("invalidacao")
    vies = trava.get("vies")
    if inv is not None and ((vies == "bull" and preco < inv) or (vies == "bear" and preco > inv)):
        return {"status": "invalidada", "motivo": f"preço {preco:.2f} cruzou a invalidação {inv:.2f}"}
    alvos = [a for a in trava.get("alvos", []) if (a > preco if vies == "bull" else a < preco)]
    return {"status": "ativa", "motivo": f"viés {vies}; próximo alvo {alvos[0]:.2f}" if alvos else f"viés {vies}; alvos atingidos"}
