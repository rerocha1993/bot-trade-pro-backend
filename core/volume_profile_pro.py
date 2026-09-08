# core/volume_profile_pro.py
"""
Volume Profile.

O volume de cada candle é distribuído uniformemente entre os bins que o candle atravessa
(low..high). Isso aproxima o "volume por preço" muito melhor do que usar só o fechamento.

    POC = bin com maior volume
    Value Area (70%) ao redor do POC -> VAH / VAL
    HVN / LVN = bins com maior / menor volume (LVN só entre bins com volume > 0)
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd


class VolumeProfilePRO:
    def __init__(self, ohlcv: Sequence, num_bins: int = 40, tolerancia: float = 0.002):
        if not ohlcv:
            raise ValueError("ohlcv vazio")
        self.ohlcv = list(ohlcv)
        self.tolerancia = tolerancia
        self.highs = np.array([float(c[2]) for c in self.ohlcv])
        self.lows = np.array([float(c[3]) for c in self.ohlcv])
        self.closes = np.array([float(c[4]) for c in self.ohlcv])
        self.vols = np.array([float(c[5] or 0) for c in self.ohlcv])
        self.candle_min_low = float(self.lows.min())
        self.candle_max_high = float(self.highs.max())
        self.min_price, self.max_price = self.candle_min_low, self.candle_max_high
        if self.max_price <= self.min_price:
            self.max_price = self.min_price + max(abs(self.min_price) * 0.001, 1e-6)
        self.num_bins = max(int(num_bins), 5)
        self.bin_edges = np.linspace(self.min_price, self.max_price, self.num_bins + 1)
        self.bin_labels = 0.5 * (self.bin_edges[:-1] + self.bin_edges[1:])
        self.bin_width = float(self.bin_edges[1] - self.bin_edges[0])
        self.hist = self._distribuir()

    def _idx(self, preco: float) -> int:
        i = int((preco - self.min_price) // self.bin_width)
        return max(0, min(i, self.num_bins - 1))

    def _distribuir(self) -> np.ndarray:
        hist = np.zeros(self.num_bins, dtype=float)
        for h, l, v in zip(self.highs, self.lows, self.vols):
            if v <= 0:
                continue
            a, b = self._idx(min(h, l)), self._idx(max(h, l))
            n = b - a + 1
            hist[a:b + 1] += v / n
        return hist

    # ---------------------------------------------------------------- níveis
    def poc_va(self, pct: float = 0.70) -> Dict[str, float]:
        total = float(self.hist.sum())
        if total <= 0:
            return {"POC": float(self.closes[-1]), "VAL": self.min_price, "VAH": self.max_price}
        poc_i = int(np.argmax(self.hist))
        alvo = pct * total
        lo_i = hi_i = poc_i
        acum = float(self.hist[poc_i])
        while acum < alvo and (lo_i > 0 or hi_i < self.num_bins - 1):
            acima = self.hist[hi_i + 1] if hi_i < self.num_bins - 1 else -1
            abaixo = self.hist[lo_i - 1] if lo_i > 0 else -1
            if acima >= abaixo:
                hi_i += 1
                acum += max(acima, 0)
            else:
                lo_i -= 1
                acum += max(abaixo, 0)
        return {
            "POC": float(self.bin_labels[poc_i]),
            "VAL": float(self.bin_edges[lo_i]),
            "VAH": float(self.bin_edges[hi_i + 1]),
        }

    def hvn_lvn(self, n: int = 3, tolerancia: float = None) -> Dict[str, List[float]]:
        com_volume = [i for i in range(self.num_bins) if self.hist[i] > 0]
        if not com_volume:
            return {"HVN": [], "LVN": []}
        ordem = sorted(com_volume, key=lambda i: self.hist[i])
        return {
            "HVN": [float(self.bin_labels[i]) for i in ordem[::-1][:n]],
            "LVN": [float(self.bin_labels[i]) for i in ordem[:n]],
        }

    def rejection_zones(self, max_pct: float = 0.02, tolerancia: float = None) -> List[float]:
        total = float(self.hist.sum())
        if total <= 0:
            return []
        return [float(self.bin_labels[i]) for i in range(self.num_bins)
                if 0 < self.hist[i] / total < max_pct]

    def top_volume_zones(self, pct: float = 0.7, tolerancia: float = None) -> List[float]:
        total = float(self.hist.sum())
        if total <= 0:
            return []
        ordem = np.argsort(self.hist)[::-1]
        acum, area = 0.0, []
        for i in ordem:
            acum += self.hist[i]
            area.append(float(self.bin_labels[i]))
            if acum / total >= pct:
                break
        return sorted(area)

    def perto(self, preco: float, nivel: float) -> bool:
        return abs(preco - nivel) <= max(self.bin_width / 2.0, abs(nivel) * self.tolerancia)

    def analisar(self) -> Dict:
        va = self.poc_va()
        nodes = self.hvn_lvn()
        return {**va, **nodes, "bin_width": self.bin_width, "range": (self.min_price, self.max_price)}

    # ----------------------------------------------------------------- sinal
    def price_signal(self, preco_atual: float, tolerancia: float = None) -> Dict:
        """
        buy  -> preço acima da VAH (aceitação acima do valor)
        sell -> preço abaixo da VAL
        hold -> dentro da value area; contexto informa HVN (defesa institucional) / LVN (rejeição)
        """
        res = self.analisar()
        preco = float(preco_atual)
        ctx = []
        if any(self.perto(preco, h) for h in res["HVN"]):
            ctx.append("HVN")
        if any(self.perto(preco, l) for l in res["LVN"]):
            ctx.append("LVN")
        if self.perto(preco, res["POC"]):
            ctx.append("POC")
        largura = max(res["VAH"] - res["VAL"], 1e-9)
        base = {k: res[k] for k in ("POC", "VAL", "VAH", "HVN", "LVN")}
        if preco > res["VAH"]:
            forca = min((preco - res["VAH"]) / largura, 1.0)
            return {"acao": "buy", "motivo": f"Acima da VAH {res['VAH']:.2f} do Volume Profile",
                    "forca": round(max(forca, 0.3), 3), "contexto": ctx, **base}
        if preco < res["VAL"]:
            forca = min((res["VAL"] - preco) / largura, 1.0)
            return {"acao": "sell", "motivo": f"Abaixo da VAL {res['VAL']:.2f} do Volume Profile",
                    "forca": round(max(forca, 0.3), 3), "contexto": ctx, **base}
        return {"acao": "hold", "motivo": f"Dentro da value area do VP {ctx or ''}", "forca": 0.0,
                "contexto": ctx, **base}

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({"bin": self.bin_labels, "volume": self.hist})

    def export_heatmap(self):
        return self.bin_labels.tolist(), self.hist.tolist()
