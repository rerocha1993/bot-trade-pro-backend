"""
As duas costuras do motor de fluxo: o cursor de negócios e a validação da configuração.

O cursor é o que impede o erro mais caro possível aqui — reler o buffer do websocket a cada ciclo e contar
o mesmo volume várias vezes na mesma barra, o que inflaria o delta e faria o robô entrar em cima de uma
agressão que nunca existiu.
"""
import pytest

from core.datasource_ws_universal import DataSourceWebsocketUniversal
from services.bot_service import BotService


def fonte(buffer=1000):
    return DataSourceWebsocketUniversal(exchange="bybit", symbol_spot="BTC/USDT", trades_buffer=buffer)


def negocio(i):
    return {"price": 100.0 + i, "qty": 0.1, "side": "buy", "timestamp": i}


# ------------------------------------------------------------------ cursor
def test_cursor_entrega_cada_negocio_uma_vez_so():
    ws = fonte()
    for i in range(5):
        ws._registrar_trade(negocio(i))
    novos, seq, perdidos = ws.trades_desde(0)
    assert len(novos) == 5 and perdidos == 0
    # sem negócio novo, a segunda leitura vem vazia: é isto que impede contar o mesmo volume duas vezes
    assert ws.trades_desde(seq)[0] == []
    ws._registrar_trade(negocio(5))
    novos2, seq2, _ = ws.trades_desde(seq)
    assert len(novos2) == 1 and seq2 == seq + 1


def test_cursor_avisa_quando_o_buffer_girou_antes_de_alguem_consumir():
    """Buraco no fluxo não pode passar calado: a barra em formação fica incompleta e o delta dela mente."""
    ws = fonte(buffer=3)
    for i in range(10):
        ws._registrar_trade(negocio(i))
    novos, _, perdidos = ws.trades_desde(2)
    assert len(novos) == 3        # o buffer só guarda os de sequência 8, 9 e 10
    assert perdidos == 5          # os de sequência 3 a 7 caíram antes de alguém consumir


def test_negocios_carregam_o_numero_de_serie():
    ws = fonte()
    ws._registrar_trade(negocio(0))
    assert ws.get_trades()[0]["seq"] == 1


# ------------------------------------------------------------------ configuração
def test_motor_de_fluxo_so_no_scalp():
    with pytest.raises(ValueError, match="scalp"):
        BotService._normalizar({"usar_motor_fluxo": True, "estilo_trade": "swing"})


def test_motor_de_fluxo_nao_se_aplica_a_grade_inversa():
    with pytest.raises(ValueError, match="grade inversa"):
        BotService._normalizar({"usar_motor_fluxo": True, "estilo_trade": "scalping",
                                "estrategia": "inverse_range"})


def test_ligar_o_motor_liga_o_websocket_junto():
    """Sem stream de negócios não existe barra de fluxo: ligar um sem o outro só daria robô parado."""
    d = BotService._normalizar({"usar_motor_fluxo": True, "estilo_trade": "scalping"})
    assert d["usar_websocket"] is True


def test_regua_da_barra_e_validada_antes_de_virar_gatilho_de_ordem():
    with pytest.raises(ValueError, match="Tipo de barra"):
        BotService._normalizar({"barra_tipo": "minuto"})
    with pytest.raises(ValueError, match="negativo"):
        BotService._normalizar({"barra_tamanho": -1})
    with pytest.raises(ValueError, match="ritmo alvo"):
        BotService._normalizar({"barra_segundos_alvo": 0})
    assert BotService._normalizar({"barra_tipo": " Volume "})["barra_tipo"] == "volume"


# ------------------------------------------------------------------ o que vai para o banco
def test_o_que_o_motor_grava_cabe_nas_colunas():
    """
    Um texto que não cabe na coluna não é só um registro perdido: o INSERT derruba a transação inteira, e
    com ela o estado do robô que estava sendo gravado. Foi assim que uma realização parcial saiu três vezes
    na corretora. O motor de fluxo escreve textos novos ('contexto buy', 'fluxo:absorcao'), então eles
    precisam caber ANTES de irem para o banco pela primeira vez.
    """
    from models.decisao_bot import DecisaoBot

    largura = {c.name: getattr(c.type, "length", None) for c in DecisaoBot.__table__.columns}
    escritos = {"acao": "hold", "cenario": "contexto neutro", "tendencia_macro": "neutro",
                "votos": "fluxo:continuacao", "timeframe": "1m"}
    for campo, valor in escritos.items():
        assert largura[campo] is None or len(valor) <= largura[campo], \
            f"{campo}={valor!r} não cabe em {largura[campo]} caracteres"
