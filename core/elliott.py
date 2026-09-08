# core/elliott.py
"""
Fachada de compatibilidade do motor de Elliott.

A implementação real está em core/elliott_pro (pivôs, padrões, cenários, multi-grau).
Aqui ficam:
    ElliottAnalyzer  -> análise de uma série (fase, direção, cenários) via elliott_pro
    ElliottDetector  -> API antiga (validar_estrutura_basica) usada por código legado
    ElliottEngine    -> varredura histórica que persiste contagens candidatas no banco (O(N))
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import numpy as np

from core.elliott_pro.pivots import Pivot, zigzag_atr
from core.elliott_pro.patterns import legs_de_pivots, ajustar_todos
from core.elliott_pro.scenarios import ScenarioEngine
from core.elliott_pro.multidegree import analisar_serie
from core.utils_indicadores import atr


class ElliottAnalyzer:
    def __init__(self, ohlcv: Sequence, fator_atr: float = 2.0, periodo_atr: int = 14, max_pivots: int = 40, **_):
        if not ohlcv or len(ohlcv) < 20:
            raise ValueError("Elliott precisa de pelo menos 20 candles")
        self.ohlcv = [list(map(float, c[:6])) for c in ohlcv]
        self.preco_atual = self.ohlcv[-1][4]
        self.atr = atr(self.ohlcv, periodo_atr) or 0.0
        self.fator_atr = fator_atr
        pivots, self.limiar = zigzag_atr(self.ohlcv, fator_atr, periodo_atr)
        self.pivots = pivots[-max_pivots:]
        self.confirmados = [p for p in self.pivots if p.confirmado]
        self.provisorio = self.pivots[-1] if self.pivots and not self.pivots[-1].confirmado else None

    def analisar(self) -> Dict:
        res = analisar_serie(self.ohlcv, self.fator_atr)
        prim = res.get("primario") or {}
        res.update({
            "ondas": prim.get("ondas", []),
            "score": prim.get("score", 0.0),
            "padrao": prim.get("padrao"),
            "niveis": {"invalidacao": prim.get("invalidacao"), **{f"alvo_{i + 1}": a for i, a in enumerate(prim.get("alvos", []))}},
            "motivo": prim.get("motivo", res.get("erro", "")),
            "atr": self.atr,
        })
        return res

    def estrutura_onda_simples(self) -> Dict:
        return {"impulsivas": [p.idx for p in self.pivots if p.tipo == "H"],
                "corretivas": [p.idx for p in self.pivots if p.tipo == "L"]}

    def hash_contagem(self, ondas: List[Dict]) -> str:
        chave = json.dumps([(o.get("ts_inicio"), o.get("ts_fim"), o.get("inicio"), o.get("fim")) for o in ondas])
        return hashlib.sha1(chave.encode()).hexdigest()[:20]


class ElliottDetector:
    """Wrapper de compatibilidade: aceita lista de preços OU candles."""

    def __init__(self, prices):
        if prices and isinstance(prices[0], (list, tuple)):
            self.ohlcv = list(prices)
        else:
            self.ohlcv = [[i, float(p), float(p), float(p), float(p), 0.0] for i, p in enumerate(prices or [])]
        self.analyzer = ElliottAnalyzer(self.ohlcv) if len(self.ohlcv) >= 20 else None

    def detectar_picos_vales(self, distance: int = 5):
        if not self.analyzer:
            return [], []
        e = self.analyzer.estrutura_onda_simples()
        return e["impulsivas"], e["corretivas"]

    def estrutura_onda_simples(self):
        peaks, troughs = self.detectar_picos_vales()
        return {"impulsivas": peaks, "corretivas": troughs}

    def validar_estrutura_basica(self):
        if not self.analyzer:
            return False, {"impulsivas": [], "corretivas": []}
        res = self.analyzer.analisar()
        estrutura = self.estrutura_onda_simples()
        estrutura["analise"] = res
        return res.get("direcao") in ("buy", "sell"), estrutura


class ElliottEngine:
    """
    Varredura histórica: percorre os pivôs em janelas deslizantes, guarda os padrões válidos
    (impulsos, diagonais, zigzags, flats, triângulos, combinações) como contagens candidatas.
    """

    def __init__(self, session, par, timeframe, candles, nivel_ciclo="macro", fator_atr: float = 2.0):
        self.session = session
        self.par = par
        self.timeframe = timeframe
        self.candles = candles
        self.nivel_ciclo = str(nivel_ciclo)
        self.fator_atr = fator_atr
        self.contagens_candidatas: List[Dict] = []
        self.analyzer = ElliottAnalyzer(candles, fator_atr=fator_atr, max_pivots=100_000) if candles and len(candles) >= 20 else None

    def detectar_todas_contagens(self, score_minimo: float = 0.6) -> List[Dict]:
        self.contagens_candidatas = []
        if not self.analyzer:
            return []
        conf = self.analyzer.confirmados
        vistos = set()
        for n_legs in (5, 3):
            for i in range(0, len(conf) - n_legs):
                legs = legs_de_pivots(conf[i:i + n_legs + 1])
                for fit in ajustar_todos(legs):
                    if fit.score < score_minimo:
                        continue
                    ondas = [{"rotulo": r, **l.dict()} for r, l in zip(fit.rotulos, fit.legs)]
                    h = self.analyzer.hash_contagem(ondas)
                    if h in vistos:
                        continue
                    vistos.add(h)
                    self.contagens_candidatas.append({
                        "padrao": fit.padrao, "classe": fit.classe, "direcao": "alta" if fit.direcao == "up" else "baixa",
                        "ondas": ondas, "score": fit.score, "hash": h, "regras": fit.regras, "extras": fit.extras,
                    })
        self.contagens_candidatas.sort(key=lambda c: c["ondas"][0]["ts_inicio"])
        return self.contagens_candidatas

    @staticmethod
    def _dt(ts_ms: int) -> datetime:
        return datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)

    def persistir_candidatas(self) -> int:
        from models.elliott_contagem_candidata import ElliottContagemCandidata
        from models.elliott_onda import ElliottOnda

        salvos = 0
        for c in self.contagens_candidatas:
            d0, d1 = self._dt(c["ondas"][0]["ts_inicio"]), self._dt(c["ondas"][-1]["ts_fim"])
            existe = self.session.query(ElliottContagemCandidata).filter_by(
                par=self.par, timeframe=self.timeframe, data_inicio=d0, data_fim=d1).first()
            if existe:
                continue
            ondas_json = []
            for k, o in enumerate(c["ondas"]):
                ondas_json.append({
                    "numero_onda": k + 1, "rotulo": o["rotulo"],
                    "tipo_onda": "impulsiva" if (c["classe"] == "motriz" and k % 2 == 0) else "corretiva",
                    "preco_inicio": o["inicio"], "preco_fim": o["fim"],
                    "data_inicio": self._dt(o["ts_inicio"]).isoformat(), "data_fim": self._dt(o["ts_fim"]).isoformat(),
                    "validada": True, "score_confianca": c["score"], "padrao": c["padrao"],
                })
            contagem = ElliottContagemCandidata(
                par=self.par, timeframe=self.timeframe, ondas_detectadas=ondas_json, score_confianca=c["score"],
                data_inicio=d0, data_fim=d1, nivel_ciclo=self.nivel_ciclo, status="candidata")
            self.session.add(contagem)
            self.session.flush()
            for o in ondas_json:
                self.session.add(ElliottOnda(
                    contagem_id=contagem.id, numero_onda=o["numero_onda"], tipo_onda=o["tipo_onda"],
                    data_inicio=datetime.fromisoformat(o["data_inicio"]), data_fim=datetime.fromisoformat(o["data_fim"]),
                    preco_inicio=o["preco_inicio"], preco_fim=o["preco_fim"], validada=True, score_confianca=c["score"]))
            salvos += 1
        self.session.commit()
        return salvos


if __name__ == "__main__":
    from core.conexoes.conexao_bybit import BybitConnector

    con = BybitConnector("simulador")
    ohlcv = con.obter_ohlcv("BTCUSDT", timeframe="15m", limite=300)
    res = ElliottAnalyzer(ohlcv).analisar()
    print({k: v for k, v in res.items() if k not in ("pivots", "ondas", "cenarios", "alternativos")})
