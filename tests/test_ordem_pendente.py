"""
Ordem limitada pendente: ela TEM que envelhecer e morrer, mesmo quando não dá para conferir na corretora.

Aconteceu de verdade, e caro em oportunidade: a ccxt passou a recusar `fetch_order` na Bybit sem o
`acknowledged`, então a consulta da situação estourava a cada ciclo. O `except` saía da função ANTES da
checagem de validade, e a ordem ficava pendente para sempre. Como um sinal novo é descartado enquanto há
ordem pendente, o robô parou de operar CALADO: uma ordem de 14:06 seguia "pendente" sete horas depois, com
311 candles de espera num limite de 2, e 28 sinais de compra foram jogados fora sem deixar registro no
painel. Na corretora não havia ordem nenhuma.
"""
import pytest

from core.bot_executor import BotExecutor
from core.conexoes.conexao_bybit import _erro_de_rede


class _Ordens:
    """OrderExecutor de mentira: a consulta de situação pode estourar, como estourava de verdade."""
    def __init__(self, erro=None, status="aberta"):
        self.simulado = False
        self.erro, self.status = erro, status
        self.canceladas = []

    def situacao_ordem(self, par, ordem_id):
        if self.erro:
            raise self.erro
        return {"status": self.status, "preco_exec": 100.0, "quantidade": 1.0}

    def cancelar_ordem(self, par, ordem_id):
        self.canceladas.append(ordem_id)
        return True


def _executor(ordens, candles_esperados=2, candles_ja=0):
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = type("B", (), {"id": 1, "nome": "teste", "limite_candles_espera": candles_esperados})()
    ex.par = "BTCUSDT"
    ex.ordens = ordens
    ex.logs = []
    ex._log = lambda **kw: ex.logs.append(kw)
    ex.ordem_pendente = {"ordem_id": "abc", "preco": 79096.1, "direcao": "buy", "quantidade": 0.3,
                         "sl": 78858.0, "tp": 80142.0, "decisao": {"acao": "buy"}, "candles": candles_ja}
    return ex


def test_ordem_que_nao_da_para_conferir_ainda_assim_expira():
    """O caso que travou o robô por sete horas."""
    ordens = _Ordens(erro=RuntimeError("bybit fetchOrder() can only access an order in last 500 orders"))
    ex = _executor(ordens, candles_esperados=2, candles_ja=1)
    ex.gerir_ordem_pendente(79000.0, [0, 0, 79100.0, 78900.0, 79000.0, 1.0], candle_novo=True)
    assert ex.ordem_pendente is None, "a ordem ficou pendente para sempre de novo"
    assert ordens.canceladas == ["abc"]
    assert "expirou" in ex.logs[-1]["motivo"]
    assert "sem conseguir confirmar" in ex.logs[-1]["motivo"]


def test_ordem_que_nao_da_para_conferir_e_ainda_e_nova_continua_esperando():
    """Envelhecer não é morrer na hora: dentro do prazo, a ordem segue de pé."""
    ordens = _Ordens(erro=RuntimeError("timeout"))
    ex = _executor(ordens, candles_esperados=3, candles_ja=0)
    ex.gerir_ordem_pendente(79000.0, [0, 0, 79100.0, 78900.0, 79000.0, 1.0], candle_novo=True)
    assert ex.ordem_pendente is not None
    assert ex.ordem_pendente["candles"] == 1
    assert ordens.canceladas == []


def test_ordem_executada_vira_posicao():
    ordens = _Ordens(status="executada")
    ex = _executor(ordens)
    registrou = {}
    ex._registrar_entrada = lambda decisao, exec_, preco, sl, tp: registrou.update(preco=preco, qty=exec_["quantidade"])
    ex.gerir_ordem_pendente(79000.0, [0, 0, 79100.0, 78900.0, 79000.0, 1.0], candle_novo=False)
    assert ex.ordem_pendente is None
    assert registrou == {"preco": 100.0, "qty": 1.0}


def test_ordem_cancelada_na_corretora_libera_o_robo():
    ordens = _Ordens(status="cancelada")
    ex = _executor(ordens)
    ex.gerir_ordem_pendente(79000.0, [0, 0, 79100.0, 78900.0, 79000.0, 1.0], candle_novo=False)
    assert ex.ordem_pendente is None
    assert "cancelada na exchange" in ex.logs[-1]["motivo"]


# ------------------------------------------------------------------ repetição em falha de rede
def test_so_repete_o_que_vale_a_pena_repetir():
    import ccxt
    assert _erro_de_rede(ccxt.RequestTimeout("estourou"))
    assert _erro_de_rede(RuntimeError('{"retCode":10006,"retMsg":"Too many visits"}'))
    assert not _erro_de_rede(ccxt.InsufficientFunds("sem saldo"))
    assert not _erro_de_rede(ValueError("parametro invalido"))


def test_leitura_publica_tenta_de_novo_antes_de_desistir(monkeypatch):
    """
    Timeout virava ciclo perdido, e ciclo perdido é a gestão da posição que não roda: stop não sobe,
    parcial não sai. Numa rajada real foram 235 timeouts em dez minutos, sem uma única repetição.
    """
    import ccxt

    from core.conexoes.conexao_bybit import BybitConnector

    con = BybitConnector.__new__(BybitConnector)
    monkeypatch.setattr("core.conexoes.conexao_bybit.time.sleep", lambda s: None)
    tentativas = {"n": 0}

    def instavel():
        tentativas["n"] += 1
        if tentativas["n"] < 3:
            raise ccxt.RequestTimeout("estourou")
        return "ok"

    assert con._com_repeticao("teste", instavel) == "ok"
    assert tentativas["n"] == 3


def test_erro_que_nao_e_de_rede_estoura_na_primeira(monkeypatch):
    import ccxt

    from core.conexoes.conexao_bybit import BybitConnector

    con = BybitConnector.__new__(BybitConnector)
    monkeypatch.setattr("core.conexoes.conexao_bybit.time.sleep", lambda s: None)
    tentativas = {"n": 0}

    def sem_saldo():
        tentativas["n"] += 1
        raise ccxt.InsufficientFunds("sem saldo")

    with pytest.raises(ccxt.InsufficientFunds):
        con._com_repeticao("teste", sem_saldo)
    assert tentativas["n"] == 1, "repetiu um erro que nunca vai passar"
