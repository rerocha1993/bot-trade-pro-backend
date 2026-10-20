# conselho/estrutura.py
"""
Motor de estrutura para os estudos de Fibonacci e Order Block (construído uma vez, sem depender de core/).

Tudo em candle fechado e sem olhar o futuro: cada pivô/swing tem o índice em que passa a ser CONHECIDO (`conf`).

- ATR(14) = média simples do true range dos 14 candles até o atual (inclusive).
- ZigZag ATR: pivô confirmado quando o preço reverte `fator` × ATR(14) DO CANDLE ATUAL a partir do extremo da perna
  (core/elliott_pro/pivots.zigzag_atr usa um ATR único da série inteira, o que no histórico olharia o futuro).
- Swing (SMC): máxima maior que as 3 anteriores e ≥ que as 3 seguintes; conhecido 3 candles depois.
- FVG: de baixa no candle i quando máxima[i+1] < mínima[i−1]; de alta quando mínima[i+1] > máxima[i−1].
- Estado de 4 h: cada fechamento acima do último swing high confirmado (ainda não rompido) é evento de alta; abaixo do
  último swing low, de baixa. Estado = "alta" se os dois últimos eventos foram de alta, "baixa" se os dois foram de
  baixa, "lateral" se diferem (houve CHoCH há pouco) ou se há menos de dois eventos.
"""
from __future__ import annotations

import numpy as np


def atr(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray, n: int = 14) -> np.ndarray:
    pc = np.concatenate(([cl[0]], cl[:-1]))
    tr = np.maximum(hi, pc) - np.minimum(lo, pc)
    c = np.cumsum(np.concatenate(([0.0], tr)))
    out = np.full(len(tr), np.nan)
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def zigzag_atr(hi: np.ndarray, lo: np.ndarray, at: np.ndarray, fator: float):
    """Lista de pivôs (idx, preço, 'H'|'L', conf). O extremo em andamento não entra (só pivôs confirmados)."""
    h, l, a = hi.tolist(), lo.tolist(), at.tolist()
    n = len(h)
    piv = []
    i0 = 0
    while i0 < n and not (a[i0] == a[i0]):
        i0 += 1
    if i0 >= n:
        return piv
    ch, cl_ = i0, i0
    direcao = 0
    ext = None
    i = i0 + 1
    while i < n:
        if h[i] > h[ch]:
            ch = i
        if l[i] < l[cl_]:
            cl_ = i
        if h[ch] - l[cl_] >= fator * a[i]:
            if ch > cl_:
                piv.append((cl_, l[cl_], "L", i))
                direcao, ext = 1, ch
            else:
                piv.append((ch, h[ch], "H", i))
                direcao, ext = -1, cl_
            i += 1
            break
        i += 1
    while i < n:
        lim = fator * a[i]
        if direcao == 1:
            if h[i] > h[ext]:
                ext = i
            elif h[ext] - l[i] >= lim:
                piv.append((ext, h[ext], "H", i))
                direcao, ext = -1, i
        else:
            if l[i] < l[ext]:
                ext = i
            elif h[i] - l[ext] >= lim:
                piv.append((ext, l[ext], "L", i))
                direcao, ext = 1, i
        i += 1
    return piv


def swings(hi: np.ndarray, lo: np.ndarray, k: int = 3):
    """(altas, baixas): listas de (idx, preço, conf=idx+k)."""
    n = len(hi)
    altas, baixas = [], []
    for j in range(k, n - k):
        hj, lj = hi[j], lo[j]
        if hj > hi[j - k:j].max() and hj >= hi[j + 1:j + k + 1].max():
            altas.append((j, float(hj), j + k))
        if lj < lo[j - k:j].min() and lj <= lo[j + 1:j + k + 1].min():
            baixas.append((j, float(lj), j + k))
    return altas, baixas


def swings_rapido(hi: np.ndarray, lo: np.ndarray, k: int = 3):
    """Mesmo que swings(), vetorizado."""
    n = len(hi)
    if n < 2 * k + 1:
        return [], []
    from numpy.lib.stride_tricks import sliding_window_view as sw
    esq_h = sw(hi, k)[:n - 2 * k].max(axis=1)          # hi[j-k:j] para j = k..n-k-1
    dir_h = sw(hi, k)[k + 1:].max(axis=1)               # hi[j+1:j+k+1]
    esq_l = sw(lo, k)[:n - 2 * k].min(axis=1)
    dir_l = sw(lo, k)[k + 1:].min(axis=1)
    js = np.arange(k, n - k)
    hj, lj = hi[k:n - k], lo[k:n - k]
    m = min(len(js), len(esq_h), len(dir_h))
    js, hj, lj = js[:m], hj[:m], lj[:m]
    sa = (hj > esq_h[:m]) & (hj >= dir_h[:m])
    sb = (lj < esq_l[:m]) & (lj <= dir_l[:m])
    altas = [(int(j), float(hi[j]), int(j) + k) for j in js[sa]]
    baixas = [(int(j), float(lo[j]), int(j) + k) for j in js[sb]]
    return altas, baixas


def estado_4h(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray, k: int = 3) -> list:
    """Estado ('alta'|'baixa'|'lateral') DEPOIS do fechamento de cada candle de 4 h."""
    altas, baixas = swings_rapido(hi, lo, k)
    conf_a = {}
    for j, p, c in altas:
        conf_a.setdefault(c, []).append(p)
    conf_b = {}
    for j, p, c in baixas:
        conf_b.setdefault(c, []).append(p)
    sh = sl = None
    eventos = []
    out = []
    for i in range(len(cl)):
        if i in conf_a:
            sh = conf_a[i][-1]
        if i in conf_b:
            sl = conf_b[i][-1]
        if sh is not None and cl[i] > sh:
            eventos.append(1)
            sh = None
        elif sl is not None and cl[i] < sl:
            eventos.append(-1)
            sl = None
        if len(eventos) >= 2 and eventos[-1] == eventos[-2]:
            out.append("alta" if eventos[-1] == 1 else "baixa")
        else:
            out.append("lateral")
    return out
