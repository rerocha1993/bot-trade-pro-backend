# core/tpo.py
"""
TPO Profile (Market Profile por tempo).

Cada candle "imprime" um TPO em TODOS os bins de preço que ele atravessa (low..high).
    POC  = bin com mais TPOs
    Value Area = menor conjunto de bins ao redor do POC que concentra 70% dos TPOs
    VAH / VAL = topo / fundo da Value Area
    HVN / LVN = bins com maior / menor contagem (LVN só entre bins tocados)
    single prints = bins impressos por um único candle

Aceita:
    TPOProfile(ohlcv)               -> lista de candles [ts, o, h, l, c, v]
    TPOProfile([closes], interval)  -> compatibilidade antiga (lista de preços)
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np


class TPOProfile:
    def __init__(self, dados: Sequence, interval: Optional[float] = None, tolerancia: float = 0.002,
                 range_min: Optional[float] = None, range_max: Optional[float] = None, bins: int = 30):
        if not dados or len(dados) == 0:
            raise ValueError("dados vazios para TPO")
        self.tolerancia = tolerancia
        if isinstance(dados[0], (list, tuple)):
            self.highs = np.array([float(c[2]) for c in dados])
            self.lows = np.array([float(c[3]) for c in dados])
            self.closes = np.array([float(c[4]) for c in dados])
        else:  # lista de preços simples
            arr = np.array([float(p) for p in dados])
            self.highs = arr
            self.lows = arr
            self.closes = arr

        lo = float(np.min(self.lows)) if range_min is None else float(range_min)
        hi = float(np.max(self.highs)) if range_max is None else float(range_max)
        if hi <= lo:
            hi = lo + max(abs(lo) * 0.001, 1e-6)
        self.min_price, self.max_price = lo, hi

        if interval and interval > 0 and (hi - lo) / interval <= 500:
            self.interval = float(interval)
        else:
            self.interval = (hi - lo) / max(int(bins), 5)
        self.bins = int(np.ceil((hi - lo) / self.interval)) + 1
        self.edges = lo + np.arange(self.bins + 1) * self.interval
        self.centros = (self.edges[:-1] + self.edges[1:]) / 2.0
        self.contagem = self._contar()

    # -------------------------------------------------------------- núcleo
    def _idx(self, preco: float) -> int:
        i = int((preco - self.min_price) // self.interval)
        return max(0, min(i, self.bins - 1))

    def _contar(self) -> np.ndarray:
        cont = np.zeros(self.bins, dtype=int)
        for h, l in zip(self.highs, self.lows):
            a, b = self._idx(min(h, l)), self._idx(max(h, l))
            cont[a:b + 1] += 1
        return cont

    def freq_table(self):
        import pandas as pd
        return pd.DataFrame({"bin": self.centros, "freq": self.contagem})

    def calculate_poc_val_vah(self) -> Dict:
        cont = self.contagem
        total = int(cont.sum())
        if total == 0:
            return {"POC": self.closes[-1], "VAL": self.min_price, "VAH": self.max_price, "freq": self.freq_table()}
        poc_i = int(np.argmax(cont))
        alvo = 0.70 * total
        lo_i = hi_i = poc_i
        acumulado = int(cont[poc_i])
        # expansão simétrica clássica: adiciona o lado (acima/abaixo) com mais TPOs
        while acumulado < alvo and (lo_i > 0 or hi_i < self.bins - 1):
            acima = int(cont[hi_i + 1]) if hi_i < self.bins - 1 else -1
            abaixo = int(cont[lo_i - 1]) if lo_i > 0 else -1
            if acima >= abaixo:
                hi_i += 1
                acumulado += max(acima, 0)
            else:
                lo_i -= 1
                acumulado += max(abaixo, 0)
        return {
            "POC": float(self.centros[poc_i]),
            "VAL": float(self.edges[lo_i]),
            "VAH": float(self.edges[hi_i + 1]),
            "freq": self.freq_table(),
        }

    def find_single_prints(self, freq=None) -> List[float]:
        return [float(self.centros[i]) for i in range(self.bins) if self.contagem[i] == 1]

    def shape_profile(self, freq=None) -> str:
        cont = self.contagem
        if cont.sum() == 0:
            return "Unknown"
        peak = int(np.argmax(cont))
        acima = cont[peak + 1:]
        abaixo = cont[:peak]
        m_acima = float(np.mean(acima)) if len(acima) else 0.0
        m_abaixo = float(np.mean(abaixo)) if len(abaixo) else 0.0
        pico = float(cont[peak])
        if m_acima < 0.6 * pico and m_abaixo < 0.6 * pico and abs(m_acima - m_abaixo) < 0.25 * pico:
            return "D"   # equilíbrio
        if m_acima > m_abaixo:
            return "b"   # volume concentrado embaixo: tendência de baixa/rejeição no topo
        return "P"       # volume concentrado em cima: tendência de alta/rejeição no fundo

    def hvn_lvn(self, freq=None, n: int = 3) -> Dict[str, List[float]]:
        cont = self.contagem
        tocados = [i for i in range(self.bins) if cont[i] > 0]
        if not tocados:
            return {"HVN": [], "LVN": []}
        ordem = sorted(tocados, key=lambda i: cont[i])
        lvn = [float(self.centros[i]) for i in ordem[:n]]
        hvn = [float(self.centros[i]) for i in ordem[::-1][:n]]
        return {"HVN": hvn, "LVN": lvn}

    def analisar(self) -> Dict:
        res = self.calculate_poc_val_vah()
        nodes = self.hvn_lvn()
        return {
            "POC": res["POC"],
            "VAL": res["VAL"],
            "VAH": res["VAH"],
            "shape": self.shape_profile(),
            "single_prints": self.find_single_prints(),
            "HVN": nodes["HVN"],
            "LVN": nodes["LVN"],
            "interval": self.interval,
            "bins": self.bins,
            "range": (self.min_price, self.max_price),
        }

    def perto(self, preco: float, nivel: float) -> bool:
        return abs(preco - nivel) <= max(self.interval / 2.0, abs(nivel) * self.tolerancia)

    # ---------------------------------------------------------------- sinal
    def sinal_estrategico(self, preco_atual: float) -> Dict:
        """
        Sinal padronizado (buy/sell/hold) + contexto:
            preço acima da VAH  -> buy  (aceitação acima do valor / breakout)
            preço abaixo da VAL -> sell (aceitação abaixo do valor / breakdown)
            dentro da value area -> hold (equilíbrio); informa se está em POC/HVN/LVN/single print
        """
        res = self.analisar()
        preco = float(preco_atual)
        ctx = []
        if any(self.perto(preco, sp) for sp in res["single_prints"]):
            ctx.append("single print")
        if any(self.perto(preco, h) for h in res["HVN"]):
            ctx.append("HVN")
        if any(self.perto(preco, l) for l in res["LVN"]):
            ctx.append("LVN")
        if self.perto(preco, res["POC"]):
            ctx.append("POC")
        largura = max(res["VAH"] - res["VAL"], 1e-9)
        if preco > res["VAH"]:
            forca = min((preco - res["VAH"]) / largura, 1.0)
            return {"acao": "buy", "motivo": f"Acima da VAH {res['VAH']:.2f} (shape {res['shape']})",
                    "forca": round(max(forca, 0.3), 3), "contexto": ctx, **{k: res[k] for k in ("POC", "VAL", "VAH", "shape")}}
        if preco < res["VAL"]:
            forca = min((res["VAL"] - preco) / largura, 1.0)
            return {"acao": "sell", "motivo": f"Abaixo da VAL {res['VAL']:.2f} (shape {res['shape']})",
                    "forca": round(max(forca, 0.3), 3), "contexto": ctx, **{k: res[k] for k in ("POC", "VAL", "VAH", "shape")}}
        return {"acao": "hold", "motivo": f"Dentro da value area [{res['VAL']:.2f}-{res['VAH']:.2f}] {ctx or ''}",
                "forca": 0.0, "contexto": ctx, **{k: res[k] for k in ("POC", "VAL", "VAH", "shape")}}
