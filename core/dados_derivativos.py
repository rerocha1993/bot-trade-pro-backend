# core/dados_derivativos.py
"""
Dados de derivativos e calendário que a multidão não olha, todos com cache:

    funding_multi(par)        funding rate atual em Bybit, Binance e OKX (ccxt público) -> média e dispersão
    open_interest_multi(par)  open interest em Bybit, Binance e OKX
    liquidacoes(par)          mapa de liquidações e long/short (Coinglass; exige COINGLASS_API_KEY no .env)
    calendario(dias)          eventos macro de alto impacto (Forex Factory JSON, gratuito, sem chave)
    evento_proximo(minutos)   True se houver evento de alto impacto (USD) na janela

Tudo falha de forma silenciosa (retorna None) para nunca travar o bot.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


class DadosDerivativos:
    def __init__(self, cache_seg: int = 300, timeout: int = 10, clientes: Optional[Dict[str, object]] = None):
        self.cache_seg = cache_seg
        self.timeout = timeout
        self._cache: Dict[str, tuple] = {}
        self._ex: Dict[str, object] = dict(clientes or {})
        self.coinglass_key = os.getenv("COINGLASS_API_KEY")

    def _cached(self, chave, fn, ttl=None):
        item = self._cache.get(chave)
        if item and time.time() - item[0] < (ttl or self.cache_seg):
            return item[1]
        try:
            valor = fn()
        except Exception as e:
            logger.warning("dados derivativos %s: %s", chave, str(e)[:100])
            valor = None
        self._cache[chave] = (time.time(), valor)
        return valor

    def _exchange(self, nome):
        if nome not in self._ex:
            import ccxt
            cfg = {"enableRateLimit": True, "timeout": self.timeout * 1000, "options": {"defaultType": "swap"}}
            self._ex[nome] = getattr(ccxt, nome)(cfg)
        return self._ex[nome]

    @staticmethod
    def _simbolo(nome, par):
        base = par.upper().replace("/", "").replace("USDT", "").replace("USD", "")
        return f"{base}/USDT:USDT"

    # ------------------------------------------------------------ funding / OI
    def funding_multi(self, par: str = "BTCUSDT") -> Optional[Dict]:
        def fetch():
            out = {}
            for nome in ("bybit", "binance", "okx"):
                try:
                    fr = self._exchange(nome).fetch_funding_rate(self._simbolo(nome, par))
                    out[nome] = float(fr.get("fundingRate") or 0.0)
                except Exception as e:
                    logger.debug("funding %s: %s", nome, e)
            if not out:
                return None
            vals = list(out.values())
            return {"por_exchange": out, "media": sum(vals) / len(vals), "max": max(vals), "min": min(vals)}
        return self._cached(f"funding:{par}", fetch)

    def open_interest_multi(self, par: str = "BTCUSDT") -> Optional[Dict]:
        def fetch():
            out = {}
            for nome in ("bybit", "binance", "okx"):
                try:
                    oi = self._exchange(nome).fetch_open_interest(self._simbolo(nome, par))
                    out[nome] = float(oi.get("openInterestAmount") or oi.get("openInterestValue") or 0.0)
                except Exception as e:
                    logger.debug("OI %s: %s", nome, e)
            return {"por_exchange": out, "total": sum(out.values())} if out else None
        return self._cached(f"oi:{par}", fetch)

    # ------------------------------------------------------------- Coinglass
    def liquidacoes(self, par: str = "BTC") -> Optional[Dict]:
        """Liquidações agregadas 24h e razão long/short global (Coinglass API v4, plano gratuito com chave)."""
        if not self.coinglass_key:
            return None
        def fetch():
            h = {"CG-API-KEY": self.coinglass_key, "accept": "application/json"}
            base = par.upper().replace("USDT", "").replace("USD", "")
            r = requests.get("https://open-api-v4.coinglass.com/api/futures/liquidation/coin-list",
                             headers=h, timeout=self.timeout).json()
            item = next((x for x in (r.get("data") or []) if str(x.get("symbol", "")).upper() == base), None)
            if not item:
                return None
            return {"liq_long_24h": float(item.get("long_liquidation_usd_24h") or 0), "liq_short_24h": float(item.get("short_liquidation_usd_24h") or 0),
                    "liq_total_24h": float(item.get("liquidation_usd_24h") or 0), "fonte": "coinglass"}
        return self._cached(f"liq:{par}", fetch, ttl=600)

    # ------------------------------------------------------------ calendário
    def calendario(self) -> Optional[List[Dict]]:
        def fetch():
            r = requests.get(FF_URL, timeout=self.timeout, headers={"User-Agent": "bot-trade-pro/2.0"})
            if r.status_code != 200:
                return None
            eventos = []
            for e in r.json():
                try:
                    dt = datetime.fromisoformat(e["date"])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                eventos.append({"titulo": e.get("title"), "pais": e.get("country"), "impacto": e.get("impact"),
                                "quando": dt.astimezone(timezone.utc), "previsao": e.get("forecast"), "anterior": e.get("previous")})
            return eventos
        return self._cached("calendario", fetch, ttl=3600)

    def evento_proximo(self, minutos: int = 30, paises=("USD",), impactos=("High",)) -> Optional[Dict]:
        eventos = self.calendario() or []
        agora = datetime.now(timezone.utc)
        for e in eventos:
            if e["pais"] in paises and e["impacto"] in impactos:
                delta = (e["quando"] - agora).total_seconds() / 60
                if -minutos / 2 <= delta <= minutos:
                    return {"titulo": e["titulo"], "em_minutos": round(delta, 1), "quando": e["quando"].isoformat()}
        return None

    def proximos_eventos(self, horas: int = 48, paises=("USD",), impactos=("High", "Medium")) -> List[Dict]:
        eventos = self.calendario() or []
        agora = datetime.now(timezone.utc)
        out = []
        for e in eventos:
            delta_h = (e["quando"] - agora).total_seconds() / 3600
            if e["pais"] in paises and e["impacto"] in impactos and 0 <= delta_h <= horas:
                out.append({**e, "quando": e["quando"].isoformat(), "em_horas": round(delta_h, 1)})
        return sorted(out, key=lambda x: x["em_horas"])


if __name__ == "__main__":
    import json
    d = DadosDerivativos()
    print("funding:", d.funding_multi())
    print("OI:", d.open_interest_multi())
    print("próximos eventos USD:", json.dumps(d.proximos_eventos(72), default=str, ensure_ascii=False)[:600])
    print("evento em 30 min:", d.evento_proximo(30))
