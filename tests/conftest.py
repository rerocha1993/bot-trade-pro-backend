import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import math  # noqa: E402
import random  # noqa: E402

import pytest  # noqa: E402


def gerar_candles(precos, ts0=1_700_000_000_000, dur_ms=900_000, volume=10.0, amplitude=0.001):
    """Candles sintéticos a partir de uma lista de fechamentos (high/low com pequena amplitude)."""
    out = []
    prev = precos[0]
    for i, c in enumerate(precos):
        o = prev
        h = max(o, c) * (1 + amplitude)
        l = min(o, c) * (1 - amplitude)
        out.append([ts0 + i * dur_ms, float(o), float(h), float(l), float(c), float(volume)])
        prev = c
    return out


def impulso_5_ondas(base=100.0, w1=10.0, r2=0.618, k3=1.618, r4=0.382, k5=1.0, passos=8, ruido=0.0005, seed=1):
    """
    Série de preços com um impulso de alta de 5 ondas respeitando as regras:
        onda1 = w1, onda2 = r2*w1, onda3 = k3*w1, onda4 = r4*onda3, onda5 = k5*w1
    """
    rnd = random.Random(seed)
    pontos = [base]
    p = base
    p1 = p + w1
    p2 = p1 - r2 * w1
    p3 = p2 + k3 * w1
    p4 = p3 - r4 * (k3 * w1)
    p5 = p4 + k5 * w1
    alvos = [p1, p2, p3, p4, p5]
    for alvo in alvos:
        inicio = pontos[-1]
        for s in range(1, passos + 1):
            v = inicio + (alvo - inicio) * s / passos
            v *= 1 + rnd.uniform(-ruido, ruido)
            pontos.append(v)
        pontos[-1] = alvo
    return pontos, alvos


@pytest.fixture
def candles_impulso():
    precos, alvos = impulso_5_ondas()
    # aquecimento lateral antes do impulso para o ATR
    aquecimento = [100 + 0.2 * math.sin(i / 3) for i in range(40)]
    return gerar_candles(aquecimento + precos), alvos
