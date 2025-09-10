from models.bot_indicador import BotIndicador

class IndicadorLoader:
    def __init__(self, db, bot_id):
        self.db = db
        self.bot_id = bot_id

    def carregar(self):
        indicadores = self.db.query(BotIndicador).filter_by(bot_id=self.bot_id).all()
        instancias = []

        for ind in indicadores:
            nome = ind.nome
            params = ind.parametros or {}

            if nome == 'fibonacci':
                from core.fibonacci import Fibonacci
                instancias.append(Fibonacci(**params))
            elif nome == 'elliott':
                from core.elliott import ElliottDetector
                instancias.append(ElliottDetector(**params))
            elif nome == 'tpo':
                from core.tpo import TPOCalculator
                instancias.append(TPOCalculator(**params))
            elif nome == 'order_flow':
                from core.order_flow import OrderFlowAnalyzer
                instancias.append(OrderFlowAnalyzer(**params))
            elif nome == 'vwap':
                from core.vwap import VWAPCalculator
                instancias.append(VWAPCalculator(**params))
            else:
                print(f"[AVISO] Indicador desconhecido: {nome}")

        return instancias
