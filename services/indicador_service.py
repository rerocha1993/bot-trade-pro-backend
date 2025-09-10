from sqlalchemy.orm import Session
from models.indicador_disponivel import IndicadorDisponivel
import sys, os, random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class IndicadorService:
    def __init__(self, db: Session):
        self.db = db

    def seed_indicadores(self):
        existentes = self.db.query(IndicadorDisponivel).count()
        if existentes == 0:
            lista = [
                {"nome": "fibonacci", "descricao": "Níveis de retração de Fibonacci", "parametros_padrao": {"nivel": 61.8}},
                {"nome": "elliott", "descricao": "Ondas de Elliott com picos/vales", "parametros_padrao": {}},
                {"nome": "tpo", "descricao": "TPO - Perfil de volume por preço", "parametros_padrao": {"intervalo": 50}},
                {"nome": "order_flow", "descricao": "Análise de fluxo de ordens (desequilíbrio bid/ask)", "parametros_padrao": {"profundidade": 10}},
                {"nome": "vwap", "descricao": "VWAP - Preço médio ponderado por volume", "parametros_padrao": {}}
            ]
            for i in lista:
                self.db.add(IndicadorDisponivel(**i))
            self.db.commit()

    def listar(self):
        return self.db.query(IndicadorDisponivel).all()

    def criar(self, data: dict):
        novo = IndicadorDisponivel(**data)
        self.db.add(novo)
        self.db.commit()
        return novo

    def atualizar(self, id: int, data: dict):
        indicador = self.db.query(IndicadorDisponivel).filter_by(id=id).first()
        if not indicador:
            return None
        for campo, valor in data.items():
            setattr(indicador, campo, valor)
        self.db.commit()
        return indicador

    def deletar(self, id: int):
        indicador = self.db.query(IndicadorDisponivel).filter_by(id=id).first()
        if indicador:
            self.db.delete(indicador)
            self.db.commit()
        return indicador
