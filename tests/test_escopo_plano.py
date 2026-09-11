"""
Alcance do plano do par por robô.

O plano é montado a partir do superciclo (semanas, meses) e travava os quatro robôs do mesmo jeito. Para o
swing isso é certo; para o scalp, que opera 1m, era obedecer uma leitura de várias semanas. Medido ao vivo: o
grau do próprio scalp enxergava uma queda de 2,7% e ele estava proibido de vender — só podia comprar recuo, e
fechou o dia em -70,79.

Agora: o swing obedece o plano inteiro; day trade e scalp obedecem só os vetos dos extremos do ciclo e tiram o
lado dos próprios graus. Os extremos continuam valendo para todos: ninguém vende fundo de ciclo, ninguém
compra correção de ciclo recém-iniciada.
"""
from conftest import gerar_candles
from core.backtest_engine import bot_padrao
from core.orquestrador.plano import (
    ALCANCE_POR_ESTILO, POR_ESTADO, VETO_COMPRA_UNIVERSAL, VETO_VENDA_UNIVERSAL, escopo_do_plano,
)
from core.strategy_engine import StrategyEngine


def _plano(estado, pode_comprar, pode_vender, **kw):
    base = {"modo": POR_ESTADO.get(estado, ("aguardar",))[0], "estado": estado, "pode_comprar": pode_comprar,
            "pode_vender": pode_vender, "risco_permitido": 0.5, "motivo": f"estado {estado}"}
    base.update(kw)
    return base


# o caso medido ao vivo: ciclo maduro com contagens viradas bear, "aguardando a barreira"
MADURO = _plano("impulso_maduro", pode_comprar=False, pode_vender=False)


def test_swing_obedece_o_plano_inteiro():
    e = escopo_do_plano(MADURO, "swing")
    assert e == {"pode_comprar": False, "pode_vender": False, "escopo": "plano inteiro"}


def test_scalp_e_day_trade_tiram_o_lado_dos_proprios_graus():
    for estilo in ("scalping", "daytrade"):
        e = escopo_do_plano(MADURO, estilo)
        assert e["pode_comprar"] is True and e["pode_vender"] is True, f"{estilo} ainda preso ao ciclo"
        assert e["escopo"] == "só vetos do ciclo"


def test_ninguem_vende_fundo_de_ciclo_nem_o_scalp():
    """A regra que o usuário fixou continua de pé para todos os graus."""
    for estado in VETO_VENDA_UNIVERSAL:
        plano = _plano(estado, pode_comprar=True, pode_vender=False)
        for estilo in ALCANCE_POR_ESTILO:
            assert escopo_do_plano(plano, estilo)["pode_vender"] is False, f"{estilo} vendeu em {estado}"


def test_ninguem_compra_correcao_de_ciclo_recem_iniciada():
    for estado in VETO_COMPRA_UNIVERSAL:
        plano = _plano(estado, pode_comprar=False, pode_vender=True)
        for estilo in ALCANCE_POR_ESTILO:
            assert escopo_do_plano(plano, estilo)["pode_comprar"] is False, f"{estilo} comprou em {estado}"


def test_sem_plano_ou_com_plano_em_erro_ninguem_trava():
    for plano in (None, {}, {"erro": "sem candles", "pode_comprar": False, "pode_vender": False}):
        for estilo in ALCANCE_POR_ESTILO:
            e = escopo_do_plano(plano, estilo)
            assert e["pode_comprar"] and e["pode_vender"]


def test_estilo_escrito_de_outro_jeito_cai_no_lugar_certo():
    assert escopo_do_plano(MADURO, "Scalp")["escopo"] == "só vetos do ciclo"
    assert escopo_do_plano(MADURO, "SWING")["escopo"] == "plano inteiro"


# ------------------------------------------------------------------ na decisão de verdade
def _engine(estilo, plano):
    precos = [100 + 0.05 * (i % 4) for i in range(40)]
    for alvo in (110, 104, 115):
        ini = precos[-1]
        precos += [ini + (alvo - ini) * s / 10 for s in range(1, 11)]
    c = gerar_candles(precos, volume=50)
    bot = bot_padrao(estilo_trade=estilo, confluencia_tipo="turbo", usar_vwap=True)
    return StrategyEngine(c, bot, db=None, servicos={
        "fetch_ohlcv": lambda tf, n: c[-n:], "ohlcv_composto": c, "plano": plano})


def test_a_decisao_registra_o_alcance_do_plano():
    """Para dar para auditar no painel POR QUE um robô obedeceu ou não obedeceu o plano."""
    assert _engine("scalping", MADURO).decidir()["plano"]["escopo"] == "só vetos do ciclo"
    assert _engine("swing", MADURO).decidir()["plano"]["escopo"] == "plano inteiro"


def test_scalp_nao_e_mais_barrado_pelo_ciclo_maduro():
    d = _engine("scalping", MADURO).decidir()
    assert "bloqueada" not in (d.get("motivo") or ""), d.get("motivo")
