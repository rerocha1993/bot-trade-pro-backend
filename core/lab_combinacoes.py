# core/lab_combinacoes.py
"""
LABORATÓRIO DE COMBINAÇÕES: testa robôs feitos de VOTAÇÃO entre os indicadores.

Um "robô" aqui é: um conjunto de indicadores, um número mínimo de votos do mesmo lado, e (opcionalmente) os
filtros de contexto — não operar contra o consenso de Elliott, e não operar em mercado serrilhado.

    entrada   no fechamento do candle em que a votação fecha (a mercado, taxa taker + slippage)
    stop      1,5 ATR contra; alvo 3,0 ATR a favor; tempo máximo de `horizonte` candles
    gestão    uma posição por vez; stop e alvo intra-candle, com o stop contando primeiro no mesmo candle

Os parâmetros de saída são FIXOS de propósito: quem varia é a combinação. Varrer também stop e alvo
multiplicaria as tentativas e faria alguma passar por sorte.

Três períodos: escolhe no treino, confirma na validação, e o holdout só é olhado no fim, uma vez, pelos poucos
finalistas. Com centenas de variantes, passar em dois períodos ainda acontece por acaso — é por isso que o
terceiro existe.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from core.executor_real import TAXA_TAKER

SLIPPAGE = 0.0002
CUSTO_ENTRADA = TAXA_TAKER + SLIPPAGE


@dataclass(frozen=True)
class Variante:
    indicadores: Tuple[str, ...]
    votos_min: int
    usar_elliott: bool
    usar_regime: bool

    @property
    def nome(self) -> str:
        filtros = ("Elliott" if self.usar_elliott else "") + ("+Regime" if self.usar_regime else "")
        return f"{self.votos_min} de {len(self.indicadores)} [{'+'.join(self.indicadores)}]" + (f" · {filtros.strip('+')}" if filtros else "")


def variantes(indicadores: Sequence[str], min_tamanho: int = 2) -> List[Variante]:
    out = []
    for n in range(min_tamanho, len(indicadores) + 1):
        for grupo in combinations(indicadores, n):
            for k in range(2, n + 1):
                for ell in (False, True):
                    for reg in (False, True):
                        out.append(Variante(grupo, k, ell, reg))
    return out


def lados(d, v: Variante) -> np.ndarray:
    """+1 / −1 / 0 por candle: votação do grupo, com os filtros de contexto aplicados."""
    m = np.vstack([d[i].values for i in v.indicadores])
    compra = (m == 1).sum(axis=0)
    venda = (m == -1).sum(axis=0)
    lado = np.where((compra >= v.votos_min) & (compra > venda), 1,
                    np.where((venda >= v.votos_min) & (venda > compra), -1, 0))
    if v.usar_elliott:                      # não operar contra o consenso das contagens
        lado = np.where(d["Elliott"].values == -lado, 0, lado)
    if v.usar_regime:                       # não operar em mercado serrilhado
        lado = np.where(d["Regime"].values == 0, 0, lado)
    return lado


def simular(lado: np.ndarray, idx: np.ndarray, close: np.ndarray, high: np.ndarray, low: np.ndarray,
            atr: np.ndarray, horizonte: int = 24, mult_stop: float = 1.5, mult_alvo: float = 3.0) -> Dict:
    """Uma posição por vez, stop/alvo em ATR e saída por tempo. Devolve o resultado em R (1 R = o stop)."""
    trades: List[float] = []
    n = len(idx)
    j = 0
    while j < n:
        if lado[j] == 0 or atr[j] <= 0:
            j += 1
            continue
        s = int(lado[j])
        i0 = int(idx[j])
        entrada = close[i0]
        risco = mult_stop * atr[j]
        stop = entrada - s * risco
        alvo = entrada + s * mult_alvo * risco
        saida, motivo, i_saida = None, "tempo", min(i0 + horizonte, len(close) - 1)
        for i in range(i0 + 1, min(i0 + horizonte, len(close) - 1) + 1):
            bateu_stop = low[i] <= stop if s == 1 else high[i] >= stop
            bateu_alvo = high[i] >= alvo if s == 1 else low[i] <= alvo
            if bateu_stop:
                saida, motivo, i_saida = stop * (1 - s * SLIPPAGE), "stop", i
                break
            if bateu_alvo:
                saida, motivo, i_saida = alvo, "alvo", i
                break
        if saida is None:
            saida = close[i_saida]
        bruto_r = (saida - entrada) * s / risco
        custo_r = (entrada * CUSTO_ENTRADA + saida * (TAXA_TAKER + (SLIPPAGE if motivo != "alvo" else 0))) / risco
        trades.append(bruto_r - custo_r)
        # o próximo sinal só vale depois que esta posição fechou
        j = int(np.searchsorted(idx, i_saida, side="right"))
    if not trades:
        return {"trades": 0, "soma_r": 0.0, "medio_r": 0.0, "fator_lucro": None, "acerto": None}
    t = np.array(trades)
    ganhos, perdas = t[t > 0].sum(), -t[t <= 0].sum()
    return {"trades": len(t), "soma_r": round(float(t.sum()), 2), "medio_r": round(float(t.mean()), 4),
            "fator_lucro": round(float(ganhos / perdas), 2) if perdas > 0 else None,
            "acerto": round(float((t > 0).mean()), 3)}


def rodar(d, candles: Sequence[Sequence[float]], v: Variante, inicio_ms: int, fim_ms: Optional[int],
          horizonte: int = 24) -> Dict:
    close = np.array([c[4] for c in candles], dtype=float)
    high = np.array([c[2] for c in candles], dtype=float)
    low = np.array([c[3] for c in candles], dtype=float)
    m = (d["ts"].values >= inicio_ms) & ((d["ts"].values < fim_ms) if fim_ms else True)
    sub = d[m]
    return simular(lados(sub, v)[:], sub["i"].values, close, high, low, sub["atr"].values, horizonte)


CRITERIO = {"trades_min_treino": 50, "trades_min_validacao": 30, "medio_min": 0.0}


def aprovada(tr: Dict, va: Dict) -> bool:
    return (tr["trades"] >= CRITERIO["trades_min_treino"] and va["trades"] >= CRITERIO["trades_min_validacao"]
            and tr["medio_r"] > CRITERIO["medio_min"] and va["medio_r"] > CRITERIO["medio_min"])
