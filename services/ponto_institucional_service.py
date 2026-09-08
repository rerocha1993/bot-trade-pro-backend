# services/ponto_institucional_service.py
"""
Pontos institucionais (suportes/resistências detectados por TPO, Volume Profile, VWAP, Order Flow
e Order Blocks em vários timeframes).

Semântica:
    testado  -> preço tocou o ponto (dentro da tolerância percentual) e ele segue válido; relevância cai
    rompido  -> fechamento atravessou o ponto: suporte rompido por baixo, resistência por cima; ponto inativa
    neutro   -> tipos sem lado definido (POC, VWAP, HVN, cluster): só são "testados"; rompem quando o
                preço se afasta mais de `tol_rompimento_neutro` do nível

Classificação por tipo (prefixo) e posição relativa ao preço no momento da detecção.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.ponto_institucional import PontoInstitucional
from models.ponto_institucional_log import PontoInstitucionalLog

SUPORTE_PREFIXOS = ("OB_BULLISH", "VP_VAL", "TPO_VAL", "SUPORTE", "VWAP_BANDA_-")
RESISTENCIA_PREFIXOS = ("OB_BEARISH", "VP_VAH", "TPO_VAH", "RESISTENCIA", "VWAP_BANDA_+")


def classificar_tipo(tipo: str, preco_ponto: float = None, preco_ref: float = None) -> str:
    t = (tipo or "").upper()
    if t.startswith(SUPORTE_PREFIXOS):
        return "suporte"
    if t.startswith(RESISTENCIA_PREFIXOS):
        return "resistencia"
    # HVN/LVN/POC/VWAP/cluster: lado definido pela posição relativa ao preço atual
    if preco_ponto is not None and preco_ref is not None:
        return "suporte" if preco_ponto < preco_ref else "resistencia"
    return "neutro"


class PontoInstitucionalService:
    @staticmethod
    def criar_ponto(db: Session, ponto_data: dict):
        ponto = PontoInstitucional(**ponto_data)
        db.add(ponto)
        db.commit()
        db.refresh(ponto)
        return ponto

    @staticmethod
    def listar_pontos(db: Session, par=None, exchange=None, status=None, tipo=None, preco_ref: float = None,
                      faixa_pct: float = None):
        query = db.query(PontoInstitucional)
        if par:
            query = query.filter(PontoInstitucional.par == par)
        if exchange:
            query = query.filter(PontoInstitucional.exchange == exchange)
        if tipo:
            query = query.filter(PontoInstitucional.tipo.like(f"%{tipo}%"))
        if status == "ativo":
            query = query.filter(PontoInstitucional.ativo == True, PontoInstitucional.rompido == False)  # noqa: E712
        elif status == "testado":
            query = query.filter(PontoInstitucional.testado == True, PontoInstitucional.rompido == False)  # noqa: E712
        elif status == "rompido":
            query = query.filter(PontoInstitucional.rompido == True)  # noqa: E712
        if preco_ref and faixa_pct:
            lo, hi = preco_ref * (1 - faixa_pct), preco_ref * (1 + faixa_pct)
            query = query.filter(PontoInstitucional.preco >= lo, PontoInstitucional.preco <= hi)
        return query.order_by(PontoInstitucional.relevancia.desc()).all()

    @staticmethod
    def atualizar_status(db: Session, ponto_id: int, status: str):
        ponto = db.query(PontoInstitucional).filter(PontoInstitucional.id == ponto_id).first()
        if not ponto:
            return None
        if status == "testar":
            ponto.testado = True
            ponto.data_testado = datetime.utcnow()
        elif status == "romper":
            ponto.rompido = True
            ponto.ativo = False
            ponto.data_rompido = datetime.utcnow()
        db.commit()
        db.refresh(ponto)
        return ponto

    @staticmethod
    def historico(db: Session, par=None, exchange=None, limite: int = 500):
        query = db.query(PontoInstitucional)
        if par:
            query = query.filter(PontoInstitucional.par == par)
        if exchange:
            query = query.filter(PontoInstitucional.exchange == exchange)
        return query.order_by(PontoInstitucional.data_identificacao.desc()).limit(limite).all()

    # ------------------------------------------------------------ manutenção
    @staticmethod
    def _log(db, ponto, acao, detalhe):
        db.add(PontoInstitucionalLog(
            ponto_id=ponto.id, preco=ponto.preco, tipo=ponto.tipo, par=ponto.par, exchange=ponto.exchange,
            acao=acao, relevancia=ponto.relevancia, data_evento=datetime.utcnow(), detalhe=detalhe))

    @staticmethod
    def atualizar_pontos_testados_ou_rompidos(db: Session, preco_atual, par, exchange, tolerancia: float = 0.0015,
                                              tol_rompimento: float = 0.002, preco_fechamento: float = None):
        """
        tolerancia      -> fração do preço para considerar "testado" (0,15%)
        tol_rompimento  -> fechamento além do ponto em mais que isto = rompido (0,2%)
        preco_fechamento-> se informado (candle fechado), usado para rompimento; senão usa preco_atual
        """
        preco = float(preco_atual)
        fech = float(preco_fechamento if preco_fechamento is not None else preco_atual)
        pontos = db.query(PontoInstitucional).filter(
            PontoInstitucional.par == par, PontoInstitucional.exchange == exchange,
            PontoInstitucional.ativo == True, PontoInstitucional.rompido == False).all()  # noqa: E712
        alterados = 0
        for ponto in pontos:
            p = float(ponto.preco)
            lado = classificar_tipo(ponto.tipo, p, preco)
            # ROMPIDO
            rompeu = False
            if lado == "suporte" and fech < p * (1 - tol_rompimento):
                rompeu = True
            elif lado == "resistencia" and fech > p * (1 + tol_rompimento):
                rompeu = True
            if rompeu:
                ponto.rompido = True
                ponto.ativo = False
                ponto.data_rompido = datetime.utcnow()
                PontoInstitucionalService._log(db, ponto, "rompido", f"{lado} rompido: fechamento {fech:.2f}")
                alterados += 1
                continue
            # TESTADO
            if abs(p - preco) <= p * tolerancia and not ponto.testado:
                ponto.testado = True
                ponto.data_testado = datetime.utcnow()
                if ponto.relevancia is not None and ponto.relevancia > 0.2:
                    ponto.relevancia = round(ponto.relevancia - 0.2, 2)
                PontoInstitucionalService._log(db, ponto, "testado", f"{lado} testado a {preco:.2f}")
                alterados += 1
        if alterados:
            db.commit()
        return alterados

    @staticmethod
    def obter_pontos_institucionais_ativos(db, par, exchange, timeframes_institucionais):
        if isinstance(timeframes_institucionais, str):
            timeframes_institucionais = [timeframes_institucionais]
        filtros = [PontoInstitucional.par == par, PontoInstitucional.exchange == exchange,
                   PontoInstitucional.ativo == True, PontoInstitucional.rompido == False]  # noqa: E712
        tipo_filtros = [PontoInstitucional.tipo.like(f"%_{tf}") for tf in timeframes_institucionais]
        return db.query(PontoInstitucional).filter(*filtros, or_(*tipo_filtros)).all()

    @staticmethod
    def pontos_proximos(db, par, exchange, preco: float, raio_pct: float, relevancia_minima: float = 0.0) -> List[Dict]:
        lo, hi = preco * (1 - raio_pct), preco * (1 + raio_pct)
        pontos = db.query(PontoInstitucional).filter(
            PontoInstitucional.par == par, PontoInstitucional.exchange == exchange,
            PontoInstitucional.ativo == True, PontoInstitucional.rompido == False,  # noqa: E712
            PontoInstitucional.preco >= lo, PontoInstitucional.preco <= hi,
            PontoInstitucional.relevancia >= relevancia_minima).all()
        return [{"id": p.id, "preco": float(p.preco), "tipo": p.tipo, "relevancia": p.relevancia,
                 "lado": classificar_tipo(p.tipo, float(p.preco), preco), "testado": p.testado} for p in pontos]

    @staticmethod
    def pontos_contra_direcao(db, par, exchange, preco: float, direcao: str, raio_pct: float,
                              relevancia_minima: float = 1.5) -> List[Dict]:
        """Resistências logo acima (para compra) ou suportes logo abaixo (para venda)."""
        prox = PontoInstitucionalService.pontos_proximos(db, par, exchange, preco, raio_pct, relevancia_minima)
        if direcao == "buy":
            return [p for p in prox if p["lado"] == "resistencia" and p["preco"] >= preco]
        return [p for p in prox if p["lado"] == "suporte" and p["preco"] <= preco]

    @staticmethod
    def limpar_antigos(db, par, exchange, dias: int = 60, manter_por_tipo: int = 40) -> int:
        """Inativa pontos rompidos antigos e limita a quantidade por tipo (mantém os mais relevantes)."""
        from datetime import timedelta
        corte = datetime.utcnow() - timedelta(days=dias)
        n = db.query(PontoInstitucional).filter(
            PontoInstitucional.par == par, PontoInstitucional.exchange == exchange,
            PontoInstitucional.rompido == True, PontoInstitucional.data_rompido < corte).delete()  # noqa: E712
        tipos = [t[0] for t in db.query(PontoInstitucional.tipo).filter(
            PontoInstitucional.par == par, PontoInstitucional.exchange == exchange).distinct()]
        for tipo in tipos:
            ativos = db.query(PontoInstitucional).filter(
                PontoInstitucional.par == par, PontoInstitucional.exchange == exchange, PontoInstitucional.tipo == tipo,
                PontoInstitucional.rompido == False).order_by(  # noqa: E712
                PontoInstitucional.relevancia.desc(), PontoInstitucional.data_identificacao.desc()).all()
            for p in ativos[manter_por_tipo:]:
                db.delete(p)
                n += 1
        db.commit()
        return n
