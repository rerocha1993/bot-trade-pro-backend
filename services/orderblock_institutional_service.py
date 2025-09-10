# services/orderblock_institutional_service.py

import ccxt
import numpy as np
    
from datetime import datetime
from models.orderblocks_institucionais import OrderBlockInstitucional

from sqlalchemy.orm import Session

class OrderBlockInstitutionalService:
    def __init__(self):
        # Instancia conexões CCXT para cada exchange
        self.bybit = ccxt.bybit()
        self.coinbase = ccxt.coinbase()

    def get_order_book(self, exchange, symbol, depth=100):
        """
        Busca o order book (profundidade limitada) da exchange para o par.
        """
        try:
            order_book = exchange.fetch_order_book(symbol, limit=depth)
            return order_book
        except Exception as e:
            print(f"Erro ao buscar order book em {exchange.name}: {e}")
            return None

    def detectar_blocos(self, order_book, lado='bids', limiar_volume=0.03):
        """
        Detecta zonas institucionais de maior concentração para o lado desejado (bids/asks).
        Retorna lista de dicts com preço e volume agregado.
        """
        if not order_book or lado not in order_book:
            return []

        # Extrai níveis (preço, volume) e converte para numpy array
        niveis = np.array(order_book[lado])
        if niveis.size == 0:
            return []

        # Cálculo institucional: identifica clusters de preço com maior volume (top X%)
        volume_total = niveis[:, 1].sum()
        limiar = limiar_volume * volume_total
        blocos = []
        for preco, volume in niveis:
            if volume >= limiar:
                blocos.append({'preco': float(preco), 'volume': float(volume)})
        return blocos

    def consolidar_blocos(self, blocos_bybit, blocos_coinbase, tolerancia=0.05):
        """
        Consolida blocos próximos entre as exchanges em um bloco único (média de preço/volume somado).
        Tolerância: fração do preço (ex: 0.05 = 5%)
        """
        consolidados = []
        usados_coinbase = set()
        for b in blocos_bybit:
            for idx, c in enumerate(blocos_coinbase):
                if idx in usados_coinbase:
                    continue
                if abs(b['preco'] - c['preco']) / b['preco'] <= tolerancia:
                    # Consolida
                    preco_medio = (b['preco'] + c['preco']) / 2
                    volume_total = b['volume'] + c['volume']
                    consolidados.append({
                        'preco': preco_medio,
                        'volume': volume_total,
                        'exchanges': ['bybit', 'coinbase']
                    })
                    usados_coinbase.add(idx)
                    break
            else:
                # Só na Bybit
                consolidados.append({**b, 'exchanges': ['bybit']})
        # Inclui blocos só da Coinbase que não foram usados
        for idx, c in enumerate(blocos_coinbase):
            if idx not in usados_coinbase:
                consolidados.append({**c, 'exchanges': ['coinbase']})
        return consolidados

    def get_orderblocks(self, symbol, depth=100, limiar_volume=0.03, tolerancia=0.05):
        """
        Consulta os blocos institucionais consolidados Bybit+Coinbase para o par.
        Retorna lista de dicts com preço, volume e exchanges de origem.
        """
        book_bybit = self.get_order_book(self.bybit, symbol, depth)
        book_coinbase = self.get_order_book(self.coinbase, symbol, depth)
        # Detecta blocos (bids = compra institucional, asks = venda institucional)
        blocos_bids_bybit = self.detectar_blocos(book_bybit, lado='bids', limiar_volume=limiar_volume)
        blocos_bids_coinbase = self.detectar_blocos(book_coinbase, lado='bids', limiar_volume=limiar_volume)
        blocos_asks_bybit = self.detectar_blocos(book_bybit, lado='asks', limiar_volume=limiar_volume)
        blocos_asks_coinbase = self.detectar_blocos(book_coinbase, lado='asks', limiar_volume=limiar_volume)
        # Consolida blocos (bids e asks)
        blocos_bids = self.consolidar_blocos(blocos_bids_bybit, blocos_bids_coinbase, tolerancia)
        blocos_asks = self.consolidar_blocos(blocos_asks_bybit, blocos_asks_coinbase, tolerancia)
        return {'bids': blocos_bids, 'asks': blocos_asks}

    def salvar_ou_atualizar_orderblock(session, bloco):
        """
        Persiste ou atualiza um OrderBlockInstitucional no banco.
        :param session: sessão SQLAlchemy aberta
        :param bloco: dict (par, exchange_origem, direcao, preco, volume, status, info_extra)
        """
        # Verifica se já existe bloco igual (par, preco, exchange, direcao, ativo)
        existente = session.query(OrderBlockInstitucional).filter_by(
            par=bloco['par'],
            preco=bloco['preco'],
            exchange_origem=bloco['exchange_origem'],
            direcao=bloco['direcao'],
            status='ativo'
        ).first()
        if existente:
            # Atualiza volume e data
            existente.volume = bloco['volume']
            existente.atualizado_em = datetime.utcnow()
            existente.info_extra = bloco.get('info_extra', existente.info_extra)
        else:
            novo = OrderBlockInstitucional(
                par=bloco['par'],
                exchange_origem=bloco['exchange_origem'],
                direcao=bloco['direcao'],
                preco=bloco['preco'],
                volume=bloco['volume'],
                status='ativo',
                criado_em=datetime.utcnow(),
                info_extra=bloco.get('info_extra')
            )
            session.add(novo)
        session.commit()

    def consultar_blocos_ativos(session, par, direcao, exchange=None, status='ativo'):
        """
        Retorna lista de blocos institucionais ativos por par, direção e opcionalmente exchange.
        """
        query = session.query(OrderBlockInstitucional).filter_by(
            par=par,
            direcao=direcao,
            status=status
        )
        if exchange:
            query = query.filter_by(exchange_origem=exchange)
        return query.order_by(OrderBlockInstitucional.preco).all()

    def marcar_bloco_rompido(session, bloco_id):
        """
        Atualiza o status do bloco para 'rompido' e grava a data.
        """
        bloco = session.query(OrderBlockInstitucional).filter_by(id=bloco_id).first()
        if bloco and bloco.status == 'ativo':
            bloco.status = 'rompido'
            bloco.rompido_em = datetime.utcnow()
            bloco.atualizado_em = datetime.utcnow()
            session.commit()

    def persistir_blocos_detectados(self, session: Session, par: str, blocos: list, direcao: str):
        """
        Persiste ou atualiza todos os blocos institucionais detectados (por par, direção, exchanges).
        """
        for bloco in blocos:
            self.salvar_ou_atualizar_orderblock(
                session=session,
                bloco={
                    'par': par,
                    'exchange_origem': ",".join(bloco['exchanges']),
                    'direcao': direcao,
                    'preco': bloco['preco'],
                    'volume': bloco['volume'],
                    'status': 'ativo',
                    'info_extra': str({
                        'volume_total': bloco['volume'],
                        'exchanges': bloco['exchanges']
                    })
                }
            )

    def atualizar_blocos_rompidos(session, par, preco_atual, margem=0.0001):
        """
        Atualiza todos os blocos institucionais ativos do par cujo preço foi rompido.
        Rompimento ocorre quando o preço de mercado atinge ou ultrapassa o preço do bloco, com margem.
        """
        blocos_ativos = session.query(OrderBlockInstitucional).filter_by(
            par=par, status='ativo'
        ).all()
        for bloco in blocos_ativos:
            if bloco.direcao == 'buy' and preco_atual <= bloco.preco + margem:
                bloco.status = 'rompido'
                bloco.rompido_em = datetime.utcnow()
                bloco.atualizado_em = datetime.utcnow()
            elif bloco.direcao == 'sell' and preco_atual >= bloco.preco - margem:
                bloco.status = 'rompido'
                bloco.rompido_em = datetime.utcnow()
                bloco.atualizado_em = datetime.utcnow()
        session.commit()

    def registrar_uso_bloco(session, bloco_id, tipo_uso, bot_id, decisao_id=None):
        """
        Marca no banco o uso de um bloco institucional, com log de contexto.
        """
        bloco = session.query(OrderBlockInstitucional).filter_by(id=bloco_id).first()
        if bloco:
            bloco.usado_como = tipo_uso
            bloco.atualizado_em = datetime.utcnow()
            logs = bloco.info_extra or ""
            novo_log = f"{datetime.utcnow()} | bot: {bot_id} | uso: {tipo_uso} | decisao: {decisao_id}\n"
            bloco.info_extra = (logs or "") + novo_log
            session.commit()



