# core/elliott_pro/pivots.py
"""ZigZag por ATR: converte candles em pivôs (topos 'H' e fundos 'L')."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from conselho.indicadores import atr


@dataclass
class Pivot:
    idx: int
    ts: int
    preco: float
    tipo: str            # 'H' topo | 'L' fundo
    confirmado: bool = True

    def dict(self):
        return asdict(self)


def zigzag_atr(ohlcv: Sequence, fator_atr: float = 2.0, periodo_atr: int = 14,
               min_pct: Optional[float] = None) -> Tuple[List[Pivot], float]:
    """
    Um pivô é confirmado quando o preço reverte pelo menos `fator_atr` ATRs a partir do extremo.
    O último pivô devolvido é PROVISÓRIO (extremo da perna em andamento).
    Retorna (pivôs, limiar_em_preco).
    """
    n = len(ohlcv)
    if n < 3:
        return [], 0.0
    highs = np.array([float(c[2]) for c in ohlcv])
    lows = np.array([float(c[3]) for c in ohlcv])
    ts = [int(c[0]) for c in ohlcv]
    a = atr(ohlcv, periodo_atr) or float(np.mean(highs - lows))
    limiar = fator_atr * a
    if min_pct:
        limiar = max(limiar, float(np.median(highs)) * min_pct)
    if limiar <= 0:
        return [], 0.0

    pivots: List[Pivot] = []
    cand_hi_i, cand_lo_i = 0, 0
    direcao = None
    start = n
    for i in range(1, n):
        if highs[i] > highs[cand_hi_i]:
            cand_hi_i = i
        if lows[i] < lows[cand_lo_i]:
            cand_lo_i = i
        if highs[cand_hi_i] - lows[cand_lo_i] >= limiar:
            if cand_hi_i > cand_lo_i:
                direcao = "up"
                pivots.append(Pivot(cand_lo_i, ts[cand_lo_i], float(lows[cand_lo_i]), "L"))
                extremo_i = cand_hi_i
            else:
                direcao = "down"
                pivots.append(Pivot(cand_hi_i, ts[cand_hi_i], float(highs[cand_hi_i]), "H"))
                extremo_i = cand_lo_i
            start = i + 1
            break
    if direcao is None:
        return [], limiar

    for i in range(start, n):
        if direcao == "up":
            if highs[i] > highs[extremo_i]:
                extremo_i = i
            elif highs[extremo_i] - lows[i] >= limiar:
                pivots.append(Pivot(extremo_i, ts[extremo_i], float(highs[extremo_i]), "H"))
                direcao = "down"
                extremo_i = i
        else:
            if lows[i] < lows[extremo_i]:
                extremo_i = i
            elif highs[i] - lows[extremo_i] >= limiar:
                pivots.append(Pivot(extremo_i, ts[extremo_i], float(lows[extremo_i]), "L"))
                direcao = "up"
                extremo_i = i
    if direcao == "up":
        pivots.append(Pivot(extremo_i, ts[extremo_i], float(highs[extremo_i]), "H", confirmado=False))
    else:
        pivots.append(Pivot(extremo_i, ts[extremo_i], float(lows[extremo_i]), "L", confirmado=False))
    return pivots, limiar


GRAUS_PADRAO = {"menor": 1.5, "intermediario": 3.0, "maior": 6.0}


def zigzag_multi(ohlcv: Sequence, graus: Dict[str, float] = None, periodo_atr: int = 14) -> Dict[str, Dict]:
    """Roda o ZigZag com vários limiares no MESMO timeframe: graus fractais dentro da mesma série."""
    graus = graus or GRAUS_PADRAO
    saida = {}
    for nome, fator in graus.items():
        piv, limiar = zigzag_atr(ohlcv, fator_atr=fator, periodo_atr=periodo_atr)
        saida[nome] = {"pivots": piv, "limiar": limiar, "fator_atr": fator}
    return saida
