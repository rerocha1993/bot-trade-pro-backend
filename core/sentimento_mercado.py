# core/sentimento_mercado.py
"""
Sentimento de mercado como FILTRO CONTRÁRIO (nunca decide a entrada; Elliott é a lei).

Score final em [-1, +1]:  -1 = medo extremo (viés contrário: comprar) ... +1 = ganância extrema (viés: vender).

Fontes (todas gratuitas, com cache):
    1. Fear & Greed Index (alternative.me)           peso 0.40
    2. Funding rate Bybit (perpétuo)                 peso 0.25  (funding alto = multidão comprada alavancada)
    3. Long/Short ratio Bybit (contas)               peso 0.20
    4. Variação do Open Interest (24h) x preço       peso 0.15  (OI e preço subindo forte = euforia)
    5. X/Twitter (opcional, exige X_BEARER_TOKEN)    peso 0.20 quando disponível (renormaliza)

Regras de uso pelo motor (perfil conservador):
    score >= +0.6  -> proíbe NOVAS COMPRAS; reduz tamanho das vendas? não: só bloqueia compras
    score <= -0.6  -> proíbe NOVAS VENDAS
    turbo: só reduz o tamanho da posição pela metade nas zonas extremas
"""
from __future__ import annotations

import logging
import os
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

LIMIAR_EXTREMO = 0.6


