# core/backtest_assimetria.py
"""
Backtest da regra de assimetria (core/assimetria.py) sobre as contagens reconstruídas do histórico
(scripts/cenarios_historicos.py).

Execução:
    - sinal no fechamento do candle; entrada a mercado nesse preço (taxa taker + slippage)
    - dos candles seguintes: stop e alvo intra-candle; os dois no mesmo candle conta o stop (pior caso)
    - saída na virada (opcional): no fechamento em que o grupo deixou de ser maioria (< 50% do peso)
    - uma posição por vez; resultado em R (1 R = distância até o stop) e em % com risco fixo de 1% por trade

O CRITÉRIO foi fixado antes de rodar e é conferido em dois períodos: treino (onde a variante é escolhida) e
validação (que a escolha não viu).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

from core.assimetria import SLIPPAGE, grupo_vivo, plano
from core.executor_real import TAXA_MAKER, TAXA_TAKER

CRITERIO = {"trades_min_treino": 30, "trades_min_validacao": 15, "fator_lucro_min_treino": 1.1}


class BacktestAssimetria:
    def __init__(self, linhas: Sequence[Dict], candles: Dict[int, Tuple[float, float, float, float]],
                 tipo_stop: str = "grupo", sair_na_virada: bool = False, rr_minimo: float = 1.0,
                 minimo_consenso: float = 0.6):
        self.linhas = sorted(linhas, key=lambda x: x["ts"])
        self.candles = candles            # ts -> (open, high, low, close)
        self.tipo_stop = tipo_stop
        self.sair_na_virada = sair_na_virada
        self.rr_minimo = rr_minimo
        self.minimo_consenso = minimo_consenso

    @staticmethod
    def _fechar(pos: Dict, saida: float, motivo: str, ts: int) -> Dict:
        s = 1 if pos["lado"] == "buy" else -1
        risco = abs(pos["entrada"] - pos["stop"])
        taxa_saida = TAXA_MAKER if motivo == "alvo" else TAXA_TAKER + SLIPPAGE
        if motivo != "alvo":
            saida = saida * (1 - s * SLIPPAGE)
        bruto_r = (saida - pos["entrada"]) * s / risco
        custo_r = (pos["entrada"] * (TAXA_TAKER + SLIPPAGE) + saida * taxa_saida) / risco
        return {**pos, "saida": saida, "motivo_saida": motivo, "ts_saida": ts, "bruto_r": bruto_r,
                "custo_r": custo_r, "liquido_r": bruto_r - custo_r, "risco_pct": risco / pos["entrada"]}

    def executar(self, inicio_ms: int = 0, fim_ms: Optional[int] = None) -> Dict:
        pos: Optional[Dict] = None
        trades: List[Dict] = []
        sinais = 0
        for linha in self.linhas:
            ts = linha["ts"]
            if ts < inicio_ms:
                continue
            if fim_ms is not None and ts >= fim_ms:
                break
            c = self.candles.get(ts)
            if c is None:
                continue
            _, hi, lo, close = c
            if pos is not None and ts > pos["ts"]:
                bateu_stop = lo <= pos["stop"] if pos["lado"] == "buy" else hi >= pos["stop"]
                bateu_alvo = hi >= pos["alvo"] if pos["lado"] == "buy" else lo <= pos["alvo"]
                if bateu_stop:
                    trades.append(self._fechar(pos, pos["stop"], "stop", ts))
                    pos = None
                elif bateu_alvo:
                    trades.append(self._fechar(pos, pos["alvo"], "alvo", ts))
                    pos = None
                elif self.sair_na_virada and grupo_vivo(linha["cenarios"], close, pos["lado"]) < 0.5:
                    trades.append(self._fechar(pos, close, "virada", ts))
                    pos = None
            if pos is None:
                p = plano(linha["cenarios"], close, linha.get("atr") or 0.0, self.tipo_stop, self.rr_minimo,
                          self.minimo_consenso)
                if p is not None:
                    sinais += 1
                    pos = {"ts": ts, "lado": p.lado, "entrada": p.entrada, "stop": p.stop, "alvo": p.alvo,
                           "rr": p.rr_liquido, "peso": p.peso, "n_grupo": p.n_grupo}
        return self._relatorio(trades, sinais)

    @staticmethod
    def _relatorio(trades: List[Dict], sinais: int) -> Dict:
        n = len(trades)
        if not n:
            return {"trades": 0, "sinais": sinais, "liquido_r": 0.0, "soma_r": 0.0, "fator_lucro": None, "lista": []}
        ganhos = sum(t["liquido_r"] for t in trades if t["liquido_r"] > 0)
        perdas = -sum(t["liquido_r"] for t in trades if t["liquido_r"] <= 0)
        acc, pico, dd = 0.0, 0.0, 0.0
        for t in trades:
            acc += t["liquido_r"]
            pico = max(pico, acc)
            dd = max(dd, pico - acc)
        ano = lambda t: datetime.fromtimestamp(t["ts"] / 1000, tz=timezone.utc).year
        por_ano: Dict[int, float] = {}
        for t in trades:
            por_ano[ano(t)] = round(por_ano.get(ano(t), 0.0) + t["liquido_r"], 2)
        return {
            "trades": n, "sinais": sinais, "acerto": round(sum(1 for t in trades if t["liquido_r"] > 0) / n, 3),
            "bruto_r": round(mean(t["bruto_r"] for t in trades), 3), "custo_r": round(mean(t["custo_r"] for t in trades), 3),
            "liquido_r": round(mean(t["liquido_r"] for t in trades), 3), "soma_r": round(sum(t["liquido_r"] for t in trades), 2),
            "fator_lucro": round(ganhos / perdas, 2) if perdas else None, "dd_max_r": round(dd, 2),
            "rr_medio": round(mean(t["rr"] for t in trades), 2), "risco_pct_mediano": round(sorted(t["risco_pct"] for t in trades)[n // 2] * 100, 2),
            "saidas": dict(Counter(t["motivo_saida"] for t in trades)), "por_ano_r": por_ano, "lista": trades,
        }


def avaliar(treino: Dict, validacao: Dict) -> Tuple[bool, List[str]]:
    c = CRITERIO
    falhas: List[str] = []
    if treino["trades"] < c["trades_min_treino"]:
        falhas.append(f"poucos trades no treino ({treino['trades']})")
    if treino["soma_r"] <= 0:
        falhas.append(f"líquido negativo no treino ({treino['soma_r']:+.1f} R)")
    elif (treino.get("fator_lucro") or 0) < c["fator_lucro_min_treino"]:
        falhas.append(f"fator de lucro no treino {treino.get('fator_lucro')} < {c['fator_lucro_min_treino']}")
    if validacao["trades"] < c["trades_min_validacao"]:
        falhas.append(f"poucos trades na validação ({validacao['trades']})")
    if validacao["soma_r"] <= 0:
        falhas.append(f"líquido negativo na validação ({validacao['soma_r']:+.1f} R): não se sustenta fora do treino")
    return (not falhas), falhas
