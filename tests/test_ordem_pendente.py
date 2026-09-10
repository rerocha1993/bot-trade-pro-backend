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


# ------------------------------------------------------------------ falha parcial não pode cegar o ciclo
class _Publico:
    """Conector público que pode estar fora do ar."""
    def __init__(self, erro=None, candles=None):
        self.erro, self.candles, self.chamadas = erro, candles or [], 0

    def obter_ohlcv(self, *a, **kw):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return self.candles


def _executor_fluxo(publico, cache=None, cache_ts=0.0):
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = type("B", (), {"id": 1, "nome": "teste"})()
    ex.par, ex.timeframe = "BTCUSDT", "1m"
    ex._con_publico = publico
    ex._ohlcv_cache, ex._ohlcv_cache_ts = cache, cache_ts
    ex.logs = []
    ex._log = lambda **kw: ex.logs.append(kw)
    return ex


def test_candles_que_nao_renovam_caem_no_cache_em_vez_de_derrubar_o_ciclo():
    """
    Regressão: a exceção subia e derrubava `_ciclo_fluxo` INTEIRO — e com ele a gestão da posição. Numa
    rajada de timeouts (235 em dez minutos, aconteceu) isso é trailing que não sobe e parcial que não sai
    justamente durante a instabilidade. Um candle de meio minuto atrás serve para máxima/mínima.
    """
    import ccxt
    velho = [[0, 1.0, 2.0, 0.5, 1.5, 10.0]]
    ex = _executor_fluxo(_Publico(erro=ccxt.RequestTimeout("estourou")), cache=velho, cache_ts=1.0)
    assert ex._candles_para_gestao() is velho


def test_sem_cache_nenhum_a_falha_de_candles_sobe():
    """Cair no cache é usar dado velho; sem dado nenhum não há o que gerir, e o ciclo tem que falhar alto."""
    import ccxt
    ex = _executor_fluxo(_Publico(erro=ccxt.RequestTimeout("estourou")))
    with pytest.raises(ccxt.RequestTimeout):
        ex._candles_para_gestao()


def test_no_motor_de_fluxo_o_sinal_engolido_tambem_vira_registro():
    """
    Regressão: `_agir_no_fluxo` descartava em silêncio o sinal do mesmo lado de uma ordem pendente — o
    mesmo buraco que deixou o robô parado sete horas sem ninguém ver, só que na metade do código que decide
    por fluxo. Com barra a cada ~30s seriam ~120 sinais por hora sumindo do painel.
    """
    ex = _executor_fluxo(_Publico())
    ex.ordens = _Ordens()
    ex.ordem_pendente = {"ordem_id": "abc", "preco": 79096.1, "direcao": "buy", "candles": 3}
    ex.posicao = None
    ex._agir_no_fluxo({"acao": "buy", "motivo": "absorção"}, 79000.0)
    assert len(ex.logs) == 1
    assert "ignorado" in ex.logs[0]["motivo"] and "79096.1" in ex.logs[0]["motivo"]
    # e não repete a cada barra: um aviso por ordem, senão vira enxurrada
    ex._agir_no_fluxo({"acao": "buy", "motivo": "absorção"}, 79000.0)
    assert len(ex.logs) == 1
