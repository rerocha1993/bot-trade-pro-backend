# services/orderblock_institutional_service.py
"""
Order blocks institucionais a partir do LIVRO DE OFERTAS de várias exchanges (cesta TradingView
+ Bybit): concentrações de liquidez passiva (bids = demanda, asks = oferta).

Fluxo:
    atualizar_blocos(session, par)  -> lê livros, detecta clusters ≥ limiar do volume, consolida
                                       níveis próximos entre exchanges e persiste (status 'ativo')
    consultar_blocos_ativos(...)     -> usado pelo motor para alvos/proteções
    atualizar_blocos_rompidos(...)   -> marca 'rompido' quando o preço atravessa o nível
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from models.orderblocks_institucionais import OrderBlockInstitucional

logger = logging.getLogger(__name__)


class OrderBlockInstitutionalService:
    def __init__(self, market_data=None):
        self.market_data = market_data  # MarketDataAggregator (lazy)

    def _agg(self):
        if self.market_data is None:
            from core.market_data import MarketDataAggregator
            self.market_data = MarketDataAggregator("tradingview")
        return self.market_data

    # ------------------------------------------------------------- detecção
    @staticmethod
    def detectar_blocos(niveis: List[tuple], limiar_volume: float = 0.03, agrupamento_pct: float = 0.0005) -> List[Dict]:
        """
        niveis: [(preco, qty, exchange)] de UM lado do livro.
        Agrupa em faixas de 0,05% e devolve as faixas com volume >= limiar_volume do total.
        """
        if not niveis:
            return []
        grupos: Dict[float, Dict] = {}
        total = 0.0
        for preco, qty, *resto in niveis:
            passo = max(preco * agrupamento_pct, 1e-9)
            chave = round(round(preco / passo) * passo, 2)
            g = grupos.setdefault(chave, {"preco": chave, "volume": 0.0, "exchanges": set()})
            g["volume"] += qty
            if resto:
                g["exchanges"].add(resto[0])
            total += qty
        if total <= 0:
            return []
        saida = [{"preco": g["preco"], "volume": round(g["volume"], 6), "exchanges": sorted(g["exchanges"]),
                  "fracao": g["volume"] / total} for g in grupos.values() if g["volume"] >= limiar_volume * total]
        return sorted(saida, key=lambda b: -b["volume"])

    def get_orderblocks(self, par: str, profundidade: int = 100, limiar_volume: float = 0.03) -> Dict[str, List[Dict]]:
        book = self._agg().order_book_composto(par, profundidade)
        det = book.get("detalhado", {})
        return {
            "bids": self.detectar_blocos(det.get("bids", []), limiar_volume),
            "asks": self.detectar_blocos(det.get("asks", []), limiar_volume),
            "fontes": book.get("fontes", []),
        }

    # ---------------------------------------------------------- persistência
    @staticmethod
    def salvar_ou_atualizar_orderblock(session: Session, bloco: Dict):
        existente = session.query(OrderBlockInstitucional).filter_by(
            par=bloco["par"], preco=bloco["preco"], direcao=bloco["direcao"], status="ativo").first()
        if existente:
            existente.volume = bloco["volume"]
            existente.exchange_origem = bloco["exchange_origem"]
            existente.atualizado_em = datetime.utcnow()
            existente.info_extra = bloco.get("info_extra", existente.info_extra)
        else:
            session.add(OrderBlockInstitucional(
                par=bloco["par"], exchange_origem=bloco["exchange_origem"], direcao=bloco["direcao"],
                preco=bloco["preco"], volume=bloco["volume"], status="ativo", criado_em=datetime.utcnow(),
                info_extra=bloco.get("info_extra")))

    def atualizar_blocos(self, session: Session, par: str, profundidade: int = 100, limiar_volume: float = 0.03,
                         max_por_lado: int = 8) -> Dict[str, int]:
        """Detecta, persiste e expira blocos que sumiram do livro."""
        blocos = self.get_orderblocks(par, profundidade, limiar_volume)
        novos = {"buy": 0, "sell": 0}
        vivos = set()
        for direcao, lado in (("buy", "bids"), ("sell", "asks")):
            for b in blocos[lado][:max_por_lado]:
                self.salvar_ou_atualizar_orderblock(session, {
                    "par": par, "exchange_origem": ",".join(b["exchanges"])[:20] or "composto", "direcao": direcao,
                    "preco": b["preco"], "volume": b["volume"],
                    "info_extra": f"fracao={b['fracao']:.3f} fontes={blocos['fontes']}"})
                vivos.add((direcao, b["preco"]))
                novos[direcao] += 1
        # blocos ativos que não aparecem mais no livro há > 30 min viram 'expirado'
        from datetime import timedelta
        corte = datetime.utcnow() - timedelta(minutes=30)
        for ob in session.query(OrderBlockInstitucional).filter_by(par=par, status="ativo").all():
            if (ob.direcao, ob.preco) not in vivos and (ob.atualizado_em or ob.criado_em) < corte:
                ob.status = "expirado"
                ob.atualizado_em = datetime.utcnow()
        session.commit()
        return novos

    @staticmethod
    def consultar_blocos_ativos(session: Session, par: str, direcao: str, exchange: Optional[str] = None,
                                status: str = "ativo") -> List[OrderBlockInstitucional]:
        query = session.query(OrderBlockInstitucional).filter_by(par=par, direcao=direcao, status=status)
        if exchange:
            query = query.filter(OrderBlockInstitucional.exchange_origem.like(f"%{exchange}%"))
        return query.order_by(OrderBlockInstitucional.volume.desc()).all()

    @staticmethod
    def marcar_bloco_rompido(session: Session, bloco_id: int):
        bloco = session.query(OrderBlockInstitucional).filter_by(id=bloco_id).first()
        if bloco and bloco.status == "ativo":
            bloco.status = "rompido"
            bloco.rompido_em = datetime.utcnow()
            bloco.atualizado_em = datetime.utcnow()
            session.commit()

    @staticmethod
    def atualizar_blocos_rompidos(session: Session, par: str, preco_atual: float, margem_pct: float = 0.001) -> int:
        """Bid (demanda) rompe quando o preço fecha abaixo; ask (oferta) rompe quando fecha acima."""
        n = 0
        for bloco in session.query(OrderBlockInstitucional).filter_by(par=par, status="ativo").all():
            if bloco.direcao == "buy" and preco_atual < bloco.preco * (1 - margem_pct):
                bloco.status, bloco.rompido_em, bloco.atualizado_em = "rompido", datetime.utcnow(), datetime.utcnow()
                n += 1
            elif bloco.direcao == "sell" and preco_atual > bloco.preco * (1 + margem_pct):
                bloco.status, bloco.rompido_em, bloco.atualizado_em = "rompido", datetime.utcnow(), datetime.utcnow()
                n += 1
        if n:
            session.commit()
        return n

    @staticmethod
    def registrar_uso_bloco(session: Session, bloco_id: int, tipo_uso: str, bot_id: int, decisao_id=None):
        bloco = session.query(OrderBlockInstitucional).filter_by(id=bloco_id).first()
        if bloco:
            bloco.usado_como = tipo_uso
            bloco.atualizado_em = datetime.utcnow()
            bloco.info_extra = (bloco.info_extra or "") + f"\n{datetime.utcnow()} | bot {bot_id} | uso {tipo_uso} | decisao {decisao_id}"
            session.commit()
