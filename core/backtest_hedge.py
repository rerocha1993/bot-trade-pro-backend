# core/backtest_hedge.py
"""
Backtest do DIAL DE HEDGE (carteira 100% em BTC; short inverso só como proteção) em candles de 4h.

Leituras (recalculadas a cada `recalculo_dias`):
    - Elliott primário no diário e ciclo no semanal (fase, viés, probabilidades, alvos, invalidação)
    - níveis para barreira/suporte: alvos e invalidação de Elliott, VAH/VAL/POC do TPO diário (120 dias),
      pivôs primários, extensões de Fibonacci da onda em curso, order blocks do diário
    - exaustão: Fear & Greed histórico (2018+), VWAP z-score (20 dias), RSI 14 diário, preço acima da VAH, prob. bear
KPIs: BTC final (realizado + marcado), comparação com segurar 1 BTC, tempo em dólar, custo dos rompimentos.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from core.elliott_pro.mestre import analisar_grau, zigzag_pct
from core.elliott_pro.superciclo import ContextoSuperciclo
from core.hedge_dial import HedgeDial
from core.market_data import reamostrar
from core.order_block import OrderBlockDetector
from core.tpo import TPOProfile
from core.vwap import VWAPCalculator


def _rsi(closes: Sequence[float], n: int = 14) -> Optional[float]:
    c = np.array(closes[-(n * 5):], dtype=float)
    if len(c) < n + 1:
        return None
    d = np.diff(c)
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    au, ad = up[:n].mean(), dn[:n].mean()
    for i in range(n, len(d)):
        au = (au * (n - 1) + up[i]) / n
        ad = (ad * (n - 1) + dn[i]) / n
    if ad == 0:
        return 100.0
    return 100 - 100 / (1 + au / ad)


def leitura_dial_ao_vivo(d1: Sequence, fear_greed: Optional[int] = None) -> Dict:
    """Mesma leitura do backtest (níveis, exaustão, Elliott) sobre candles diários ao vivo; devolve barreira/suporte/exaustão."""
    from core.hedge_dial import barreiras, exaustao
    dados = [list(map(float, c[:6])) for c in d1]
    for c in dados:
        c[0] = int(c[0])
    bt = BacktestHedge.__new__(BacktestHedge)
    bt.d1 = dados
    bt.w1 = reamostrar(dados, "1d", "1w")
    bt.fg = {dados[-1][0] // 86_400_000: fear_greed} if fear_greed is not None else {}
    bt.ctx, bt._ctx_i = ContextoSuperciclo(), 0
    lei = bt._leitura(dados[-1][0] + 86_400_000)
    if not lei:
        return {"erro": "candles insuficientes"}
    preco = dados[-1][4]
    b = barreiras(preco, lei["niveis"])
    ex = exaustao(lei["sinais"])
    fase = lei["elliott"].get("fase")
    sc = lei["elliott"].get("superciclo")
    impulso = ((fase in ("inicio_onda_3", "meio_onda_3", "onda_1", "onda_5") and lei["elliott"].get("prob_bull", 0) >= 0.55)
               or lei["elliott"].get("ciclo_prob_bull", 0) >= 0.7 or sc in ("fundo_terminal", "novo_impulso", "impulso_alta", "zona_onda_2"))
    if sc in ("impulso_maduro", "correcao_inicial", "correcao_em_curso"):
        impulso = False
    return {"preco": preco, "barreira": b["resistencia"], "suporte": b["suporte"], "exaustao": ex, "elliott": lei["elliott"],
            "superciclo": bt.ctx.estado(),
            "impulso_de_alta": impulso, "recomendacao": ("deixar andar (impulso de alta sem exaustão)" if impulso and ex["score"] < 0.6 else
                                                          "montar hedge escalonado até a barreira" if ex["confluencias"] >= 2 else "aguardar exaustão na barreira"),
            "niveis": sorted(lei["niveis"], key=lambda n: n["preco"])}


class BacktestHedge:
    def __init__(self, ohlcv_4h: Sequence, banca_btc: float = 1.0, desde_ms: Optional[int] = None, recalculo_dias: int = 3,
                 exaustao_minima: float = 0.35, prob_impulso: float = 0.55, folga_rompimento: float = 0.02, verbose: bool = False):
        dados = [list(map(float, c[:6])) for c in ohlcv_4h]
        for c in dados:
            c[0] = int(c[0])
        self.h4 = dados
        self.d1 = reamostrar(dados, "4h", "1d")
        self.w1 = reamostrar(self.d1, "1d", "1w")
        self.banca0 = banca_btc
        self.desde = desde_ms or 0
        self.recalculo = recalculo_dias
        self.dial = HedgeDial(exaustao_minima=exaustao_minima, prob_impulso=prob_impulso, folga_rompimento=folga_rompimento)
        self.verbose = verbose
        self.fg = self._carregar_fg()
        self.ctx, self._ctx_i = ContextoSuperciclo(), 0
        self.eventos: List[Dict] = []
        self.curva: List[Dict] = []

    @staticmethod
    def _carregar_fg() -> Dict[int, int]:
        caminho = os.path.join("data", "historico", "fear_greed.csv")
        if not os.path.exists(caminho):
            return {}
        df = pd.read_csv(caminho)
        return {int(t) // 86_400_000: int(v) for t, v in zip(df.timestamp, df.valor)}

    def _leitura(self, ts: int) -> Dict:
        d1 = [c for c in self.d1 if c[0] + 86_400_000 <= ts]
        if len(d1) < 120:
            return {}
        while self._ctx_i < len(d1):
            c = d1[self._ctx_i]
            self.ctx.passo(c[0], c[2], c[3], c[4])
            self._ctx_i += 1
        d1 = d1[-800:]
        prim = analisar_grau(d1, 0.22, "primario")
        w1 = [c for c in self.w1 if c[0] + 7 * 86_400_000 <= ts]
        ciclo = analisar_grau(w1, 0.40, "ciclo") if len(w1) >= 40 else {}
        p = prim.get("primario") or {}
        preco = d1[-1][4]
        niveis: List[Dict] = []
        for a in (p.get("alvos") or []):
            niveis.append({"preco": a, "fonte": "elliott_alvo", "peso": 2.0})
        if p.get("invalidacao"):
            niveis.append({"preco": p["invalidacao"], "fonte": "elliott_invalidacao", "peso": 2.0})
        for c in (prim.get("cenarios") or [])[1:3]:
            for a in (c.get("alvos") or [])[:1]:
                niveis.append({"preco": a, "fonte": "elliott_alt", "peso": 1.0})
        for pv in zigzag_pct(d1, 0.22)[-6:]:
            niveis.append({"preco": pv.preco, "fonte": "pivo", "peso": 1.5 if pv.confirmado else 0.5})
        try:
            tpo = TPOProfile(d1[-120:], bins=30).analisar()
            niveis += [{"preco": tpo["VAH"], "fonte": "tpo_vah", "peso": 1.5}, {"preco": tpo["VAL"], "fonte": "tpo_val", "peso": 1.5},
                       {"preco": tpo["POC"], "fonte": "tpo_poc", "peso": 1.0}]
            acima_vah = preco > tpo["VAH"]
        except Exception:
            acima_vah = None
        try:
            obd = OrderBlockDetector(d1[-200:])
            for b in obd.identificar_blocks("bearish")[-3:]:
                niveis.append({"preco": b["preco"], "fonte": "ob_bearish", "peso": 1.5})
            for b in obd.identificar_blocks("bullish")[-3:]:
                niveis.append({"preco": b["preco"], "fonte": "ob_bullish", "peso": 1.5})
        except Exception:
            pass
        # extensões de Fibonacci da última perna de alta (pivô L -> H)
        piv = zigzag_pct(d1, 0.22)
        conf = [x for x in piv if x.confirmado]
        if len(conf) >= 2:
            a, b = conf[-2], conf[-1]
            lo, hi = min(a.preco, b.preco), max(a.preco, b.preco)
            for ext in (1.272, 1.618, 2.0):
                niveis.append({"preco": lo + (hi - lo) * ext, "fonte": f"fib_{ext}", "peso": 1.0})
        try:
            vz = VWAPCalculator(d1[-20:]).sinal(preco)["z"]
        except Exception:
            vz = None
        sinais = {"fear_greed": self.fg.get(ts // 86_400_000), "vwap_z": vz, "acima_vah": acima_vah,
                  "prob_bear": prim.get("prob_bear", 0), "rsi": _rsi([c[4] for c in d1])}
        elliott = {"fase": prim.get("fase"), "vies": p.get("vies"), "prob_bull": prim.get("prob_bull", 0), "prob_bear": prim.get("prob_bear", 0),
                   "alvos": p.get("alvos"), "invalidacao": p.get("invalidacao"), "ciclo_prob_bull": ciclo.get("prob_bull", 0) if ciclo else 0,
                   "superciclo": self.ctx.estado().get("estado")}
        return {"niveis": niveis, "sinais": sinais, "elliott": elliott}

    def executar(self) -> Dict:
        t0 = time.time()
        banca = self.banca0
        leitura: Dict = {}
        ultima = 0
        pico, dd = banca, 0.0
        hedge_acum, n = 0.0, 0
        custo_romp = 0.0
        for c in self.h4:
            ts, h, l, close = c[0], c[2], c[3], c[4]
            if ts < self.desde:
                continue
            if ts - ultima >= self.recalculo * 86_400_000:
                leitura = self._leitura(ts) or leitura
                ultima = ts
            if not leitura:
                continue
            r = self.dial.passo(ts, h, l, close, max(banca, 1e-6), leitura["niveis"], leitura["elliott"], leitura["sinais"])
            for e in r["execs"]:
                if e["tipo"] == "recompra":
                    banca += e["pnl_btc"]
                    if e.get("motivo") == "rompimento com onda 3":
                        custo_romp += e["pnl_btc"]
            if r["execs"] or (self.curva and self.curva[-1]["modo"] != r["modo"]):
                self.eventos.append({"ts": ts, "modo": r["modo"], "hedge": r["hedge"], "preco": close, "barreira": r["barreira"], "suporte": r["suporte"],
                                     "exaustao": r["exaustao"], "n_execs": len(r["execs"]), "motivo": r["motivo"]})
            grade = self.dial.estado.grade
            equity = banca + (grade.pnl_nao_realizado(close) if grade else 0.0)
            pico = max(pico, equity)
            dd = max(dd, (pico - equity) / pico if pico else 0.0)
            hedge_acum += r["hedge"]
            n += 1
            self.curva.append({"ts": ts, "btc": equity, "realizado": banca, "preco": close, "hedge": r["hedge"], "modo": r["modo"]})
        preco_fim = self.h4[-1][4]
        grade = self.dial.estado.grade
        aberto = grade.pnl_nao_realizado(preco_fim) if grade else 0.0
        taxas = grade.taxas_btc if grade else 0.0
        preco_ini = next(c[4] for c in self.h4 if c[0] >= self.desde)
        return {"btc_inicial": self.banca0, "btc_realizado": round(banca - taxas, 6), "btc_marcado": round(banca + aberto - taxas, 6),
                "ganho_btc_pct": round((banca + aberto - taxas) / self.banca0 * 100 - 100, 2), "hedge_medio": round(hedge_acum / max(n, 1), 3),
                "drawdown_btc_pct": round(dd * 100, 2), "custo_rompimentos_btc": round(custo_romp, 6),
                "usd_final": round((banca + aberto - taxas) * preco_fim, 2), "hold_usd_final": round(self.banca0 * preco_fim, 2),
                "preco_inicial": preco_ini, "preco_final": preco_fim, "eventos": len(self.eventos), "tempo_s": round(time.time() - t0, 1)}

    def por_ano(self) -> pd.DataFrame:
        df = pd.DataFrame(self.curva)
        if df.empty:
            return df
        df["ano"] = pd.to_datetime(df.ts, unit="ms").dt.year
        return df.groupby("ano").agg(btc_fim=("btc", "last"), realizado_fim=("realizado", "last"), hedge_medio=("hedge", "mean"),
                                     preco_fim=("preco", "last")).round(4)
