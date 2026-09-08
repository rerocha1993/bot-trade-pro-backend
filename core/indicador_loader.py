# core/indicador_loader.py
"""Carrega os indicadores configurados em BotIndicadores como funções de análise prontas para uso."""
from models.bot_indicador import BotIndicador

NOMES = {"fibonacci": "Fibonacci", "elliott": "Elliott", "tpo": "TPO", "order_flow": "OrderFlow",
         "vwap": "VWAP", "volume_profile": "VolumeProfile", "order_block": "OrderBlock"}


class IndicadorLoader:
    def __init__(self, db, bot_id):
        self.db = db
        self.bot_id = bot_id

    def carregar(self):
        """Devolve lista de (nome_canonico, parametros) dos indicadores cadastrados para o bot."""
        indicadores = self.db.query(BotIndicador).filter_by(bot_id=self.bot_id).all()
        saida = []
        for ind in indicadores:
            nome = NOMES.get((ind.nome or "").lower())
            if not nome:
                print(f"[AVISO] Indicador desconhecido: {ind.nome}")
                continue
            saida.append((nome, ind.parametros or {}))
        return saida
