# core/backtest_grade.py
"""
Backtest da GRADE inversa em BTC, candles de 4h com leitura diária/semanal — com a MESMA lógica do robô ao vivo.

O passo de cada candle é `core.inverse_passo.passo_inverse`, o mesmo que o InverseRangeExecutor usa:
    - range proposto pela contagem do diário (`propor_range`, exigindo contagem corretiva como ao vivo) e dado por
      APROVADO na hora (no robô real quem aprova é o usuário, pelo botão);
    - grade com os pesos do inverse (nada acima do topo) e SÓ com os níveis acima do preço de aprovação ativos
      (`desativar_abaixo`) — sem vender tudo de uma vez no primeiro candle;
    - rompimento pela máquina (core/inverse_rompimento.py): topo rompido de verdade zera o short e encerra o
      range; topo falso mantém; fundo rompido de verdade espera o reteste e vende quase 100%; fundo falso não vende;
    - range encerrado ou concluído -> nova proposta.
KPIs: BTC realizado, BTC marcado a mercado, fração média da carteira em dólar, ranges, rompimentos.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import pandas as pd

from core.elliott_pro.mestre import analisar_grau, zigzag_pct
from core.inverse_grade import GradeInversa
from core.inverse_passo import passo_inverse
from core.inverse_range import propor_range
from core.inverse_rompimento import MaquinaRompimento, ParametrosRompimento, pesos_inverse
from core.market_data import reamostrar
from core.regime import analisar_regime


class BacktestGrade:
    def __init__(self, ohlcv_4h: Sequence, banca_btc: float = 1.0, pct_primario: float = 0.22, recalculo_dias: int = 7,
                 desde_ms: Optional[int] = None, bloquear_ciclo_bull: bool = False, exigir_corretivo: bool = True,
                 subfatias: int = 3, pesos: Optional[Dict[float, float]] = None, verbose: bool = False,
                 parametros: Optional[ParametrosRompimento] = None, funding: Optional[Dict[int, float]] = None):
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
        self.parametros = parametros or ParametrosRompimento()
        # funding do perpétuo inverse (timestamp ms -> taxa). Positivo: quem está VENDIDO recebe. Sem ele o
        # backtest ignorava a principal fonte de ganho de um short de BTC: em 2019-2025 o vendido recebeu em
        # 80-92% dos pagamentos na maioria dos anos (dados da Bybit)
        self.funding = funding or {}
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
        maquina = MaquinaRompimento(self.parametros)
        banca = self.banca0            # BTC realizado
        leitura: Dict = {}
        ultima = 0
        pico, dd_max = banca, 0.0
        fracao_acum, n_candles = 0.0, 0
        funding_btc = 0.0
        for c in self.h4:
            ts, h, l, close = c[0], c[2], c[3], c[4]
            if ts < self.desde:
                continue
            if ts - ultima >= self.recalculo * 86_400_000:
                leitura = self._leitura(ts) or leitura
                ultima = ts
            if grade is None and leitura:
                prop = propor_range(leitura["pivots"], close, leitura.get("regime"), leitura.get("primario"),
                                    exigir_corretivo=self.exigir_corretivo)
                if prop and prop.get("valido") and self.bloquear_ciclo_bull and (leitura.get("ciclo") or {}).get("prob_bull", 0) >= 0.55:
                    prop = None
                if prop and prop.get("valido") and prop["low"] < close < prop["high"]:
                    grade = GradeInversa(prop["low"], prop["high"], pesos=dict(self.pesos) if self.pesos else pesos_inverse(),
                                         subfatias=self.subfatias)
                    grade.desativar_abaixo(close)          # como o robô: só os níveis acima do preço de aprovação
                    maquina = MaquinaRompimento(self.parametros)
                    self.eventos.append({"ts": ts, "evento": "grade", "low": grade.low, "high": grade.high,
                                         "preco": close, "motivo": prop["motivo"]})
                    if self.verbose:
                        print(f"{datetime.fromtimestamp(ts / 1000, tz=timezone.utc):%Y-%m-%d} GRADE {grade.low:.0f}-{grade.high:.0f} @ {close:.0f}")
            if grade is not None:
                r = passo_inverse(grade, maquina, ts, h, l, close, max(banca, 0.05),
                                  (leitura.get("primario") or None) if leitura else None)
                banca += sum(e.get("pnl_btc", 0.0) for e in r["execs"] if e["tipo"] == "recompra")
                self.eventos.extend(r["execs"])
                # pagamentos de funding dentro deste candle, sobre o short que ficou aberto nele (contratos em USD)
                if self.funding:
                    # o funding é cobrado às 00h, 08h e 16h UTC: cai sempre no FIM de um candle de 4h
                    taxa = self.funding.get(ts + 4 * 3_600_000)
                    vendido = grade.contratos_abertos() + ((maquina.reteste or {}).get("contratos") or 0.0)
                    if taxa and vendido > 0:
                        f_btc = vendido * taxa / close
                        banca += f_btc
                        funding_btc += f_btc
                if r["fechar_grade"] or r["concluido"]:
                    self.eventos.append({"ts": ts, "evento": "range_encerrado" if r["fechar_grade"] else "range_concluido",
                                         "preco": close, "motivo": r["motivo"], "btc_realizado": round(banca, 6)})
                    if self.verbose:
                        print(f"{datetime.fromtimestamp(ts / 1000, tz=timezone.utc):%Y-%m-%d} FIM {r['motivo'][:90]}")
                    banca -= grade.taxas_btc
                    grade = None
                    maquina = MaquinaRompimento(self.parametros)
            aberto = (grade.pnl_nao_realizado(close) - grade.taxas_btc if grade else 0.0) + maquina.pnl_nao_realizado(close)
            equity = banca + aberto
            pico = max(pico, equity)
            dd_max = max(dd_max, (pico - equity) / pico if pico else 0.0)
            fr = grade.fracao_aberta() if grade else 0.0
            fracao_acum += fr
            n_candles += 1
            self.curva.append({"ts": ts, "btc_realizado": banca, "btc_mercado": equity, "preco": close, "fracao": fr})
        preco_fim = self.h4[-1][4]
        aberto = (grade.pnl_nao_realizado(preco_fim) if grade else 0.0) + maquina.pnl_nao_realizado(preco_fim)
        taxas = grade.taxas_btc if grade else 0.0
        conta = lambda nome: sum(1 for e in self.eventos if e.get("evento") == nome)
        return {
            "btc_inicial": self.banca0, "btc_realizado": round(banca - taxas, 6), "btc_marcado": round(banca + aberto - taxas, 6),
            "ganho_realizado_pct": round((banca - taxas) / self.banca0 * 100 - 100, 2),
            "ganho_marcado_pct": round((banca + aberto - taxas) / self.banca0 * 100 - 100, 2),
            "fracao_em_dolar_no_fim": round(grade.fracao_aberta(), 3) if grade else 0.0,
            "fracao_media_em_dolar": round(fracao_acum / max(n_candles, 1), 3),
            "drawdown_marcado_pct": round(dd_max * 100, 2), "grades": conta("grade"),
            "ranges_encerrados_topo": conta("range_encerrado"), "ranges_concluidos": conta("range_concluido"),
            "vendas": sum(1 for e in self.eventos if e.get("tipo") == "venda"),
            "recompras": sum(1 for e in self.eventos if e.get("tipo") == "recompra"),
            "hold_usd_final": round(self.banca0 * preco_fim, 2), "usd_marcado_final": round((banca + aberto - taxas) * preco_fim, 2),
            "funding_btc": round(funding_btc, 6),
            "tempo_s": round(time.time() - t0, 1), "eventos": self.eventos,
        }

    def por_ano(self) -> pd.DataFrame:
        df = pd.DataFrame(self.curva)
        if df.empty:
            return df
        df["ano"] = pd.to_datetime(df.ts, unit="ms").dt.year
        return df.groupby("ano").agg(realizado_fim=("btc_realizado", "last"), marcado_fim=("btc_mercado", "last"),
                                     em_dolar_medio=("fracao", "mean")).round(4)
