# services/bot_service.py
from sqlalchemy.orm import Session

from core.alavancagem import normalizar as normalizar_alavancagem
from core.barras_fluxo import TIPOS as TIPOS_BARRA
from core.perfil_saida import perfil as perfil_saida
from core.saida_escalonada import analisar_plano, escrever_plano
from models.bot import Bot
from models.bot_indicador import BotIndicador

CAMPOS_BOT = {c.name for c in Bot.__table__.columns} - {"id"}


def _numero(d: dict, campo: str, rotulo: str) -> float:
    """Le um numero recusando o valor com uma mensagem util, em vez do ValueError cru do float()."""
    try:
        return float(d[campo])
    except (TypeError, ValueError):
        raise ValueError(f"{rotulo}: {d[campo]!r} nao e um numero.") from None
OBRIGATORIOS = ("nome", "ativo", "timeframe", "quantidade")


class BotService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _normalizar(data: dict) -> dict:
        d = {k: v for k, v in data.items() if k in CAMPOS_BOT}
        if d.get("ativo"):
            d["ativo"] = str(d["ativo"]).replace("/", "").upper()
        if d.get("exchange") and "testnet" in str(d["exchange"]).lower():
            d["exchange"] = "bybit"
            d.setdefault("modo_execucao", "testnet")
        if d.get("confluencia_tipo"):
            d["confluencia_tipo"] = str(d["confluencia_tipo"]).lower()
        if d.get("estilo_trade"):
            e = str(d["estilo_trade"]).lower()
            d["estilo_trade"] = "scalping" if "scalp" in e else "swing" if "swing" in e else "daytrade"
        if d.get("modo_execucao"):
            d["modo_execucao"] = str(d["modo_execucao"]).lower()
        if "alavancagem" in d:
            d["alavancagem"] = normalizar_alavancagem(d["alavancagem"])

        # o plano de saída escalonada é recusado quando não dá para entender, em vez de virar o padrão calado
        if d.get("saida_escalonada"):
            plano = analisar_plano(d["saida_escalonada"])
            if plano is None:
                raise ValueError(
                    f"Plano de saída escalonada inválido: {d['saida_escalonada']!r}. "
                    "Use 'avanço/fração' em porcentagem, ex.: '50/30, 75/30, 90/25'. "
                    "As frações precisam somar menos de 100%, para sobrar posição até o alvo.")
            d["saida_escalonada"] = escrever_plano(plano)
        elif "saida_escalonada" in d:
            d["saida_escalonada"] = perfil_saida(d.get("estilo_trade", "")).saida_escalonada

        # trailing que liga depois de andar MENOS do que a sua própria distância trava prejuízo em vez de lucro
        ativ, dist = d.get("ativador_trailing"), d.get("distancia_trailing")
        if ativ is not None and dist is not None and float(ativ) <= float(dist):
            raise ValueError(
                f"Trailing inválido: ativa com {float(ativ):.2%} de avanço mas cola a {float(dist):.2%} do preço, "
                "então o stop nasceria abaixo da entrada. O ativador tem que ser maior que a distância.")
        # motor de fluxo (scalp): a regua da barra precisa fazer sentido antes de virar gatilho de ordem
        if d.get("barra_tipo"):
            d["barra_tipo"] = str(d["barra_tipo"]).strip().lower()
            if d["barra_tipo"] not in TIPOS_BARRA:
                raise ValueError(f"Tipo de barra invalido: {d['barra_tipo']!r}. Use: {', '.join(TIPOS_BARRA)}.")
        # numero que nao da para ler tem que ser recusado COM explicacao: um campo esvaziado no painel
        # virava um ValueError cru do float(), sem dizer ao usuario o que estava errado
        if d.get("barra_tamanho") is not None and _numero(d, "barra_tamanho", "Tamanho da barra") < 0:
            raise ValueError("Tamanho da barra nao pode ser negativo (use 0 para calibrar pelo fluxo).")
        if d.get("barra_segundos_alvo") is not None and _numero(d, "barra_segundos_alvo", "Ritmo alvo da barra") <= 0:
            raise ValueError("O ritmo alvo da barra tem que ser maior que zero.")
        if d.get("usar_motor_fluxo"):
            estilo = d.get("estilo_trade")
            if estilo is not None and "scalp" not in str(estilo).lower():
                raise ValueError(
                    "O motor de fluxo e do scalp. Nos graus maiores o candle de tempo e uma regua honesta, "
                    "e trocar por barra de volume so tiraria contexto da leitura.")
            if d.get("estrategia") == "inverse_range":
                raise ValueError("A grade inversa tem motor proprio: o motor de fluxo nao se aplica a ela.")
            # sem stream de negocios nao existe barra de fluxo; ligar um sem o outro so daria robo parado
            d["usar_websocket"] = True
        return d

    def create_bot(self, data: dict) -> Bot:
        faltando = [c for c in OBRIGATORIOS if data.get(c) in (None, "")]
        if faltando:
            raise ValueError(f"Campos obrigatórios ausentes: {faltando}")
        bot = Bot(**self._normalizar(data))
        self.db.add(bot)
        self.db.flush()
        for indicador in data.get("indicadores", []) or []:
            self.db.add(BotIndicador(bot_id=bot.id, nome=indicador["nome"], parametros=indicador.get("parametros", {})))
        self.db.commit()
        self.db.refresh(bot)
        return bot

    def get_bots(self):
        return self.db.query(Bot).order_by(Bot.id).all()

    def get_bot(self, bot_id: int):
        return self.db.query(Bot).filter(Bot.id == bot_id).first()

    def update_bot(self, bot_id: int, data: dict):
        bot = self.get_bot(bot_id)
        if not bot:
            return None
        for campo, valor in self._normalizar(data).items():
            setattr(bot, campo, valor)
        self.db.commit()
        self.db.refresh(bot)
        return bot

    def delete_bot(self, bot_id: int) -> bool:
        bot = self.get_bot(bot_id)
        if not bot:
            return False
        self.db.query(BotIndicador).filter(BotIndicador.bot_id == bot_id).delete()
        self.db.delete(bot)
        self.db.commit()
        return True

    def get_indicadores(self, bot_id: int):
        return self.db.query(BotIndicador).filter(BotIndicador.bot_id == bot_id).all()
