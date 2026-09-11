# core/backtest_scalp.py
"""
Backtest do SCALP POR INDICADORES em 5m (core/scalp_indicadores.py).

Execução, do jeito que o robô ao vivo faria:
    - o sinal sai no FECHAMENTO do candle; vira ordem limitada no preço de fechamento, válida por 3 candles
    - a ordem executa quando um candle seguinte encosta no preço (taxa maker)
    - no candle da execução só o stop vale; alvo, só a partir do candle seguinte (pior caso)
    - stop e alvo no mesmo candle: conta o stop (pior caso)
    - alvo sai por ordem limitada (maker); stop sai a mercado (taker) com slippage
    - limite de trades e de perda no dia, como no robô

O que decide se um setup vai para o robô é o CRITÉRIO, fixado antes de rodar (`avaliar_criterio`). E ele é
conferido em dois períodos: o de treino, onde o setup é escolhido, e o de validação, que a escolha não viu —
com seis candidatos, o melhor num período só pode ser apenas o mais sortudo.

O que fica de fora, e é dito: os vetos de ciclo do plano (não há histórico do plano) e a saída escalonada.
"""
from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone
from statistics import mean
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.scalp_indicadores import Ctx

# critério fixado ANTES de ver qualquer resultado
CRITERIO = {"trades_min_treino": 100, "trades_min_validacao": 30, "bruto_sobre_custo": 2.0}


