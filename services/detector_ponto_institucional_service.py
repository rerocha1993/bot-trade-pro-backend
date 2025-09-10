from models.ponto_institucional_log import PontoInstitucionalLog
from sqlalchemy.orm import Session
from models.ponto_institucional import PontoInstitucional
from datetime import datetime

class DetectorPontoInstitucionalService:
    @staticmethod
    def registrar_ponto(
        db, preco, tipo, motivo, par, exchange, relevancia=1.0, extra=None
    ):
        # Verifica se já existe ponto igual (ativo e não rompido)
        ponto_existente = db.query(PontoInstitucional).filter(
            PontoInstitucional.preco == preco,
            PontoInstitucional.par == par,
            PontoInstitucional.exchange == exchange,
            PontoInstitucional.tipo == tipo,
            PontoInstitucional.rompido == False
        ).first()

        if ponto_existente:
            return ponto_existente

        ponto = PontoInstitucional(
            preco=preco,
            tipo=tipo,
            motivo=motivo,
            ativo=True,
            testado=False,
            rompido=False,
            data_identificacao=datetime.utcnow(),
            par=par,
            exchange=exchange,
            relevancia=relevancia,
            extra=str(extra) if extra else None
        )
        db.add(ponto)
        db.commit()
        db.refresh(ponto)

        # === LOG DE CRIAÇÃO ===
        log = PontoInstitucionalLog(
            ponto_id=ponto.id,
            preco=ponto.preco,
            tipo=ponto.tipo,
            par=ponto.par,
            exchange=ponto.exchange,
            acao="criado",
            relevancia=ponto.relevancia,
            data_evento=ponto.data_identificacao,
            detalhe=motivo  # Salva o motivo institucional
        )
        db.add(log)
        db.commit()
        # === FIM LOG ===

        return ponto
