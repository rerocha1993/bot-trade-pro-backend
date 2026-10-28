# core/tpo_sessao.py
"""
TPO DE VERDADE, como no TradingView/ExoCharts e como o Tradeiros usa:

    - um perfil POR DIA (UTC), em blocos de 30 minutos: cada bloco "imprime" em todas as faixas de preço que tocou
    - faixa de preço com altura FIXA (0,1% do preço, arredondada para US$ 10) — não um número fixo de faixas
    - POC (a faixa com mais blocos, a "pisada do leão"), área de valor de 70% (VAL/VAH)
    - single prints (faixas tocadas por um bloco só, dentro do perfil) e caudas (single prints no extremo:
      cauda compradora embaixo, vendedora em cima)
    - perfis por SESSÃO: Ásia, Europa e América
    - MERGE: vários dias juntos num perfil composto — é assim que o range é desenhado
    - naked POC: POC de um dia que o preço ainda não voltou a tocar

O perfil guarda os blocos (máxima e mínima de cada 30 min), então o merge é exato em qualquer grade.
O antigo core/tpo.py (perfil de uma janela de candles com 30 faixas) continua para quem já usa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

BLOCO_MS = 30 * 60 * 1000
DIA_MS = 86_400_000
TICK_PCT = 0.001
AREA_VALOR = 0.70
# sessões em horário UTC (início, fim) em minutos do dia
SESSOES = {"asia": (0, 8 * 60), "europa": (8 * 60, 13 * 60 + 30), "america": (13 * 60 + 30, 20 * 60)}


def tick_para(preco: float) -> float:
    """Altura da faixa: 0,1% do preço, arredondada para US$ 10 (mínimo US$ 1)."""
    return max(1.0, round(preco * TICK_PCT / 10.0) * 10.0) if preco >= 1000 else max(preco * TICK_PCT, 1e-8)


def blocos_30m(candles: Sequence[Sequence[float]]) -> List[Tuple[int, float, float, float, float, float]]:
    """Agrupa candles (de 30 min ou menores) em blocos de 30 min: (ts, open, high, low, close, volume)."""
    out: Dict[int, list] = {}
    for c in candles:
        ts = int(c[0]) - int(c[0]) % BLOCO_MS
        b = out.get(ts)
        if b is None:
            out[ts] = [ts, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)]
        else:
            b[2] = max(b[2], float(c[2]))
            b[3] = min(b[3], float(c[3]))
            b[4] = float(c[4])
            b[5] += float(c[5] or 0)
    return [tuple(out[k]) for k in sorted(out)]


@dataclass
class Perfil:
    blocos: List[Tuple[int, float, float, float, float, float]]
    tick: Optional[float] = None
    _cache: Dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if not self.blocos:
            raise ValueError("perfil sem blocos")
        if self.tick is None:
            self.tick = tick_para(self.blocos[-1][4])

    # ---------------------------------------------------------------- básico
    @property
    def inicio(self) -> int:
        return self.blocos[0][0]

    @property
    def fim(self) -> int:
        return self.blocos[-1][0] + BLOCO_MS

    @property
    def abertura(self) -> float:
        return self.blocos[0][1]

    @property
    def fechamento(self) -> float:
        return self.blocos[-1][4]

    @property
    def maxima(self) -> float:
        return max(b[2] for b in self.blocos)

    @property
    def minima(self) -> float:
        return min(b[3] for b in self.blocos)

    def _faixa(self, preco: float) -> int:
        """Índice absoluto da faixa (preço // tick). A folga de 1e-9 segura o preço que cai exatamente na borda:
        com tick < 1 (altcoins), 1,201 / 0,001 dá 1200,9999999999998 e a faixa 1201 se perdia."""
        return int(np.floor(preco / self.tick + 1e-9))

    def _grade(self):
        if "grade" not in self._cache:
            i0 = self._faixa(self.minima)
            base = i0 * self.tick
            n = self._faixa(self.maxima) - i0 + 1
            cont = np.zeros(n, dtype=int)
            vol = np.zeros(n, dtype=float)
            for _, _, h, l, _, v in self.blocos:
                a = self._faixa(l) - i0
                z = self._faixa(h) - i0
                cont[a:z + 1] += 1
                vol[a:z + 1] += v / (z - a + 1)
            self._cache["grade"] = (base, cont, vol)
        return self._cache["grade"]

    def preco_da_faixa(self, i: int) -> float:
        base, _, _ = self._grade()
        return base + (i + 0.5) * self.tick

    # ---------------------------------------------------------------- níveis
    def poc(self) -> float:
        """A faixa com mais blocos; no empate, a mais perto do meio do perfil (convenção do Market Profile)."""
        base, cont, _ = self._grade()
        mx = cont.max()
        candidatas = np.flatnonzero(cont == mx)
        meio = (len(cont) - 1) / 2
        return self.preco_da_faixa(int(candidatas[np.argmin(np.abs(candidatas - meio))]))

    def area_valor(self, pct: float = AREA_VALOR, empate: str = "acima") -> Tuple[float, float]:
        """(VAL, VAH): a partir do POC, soma o lado com mais blocos até cobrir `pct` do total (ver `expandir_area`)."""
        base, cont, _ = self._grade()
        i_poc = int(round((self.poc() - base) / self.tick - 0.5))
        lo, hi = expandir_area(cont, i_poc, pct, empate)
        return base + lo * self.tick, base + (hi + 1) * self.tick

    def niveis(self) -> Dict[str, float]:
        val, vah = self.area_valor()
        return {"POC": self.poc(), "VAL": val, "VAH": vah, "maxima": self.maxima, "minima": self.minima}

    def single_prints(self) -> List[float]:
        """Faixas tocadas por um bloco só (fora das pontas, que são as caudas)."""
        _, cont, _ = self._grade()
        return [self.preco_da_faixa(i) for i in range(1, len(cont) - 1) if cont[i] == 1]

    def caudas(self, minimo: int = 2) -> Dict[str, Optional[Tuple[float, float]]]:
        """
        Cauda compradora: pelo menos `minimo` faixas seguidas com um bloco só na mínima do perfil — o preço foi lá
        embaixo, foi rejeitado rápido e não voltou. A vendedora é o espelho na máxima.
        """
        base, cont, _ = self._grade()
        n = 0
        while n < len(cont) and cont[n] == 1:
            n += 1
        m = 0
        while m < len(cont) and cont[len(cont) - 1 - m] == 1:
            m += 1
        compra = (base, base + n * self.tick) if minimo <= n < len(cont) else None
        venda = (base + (len(cont) - m) * self.tick, base + len(cont) * self.tick) if minimo <= m < len(cont) else None
        return {"compradora": compra, "vendedora": venda}

    def perfil_por_faixa(self) -> List[Dict]:
        """Para desenhar: cada faixa com os blocos e o volume."""
        base, cont, vol = self._grade()
        return [{"lo": base + i * self.tick, "hi": base + (i + 1) * self.tick, "tpo": int(cont[i]), "volume": float(vol[i])}
                for i in range(len(cont))]


# ------------------------------------------------------------------ dias, sessões e merge
def dias(candles: Sequence[Sequence[float]]) -> List[Perfil]:
    """Um perfil por dia UTC (o último pode estar em formação)."""
    por_dia: Dict[int, list] = {}
    for b in blocos_30m(candles):
        por_dia.setdefault(b[0] // DIA_MS, []).append(b)
    return [Perfil(por_dia[d]) for d in sorted(por_dia)]


def sessoes(perfil_dia: Perfil) -> Dict[str, Perfil]:
    out = {}
    for nome, (a, z) in SESSOES.items():
        bl = [b for b in perfil_dia.blocos if a <= (b[0] % DIA_MS) // 60000 < z]
        if bl:
            out[nome] = Perfil(bl, perfil_dia.tick)
    return out


def expandir_area(cont: Sequence[int], i_poc: int, pct: float = AREA_VALOR, empate: str = "acima") -> Tuple[int, int]:
    """
    Área de valor nas contagens por faixa: começa no POC e, uma faixa por vez, acrescenta a vizinha (logo acima da
    mais alta ou logo abaixo da mais baixa) com mais blocos, até somar `pct` do total. Devolve (faixa mais baixa,
    faixa mais alta).

    Empate entre as duas vizinhas:
      "acima"        sempre a de cima (regra antiga; os robôs e avisos usam esta, para não mudar o que já foi medido);
      "tradingview"  a mais perto do POC e, na mesma distância, a de cima (a regra do TPO da TradingView).
    """
    n = len(cont)
    total = int(sum(cont))
    lo = hi = i_poc
    soma = int(cont[i_poc])
    while soma < pct * total and (lo > 0 or hi < n - 1):
        acima = int(cont[hi + 1]) if hi < n - 1 else -1
        abaixo = int(cont[lo - 1]) if lo > 0 else -1
        if acima == abaixo and empate == "tradingview":
            sobe = (hi + 1 - i_poc) <= (i_poc - (lo - 1))
        else:
            sobe = acima >= abaixo
        if sobe:
            hi += 1
            soma += max(acima, 0)
        else:
            lo -= 1
            soma += max(abaixo, 0)
    return lo, hi


def merge(perfis: Sequence[Perfil], tick: Optional[float] = None) -> Perfil:
    """Perfil composto de vários dias (o 'merge' do range)."""
    blocos = [b for p in perfis for b in p.blocos]
    return Perfil(sorted(blocos), tick or (perfis[-1].tick if perfis else None))


def naked_pocs(perfis: Sequence[Perfil], ate: Optional[int] = None) -> List[Dict]:
    """
    POCs de dias anteriores que o preço ainda não voltou a tocar ("o preço volta, bate e reage").
    `ate`: índice do perfil até onde olhar (exclusive); por padrão, todos.
    """
    ate = len(perfis) if ate is None else ate
    out = []
    for i in range(ate - 1):
        poc = perfis[i].poc()
        tocado = any(p.minima <= poc <= p.maxima for p in perfis[i + 1:ate])
        if not tocado:
            out.append({"preco": poc, "dia_ms": perfis[i].inicio})
    return out
