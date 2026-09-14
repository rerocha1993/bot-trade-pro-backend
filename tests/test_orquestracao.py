"""Fase 3: o bot é tático e obedece ao plano do par. Quem decide a direção do grau maior é o orquestrador."""
import pytest

from conftest import gerar_candles
from core.backtest_engine import bot_padrao
from core.conexoes.conexao_bybit import credenciais, nomes_variaveis
from core.strategy_engine import StrategyEngine


def _serie():
    precos = [100 + 0.05 * (i % 4) for i in range(40)]
    for alvo in (110, 104, 115):
        ini = precos[-1]
        precos += [ini + (alvo - ini) * s / 10 for s in range(1, 11)]
    return gerar_candles(precos, volume=50)


def _engine(candles, plano, **kw):
    bot = bot_padrao(confluencia_tipo="turbo", usar_tpo=True, usar_vwap=True, usar_volume_profile=True,
                     usar_orderblock=False, **kw)
    return StrategyEngine(candles, bot, db=None, servicos={
        "fetch_ohlcv": lambda tf, n: candles[-n:], "ohlcv_composto": candles, "plano": plano,
    })


def _plano(**kw):
    base = {"modo": "acumular", "estado": "fundo_terminal", "direcao_grau_maior": "buy", "risco_permitido": 1.0,
            "teto_hedge": 0.0, "pode_comprar": True, "pode_vender": False, "motivo": "fundo de ciclo"}
    base.update(kw)
    return base


def test_plano_bloqueia_venda_em_fundo_de_ciclo():
    """A regra do usuário: ninguém vende num fundo terminal, nem o perfil turbo."""
    c = _serie()
    eng = _engine(c, _plano(pode_vender=False))
    d = eng.decidir()
    assert d["acao"] != "sell"
    if d["acao"] == "hold" and "venda bloqueada" in (d.get("motivo") or ""):
        assert "fundo_terminal" in d["motivo"]


def test_plano_bloqueia_compra_em_correcao():
    c = _serie()
    eng = _engine(c, _plano(modo="hedge", estado="correcao_inicial", direcao_grau_maior="sell",
                            pode_comprar=False, pode_vender=True, motivo="correção de ciclo"))
    d = eng.decidir()
    assert d["acao"] != "buy"


def test_plano_entra_na_decisao_para_auditoria():
    c = _serie()
    d = _engine(c, _plano()).decidir()
    assert d.get("plano") is not None
    assert d["plano"]["modo"] == "acumular"
    assert d["plano"]["estado"] == "fundo_terminal"


def test_risco_do_plano_limita_o_tamanho_sem_multiplicar_duas_vezes():
    """O plano e o alinhamento vêm da mesma leitura de superciclo: aplica-se o menor, nunca o produto."""
    c = _serie()
    cheio = _engine(c, _plano(risco_permitido=1.0)).decidir()
    meio = _engine(c, _plano(risco_permitido=0.5)).decidir()
    if cheio["acao"] in ("buy", "sell") and meio["acao"] in ("buy", "sell"):
        assert meio["tamanho_fator"] == pytest.approx(cheio["tamanho_fator"] * 0.5, rel=1e-6)


def test_sem_plano_o_bot_continua_operando():
    """Se o orquestrador estiver fora do ar, o bot não pode travar: cai na análise própria."""
    c = _serie()
    eng = StrategyEngine(c, bot_padrao(confluencia_tipo="turbo", usar_vwap=True), db=None,
                         servicos={"fetch_ohlcv": lambda tf, n: c[-n:], "ohlcv_composto": c, "plano": None})
    d = eng.decidir()
    assert d["acao"] in ("buy", "sell", "hold")
    assert d.get("plano") is None


def test_plano_com_erro_nao_bloqueia():
    c = _serie()
    d = _engine(c, {"erro": "sem candles", "modo": "aguardar", "pode_comprar": False, "pode_vender": False}).decidir()
    assert "bloqueada" not in (d.get("motivo") or "")


# ------------------------------------------------------------------ subcontas
def test_nome_das_variaveis_da_subconta():
    assert nomes_variaveis("principal", "testnet") == ("BYBIT_API_KEY_TESTNET", "BYBIT_SECRET_KEY_TESTNET")
    assert nomes_variaveis(None, "real") == ("BYBIT_API_KEY_REAL", "BYBIT_SECRET_KEY_REAL")
    assert nomes_variaveis("scalp-fluxo", "testnet") == (
        "BYBIT_SUB_SCALP_FLUXO_API_KEY_TESTNET", "BYBIT_SUB_SCALP_FLUXO_SECRET_KEY_TESTNET")
    assert nomes_variaveis("Day TPO", "real") == (
        "BYBIT_SUB_DAY_TPO_API_KEY_REAL", "BYBIT_SUB_DAY_TPO_SECRET_KEY_REAL")


def test_outra_conta_principal_entra_como_grupo():
    assert nomes_variaveis("tradeiros:principal", "demo") == ("BYBIT_API_KEY_DEMO_TRADEIROS", "BYBIT_SECRET_KEY_DEMO_TRADEIROS")
    assert nomes_variaveis("tradeiros:scalp", "demo") == ("BYBIT_SUB_SCALP_API_KEY_DEMO_TRADEIROS",
                                                         "BYBIT_SUB_SCALP_SECRET_KEY_DEMO_TRADEIROS")
    assert nomes_variaveis("scalp", "demo") == ("BYBIT_SUB_SCALP_API_KEY_DEMO", "BYBIT_SUB_SCALP_SECRET_KEY_DEMO")


