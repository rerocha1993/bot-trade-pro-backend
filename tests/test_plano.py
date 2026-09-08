"""Camada 2: o plano de mercado do par. O superciclo é o veto de todos os bots."""
from conftest import gerar_candles
from core.orquestrador.plano import MODOS, POR_ESTADO, montar_plano


def _serie(n=320, base=100.0, passo=0.35):
    return gerar_candles([base + i * passo for i in range(n)], dur_ms=86_400_000)


def _trader(estado, prob_bear=0.2, prob_bull=0.8):
    return {
        "direcao": "hold", "prob_bull": prob_bull, "prob_bear": prob_bear,
        "superciclo": {"estado": estado, "leitura": f"estado {estado}"},
        "subordinado": {"direcao": "hold", "prob_bull": prob_bull, "prob_bear": prob_bear},
        "ciclo": {"prob_bull": prob_bull, "prob_bear": prob_bear, "primaria": "cenario x", "exaurido": {"bull": False, "bear": False}},
        "vivas": [{"nome": "hipotese", "vies": "bull", "invalidacao": 80.0, "alvos": [200.0]}],
    }


def test_plano_tem_contrato_minimo():
    ohlcv = _serie()
    p = montar_plano("BTCUSDT", ohlcv[-1][4], _trader("impulso_alta"), {"1d": ohlcv})
    for k in ("par", "preco", "estado", "modo", "direcao_grau_maior", "risco_permitido", "teto_hedge",
              "pode_comprar", "pode_vender", "zonas_compra", "zonas_venda", "leituras", "niveis", "motivo"):
        assert k in p, f"falta {k} no plano"
    assert p["modo"] in MODOS
    assert 0.0 <= p["risco_permitido"] <= 1.0


def test_fundo_de_ciclo_proibe_venda_de_todo_mundo():
    """A regra que o usuário fixou: ninguém vende num fundo terminal, nem o perfil turbo."""
    ohlcv = _serie()
    for estado in ("fundo_terminal", "novo_impulso", "zona_onda_2"):
        p = montar_plano("BTCUSDT", ohlcv[-1][4], _trader(estado, prob_bear=0.9, prob_bull=0.1), {"1d": ohlcv})
        assert p["modo"] == "acumular"
        assert p["pode_vender"] is False, f"{estado} deixou vender"
        assert p["teto_hedge"] == 0.0
        assert p["direcao_grau_maior"] == "buy"


def test_correcao_confirmada_libera_hedge_total():
    ohlcv = _serie()
    p = montar_plano("BTCUSDT", ohlcv[-1][4], _trader("correcao_inicial", prob_bear=0.8, prob_bull=0.2), {"1d": ohlcv})
    assert p["modo"] == "hedge"
    assert p["pode_vender"] is True
    assert p["teto_hedge"] == 1.0
    assert p["direcao_grau_maior"] == "sell"


def test_impulso_maduro_sem_exaustao_nao_vende():
    """Maduro não é venda: é não perseguir. Só vira 'reduzir' quando as contagens viram COM exaustão."""
    ohlcv = _serie()
    p = montar_plano("BTCUSDT", ohlcv[-1][4], _trader("impulso_maduro", prob_bear=0.7, prob_bull=0.3), {"1d": ohlcv})
    assert p["modo"] in ("nao_perseguir", "reduzir")
    if not p["exaustao"]["confirmada"]:
        assert p["modo"] == "nao_perseguir"
        assert p["pode_vender"] is False
    assert p["risco_permitido"] <= 0.5


def test_impulso_maduro_com_contagens_bull_segura():
    ohlcv = _serie()
    p = montar_plano("BTCUSDT", ohlcv[-1][4], _trader("impulso_maduro", prob_bear=0.2, prob_bull=0.8), {"1d": ohlcv})
    assert p["modo"] == "nao_perseguir"
    assert p["pode_comprar"] is True
    assert p["risco_permitido"] == 0.5


def test_todo_estado_do_superciclo_tem_modo():
    for estado, (modo, direcao, risco) in POR_ESTADO.items():
        assert modo in MODOS, f"{estado} aponta para modo desconhecido {modo}"
        assert direcao in ("buy", "sell", "hold")
        assert 0.0 <= risco <= 1.0


def test_sem_candles_devolve_plano_de_espera():
    p = montar_plano("BTCUSDT", 100.0, _trader("impulso_alta"), {})
    assert p["modo"] == "aguardar"
    assert p["risco_permitido"] == 0.0
    assert "erro" in p


def test_invalidacao_do_trader_entra_como_nivel():
    ohlcv = _serie()
    p = montar_plano("BTCUSDT", ohlcv[-1][4], _trader("impulso_alta"), {"1d": ohlcv})
    fontes = {n["fonte"] for n in p["niveis"]}
    assert "trader_invalidacao" in fontes
    assert "trader_alvo" in fontes


def test_zonas_ficam_do_lado_certo_do_preco():
    ohlcv = _serie()
    preco = ohlcv[-1][4]
    p = montar_plano("BTCUSDT", preco, _trader("impulso_alta"), {"1d": ohlcv})
    assert all(z["preco"] < preco for z in p["zonas_compra"])
    assert all(z["preco"] > preco for z in p["zonas_venda"])


def test_estado_desconhecido_cai_em_aguardar():
    ohlcv = _serie()
    p = montar_plano("BTCUSDT", ohlcv[-1][4], _trader("estado_que_nao_existe"), {"1d": ohlcv})
    assert p["modo"] == "aguardar"
    assert p["pode_comprar"] is False and p["pode_vender"] is False
