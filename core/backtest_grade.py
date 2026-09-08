# core/backtest_grade.py
"""
Backtest da GRADE inversa (sem stop) em BTC, candles de 4h com leitura diária/semanal.

    - o range (grade) é montado quando a proposta é válida (no bot real: aprovado pelo usuário);
    - a grade fica viva até o preço FECHAR abaixo do fundo com todas as fatias recompradas (correção concluída);
      então uma nova grade pode ser proposta; se o preço rompe o topo, as fatias das extensões entram e o bot espera;
    - a grade também é renovada quando o preço cai mais de `renovar_pct` abaixo do fundo por muito tempo e
      não há fatia aberta (range antigo ficou longe demais), sem nunca recomprar com prejuízo.
KPIs: BTC realizado (só cresce), BTC marcado a mercado, fração média da carteira em dólar, ciclos por fatia.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import pandas as pd

from core.elliott_pro.mestre import analisar_grau, zigzag_pct
from core.inverse_grade import GradeInversa
from core.inverse_range import propor_range
from core.market_data import reamostrar
from core.regime import analisar_regime


class BacktestGrade:
    def __init__(self, ohlcv_4h: Sequence, banca_btc: float = 1.0, pct_primario: float = 0.22, recalculo_dias: int = 7,
                 desde_ms: Optional[int] = None, bloquear_ciclo_bull: bool = False, exigir_corretivo: bool = False,
                 subfatias: int = 3, pesos: Optional[Dict[float, float]] = None, verbose: bool = False,
                 saida_estrutural: bool = False, prob_impulso: float = 0.6):
        dados = [list(map(float, c[:6])) for c in ohlcv_4h]
        for c in dados:
            c[0] = int(c[0])
        self.h4 = dados
        self.d1 = reamostrar(dados, "4h", "1d")
        self.w1 = reamostrar(self.d1, "1d", "1w")
        self.banca0 = banca_btc
        self.pct = pct_primario
        self.recalculo = recalculo_dias
        self.desde = desde_ms or 0
        self.bloquear_ciclo_bull = bloquear_ciclo_bull
        self.exigir_corretivo = exigir_corretivo
        self.subfatias = subfatias
        self.pesos = pesos
        self.verbose = verbose
        self.saida_estrutural = saida_estrutural
        self.prob_impulso = prob_impulso
        self.eventos: List[Dict] = []
        self.curva: List[Dict] = []

    def _leitura(self, ts: int) -> Dict:
        d1 = [c for c in self.d1 if c[0] + 86_400_000 <= ts]
        if len(d1) < 60:
            return {}
        d1 = d1[-800:]
        res = analisar_grau(d1, self.pct, "primario")
        piv = [{"preco": p.preco, "tipo": p.tipo, "confirmado": p.confirmado,
                "data": datetime.fromtimestamp(p.ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")} for p in zigzag_pct(d1, self.pct)]
        ciclo = {}
        w1 = [c for c in self.w1 if c[0] + 7 * 86_400_000 <= ts]
        if len(w1) >= 40:
            rc = analisar_grau(w1, 0.40, "ciclo")
            ciclo = {"prob_bull": rc.get("prob_bull", 0), "prob_bear": rc.get("prob_bear", 0), "fase": rc.get("fase")}
        return {"pivots": piv, "regime": analisar_regime(d1), "primario": res.get("primario") or {}, "ciclo": ciclo}

    def executar(self) -> Dict:
        t0 = time.time()
        grade: Optional[GradeInversa] = None
        banca = self.banca0            # BTC realizado
        leitura: Dict = {}
        ultima = 0
        pico, dd_max = banca, 0.0
        fracao_acum, n_candles = 0.0, 0
        for c in self.h4:
            ts, o, h, l, close = c[0], c[1], c[2], c[3], c[4]
            if ts < self.desde:
                continue
            if ts - ultima >= self.recalculo * 86_400_000:
                leitura = self._leitura(ts) or leitura
                ultima = ts
                # saída de CENÁRIO (não de preço): a contagem virou impulso de alta -> fecha a grade e espera nova correção
                if grade is not None and self.saida_estrutural and leitura:
                    prim = leitura.get("primario") or {}
                    ciclo = leitura.get("ciclo") or {}
                    impulso_alta = (prim.get("vies") == "bull" and prim.get("fase") in ("inicio_onda_3", "meio_onda_3", "onda_5", "onda_1", "final_onda_3")
                                    and float(prim.get("probabilidade") or 0) >= 0.3) or ciclo.get("prob_bull", 0) >= self.prob_impulso
                    if impulso_alta and close > grade.high and grade.contratos_abertos() > 0:
                        pnl = grade.pnl_nao_realizado(close)
                        banca += pnl
                        self.eventos.append({"ts": ts, "evento": "saida_estrutural", "preco": close, "pnl_btc": round(pnl, 6),
                                             "motivo": f"Elliott virou impulso de alta ({prim.get('fase')}, ciclo bull {ciclo.get('prob_bull', 0):.0%}) acima do topo"})
                        grade = None
                if grade is None and leitura:
                    prop = propor_range(leitura["pivots"], close, leitura.get("regime"), leitura.get("primario"), exigir_corretivo=self.exigir_corretivo)
                    if prop and prop.get("valido") and self.bloquear_ciclo_bull and (leitura.get("ciclo") or {}).get("prob_bull", 0) >= 0.55:
                        prop = None
                    if prop and prop.get("valido"):
                        grade = GradeInversa(prop["low"], prop["high"], pesos=dict(self.pesos) if self.pesos else dict(GradeInversa.__dataclass_fields__["pesos"].default_factory()),
                                             subfatias=self.subfatias)
                        self.eventos.append({"ts": ts, "evento": "grade", "low": grade.low, "high": grade.high, "motivo": prop["motivo"]})
                        if self.verbose:
                            print(f"{datetime.fromtimestamp(ts / 1000, tz=timezone.utc):%Y-%m-%d} GRADE {grade.low:.0f}-{grade.high:.0f}")
            if grade is not None:
                equity = banca + grade.pnl_nao_realizado(close)
                execs = grade.processar_candle(ts, h, l, close, max(equity, 0.05), leitura.get("primario") if leitura else None)
                for e in execs:
                    if e["tipo"] == "recompra":
                        banca += e["pnl_btc"]
                self.eventos.extend(execs)
                # grade concluída: fechou abaixo do fundo sem nenhuma fatia aberta -> libera nova grade
                if close < grade.low and grade.contratos_abertos() <= 0:
                    self.eventos.append({"ts": ts, "evento": "grade_concluida", "preco": close, "btc_realizado": round(banca, 6)})
                    grade = None
            equity = banca + (grade.pnl_nao_realizado(close) if grade else 0.0) - (grade.taxas_btc if grade else 0.0)
            pico = max(pico, equity)
            dd_max = max(dd_max, (pico - equity) / pico if pico else 0.0)
            fr = grade.fracao_aberta() if grade else 0.0
            fracao_acum += fr
            n_candles += 1
            self.curva.append({"ts": ts, "btc_realizado": banca, "btc_mercado": equity, "preco": close, "fracao": fr})
        preco_fim = self.h4[-1][4]
        aberto = grade.pnl_nao_realizado(preco_fim) if grade else 0.0
        taxas = grade.taxas_btc if grade else 0.0
        return {
            "btc_inicial": self.banca0, "btc_realizado": round(banca - taxas, 6), "btc_marcado": round(banca + aberto - taxas, 6),
            "ganho_realizado_pct": round((banca - taxas) / self.banca0 * 100 - 100, 2),
            "ganho_marcado_pct": round((banca + aberto - taxas) / self.banca0 * 100 - 100, 2),
            "fracao_em_dolar_no_fim": round(grade.fracao_aberta(), 3) if grade else 0.0,
            "fracao_media_em_dolar": round(fracao_acum / max(n_candles, 1), 3),
            "drawdown_marcado_pct": round(dd_max * 100, 2), "grades": sum(1 for e in self.eventos if e.get("evento") == "grade"),
            "grades_concluidas": sum(1 for e in self.eventos if e.get("evento") == "grade_concluida"),
            "saidas_estruturais": sum(1 for e in self.eventos if e.get("evento") == "saida_estrutural"),
            "vendas": sum(1 for e in self.eventos if e.get("tipo") == "venda"), "recompras": sum(1 for e in self.eventos if e.get("tipo") == "recompra"),
            "hold_usd_final": round(self.banca0 * preco_fim, 2), "usd_marcado_final": round((banca + aberto - taxas) * preco_fim, 2),
            "tempo_s": round(time.time() - t0, 1), "eventos": self.eventos,
        }

    def por_ano(self) -> pd.DataFrame:
        df = pd.DataFrame(self.curva)
        if df.empty:
            return df
        df["ano"] = pd.to_datetime(df.ts, unit="ms").dt.year
        return df.groupby("ano").agg(realizado_fim=("btc_realizado", "last"), marcado_fim=("btc_mercado", "last"),
                                     em_dolar_medio=("fracao", "mean")).round(4)
