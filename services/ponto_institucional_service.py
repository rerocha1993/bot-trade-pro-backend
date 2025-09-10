# services/ponto_institucional_service.py

from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from models.ponto_institucional import PontoInstitucional
from models.ponto_institucional_log import PontoInstitucionalLog

class PontoInstitucionalService:
    @staticmethod
    def criar_ponto(db: Session, ponto_data: dict):
        ponto = PontoInstitucional(**ponto_data)
        db.add(ponto)
        db.commit()
        db.refresh(ponto)
        return ponto

    @staticmethod
    def listar_pontos(db: Session, par=None, exchange=None, status=None, tipo=None):
        query = db.query(PontoInstitucional)
        if par:
            query = query.filter(PontoInstitucional.par == par)
        if exchange:
            query = query.filter(PontoInstitucional.exchange == exchange)
        if tipo:
            query = query.filter(PontoInstitucional.tipo == tipo)
        if status == "ativo":
            query = query.filter(PontoInstitucional.ativo == True, PontoInstitucional.rompido == False)
        if status == "testado":
            query = query.filter(PontoInstitucional.testado == True, PontoInstitucional.rompido == False)
        if status == "rompido":
            query = query.filter(PontoInstitucional.rompido == True)
        return query.all()

    @staticmethod
    def atualizar_status(db: Session, ponto_id: int, status: str):
        ponto = db.query(PontoInstitucional).filter(PontoInstitucional.id == ponto_id).first()
        if not ponto:
            return None

        if status == "testar":
            ponto.testado = True
            ponto.data_testado = func.now()
        elif status == "romper":
            ponto.rompido = True
            ponto.ativo = False
            ponto.data_rompido = func.now()

        db.commit()
        db.refresh(ponto)
        return ponto

    @staticmethod
    def historico(db: Session, par=None, exchange=None):
        query = db.query(PontoInstitucional)
        if par:
            query = query.filter(PontoInstitucional.par == par)
        if exchange:
            query = query.filter(PontoInstitucional.exchange == exchange)
        return query.order_by(PontoInstitucional.data_identificacao.desc()).all()
    
    @staticmethod
    def atualizar_pontos_testados_ou_rompidos(db, preco_atual, par, exchange, tolerancia=0.01):
        pontos_ativos = db.query(PontoInstitucional).filter(
            PontoInstitucional.par == par,
            PontoInstitucional.exchange == exchange,
            PontoInstitucional.ativo == True,
            PontoInstitucional.rompido == False
        ).all()
        for ponto in pontos_ativos:
            preco_ponto = float(ponto.preco)
            preco_atual_f = float(preco_atual)
            status_modificado = False

            # TESTADO
            if not ponto.testado and abs(preco_ponto - preco_atual_f) <= tolerancia:
                ponto.testado = True
                ponto.data_testado = datetime.utcnow()
                status_modificado = True
                if ponto.relevancia is not None and ponto.relevancia > 0.2:
                    ponto.relevancia = round(ponto.relevancia - 0.2, 2)

                log = PontoInstitucionalLog(
                    ponto_id=ponto.id,
                    preco=ponto.preco,
                    tipo=ponto.tipo,
                    par=ponto.par,
                    exchange=ponto.exchange,
                    acao="testado",
                    relevancia=ponto.relevancia,
                    data_evento=ponto.data_testado,
                    detalhe="Ponto testado automaticamente pelo sistema."
                )
                db.add(log)

            # ROMPIDO
            if not ponto.rompido:
                if (
                    ponto.tipo.upper().startswith(('TPO', 'HVN', 'VWAP', 'ORDER_BLOCK_BULLISH')) and preco_atual_f > preco_ponto
                    or ponto.tipo.upper().startswith(('SUPORTE', 'LQN', 'ORDER_BLOCK_BEARISH')) and preco_atual_f < preco_ponto
                ):
                    ponto.rompido = True
                    ponto.ativo = False
                    ponto.data_rompido = datetime.utcnow()
                    status_modificado = True

                    log = PontoInstitucionalLog(
                        ponto_id=ponto.id,
                        preco=ponto.preco,
                        tipo=ponto.tipo,
                        par=ponto.par,
                        exchange=ponto.exchange,
                        acao="rompido",
                        relevancia=ponto.relevancia,
                        data_evento=ponto.data_rompido,
                        detalhe="Ponto rompido automaticamente pelo sistema."
                    )
                    db.add(log)

        db.commit()
        
    @staticmethod
    def obter_pontos_institucionais_ativos(db, par, exchange, timeframes_institucionais):
        """
        Busca todos os pontos institucionais ativos/não rompidos do par, exchange e timeframes desejados.
        timeframes_institucionais: lista ou string (ex: ['4h','1d'] ou '4h')
        """
        if isinstance(timeframes_institucionais, str):
            timeframes_institucionais = [timeframes_institucionais]

        filtros = [
            PontoInstitucional.par == par,
            PontoInstitucional.exchange == exchange,
            PontoInstitucional.ativo == True,
            PontoInstitucional.rompido == False,
        ]
        # Inclui o filtro para múltiplos timeframes institucionais
        tipo_filtros = [
            PontoInstitucional.tipo.like(f"%{tf}%")
            for tf in timeframes_institucionais
        ]
        from sqlalchemy import or_
        return db.query(PontoInstitucional).filter(
            *filtros,
            or_(*tipo_filtros)
        ).all()