class SentimentoMercado:
    def __init__(self, connector=None, cache_seg: int = 300, timeout: int = 10):
        """
        connector: BybitConnector (qualquer modo) para funding/ratio/OI. Se None, cria um público.
        """
        self.connector = connector
        self.cache_seg = cache_seg
        self.timeout = timeout
        self._cache: Dict[str, tuple] = {}
        self.x_token = os.getenv("X_BEARER_TOKEN")
        try:
            from core.dados_derivativos import DadosDerivativos
            self.derivativos = DadosDerivativos(clientes={"bybit": connector.exchange} if connector is not None else None)
        except Exception:
            self.derivativos = None

    def _con(self):
        if self.connector is None:
            from core.conexoes.conexao_bybit import BybitConnector
            self.connector = BybitConnector("simulador")
        return self.connector

    def _cached(self, chave, fn):
        item = self._cache.get(chave)
        if item and time.time() - item[0] < self.cache_seg:
            return item[1]
        try:
            valor = fn()
        except Exception as e:
            logger.warning("sentimento %s falhou: %s", chave, str(e)[:100])
            valor = None
        self._cache[chave] = (time.time(), valor)
        return valor

    # ------------------------------------------------------------ fontes
    def fear_greed(self) -> Optional[Dict]:
        def fetch():
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=self.timeout).json()
            d = r["data"][0]
            return {"valor": int(d["value"]), "classificacao": d["value_classification"]}
        return self._cached("fng", fetch)

    def funding(self, par: str) -> Optional[float]:
        def fetch():
            fr = self._con().exchange.fetch_funding_rate(self._con().simbolo(par))
            return float(fr.get("fundingRate") or 0.0)
        return self._cached(f"funding:{par}", fetch)

    def long_short_ratio(self, par: str) -> Optional[float]:
        def fetch():
            r = self._con().exchange.publicGetV5MarketAccountRatio({
                "category": "linear", "symbol": self._con().simbolo_bybit(par), "period": "1h", "limit": 1})
            lista = (r.get("result") or {}).get("list") or []
            return float(lista[0]["buyRatio"]) if lista else None
        return self._cached(f"ratio:{par}", fetch)

    def open_interest_var(self, par: str) -> Optional[Dict]:
        """Variação do OI nas últimas 24h (histórico 1h) e variação de preço no mesmo período."""
        def fetch():
            con = self._con()
            hist = con.exchange.fetch_open_interest_history(con.simbolo(par), timeframe="1h", limit=25)
            if len(hist) < 2:
                return None
            oi0 = float(hist[0].get("openInterestAmount") or hist[0].get("openInterestValue") or 0)
            oi1 = float(hist[-1].get("openInterestAmount") or hist[-1].get("openInterestValue") or 0)
            candles = con.obter_ohlcv(par, "1h", 25)
            p0, p1 = float(candles[0][4]), float(candles[-1][4])
            return {"oi_var": (oi1 - oi0) / oi0 if oi0 else 0.0, "preco_var": (p1 - p0) / p0 if p0 else 0.0}
        return self._cached(f"oi:{par}", fetch)

    def x_twitter(self, termo: str = "bitcoin") -> Optional[float]:
        """Opcional: proporção de tweets recentes com palavras de euforia vs medo. Exige X_BEARER_TOKEN."""
        if not self.x_token:
            return None
        def fetch():
            url = "https://api.x.com/2/tweets/search/recent"
            params = {"query": f"{termo} lang:en -is:retweet", "max_results": 100}
            r = requests.get(url, params=params, headers={"Authorization": f"Bearer {self.x_token}"}, timeout=self.timeout)
            if r.status_code != 200:
                return None
            textos = [t.get("text", "").lower() for t in r.json().get("data", [])]
            euforia = ("moon", "ath", "all time high", "bull run", "pump", "euphoria", "to the moon", "buy the top")
            medo = ("crash", "dump", "fear", "capitulation", "bear market", "liquidat", "panic", "sell everything")
            e = sum(any(w in t for w in euforia) for t in textos)
            m = sum(any(w in t for w in medo) for t in textos)
            if e + m == 0:
                return 0.0
            return (e - m) / (e + m)
        return self._cached(f"x:{termo}", fetch)

    # ------------------------------------------------------------- score
    def score(self, par: str = "BTCUSDT") -> Dict:
        componentes = {}
        pesos = {}

        fng = self.fear_greed()
        if fng:
            componentes["fear_greed"] = (fng["valor"] - 50) / 50.0
            pesos["fear_greed"] = 0.40

        f = self.funding(par)
        if f is not None:
            # 0.01% por 8h é neutro; 0.1% = euforia forte; -0.05% = medo forte
            componentes["funding"] = max(-1.0, min(1.0, (f - 0.0001) / 0.0009))
            pesos["funding"] = 0.25

        r = self.long_short_ratio(par)
        if r is not None:
            componentes["long_short"] = max(-1.0, min(1.0, (r - 0.5) / 0.2))
            pesos["long_short"] = 0.20

        oi = self.open_interest_var(par)
        if oi:
            # euforia: OI subindo com preço subindo; medo: OI subindo com preço caindo (shorts) ou OI caindo forte
            sinal = oi["oi_var"] * (1 if oi["preco_var"] >= 0 else -1)
            componentes["open_interest"] = max(-1.0, min(1.0, sinal / 0.10))
            pesos["open_interest"] = 0.15

        x = self.x_twitter()
        if x is not None:
            componentes["x_twitter"] = x
            pesos["x_twitter"] = 0.20

        # derivativos multi-exchange: funding médio Bybit/Binance/OKX e liquidações (Coinglass, opcional)
        deriv = getattr(self, "derivativos", None)
        if deriv is not None:
            fm = deriv.funding_multi(par)
            if fm:
                componentes["funding"] = max(-1.0, min(1.0, (fm["media"] - 0.0001) / 0.0009))
                pesos["funding"] = 0.25
            liq = deriv.liquidacoes(par)
            if liq and liq.get("liq_total_24h"):
                razao = (liq["liq_short_24h"] - liq["liq_long_24h"]) / liq["liq_total_24h"]
                componentes["liquidacoes"] = max(-1.0, min(1.0, razao))
                pesos["liquidacoes"] = 0.15

        total = sum(pesos.values())
        valor = sum(componentes[k] * pesos[k] for k in componentes) / total if total else 0.0
        valor = round(max(-1.0, min(1.0, valor)), 3)
        if valor >= LIMIAR_EXTREMO:
            zona, vies = "ganancia_extrema", "sell"
        elif valor <= -LIMIAR_EXTREMO:
            zona, vies = "medo_extremo", "buy"
        elif valor >= 0.25:
            zona, vies = "ganancia", None
        elif valor <= -0.25:
            zona, vies = "medo", None
        else:
            zona, vies = "neutro", None
        return {
            "score": valor, "zona": zona, "vies_contrario": vies,
            "componentes": {k: round(v, 3) for k, v in componentes.items()},
            "fear_greed": fng, "funding": f, "long_short_ratio": r, "open_interest": oi,
            "bloqueia_compra": valor >= LIMIAR_EXTREMO, "bloqueia_venda": valor <= -LIMIAR_EXTREMO,
            "timestamp": int(time.time()),
        }


if __name__ == "__main__":
    import json
    print(json.dumps(SentimentoMercado().score("BTCUSDT"), indent=2, ensure_ascii=False))
