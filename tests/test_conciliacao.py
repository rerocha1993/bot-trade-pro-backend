"""
Conciliação do scalp (demo) com a corretora, 11/09/2026: a Bybit mostrava −217,61 e o banco −72,50.
A diferença inteira foi explicada, e cada pedaço virou um teste:

    −146,66  dois trades que executaram sem o robô ver (ordem esquecida e ordem sem confirmação) — ver
             test_ordem_pendente.py e test_cancela_entrada_esquecida_*
      +3,03  parcial que o fechamento esquecia de somar
      −1,48  preço de saída: o demo deduzia o stop pelo candle (preço do stop, não o executado) e a consulta ao
             P&L da corretora olhava 3 h no futuro (hora UTC lida como local)
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.bot_executor import BotExecutor, _ms_utc


class _Db:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def add(self, *a):
        pass

    def rollback(self):
        pass


class _Pos:
    def __init__(self, **kw):
        base = dict(id=10, direcao="buy", quantidade=0.195, quantidade_inicial=0.324, preco_entrada=77070.9,
                    pnl_parcial=3.054, taxas=4.994, sl=77070.9, tp=77500.0, status="aberta", preco_saida=None,
                    pnl=None, motivo_saida=None, fechado_em=None, trailing_ativo=False,
                    aberto_em=datetime(2026, 9, 10, 22, 7, 8))
        base.update(kw)
        self.__dict__.update(base)


class _Con:
    def __init__(self, fechados=None, posicao="nao_consultada", pode=True):
        self.fechados, self.posicao, self.pode_enviar_ordens = fechados or [], posicao, pode
        self.desde = None
        self.consultas_posicao = 0

    def obter_pnl_fechado(self, par, desde):
        self.desde = desde
        return self.fechados

    def obter_posicao(self, par):
        self.consultas_posicao += 1
        return None if self.posicao == "nao_consultada" else self.posicao


def _executor(pos, con, modo="demo"):
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = type("B", (), {"id": 4, "nome": "Scalp"})()
    ex.par, ex.modo, ex.db, ex.con, ex.posicao = "BTCUSDT", modo, _Db(), con, pos
    ex.estado = {"pnl_dia": 3.054}          # a parcial já entrou no dia quando saiu
    ex.logs = []
    ex._log = lambda **kw: ex.logs.append(kw)
    ex.alertas = type("A", (), {"ordem": lambda *a, **k: None})()
    return ex


def test_fechamento_local_soma_as_parciais():
    """Posição 10: parcial de +3,05 e o resto no zero a zero. O banco gravou −13,26; a corretora, −10,23."""
    pos = _Pos()
    ex = _executor(pos, _Con(pode=False))
    ex._registrar_saida(77070.9, "Stop no zero a zero", taxa_saida=8.266)
    assert pos.pnl == pytest.approx(3.054 - (4.994 + 8.266), abs=0.01)
    assert pos.pnl == pytest.approx(-10.21, abs=0.02)


def test_resultado_do_dia_nao_conta_a_parcial_duas_vezes():
    pos = _Pos()
    ex = _executor(pos, _Con(pode=False))
    ex._registrar_saida(77070.9, "Stop no zero a zero", taxa_saida=8.266)
    assert ex.estado["pnl_dia"] == pytest.approx(pos.pnl, abs=1e-6), "dia = parcial (já somada) + o resto"


def test_pnl_da_corretora_usa_a_janela_certa_e_o_ultimo_preco():
    """A Bybit devolve do mais novo para o mais velho; o preço de saída é o do último fechamento."""
    pos = _Pos()
    t_abre = _ms_utc(pos.aberto_em)
    fechados = [  # como a Bybit devolve: mais novo primeiro
        {"pnl": -11.29, "preco_saida": 77070.8, "timestamp": t_abre + 421_000},
        {"pnl": 1.07, "preco_saida": 77137.0, "timestamp": t_abre + 99_000},
        {"pnl": -50.0, "preco_saida": 70000.0, "timestamp": t_abre - 30_000},   # operação ANTERIOR
    ]
    con = _Con(fechados)
    ex = _executor(pos, con)
    ex._registrar_saida(77000.0, "SL/TP executado pela exchange", pnl_exchange=True)
    assert pos.pnl == pytest.approx(-10.22, abs=0.01)
    assert pos.preco_saida == 77070.8
    assert con.desde == t_abre - 5_000


def test_hora_do_banco_e_utc_nao_local():
    """O .timestamp() de um datetime sem fuso usa a hora LOCAL: aqui (−3 h) a consulta ia 3 h para o futuro."""
    momento = datetime(2026, 9, 10, 22, 7, 8)
    esperado = int(momento.replace(tzinfo=timezone.utc).timestamp() * 1000)
    assert _ms_utc(momento) == esperado
    assert _ms_utc(momento.replace(tzinfo=timezone(timedelta(hours=-3)))) == esperado + 3 * 3600 * 1000


def test_demo_consulta_a_corretora_em_vez_de_deduzir_o_stop_pelo_candle():
    """Posição 11: o demo gravou 'Stop loss (simulado)' a 76.488,5; a execução real foi 76.475,9."""
    pos = _Pos(id=11, quantidade=0.326, quantidade_inicial=0.326, preco_entrada=76666.7, pnl_parcial=0.0,
               sl=76488.5, aberto_em=datetime(2026, 9, 10, 23, 11, 45))
    t = _ms_utc(pos.aberto_em)
    con = _Con([{"pnl": -80.91, "preco_saida": 76475.9, "timestamp": t + 190_000}], posicao=None)
    ex = _executor(pos, con)
    ex.aplicar_saida_escalonada = lambda preco: None
    ex.aplicar_trailing_stop = lambda preco: None
    ex.gerir_posicao(76480.0, [0, 76600.0, 76610.0, 76470.0, 76480.0, 1.0], candle_novo=False)
    assert con.consultas_posicao == 1
    assert pos.status == "fechada" and "exchange" in pos.motivo_saida and "simulado" not in pos.motivo_saida
    assert pos.preco_saida == 76475.9 and pos.pnl == pytest.approx(-80.91)


def test_simulador_continua_deduzindo_pelo_candle():
    pos = _Pos(pnl_parcial=0.0, quantidade=0.1, sl=77000.0)
    con = _Con(pode=False)
    ex = _executor(pos, con, modo="simulador")
    ex.aplicar_saida_escalonada = lambda preco: None
    ex.aplicar_trailing_stop = lambda preco: None
    ex.gerir_posicao(77050.0, [0, 77100.0, 77120.0, 76990.0, 77050.0, 1.0], candle_novo=False)
    assert con.consultas_posicao == 0 and "simulado" in pos.motivo_saida


# ------------------------------------------------------------------ ordem de entrada esquecida
class _Exchange:
    def __init__(self, ordens):
        self.ordens, self.canceladas = ordens, []

    def fetch_open_orders(self, simbolo):
        return self.ordens

    def cancel_order(self, oid, simbolo):
        self.canceladas.append(oid)


def _conector(ordens):
    from core.conexoes.conexao_bybit import BybitConnector
    con = BybitConnector.__new__(BybitConnector)
    con.exchange = _Exchange(ordens)
    con._exigir_credenciais = lambda *a: None
    con.simbolo = lambda par: "BTC/USDT:USDT"
    return con


def test_cancela_entrada_esquecida_mas_nao_as_saidas_nem_o_stop():
    con = _conector([
        {"id": "entrada", "side": "buy", "amount": 0.318, "price": 78519.3, "reduceOnly": False, "info": {}},
        {"id": "parcial", "side": "sell", "amount": 0.1, "price": 79000.0, "reduceOnly": True, "info": {}},
        {"id": "stop", "side": "sell", "amount": 0.3, "price": None, "reduceOnly": False,
         "triggerPrice": 78000.0, "info": {"stopOrderType": "StopLoss"}},
    ])
    assert con.cancelar_entradas_abertas("BTCUSDT") == 1
    assert con.exchange.canceladas == ["entrada"]


def test_robo_cancela_entradas_esquecidas_na_subida_e_registra():
    ex = _executor(None, _Con())
    ex.con.cancelar_entradas_abertas = lambda par: 1
    ex._cancelar_entradas_esquecidas()
    assert "esquecida" in ex.logs[-1]["motivo"]


def test_simulador_nao_toca_na_corretora_na_subida():
    ex = _executor(None, _Con(pode=False), modo="simulador")
    ex.con.cancelar_entradas_abertas = lambda par: pytest.fail("simulador não manda nada para a corretora")
    ex._cancelar_entradas_esquecidas()
