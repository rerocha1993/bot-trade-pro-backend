# core/contexto_derivativos.py
"""
CONTEXTO DE ORDER FLOW para o jogo do range: quem está posicionado e pode ficar PRESO na borda.

    Proporção long/short de CONTAS da Bybit (BTCUSDT, 1h) comparada com a mediana dos últimos 30 dias.
    No VAL, mais contas vendidas que o normal = vendidos atrasados no fundo, combustível para voltar ao POC.
    No VAH, mais contas compradas que o normal = comprados atrasados no topo.

Medido em scripts/estudo_bordas.py (1.143 toques desde 2020, efeito nos dois períodos e nos dois lados).
O valor de cada hora só é usado depois que a hora fecha (sem olhar o futuro).
"""
from __future__ import annotations

import logging
import time
from bisect import bisect_right
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

HORA_MS = 3_600_000
JANELA_MS = 30 * 24 * HORA_MS


class ContextoLSR:
    def __init__(self, serie: Dict[int, float], janela_ms: int = JANELA_MS):
        pares = sorted((int(k), float(v)) for k, v in serie.items())
        self.ts: List[int] = [p[0] for p in pares]
        self.val: List[float] = [p[1] for p in pares]
        self.janela_ms = janela_ms
        self._cache: Dict[int, Optional[float]] = {}

    def _indice(self, agora_ms: int) -> int:
        """Último ponto cuja hora já fechou em `agora_ms`."""
        return bisect_right(self.ts, agora_ms - HORA_MS) - 1

    def mediana(self, agora_ms: int) -> Optional[float]:
        i = self._indice(agora_ms)
        if i < 0:
            return None
        if i in self._cache:
            return self._cache[i]
        j = bisect_right(self.ts, self.ts[i] - self.janela_ms)
        janela = sorted(self.val[j:i + 1])
        m = janela[len(janela) // 2] if len(janela) >= 24 * 7 else None      # pelo menos uma semana de dado
        self._cache[i] = m
        return m

    def atual(self, agora_ms: int) -> Optional[float]:
        i = self._indice(agora_ms)
        return self.val[i] if i >= 0 else None

    def presos_contra(self, agora_ms: int, lado: int) -> Optional[bool]:
        """True quando a multidão está do lado errado da borda (vendida no VAL, comprada no VAH). None = sem dado."""
        v, m = self.atual(agora_ms), self.mediana(agora_ms)
        if v is None or m is None:
            return None
        return v < m if lado == 1 else v > m

    def filtro(self, sem_dado: bool = False):
        """Função para o BacktestRange: entra só com presos do outro lado."""
        def f(ts: int, lado: int) -> bool:
            r = self.presos_contra(ts + 30 * 60 * 1000, lado)       # a decisão é no fechamento do bloco de 30 min
            return sem_dado if r is None else r
        return f


def baixar_lsr(exchange=None, dias: int = 32, simbolo: str = "BTCUSDT") -> Dict[int, float]:
    """Long/short de contas da Bybit (1h), dado público da mainnet: {timestamp_ms: compradas / vendidas}."""
    if exchange is None:
        import ccxt
        exchange = ccxt.bybit({"enableRateLimit": True})
    out: Dict[int, float] = {}
    fim = int(time.time() * 1000)
    desde = fim - dias * 24 * HORA_MS
    while fim > desde:
        ini = max(desde, fim - 500 * HORA_MS)
        r = exchange.publicGetV5MarketAccountRatio({"category": "linear", "symbol": simbolo, "period": "1h",
                                                     "startTime": ini, "endTime": fim, "limit": 500})
        for x in (r.get("result") or {}).get("list") or []:
            out[int(x["timestamp"])] = float(x["buyRatio"]) / max(float(x["sellRatio"]), 1e-9)
        fim = ini - 1
    return out


class LeitorLSR:
    """Mantém o ContextoLSR ao vivo, relendo a cada `validade_s`. Falha de rede mantém a última leitura."""

    def __init__(self, validade_s: float = 900, baixar=baixar_lsr):
        self.validade_s = validade_s
        self.baixar = baixar
        self._ctx: Optional[ContextoLSR] = None
        self._lido_em = 0.0

    def contexto(self) -> Optional[ContextoLSR]:
        if self._ctx is None or time.time() - self._lido_em > self.validade_s:
            try:
                self._ctx = ContextoLSR(self.baixar())
                self._lido_em = time.time()
            except Exception as e:
                logger.warning("long/short da Bybit indisponível: %s", e)
        return self._ctx