class BacktestScalp:
    def __init__(self, ctxs: Sequence[Ctx], setups: Dict[str, Callable], banca: float = 10000.0,
                 risco_pct: float = 0.01, max_alocacao: float = 0.5, alavancagem: int = 1,
                 max_trades_dia: int = 10, max_perda_dia_pct: float = 0.03, espera_limite: int = 3,
                 slippage: float = 0.0002):
        self.ctxs = ctxs
        self.setups = setups
        self.banca0 = float(banca)
        self.risco_pct = risco_pct
        self.max_alocacao = max_alocacao
        self.alavancagem = max(int(alavancagem or 1), 1)
        self.max_trades_dia = max_trades_dia
        self.max_perda_dia = max_perda_dia_pct * self.banca0
        self.espera = espera_limite
        self.slip = slippage

    def _tamanho(self, banca: float, entrada: float, sl: float) -> float:
        risco = abs(entrada - sl)
        if risco <= 0 or entrada <= 0:
            return 0.0
        return min(banca * self.risco_pct / risco, banca * self.max_alocacao * self.alavancagem / entrada)

    def _fechar(self, pos: Dict, preco: float, motivo: str, ts: int, taxa_saida: float, trades: List[Dict]) -> float:
        s, q, e = pos["s"], pos["qty"], pos["entrada"]
        bruto = (preco - e) * q * s
        taxas = pos["taxa_entrada"] + preco * q * taxa_saida
        risco = abs(e - pos["sl"])
        notional = e * q
        trades.append({
            "setup": pos["setup"], "lado": "buy" if s == 1 else "sell", "entrada": e, "saida": preco,
            "sl": pos["sl"], "tp": pos["tp"], "ts_entrada": pos["ts_entrada"], "ts_saida": ts,
            "motivo_saida": motivo, "qty": q, "bruto": bruto, "taxas": taxas, "pnl": bruto - taxas,
            "bruto_pct": (preco - e) / e * s, "custo_pct": taxas / notional if notional else 0.0,
            "r": (preco - e) * s / risco if risco else 0.0, "motivo": pos["motivo"]})
        return bruto - taxas

    def executar(self, inicio_ms: int = 0, fim_ms: Optional[int] = None) -> Dict:
        """Roda entre `inicio_ms` e `fim_ms`. Os contextos já vêm aquecidos pelo histórico anterior ao início."""
        t0 = time.time()
        banca = self.banca0
        pos: Optional[Dict] = None
        pend: Optional[Dict] = None
        est: Dict = {}
        trades: List[Dict] = []
        curva: List[float] = []
        dia, n_dia, pnl_dia, sinais = None, 0, 0.0, 0
        for i, x in enumerate(self.ctxs):
            if x.ts < inicio_ms:
                continue
            if fim_ms is not None and x.ts >= fim_ms:
                break
            if x.dia != dia:
                dia, n_dia, pnl_dia = x.dia, 0, 0.0
            recem = False
            # 1) ordem limitada esperando
            if pend is not None and pos is None:
                s = pend["s"]
                if (s == 1 and x.l <= pend["entrada"]) or (s == -1 and x.h >= pend["entrada"]):
                    qty = self._tamanho(banca, pend["entrada"], pend["sl"])
                    if qty > 0:
                        pos = {**pend, "qty": qty, "ts_entrada": x.ts, "taxa_entrada": pend["entrada"] * qty * TAXA_MAKER}
                        n_dia += 1
                        recem = True
                    pend = None
                else:
                    pend["candles"] += 1
                    if pend["candles"] >= self.espera:
                        pend = None
            # 2) posição aberta: stop antes do alvo; no candle da execução só o stop
            if pos is not None:
                s = pos["s"]
                bateu_sl = x.l <= pos["sl"] if s == 1 else x.h >= pos["sl"]
                bateu_tp = (not recem) and (x.h >= pos["tp"] if s == 1 else x.l <= pos["tp"])
                if bateu_sl:
                    pnl = self._fechar(pos, pos["sl"] * (1 - s * self.slip), "SL", x.ts, TAXA_TAKER, trades)
                    banca += pnl
                    pnl_dia += pnl
                    pos = None
                elif bateu_tp:
                    pnl = self._fechar(pos, pos["tp"], "TP", x.ts, TAXA_MAKER, trades)
                    banca += pnl
                    pnl_dia += pnl
                    pos = None
            # 3) sinal no fechamento
            if pos is None and pend is None and n_dia < self.max_trades_dia and pnl_dia > -self.max_perda_dia:
                for f in self.setups.values():
                    sig = f(self.ctxs, i, est)
                    if sig is not None:
                        pend = {"setup": sig.setup, "s": 1 if sig.acao == "buy" else -1, "entrada": sig.entrada,
                                "sl": sig.sl, "tp": sig.tp, "candles": 0, "motivo": sig.motivo}
                        sinais += 1
                        break
            curva.append(banca)
        if pos is not None:
            ultimo = [x for x in self.ctxs if x.ts < (fim_ms or float("inf"))][-1]
            banca += self._fechar(pos, ultimo.c * (1 - pos["s"] * self.slip), "fim", ultimo.ts, TAXA_TAKER, trades)
        return self._relatorio(trades, curva, banca, sinais, time.time() - t0)

    def _relatorio(self, trades: List[Dict], curva: List[float], banca: float, sinais: int, tempo: float) -> Dict:
        n = len(trades)
        ganhos = [t["pnl"] for t in trades if t["pnl"] > 0]
        perdas = [-t["pnl"] for t in trades if t["pnl"] <= 0]
        pico, dd = self.banca0, 0.0
        for v in curva:
            pico = max(pico, v)
            dd = max(dd, (pico - v) / pico if pico else 0.0)
        bruto = mean(t["bruto_pct"] for t in trades) if n else 0.0
        custo = mean(t["custo_pct"] for t in trades) if n else 0.0
        por_mes: Dict[str, float] = {}
        for t in trades:
            m = datetime.fromtimestamp(t["ts_entrada"] / 1000, tz=timezone.utc).strftime("%Y-%m")
            por_mes[m] = round(por_mes.get(m, 0.0) + t["pnl"], 2)
        return {
            "trades": n, "sinais": sinais, "acerto": round(len(ganhos) / n, 3) if n else None,
            "bruto_pct_medio": bruto, "custo_pct_medio": custo,
            "razao_bruto_custo": round(bruto / custo, 2) if custo else None,
            "liquido_pct_medio": bruto - custo, "pnl_liquido": round(sum(t["pnl"] for t in trades), 2),
            "retorno_pct": round((banca / self.banca0 - 1) * 100, 2),
            "fator_lucro": round(sum(ganhos) / sum(perdas), 2) if perdas and sum(perdas) else None,
            "r_medio": round(mean(t["r"] for t in trades), 3) if n else None,
            "dd_max_pct": round(dd * 100, 2), "saidas": dict(Counter(t["motivo_saida"] for t in trades)),
            "por_mes": por_mes, "tempo_s": round(tempo, 1), "lista": trades,
        }


def avaliar_criterio(treino: Dict, validacao: Dict) -> Tuple[bool, List[str]]:
    """O que reprova um setup. Vazio = aprovado. O critério foi escrito antes de qualquer resultado."""
    c = CRITERIO
    falhas: List[str] = []
    if treino["trades"] < c["trades_min_treino"]:
        falhas.append(f"poucos trades no treino ({treino['trades']} < {c['trades_min_treino']})")
    if treino["bruto_pct_medio"] <= 0 or treino["bruto_pct_medio"] < c["bruto_sobre_custo"] * treino["custo_pct_medio"]:
        falhas.append(f"bruto por trade no treino ({treino['bruto_pct_medio']:.4%}) abaixo de "
                      f"{c['bruto_sobre_custo']:g}x o custo ({treino['custo_pct_medio']:.4%})")
    if treino["pnl_liquido"] <= 0:
        falhas.append(f"líquido negativo no treino ({treino['pnl_liquido']:+.2f})")
    if validacao["trades"] < c["trades_min_validacao"]:
        falhas.append(f"poucos trades na validação ({validacao['trades']} < {c['trades_min_validacao']})")
    if validacao["pnl_liquido"] <= 0:
        falhas.append(f"líquido negativo na validação ({validacao['pnl_liquido']:+.2f}): não se sustenta fora do treino")
    return (not falhas), falhas
