# services/elliott_mestre_service.py
"""
Contagem mestre (desde 2011) e TRAVA de cenário.

    calcular(par)                       -> graus ciclo/primario/intermediario com cenários (usa data/historico ou Bybit)
    travar(par, grau, cenario_id, ...)  -> grava o cenário escolhido em elliott_contagens_validadas (status 'travada')
    trava_ativa(par)                    -> trava vigente (ou None) já verificada contra o preço atual
    destravar(par)

A trava vigente entra no alinhamento multi-grau como grau 'mestre' (services/strategy via AnaliseMultiGrau):
    conservador: não opera contra o viés da trava; turbo: opera contra com metade do tamanho.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from core.elliott_pro.mestre import GRAUS_MESTRE, contagem_mestre, verificar_trava
from core.market_data import reamostrar
from models.elliott_contagem_validada import ElliottContagemValidada
from models.elliott_revisao import ElliottRevisao

ARQUIVOS_BTC = {"1d": "BTCUSD_bitstamp_1d.csv", "4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv"}
_CACHE: Dict[str, tuple] = {}


class ElliottMestreService:
    def __init__(self, session=None, connector=None, backtest_service=None):
        self.session = session
        self.connector = connector
        self.backtests = backtest_service

    # ------------------------------------------------------------- dados
    def _series(self, par: str) -> Dict[str, List]:
        par = par.replace("/", "").upper()
        pasta = os.path.join("data", "historico")
        series = {}
        if par == "BTCUSDT" and all(os.path.exists(os.path.join(pasta, f)) for f in ARQUIVOS_BTC.values()):
            for tf, nome in ARQUIVOS_BTC.items():
                df = pd.read_csv(os.path.join(pasta, nome)).sort_values("timestamp")
                series[tf] = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
        else:
            if self.backtests is None:
                from services.backtest_service import BacktestService
                from api.database import SessionLocal
                self.backtests = BacktestService(SessionLocal, self.connector)
            for tf, dias in (("1d", 3650), ("4h", 1460), ("1h", 365)):
                try:
                    series[tf] = self.backtests.historico(par, tf, dias)
                except Exception:
                    continue
        if "1d" in series:
            series["1w"] = reamostrar(series["1d"], "1d", "1w")
        return series

    def calcular(self, par: str = "BTCUSDT", cache_seg: int = 900) -> Dict:
        import time
        par = par.replace("/", "").upper()
        item = _CACHE.get(par)
        if item and time.time() - item[0] < cache_seg:
            return item[1]
        res = contagem_mestre(self._series(par))
        res["par"] = par
        try:
            from services.trader_service import TraderService
            res["trader"] = TraderService(self.connector, self.backtests).leitura(par)
        except Exception as e:
            res["trader"] = {"erro": str(e)[:160]}
        trava = self.trava_ativa(par) if self.session is not None else None
        res["trava"] = trava
        _CACHE[par] = (time.time(), res)
        return res

    # ------------------------------------------------------------- trava
    def travar(self, par: str, grau: str, cenario_id: str, motivo: str = "escolha do usuário") -> Dict:
        par = par.replace("/", "").upper()
        res = self.calcular(par, cache_seg=0)
        g = res["graus"].get(grau) or {}
        cen = next((c for c in g.get("cenarios", []) if c["id"] == cenario_id), None)
        if not cen:
            raise ValueError(f"cenário {cenario_id} não encontrado no grau {grau}")
        self.destravar(par, motivo="substituída por nova trava")
        ondas = cen.get("ondas", [])
        d0 = datetime.strptime(ondas[0]["data_inicio"], "%Y-%m-%d") if ondas else datetime.utcnow()
        d1 = datetime.strptime(ondas[-1]["data_fim"], "%Y-%m-%d") if ondas else datetime.utcnow()
        payload = {"grau": grau, "timeframe": g.get("timeframe"), "cenario": cen, "vies": cen["vies"], "fase": cen["fase"],
                   "invalidacao": cen.get("invalidacao"), "alvos": cen.get("alvos", []), "travada_em": datetime.utcnow().isoformat(),
                   "preco_na_trava": res.get("preco")}
        reg = ElliottContagemValidada(par=par, timeframe=g.get("timeframe") or "1w", ondas_detectadas=payload,
                                      score_confianca=cen.get("prob_sucesso") or cen.get("probabilidade"), data_inicio=d0, data_fim=d1,
                                      nivel_ciclo=grau, status="travada")
        self.session.add(reg)
        self.session.flush()
        self.session.add(ElliottRevisao(contagem_id=reg.id, tipo_revisao="trava", motivo=motivo[:200], dados_corrigidos=payload))
        self.session.commit()
        _CACHE.pop(par, None)
        return {"id": reg.id, **payload}

    def destravar(self, par: str, motivo: str = "destravada pelo usuário") -> int:
        par = par.replace("/", "").upper()
        n = 0
        for reg in self.session.query(ElliottContagemValidada).filter_by(par=par, status="travada").all():
            reg.status = "destravada"
            self.session.add(ElliottRevisao(contagem_id=reg.id, tipo_revisao="destrava", motivo=motivo[:200], dados_anteriores=reg.ondas_detectadas))
            n += 1
        self.session.commit()
        _CACHE.pop(par, None)
        return n

    def trava_ativa(self, par: str, preco: Optional[float] = None) -> Optional[Dict]:
        par = par.replace("/", "").upper()
        reg = (self.session.query(ElliottContagemValidada).filter_by(par=par, status="travada")
               .order_by(ElliottContagemValidada.id.desc()).first())
        if not reg:
            return None
        trava = dict(reg.ondas_detectadas or {})
        trava["id"] = reg.id
        if preco is None:
            try:
                from core.conexoes.conexao_bybit import BybitConnector
                preco = (self.connector or BybitConnector("simulador")).obter_preco_atual(par)
            except Exception:
                preco = None
        if preco is not None:
            st = verificar_trava(trava, preco)
            trava.update(st)
            if st["status"] == "invalidada":
                reg.status = "invalidada"
                self.session.add(ElliottRevisao(contagem_id=reg.id, tipo_revisao="invalidacao", motivo=st["motivo"][:200],
                                                dados_anteriores=reg.ondas_detectadas))
                self.session.commit()
                _CACHE.pop(par, None)
        return trava
