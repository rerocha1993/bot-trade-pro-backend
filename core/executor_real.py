# core/executor_real.py
"""
Executor de ordens.

    simulador -> NUNCA envia ordem; devolve uma execução fictícia ao preço atual (paper trading).
    testnet   -> envia para testnet.bybit.com (chaves *_TESTNET).
    real      -> envia para a mainnet (chaves *_REAL).

Entrada: ordem a mercado com SL/TP anexados à posição (um único request na Bybit).
Saída:   ordem a mercado reduceOnly com a quantidade REAL da posição.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Optional

from core.conexoes.conexao_bybit import BybitConnector

logger = logging.getLogger(__name__)

TAXA_TAKER = 0.00055  # Bybit linear (0,055%)
TAXA_MAKER = 0.0002   # Bybit linear (0,02%) para ordens limitadas post-only


def position_idx(position_mode: Optional[str], direcao: str) -> int:
    """one-way -> 0 ; hedged -> 1 (long) / 2 (short)."""
    if (position_mode or "one-way").lower() in ("hedged", "hedge", "both"):
        return 1 if direcao == "buy" else 2
    return 0


class OrderExecutor:
    def __init__(self, connector: BybitConnector):
        self.con = connector
        self.modo = connector.modo_execucao

    @property
    def simulado(self) -> bool:
        return self.modo == "simulador" or not self.con.pode_enviar_ordens

    # ---------------------------------------------------------------- abrir
    def abrir(self, par: str, direcao: str, quantidade: float, stop_loss: Optional[float], take_profit: Optional[float],
              position_mode: str = "one-way", preco_ref: Optional[float] = None) -> Dict:
        direcao = direcao.lower()
        qty = self.con.arredondar_quantidade(par, quantidade)
        if qty <= 0:
            raise ValueError(f"Quantidade {quantidade} abaixo do mínimo negociável de {par}")
        if self.simulado:
            preco = float(preco_ref or self.con.obter_preco_atual(par))
            return {"ordem_id": f"SIM-{uuid.uuid4().hex[:12]}", "preco_exec": preco, "quantidade": qty,
                    "simulado": True, "taxa": preco * qty * TAXA_TAKER, "timestamp": int(time.time() * 1000)}
        pidx = position_idx(position_mode, direcao)
        ordem = self.con.criar_ordem(par, direcao, qty, tipo="market", stop_loss=stop_loss, take_profit=take_profit,
                                     position_idx=pidx, client_id=f"bt-{uuid.uuid4().hex[:24]}")
        preco_exec = self._preco_execucao(par, ordem, preco_ref)
        return {"ordem_id": ordem.get("id"), "preco_exec": preco_exec, "quantidade": qty, "simulado": False,
                "taxa": preco_exec * qty * TAXA_TAKER, "timestamp": int(time.time() * 1000), "raw": ordem}

    # ------------------------------------------------------- ordem limitada
    def abrir_limite(self, par: str, direcao: str, quantidade: float, preco_limite: float, stop_loss: Optional[float],
                     take_profit: Optional[float], position_mode: str = "one-way") -> Dict:
        """Ordem limitada post-only com SL/TP anexados. Em simulador devolve um pedido pendente fictício."""
        direcao = direcao.lower()
        qty = self.con.arredondar_quantidade(par, quantidade)
        if qty <= 0:
            raise ValueError(f"Quantidade {quantidade} abaixo do mínimo negociável de {par}")
        preco_limite = self.con.arredondar_preco(par, preco_limite)
        if self.simulado:
            return {"ordem_id": f"SIM-LIM-{uuid.uuid4().hex[:10]}", "preco": preco_limite, "quantidade": qty, "simulado": True,
                    "status": "aberta", "timestamp": int(time.time() * 1000)}
        pidx = position_idx(position_mode, direcao)
        ordem = self.con.criar_ordem(par, direcao, qty, tipo="limit", preco=preco_limite, stop_loss=stop_loss, take_profit=take_profit,
                                     position_idx=pidx, post_only=True, client_id=f"btl-{uuid.uuid4().hex[:24]}")
        return {"ordem_id": ordem.get("id"), "preco": preco_limite, "quantidade": qty, "simulado": False,
                "status": "aberta", "timestamp": int(time.time() * 1000), "raw": ordem}

    def situacao_ordem(self, par: str, ordem_id: str) -> Dict:
        """'aberta' | 'executada' (com preco_exec/quantidade) | 'cancelada'."""
        if self.simulado:
            return {"status": "aberta"}
        o = self.con.exchange.fetch_order(ordem_id, self.con.simbolo(par))
        st = (o.get("status") or "").lower()
        if st == "closed" or (o.get("filled") and float(o["filled"]) >= float(o.get("amount") or 0) > 0):
            preco = float(o.get("average") or o.get("price") or 0)
            return {"status": "executada", "preco_exec": preco, "quantidade": float(o.get("filled") or o.get("amount") or 0),
                    "taxa": preco * float(o.get("filled") or 0) * TAXA_MAKER}
        if st in ("canceled", "cancelled", "rejected", "expired"):
            return {"status": "cancelada"}
        return {"status": "aberta", "executada_parcial": float(o.get("filled") or 0)}

    def cancelar_ordem(self, par: str, ordem_id: str) -> bool:
        if self.simulado:
            return True
        try:
            self.con.exchange.cancel_order(ordem_id, self.con.simbolo(par))
            return True
        except Exception as e:
            logger.warning("cancelar ordem %s: %s", ordem_id, e)
            return False

    # --------------------------------------------------------------- fechar
    def fechar(self, par: str, direcao_posicao: str, quantidade: float, position_mode: str = "one-way",
               preco_ref: Optional[float] = None) -> Dict:
        lado = "sell" if direcao_posicao == "buy" else "buy"
        if self.simulado:
            preco = float(preco_ref or self.con.obter_preco_atual(par))
            return {"ordem_id": f"SIM-{uuid.uuid4().hex[:12]}", "preco_exec": preco, "quantidade": quantidade,
                    "simulado": True, "taxa": preco * quantidade * TAXA_TAKER}
        pos = self.con.obter_posicao(par)
        if not pos:
            return {"ordem_id": None, "preco_exec": None, "quantidade": 0, "simulado": False, "ja_fechada": True}
        qty = pos["quantidade"]
        ordem = self.con.criar_ordem(par, lado, qty, tipo="market", reduce_only=True,
                                     position_idx=pos.get("position_idx", position_idx(position_mode, direcao_posicao)))
        preco_exec = self._preco_execucao(par, ordem, preco_ref)
        return {"ordem_id": ordem.get("id"), "preco_exec": preco_exec, "quantidade": qty, "simulado": False,
                "taxa": preco_exec * qty * TAXA_TAKER, "raw": ordem}

    def atualizar_stop(self, par: str, stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
                       position_mode: str = "one-way", direcao: str = "buy") -> bool:
        if self.simulado:
            return True
        try:
            self.con.atualizar_stop_posicao(par, stop_loss, take_profit, position_idx(position_mode, direcao))
            return True
        except Exception as e:
            logger.warning("Falha ao atualizar stop na exchange: %s", e)
            return False

    def _preco_execucao(self, par: str, ordem: Dict, preco_ref: Optional[float]) -> float:
        preco = ordem.get("average") or ordem.get("price")
        if not preco:
            try:
                time.sleep(0.5)
                o = self.con.exchange.fetch_order(ordem["id"], self.con.simbolo(par))
                preco = o.get("average") or o.get("price")
            except Exception:
                preco = None
        return float(preco or preco_ref or self.con.obter_preco_atual(par))


class ExecutorReal(OrderExecutor):
    """Compatibilidade com o nome antigo."""

    def __init__(self, par: str, modo_execucao: str = "simulador", connector: Optional[BybitConnector] = None):
        super().__init__(connector or BybitConnector(modo_execucao))
        self.par = par

    def executar_ordem(self, direcao, quantidade, preco_entrada=None, stop_loss=None, take_profit=None):
        return self.abrir(self.par, direcao, quantidade, stop_loss, take_profit, preco_ref=preco_entrada)
