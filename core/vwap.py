# core/vwap.py
"""
VWAP (Volume Weighted Average Price) com bandas de desvio-padrão ponderadas por volume.

    VWAP = Σ(preço_típico_i * volume_i) / Σ(volume_i)
    preço_típico = (high + low + close) / 3
    σ = sqrt( Σ(volume_i * (tp_i - VWAP)^2) / Σ(volume_i) )

Âncoras suportadas:
    - toda a janela (padrão)
    - início do dia UTC (vwap_intraday)
    - índice arbitrário (anchor_idx)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import numpy as np

from core.utils_indicadores import precos_tipicos


class VWAPCalculator:
    def __init__(self, ohlcv: Sequence):
        if not ohlcv:
            raise ValueError("ohlcv vazio")
        self.ohlcv = list(ohlcv)
        self.timestamps = np.array([int(c[0]) for c in self.ohlcv])
        self.prices = np.array(precos_tipicos(self.ohlcv), dtype=float)
        self.closes = np.array([float(c[4]) for c in self.ohlcv], dtype=float)
        self.volumes = np.array([float(c[5] or 0) for c in self.ohlcv], dtype=float)
        self.highs = np.array([float(c[2]) for c in self.ohlcv], dtype=float)
        self.lows = np.array([float(c[3]) for c in self.ohlcv], dtype=float)

    # -------------------------------------------------------------- núcleo
    def vwap(self, anchor_idx: int = 0) -> Optional[float]:
        anchor_idx = max(0, min(anchor_idx, len(self.prices) - 1))
        p = self.prices[anchor_idx:]
        v = self.volumes[anchor_idx:]
        soma_v = float(np.sum(v))
        if soma_v <= 0:
            return float(np.mean(p)) if len(p) else None
        return float(np.sum(p * v) / soma_v)

    def vwap_bandas(self, anchor_idx: int = 0, desvios: Sequence[float] = (1, 2, 3)) -> Optional[Dict]:
        valor = self.vwap(anchor_idx)
        if valor is None:
            return None
        p = self.prices[anchor_idx:]
        v = self.volumes[anchor_idx:]
        soma_v = float(np.sum(v))
        if soma_v > 0:
            variancia = float(np.sum(v * (p - valor) ** 2) / soma_v)
        else:
            variancia = float(np.var(p))
        stddev = float(np.sqrt(max(variancia, 0.0)))
        bandas = {}
        for n in desvios:
            bandas[f"+{n}σ"] = valor + n * stddev
            bandas[f"-{n}σ"] = valor - n * stddev
        return {"vwap": valor, "stddev": stddev, "bandas": bandas, "anchor_idx": anchor_idx}

    def serie_vwap(self, anchor_idx: int = 0) -> List[float]:
        """VWAP cumulativo candle a candle (para plotar)."""
        p = self.prices[anchor_idx:]
        v = self.volumes[anchor_idx:]
        cum_pv = np.cumsum(p * v)
        cum_v = np.cumsum(v)
        with np.errstate(divide="ignore", invalid="ignore"):
            serie = np.where(cum_v > 0, cum_pv / np.where(cum_v == 0, 1, cum_v), p)
        return [float(x) for x in serie]

    # ------------------------------------------------------------- âncoras
    def _index_inicio_dia(self) -> int:
        """Índice do primeiro candle do dia UTC mais recente (0 se não houver)."""
        ultimo = datetime.fromtimestamp(int(self.timestamps[-1]) / 1000, tz=timezone.utc).date()
        for idx in range(len(self.timestamps) - 1, -1, -1):
            d = datetime.fromtimestamp(int(self.timestamps[idx]) / 1000, tz=timezone.utc).date()
            if d != ultimo:
                return min(idx + 1, len(self.timestamps) - 1)
        return 0

    def vwap_intraday(self) -> Optional[Dict]:
        return self.vwap_bandas(anchor_idx=self._index_inicio_dia())

    def obter_vwap_atual(self) -> Optional[float]:
        return self.vwap(anchor_idx=0)

    def obter_vwap_ultimos(self, n: int) -> Optional[float]:
        return self.vwap(anchor_idx=max(0, len(self.prices) - n))

    # ---------------------------------------------------------------- sinal
    def sinal(self, preco_atual: Optional[float] = None, anchor_idx: int = 0,
              zona_neutra_sigma: float = 0.25) -> Dict:
        """
        Sinal direcional em relação ao VWAP:
            preço acima do VWAP por mais de `zona_neutra_sigma` desvios -> buy (viés comprador)
            preço abaixo -> sell
            dentro da zona neutra -> hold
        Também informa se o preço está esticado (> 2σ), útil para evitar entradas tardias.
        """
        res = self.vwap_bandas(anchor_idx)
        if not res:
            return {"acao": "hold", "motivo": "VWAP indisponível", "forca": 0.0}
        preco = float(preco_atual if preco_atual is not None else self.closes[-1])
        vwap, sd = res["vwap"], res["stddev"]
        if sd <= 0:
            sd = max(abs(vwap) * 0.001, 1e-9)
        z = (preco - vwap) / sd
        esticado = abs(z) >= 2.0
        forca = min(abs(z) / 2.0, 1.0)
        if z > zona_neutra_sigma:
            acao = "buy"
        elif z < -zona_neutra_sigma:
            acao = "sell"
        else:
            acao = "hold"
        return {
            "acao": acao,
            "motivo": f"Preço {preco:.2f} vs VWAP {vwap:.2f} (z={z:+.2f}σ{', esticado' if esticado else ''})",
            "forca": round(forca, 3),
            "vwap": vwap,
            "stddev": sd,
            "z": z,
            "esticado": esticado,
            "bandas": res["bandas"],
        }
