# core/backtest_inverse.py
"""
Backtest do modo inverse (short-only em range, P&L em BTC).

Simulação em candles de 4h com leitura diária:
    - a cada semana recalcula a contagem mestre no diário (grau primário) e o regime; se não há range ativo
      e a proposta é válida, aprova automaticamente (no bot real o usuário aprova)
    - a cada fechamento de 4h aplica a escada (vende/recompra pela diferença entre alocação atual e alvo)
    - stop no rompimento do topo; depois espera nova proposta
    - short de base pelo cenário primário (calculado; no bot real pode ser a trava)
KPI: BTC final / BTC inicial (a carteira parte de 1 BTC), valor em USD, drawdown em BTC, comparado a segurar 1 BTC.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import pandas as pd

from core.elliott_pro.mestre import analisar_grau, zigzag_pct
from core.inverse_range import PosicaoInversa, RangeConfig, decidir_alocacao, propor_range
from core.market_data import reamostrar
from core.regime import analisar_regime

TAXA_MAKER = 0.0002


class BacktestInverse:
    def __init__(self, ohlcv_4h: Sequence, banca_btc: float = 1.0, short_base_max: float = 0.5, folga_stop: float = 0.01,
                 pct_primario: float = 0.22, recalculo_dias: int = 7, verbose: bool = False, desde_ms: Optional[int] = None,
                 bloquear_ciclo_bull: bool = True, pct_ciclo: float = 0.40):
        dados = [list(map(float, c[:6])) for c in ohlcv_4h]
        for c in dados:
            c[0] = int(c[0])
        self.h4 = dados
        self.d1 = reamostrar(dados, "4h", "1d")
        self.banca0 = banca_btc
        self.short_base_max = short_base_max
        self.folga = folga_stop
        self.pct = pct_primario
        self.recalculo = recalculo_dias
        self.verbose = verbose
        self.desde = desde_ms or 0
        self.bloquear_ciclo_bull = bloquear_ciclo_bull
        self.pct_ciclo = pct_ciclo
        self.w1 = reamostrar(self.d1, "1d", "1w")
        self.eventos: List[Dict] = []
        self.curva: List[Dict] = []

    def _leitura_diaria(self, ts: int) -> Dict:
        d1 = [c for c in self.d1 if c[0] + 86_400_000 <= ts]
        if len(d1) < 60:
            return {}
        d1 = d1[-800:]
        res = analisar_grau(d1, self.pct, "primario")
        piv = [{"preco": p.preco, "tipo": p.tipo, "confirmado": p.confirmado,
                "data": datetime.fromtimestamp(p.ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")} for p in zigzag_pct(d1, self.pct)]
        prim = res.get("primario") or {}
        ciclo = {}
        w1 = [c for c in self.w1 if c[0] + 7 * 86_400_000 <= ts]
        if len(w1) >= 40:
            rc = analisar_grau(w1, self.pct_ciclo, "ciclo")
            ciclo = {"prob_bull": rc.get("prob_bull", 0), "prob_bear": rc.get("prob_bear", 0), "fase": rc.get("fase")}
        return {"pivots": piv, "regime": analisar_regime(d1), "primario": prim, "preco": d1[-1][4], "ciclo": ciclo}

    def executar(self) -> Dict:
        t0 = time.time()
        pos = PosicaoInversa()
        banca = self.banca0
        cfg: Optional[RangeConfig] = None
        estado = "sem_range"
        aloc = 0.0
        ultima_leitura_ts = 0
        leitura: Dict = {}
        pico_btc, dd_max = banca, 0.0
        for c in self.h4:
            ts, preco = c[0], c[4]
            if ts < self.desde:
                continue
            equity = banca + pos.pnl_nao_realizado(preco)
            if ts - ultima_leitura_ts >= self.recalculo * 86_400_000:
                leitura = self._leitura_diaria(ts) or leitura
                ultima_leitura_ts = ts
                if cfg is None and leitura:
                    prop = propor_range(leitura["pivots"], preco, leitura.get("regime"), leitura.get("primario"))
                    ciclo = leitura.get("ciclo") or {}
                    if prop and prop.get("valido") and self.bloquear_ciclo_bull and ciclo.get("prob_bull", 0) >= 0.55:
                        prop = {"valido": False, "motivo": f"ciclo semanal com viés de alta ({ciclo.get('prob_bull'):.0%}): sem range"}
                    if prop and prop.get("valido"):
                        cfg = RangeConfig(prop["low"], prop["high"], "pivots", self.folga, short_base_max=self.short_base_max)
                        estado = "ativo"
                        self.eventos.append({"ts": ts, "evento": "range", "low": cfg.low, "high": cfg.high, "motivo": prop["motivo"]})
                        if self.verbose:
                            print(f"{datetime.fromtimestamp(ts / 1000, tz=timezone.utc):%Y-%m-%d} RANGE {cfg.low:.0f}-{cfg.high:.0f} | {prop['motivo']}")
            if cfg is not None:
                mestre = leitura.get("primario") if leitura else None
                dec = decidir_alocacao(cfg, preco, aloc, mestre, estado)
                if dec["estado"] == "stopado" and estado != "stopado":
                    estado = "stopado"
                    self.eventos.append({"ts": ts, "evento": "stop", "preco": preco, "motivo": dec["motivo"]})
                alvo = dec["alvo"]
                if abs(alvo - aloc) >= 0.02:
                    valor_usd = equity * preco
                    contratos_alvo = alvo * valor_usd
                    delta = contratos_alvo - pos.contratos
                    if delta > 0:
                        pos.vender(delta, preco, TAXA_MAKER)
                    else:
                        pnl = pos.recomprar(-delta, preco, TAXA_MAKER)
                        banca += pnl
                    aloc = alvo
                    self.eventos.append({"ts": ts, "evento": "ajuste", "preco": preco, "alocacao": alvo, "contratos": round(pos.contratos),
                                         "banca_btc": round(banca, 6), "motivo": dec["motivo"][:120]})
                if estado == "stopado":
                    # fecha o que sobrou e libera para novo range
                    if pos.contratos > 0:
                        banca += pos.recomprar(pos.contratos, preco, TAXA_MAKER)
                    aloc, cfg, estado = 0.0, None, "sem_range"
                elif dec["estado"] == "carregando" and preco < cfg.low * 0.97:
                    # fundo rompido com short de base: o range acabou; mantém a base como posição livre até o alvo/invalidação
                    if mestre and mestre.get("invalidacao") and preco > mestre["invalidacao"]:
                        banca += pos.recomprar(pos.contratos, preco, TAXA_MAKER); aloc = 0.0; cfg = None; estado = "sem_range"
            equity = banca + pos.pnl_nao_realizado(preco) - pos.taxas_btc
            pico_btc = max(pico_btc, equity)
            dd_max = max(dd_max, (pico_btc - equity) / pico_btc if pico_btc else 0)
            self.curva.append({"ts": ts, "btc": equity, "preco": preco, "alocacao": aloc})
        if pos.contratos > 0:
            banca += pos.recomprar(pos.contratos, self.h4[-1][4], TAXA_MAKER)
        banca -= pos.taxas_btc
        preco_ini = next(c[4] for c in self.h4 if c[0] >= self.desde)
        preco_fim = self.h4[-1][4]
        return {
            "btc_inicial": self.banca0, "btc_final": round(banca, 6), "ganho_btc_pct": round((banca / self.banca0 - 1) * 100, 2),
            "usd_inicial": round(self.banca0 * preco_ini, 2), "usd_final": round(banca * preco_fim, 2),
            "hold_usd_final": round(self.banca0 * preco_fim, 2), "drawdown_btc_pct": round(dd_max * 100, 2),
            "ranges": sum(1 for e in self.eventos if e["evento"] == "range"), "stops": sum(1 for e in self.eventos if e["evento"] == "stop"),
            "ajustes": sum(1 for e in self.eventos if e["evento"] == "ajuste"), "taxas_btc": round(pos.taxas_btc, 6),
            "pnl_realizado_btc": round(pos.pnl_btc_realizado, 6), "tempo_s": round(time.time() - t0, 1), "eventos": self.eventos,
        }

    def por_ano(self) -> pd.DataFrame:
        df = pd.DataFrame(self.curva)
        if df.empty:
            return df
        df["ano"] = pd.to_datetime(df.ts, unit="ms").dt.year
        return df.groupby("ano").agg(btc_inicio=("btc", "first"), btc_fim=("btc", "last"), aloc_media=("alocacao", "mean")).round(4)
