# core/ia/memoria.py
"""
MEMÓRIA DE SITUAÇÕES (o "R" do RAG): cada candle vira um vetor numérico da leitura de Elliott + contexto de
preço, guardado com o que aconteceu DEPOIS. Na hora de decidir, as situações mais parecidas do passado (e o que
veio depois delas) vão junto para o modelo.

Por que vetor de números e não texto com embedding: a leitura é numérica (pesos das contagens, distâncias em ATR,
fase), então a distância entre vetores padronizados mede "situação parecida" melhor e sem serviço externo. E dá
para TESTAR no histórico se a memória prevê alguma coisa (scripts/ia_memoria.py), antes de pagar uma chamada.

Sem olhar o futuro: `vizinhos(..., ate_ts)` só enxerga situações cujo resultado já era conhecido em `ate_ts`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

FASES = ["onda_1", "onda_2", "inicio_onda_3", "meio_onda_3", "final_onda_3", "onda_4", "onda_5",
         "correcao_a", "correcao_b", "correcao_c"]
NOMES = (["peso_compra", "peso_venda", "n_cenarios", "prob_primario", "dir_primario", "dist_inv_atr", "dist_alvo_atr",
          "ret_6_atr", "ret_30_atr", "eficiencia", "vol_rel"] + [f"fase_{f}" for f in FASES])


def normalizar_cenarios(cenarios: Sequence[Dict]) -> List[Dict]:
    """Aceita o formato do motor ao vivo (direcao_trade, probabilidade, invalidacao) e o do histórico."""
    out = []
    for c in cenarios or []:
        out.append({"direcao": c.get("direcao") or c.get("direcao_trade"), "prob": float(c.get("prob", c.get("probabilidade")) or 0),
                    "inv": c.get("inv", c.get("invalidacao")), "alvos": c.get("alvos") or [], "fase": c.get("fase")})
    return out


def _eficiencia(closes: np.ndarray) -> float:
    if len(closes) < 3:
        return 0.0
    caminho = float(np.sum(np.abs(np.diff(closes)))) or 1e-9
    return abs(float(closes[-1] - closes[0])) / caminho


def vetor_situacao(cenarios: Sequence[Dict], closes: Sequence[float], atr: float, atr_longo: Optional[float] = None) -> np.ndarray:
    """A situação de um candle fechado. `closes` termina no candle da decisão (o último é o preço)."""
    cen = normalizar_cenarios(cenarios)
    closes = np.asarray(closes, dtype=float)
    preco = float(closes[-1])
    total = sum(c["prob"] for c in cen) or 1.0
    compra = sum(c["prob"] for c in cen if c["direcao"] == "buy") / total
    venda = sum(c["prob"] for c in cen if c["direcao"] == "sell") / total
    prim = max(cen, key=lambda c: c["prob"]) if cen else None
    a = atr or preco * 0.01
    dist_inv = abs(preco - float(prim["inv"])) / a if prim and prim["inv"] is not None else 0.0
    dist_alvo = abs(float(prim["alvos"][0]) - preco) / a if prim and prim["alvos"] else 0.0
    ret = lambda n: (preco - closes[-n - 1]) / a if len(closes) > n else 0.0
    fase = [1.0 if prim and prim["fase"] == f else 0.0 for f in FASES]
    return np.array([compra, venda, min(len(cen), 8) / 8, prim["prob"] if prim else 0.0,
                     (1 if prim["direcao"] == "buy" else -1 if prim["direcao"] == "sell" else 0) if prim else 0,
                     min(dist_inv, 15.0), min(dist_alvo, 15.0), float(np.clip(ret(6), -10, 10)), float(np.clip(ret(30), -20, 20)),
                     _eficiencia(closes[-21:]), (atr / atr_longo) if atr_longo else 1.0] + fase, dtype=float)


def desfecho(candles_futuros: Sequence[Sequence[float]], preco: float, atr: float) -> Optional[Dict]:
    """O que aconteceu nos candles seguintes: retorno no fim, máxima alta e máxima queda (em % e em ATR)."""
    if not candles_futuros:
        return None
    fim = float(candles_futuros[-1][4])
    mx = max(float(c[2]) for c in candles_futuros)
    mn = min(float(c[3]) for c in candles_futuros)
    a = atr or preco * 0.01
    return {"ret_pct": (fim / preco - 1) * 100, "max_pct": (mx / preco - 1) * 100, "min_pct": (mn / preco - 1) * 100,
            "ret_atr": (fim - preco) / a, "candles": len(candles_futuros)}


@dataclass
class Situacao:
    ts: int
    vetor: np.ndarray
    preco: float
    resumo: str
    desfecho: Optional[Dict]
    conhecido_em: int        # ts a partir do qual o desfecho é conhecido (sem look-ahead)


class Memoria:
    """Busca por vizinhos mais próximos em vetores padronizados (média/desvio das próprias situações)."""

    def __init__(self, situacoes: Sequence[Situacao]):
        self.s = [x for x in situacoes if x.desfecho is not None]
        if self.s:
            self.X = np.vstack([x.vetor for x in self.s])
            self.mu = self.X.mean(axis=0)
            self.sd = self.X.std(axis=0) + 1e-9
            self.Z = (self.X - self.mu) / self.sd
            self.conhecido = np.array([x.conhecido_em for x in self.s])
        else:
            self.X = self.Z = np.zeros((0, len(NOMES)))
            self.mu, self.sd, self.conhecido = np.zeros(len(NOMES)), np.ones(len(NOMES)), np.zeros(0)

    def __len__(self):
        return len(self.s)

    def vizinhos(self, vetor: np.ndarray, k: int = 5, ate_ts: Optional[int] = None) -> List[Dict]:
        if not len(self.s):
            return []
        z = (np.asarray(vetor, dtype=float) - self.mu) / self.sd
        d = np.sqrt(((self.Z - z) ** 2).sum(axis=1))
        if ate_ts is not None:
            d = np.where(self.conhecido <= ate_ts, d, np.inf)
        idx = np.argsort(d)[:k]
        return [{"ts": self.s[i].ts, "distancia": round(float(d[i]), 3), "preco": self.s[i].preco,
                 "resumo": self.s[i].resumo, "desfecho": self.s[i].desfecho} for i in idx if np.isfinite(d[i])]

    @staticmethod
    def agregado(viz: Sequence[Dict]) -> Dict:
        """O que os vizinhos dizem, junto: quantos subiram, retorno mediano, piores e melhores excursões."""
        if not viz:
            return {"n": 0}
        r = [v["desfecho"]["ret_pct"] for v in viz]
        return {"n": len(viz), "subiram": round(sum(1 for x in r if x > 0) / len(r), 2),
                "ret_mediano_pct": round(float(np.median(r)), 2),
                "max_mediano_pct": round(float(np.median([v["desfecho"]["max_pct"] for v in viz])), 2),
                "min_mediano_pct": round(float(np.median([v["desfecho"]["min_pct"] for v in viz])), 2)}
