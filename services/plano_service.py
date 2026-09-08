# services/plano_service.py
"""
Busca os dados e emite o PLANO DE MERCADO do par (core/orquestrador/plano.py).

Um plano por par, com cache curto: todos os bots do par leem o mesmo plano no mesmo ciclo, em vez de cada um
recalcular superciclo, contagens e níveis por conta própria.

    PlanoService(servicos).plano("BTCUSDT")   -> dict do plano (cacheado)

O plano vigente também fica em data/plano_<PAR>.json para inspeção e para o painel.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Dict, Optional

from core.orquestrador.plano import montar_plano

logger = logging.getLogger(__name__)
PASTA = os.path.join("data")
_CACHE: Dict[str, tuple] = {}
_LOCK = threading.Lock()


class PlanoService:
    def __init__(self, servicos: Optional[Dict] = None, connector=None, db=None):
        self.servicos = servicos or {}
        self.connector = connector or (self.servicos.get("connectors") or {}).get("simulador")
        self.db = db

    # ------------------------------------------------------------- coleta
    def _connector(self):
        if self.connector is None:
            from core.conexoes.conexao_bybit import BybitConnector
            self.connector = BybitConnector("simulador")
        return self.connector

    def _trader(self, par: str) -> Optional[Dict]:
        svc = self.servicos.get("trader")
        try:
            if svc is not None and hasattr(svc, "leitura"):
                return svc.leitura(par)
            from services.trader_service import TraderService
            return TraderService(self._connector()).leitura(par)
        except Exception as e:
            logger.warning("plano: leitura do trader indisponível: %s", e)
            return None

    def _graus_mestre(self, par: str) -> Dict[str, Dict]:
        if self.db is None:
            return {}
        try:
            from services.elliott_mestre_service import ElliottMestreService
            res = ElliottMestreService(self.db, self._connector()).calcular(par)
            return {k: v for k, v in (res.get("graus") or {}).items() if isinstance(v, dict)}
        except Exception as e:
            logger.warning("plano: contagem mestre indisponível: %s", e)
            return {}

    def _sentimento(self, par: str) -> Optional[Dict]:
        svc = self.servicos.get("sentimento")
        if svc is None:
            return None
        try:
            return svc.score(par)
        except Exception as e:
            logger.warning("plano: sentimento indisponível: %s", e)
            return None

    def _candles(self, par: str) -> Dict[str, list]:
        con = self._connector()
        out: Dict[str, list] = {}
        for tf, n in (("1d", 400), ("4h", 400)):
            try:
                out[tf] = con.obter_ohlcv(par, tf, n, somente_fechados=True)
            except Exception as e:
                logger.warning("plano: candles %s indisponíveis: %s", tf, e)
        return out

    def _composto(self, par: str) -> Optional[list]:
        md = self.servicos.get("market_data")
        if md is None:
            return None
        try:
            return md.ohlcv_composto(par, "1d", 300)
        except Exception as e:
            logger.debug("plano: candles compostos indisponíveis: %s", e)
            return None

    # ------------------------------------------------------------- plano
    def plano(self, par: str = "BTCUSDT", cache_seg: int = 300, forcar: bool = False) -> Dict:
        par = par.replace("/", "").upper()
        item = _CACHE.get(par)
        if item and not forcar and time.time() - item[0] < cache_seg:
            return item[1]
        with _LOCK:
            item = _CACHE.get(par)
            if item and not forcar and time.time() - item[0] < cache_seg:
                return item[1]
            candles = self._candles(par)
            preco = None
            try:
                preco = float(self._connector().obter_preco_atual(par))
            except Exception:
                d1 = candles.get("1d") or []
                preco = float(d1[-1][4]) if d1 else 0.0
            p = montar_plano(
                par=par, preco=preco, trader=self._trader(par), ohlcv_por_tf=candles,
                elliott_por_grau=self._graus_mestre(par), sentimento=self._sentimento(par),
                ohlcv_composto=self._composto(par),
            )
            _CACHE[par] = (time.time(), p)
            self._salvar(par, p)
            return p

    @staticmethod
    def _salvar(par: str, plano: Dict):
        try:
            os.makedirs(PASTA, exist_ok=True)
            leve = {k: v for k, v in plano.items() if k not in ("leituras", "niveis")}
            leve["n_leituras"] = len(plano.get("leituras") or [])
            leve["n_niveis"] = len(plano.get("niveis") or [])
            with open(os.path.join(PASTA, f"plano_{par}.json"), "w", encoding="utf-8") as f:
                json.dump(leve, f, ensure_ascii=False, indent=1, default=str)
        except Exception as e:
            logger.debug("plano: não foi possível salvar: %s", e)