def test_subconta_sem_chave_falha_em_vez_de_usar_a_principal(monkeypatch):
    """Operar na conta errada é pior que não operar: o conector tem que recusar."""
    from core.conexoes.conexao_bybit import BybitConnector
    monkeypatch.setenv("BYBIT_API_KEY_TESTNET", "chave_principal")
    monkeypatch.setenv("BYBIT_SECRET_KEY_TESTNET", "segredo_principal")
    monkeypatch.delenv("BYBIT_SUB_SCALP_API_KEY_TESTNET", raising=False)
    with pytest.raises(ValueError, match="sem credenciais"):
        BybitConnector("testnet", "linear", subconta="scalp")


def test_subconta_usa_a_propria_chave(monkeypatch):
    monkeypatch.setenv("BYBIT_SUB_SCALP_API_KEY_TESTNET", "chave_do_scalp")
    monkeypatch.setenv("BYBIT_SUB_SCALP_SECRET_KEY_TESTNET", "segredo_do_scalp")
    k, s = credenciais("scalp", "testnet")
    assert (k, s) == ("chave_do_scalp", "segredo_do_scalp")


def test_simulador_ignora_subconta(monkeypatch):
    from core.conexoes.conexao_bybit import BybitConnector
    con = BybitConnector("simulador", "linear", subconta="scalp")
    assert con.subconta == "principal"
    assert con.tem_credenciais is False


# ------------------------------------------------------------------ modo demo (conta oficial)
def test_modo_demo_usa_a_conta_oficial_e_nao_o_testnet(monkeypatch):
    """
    Demo Trading vive em bybit.com (api-demo), não em testnet.bybit.com. É o caminho para quem o testnet
    bloqueia por jurisdição: o testnet é um cadastro separado, sem o KYC da conta oficial.
    """
    from core.conexoes.conexao_bybit import BybitConnector
    monkeypatch.setenv("BYBIT_API_KEY_DEMO", "chave_demo")
    monkeypatch.setenv("BYBIT_SECRET_KEY_DEMO", "segredo_demo")
    con = BybitConnector("demo", "linear")
    assert con.demo is True
    assert con.sandbox is False, "demo NÃO é sandbox: sandbox aponta para o testnet"
    assert con.pode_enviar_ordens is True
    url = con.exchange.urls["api"]
    assert "api-demo" in str(url), f"demo deveria usar api-demo, veio {url}"


def test_demo_tem_as_proprias_variaveis():
    assert nomes_variaveis("principal", "demo") == ("BYBIT_API_KEY_DEMO", "BYBIT_SECRET_KEY_DEMO")
    assert nomes_variaveis("scalp", "demo") == ("BYBIT_SUB_SCALP_API_KEY_DEMO", "BYBIT_SUB_SCALP_SECRET_KEY_DEMO")


def test_demo_nao_exige_backtest_porque_nao_arrisca_dinheiro():
    from types import SimpleNamespace
    from services.backtest_service import BacktestService
    for modo in ("simulador", "demo"):
        ok, motivo = BacktestService.pode_ativar(None, SimpleNamespace(modo_execucao=modo, id=1))
        assert ok is True, f"{modo} não deveria exigir backtest"
        assert modo in motivo


def test_pedir_fundos_demo_recusa_fora_do_modo_demo(monkeypatch):
    from core.conexoes.conexao_bybit import BybitConnector
    monkeypatch.setenv("BYBIT_API_KEY_TESTNET", "k")
    monkeypatch.setenv("BYBIT_SECRET_KEY_TESTNET", "s")
    con = BybitConnector("testnet", "linear")
    with pytest.raises(ValueError, match="só funciona no modo demo"):
        con.pedir_fundos_demo()


def test_info_chave_normaliza_a_resposta_da_bybit(monkeypatch):
    """
    info_chave() é o que prova a separação por subconta: dois robôs com o mesmo UID disputam a mesma posição.
    Aqui checamos a normalização, sem rede.
    """
    from core.conexoes.conexao_bybit import BybitConnector
    monkeypatch.setenv("BYBIT_API_KEY_DEMO", "k")
    monkeypatch.setenv("BYBIT_SECRET_KEY_DEMO", "s")
    con = BybitConnector("demo", "linear")
    con.exchange.privateGetV5UserQueryApi = lambda *a, **k: {"result": {
        "userID": 987654, "parentUid": "123456", "note": "scalp", "readOnly": 0,
        "permissions": {"ContractTrade": ["Order", "Position"], "Spot": [], "Wallet": []},
        "ips": ["*"], "expiredAt": "2027-01-01T00:00:00Z",
    }}
    info = con.info_chave()
    assert info["uid"] == "987654"
    assert info["tipo"] == "subconta"
    assert info["uid_pai"] == "123456"
    assert "ContractTrade" in info["permissoes"]
    assert "Spot" not in info["permissoes"], "permissões vazias não deveriam aparecer"
    assert info["somente_leitura"] is False


def test_info_chave_reconhece_conta_principal(monkeypatch):
    from core.conexoes.conexao_bybit import BybitConnector
    monkeypatch.setenv("BYBIT_API_KEY_DEMO", "k")
    monkeypatch.setenv("BYBIT_SECRET_KEY_DEMO", "s")
    con = BybitConnector("demo", "linear")
    con.exchange.privateGetV5UserQueryApi = lambda *a, **k: {"result": {"userID": 111, "parentUid": "0"}}
    info = con.info_chave()
    assert info["tipo"] == "principal"
    assert info["uid_pai"] is None
