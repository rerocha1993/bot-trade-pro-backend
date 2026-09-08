# services/detector_ponto_institucional_service.py
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.ponto_institucional import PontoInstitucional
from models.ponto_institucional_log import PontoInstitucionalLog


class DetectorPontoInstitucionalService:
    @staticmethod
    def registrar_ponto(db: Session, preco: float, tipo: str, motivo: str, par: str, exchange: str,
                        relevancia: float = 1.0, extra: Optional[dict] = None, tolerancia_pct: float = 0.0015):
        """
        Registra um ponto institucional sem duplicar: se já existe ponto ATIVO do mesmo tipo/par/exchange
        a menos de `tolerancia_pct` do preço, atualiza a relevância (máximo) e a data, em vez de criar outro.
        """
        preco = float(preco)
        lo, hi = preco * (1 - tolerancia_pct), preco * (1 + tolerancia_pct)
        existente = db.query(PontoInstitucional).filter(
            PontoInstitucional.par == par, PontoInstitucional.exchange == exchange, PontoInstitucional.tipo == tipo,
            PontoInstitucional.rompido == False,  # noqa: E712
            PontoInstitucional.preco >= lo, PontoInstitucional.preco <= hi).first()
        if existente:
            if relevancia and (existente.relevancia or 0) < relevancia:
                existente.relevancia = relevancia
            existente.data_identificacao = datetime.utcnow()
            db.commit()
            return existente

        ponto = PontoInstitucional(
            preco=preco, tipo=tipo, motivo=motivo, ativo=True, testado=False, rompido=False,
            data_identificacao=datetime.utcnow(), par=par, exchange=exchange, relevancia=relevancia,
            extra=str(extra) if extra else None)
        db.add(ponto)
        db.commit()
        db.refresh(ponto)
        db.add(PontoInstitucionalLog(
            ponto_id=ponto.id, preco=ponto.preco, tipo=ponto.tipo, par=ponto.par, exchange=ponto.exchange,
            acao="criado", relevancia=ponto.relevancia, data_evento=ponto.data_identificacao, detalhe=motivo))
        db.commit()
        return ponto
