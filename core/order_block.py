# core/order_block.py
"""
Order Blocks (conceito ICT/SMC).

Order block de ALTA (bullish): último candle de BAIXA antes de um deslocamento forte de alta
que rompe a máxima dos candles anteriores. Zona = [low, open] desse candle (corpo + pavio inferior).
Order block de BAIXA (bearish): último candle de ALTA antes de um deslocamento forte de baixa
que rompe a mínima anterior. Zona = [open, high].

Deslocamento forte = o movimento dos próximos `janela_deslocamento` candles percorre
pelo menos `fator_atr` ATRs e rompe a estrutura (máxima/mínima dos `lookback` candles anteriores).

Um bloco fica "mitigado" quando o preço volta e fecha além da zona.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from core.utils_indicadores import atr


class OrderBlockDetector:
    def __init__(self, ohlcv: Sequence, fator_atr: float = 1.5, janela_deslocamento: int = 3,
                 lookback: int = 5, tolerancia: float = 0.02):
        if not ohlcv or len(ohlcv) < lookback + janela_deslocamento + 2:
            raise ValueError("candles insuficientes para detectar order blocks")
        self.ohlcv = [list(map(float, c[:6])) for c in ohlcv]
        self.fator_atr = fator_atr
        self.janela = janela_deslocamento
        self.lookback = lookback
        self.tolerancia = tolerancia
        self.highs = [c[2] for c in self.ohlcv]
        self.lows = [c[3] for c in self.ohlcv]
        self.max_high = max(self.highs)
        self.min_low = min(self.lows)
        self.atr = atr(self.ohlcv, 14) or (self.max_high - self.min_low) / 20.0

    def identificar_blocks(self, tipo: str = "bullish", apenas_ativos: bool = True) -> List[Dict]:
        blocks: List[Dict] = []
        n = len(self.ohlcv)
        for i in range(self.lookback, n - self.janela):
            ts, o, h, l, c, v = self.ohlcv[i]
            prox = self.ohlcv[i + 1:i + 1 + self.janela]
            if not prox:
                continue
            if tipo == "bullish":
                if not c < o:  # precisa ser candle de baixa
                    continue
                max_prox = max(p[2] for p in prox)
                estrutura = max(self.highs[i - self.lookback:i])
                deslocamento = max_prox - l
                if deslocamento >= self.fator_atr * self.atr and max_prox > estrutura \
                        and all(p[4] > p[1] for p in prox[:1]):
                    zona = (l, o)
                    blocks.append(self._bloco(i, "bullish", zona, deslocamento))
            else:
                if not c > o:
                    continue
                min_prox = min(p[3] for p in prox)
                estrutura = min(self.lows[i - self.lookback:i])
                deslocamento = h - min_prox
                if deslocamento >= self.fator_atr * self.atr and min_prox < estrutura \
                        and all(p[4] < p[1] for p in prox[:1]):
                    zona = (o, h)
                    blocks.append(self._bloco(i, "bearish", zona, deslocamento))
        self._marcar_mitigados(blocks)
        if apenas_ativos:
            blocks = [b for b in blocks if not b["mitigado"]]
        return blocks

    def _bloco(self, i: int, tipo: str, zona, deslocamento: float) -> Dict:
        lo, hi = min(zona), max(zona)
        return {
            "index": i,
            "timestamp": int(self.ohlcv[i][0]),
            "tipo": tipo,
            "zona": (lo, hi),
            "preco": round((lo + hi) / 2.0, 4),
            "forca": round(deslocamento / self.atr, 2) if self.atr else 0.0,
            "volume": self.ohlcv[i][5],
            "mitigado": False,
        }

    def _marcar_mitigados(self, blocks: List[Dict]):
        for b in blocks:
            lo, hi = b["zona"]
            for c in self.ohlcv[b["index"] + self.janela + 1:]:
                if b["tipo"] == "bullish" and c[4] < lo:
                    b["mitigado"] = True
                    break
                if b["tipo"] == "bearish" and c[4] > hi:
                    b["mitigado"] = True
                    break

    def _zona_valida(self, zona) -> bool:
        min_limit = self.min_low * (1 - self.tolerancia)
        max_limit = self.max_high * (1 + self.tolerancia)
        return all(min_limit <= p <= max_limit for p in zona)

    def blocos_proximos(self, preco: float, tipo: str, max_dist_pct: float = 0.03, n: int = 3) -> List[Dict]:
        """Blocos ativos do tipo pedido, ordenados pela distância ao preço (até max_dist_pct)."""
        blocos = self.identificar_blocks(tipo)
        proximos = [b for b in blocos if abs(b["preco"] - preco) / preco <= max_dist_pct]
        return sorted(proximos, key=lambda b: abs(b["preco"] - preco))[:n]

    def sinal(self, preco: float) -> Dict:
        """
        buy  -> preço dentro/tocando um order block bullish ativo (zona de demanda)
        sell -> preço dentro/tocando um order block bearish ativo (zona de oferta)
        hold -> fora das zonas
        """
        tol = self.atr * 0.25
        for b in self.identificar_blocks("bullish"):
            lo, hi = b["zona"]
            if lo - tol <= preco <= hi + tol:
                return {"acao": "buy", "motivo": f"Preço em order block bullish [{lo:.2f}-{hi:.2f}]",
                        "forca": round(min(b["forca"] / 3.0, 1.0), 3), "bloco": b}
        for b in self.identificar_blocks("bearish"):
            lo, hi = b["zona"]
            if lo - tol <= preco <= hi + tol:
                return {"acao": "sell", "motivo": f"Preço em order block bearish [{lo:.2f}-{hi:.2f}]",
                        "forca": round(min(b["forca"] / 3.0, 1.0), 3), "bloco": b}
        return {"acao": "hold", "motivo": "Fora de order blocks ativos", "forca": 0.0}


if __name__ == "__main__":
    from core.conexoes.conexao_bybit import BybitConnector

    con = BybitConnector("simulador")
    ohlcv = con.obter_ohlcv("BTCUSDT", timeframe="15m", limite=200)
    det = OrderBlockDetector(ohlcv)
    for b in det.identificar_blocks("bullish"):
        print("bullish", b)
    for b in det.identificar_blocks("bearish"):
        print("bearish", b)
