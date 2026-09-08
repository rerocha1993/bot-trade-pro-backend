import pytest

from core.inverse_range import PosicaoInversa, RangeConfig, alocacao_escada, decidir_alocacao, propor_range


def test_escada_sobe_e_desce_com_histerese():
    cfg = RangeConfig(61000, 85000)
    assert alocacao_escada(cfg, 61000) == 0.0
    assert alocacao_escada(cfg, 85000) == 1.0
    a73 = alocacao_escada(cfg, 73500)      # ~52% do range -> degrau 0.5 -> 40%
    assert a73 == 0.40
    # descendo de volta para logo abaixo do nível 0.5 mantém 40% pela histerese
    assert alocacao_escada(cfg, 72950, alocacao_atual=0.40) == 0.40
    # bem abaixo do nível cai para o degrau anterior (0.382 -> 25%)
    assert alocacao_escada(cfg, 71000, alocacao_atual=0.40) == 0.25


def test_stop_e_short_base():
    cfg = RangeConfig(61000, 85000, folga_stop=0.01)
    d = decidir_alocacao(cfg, 86000, 0.8)
    assert d["estado"] == "stopado" and d["alvo"] == 0.0
    # no fundo sem cenário bear: zera
    assert decidir_alocacao(cfg, 60500, 0.3)["alvo"] == 0.0
    # no fundo com cenário bear apontando abaixo: mantém short de base = 0.5 * prob
    d2 = decidir_alocacao(cfg, 60500, 0.3, {"vies": "bear", "alvos": [52000], "prob_sucesso": 0.7, "status": "ativa"})
    assert d2["alvo"] == pytest.approx(0.35, abs=0.01) and d2["estado"] == "carregando"
    # bull forte limita a escada a 50%
    d3 = decidir_alocacao(cfg, 85000, 0.0, {"vies": "bull", "alvos": [95000], "prob_sucesso": 0.8, "status": "ativa"})
    assert d3["alvo"] == 0.5


def test_pnl_inverso_em_btc():
    pos = PosicaoInversa()
    pos.vender(50000, 80000, taxa=0.0)
    pos.vender(50000, 84000, taxa=0.0)
    assert pos.entrada_media == pytest.approx(100000 / (50000 / 80000 + 50000 / 84000))
    pnl = pos.recomprar(100000, 62000, taxa=0.0)
    esperado = 100000 / 62000 - (50000 / 80000 + 50000 / 84000)   # contratos*(1/saida - 1/entrada)
    assert pnl == pytest.approx(esperado)
    assert pnl > 0   # short inverso lucra em BTC quando o preço cai
    pos2 = PosicaoInversa(); pos2.vender(80000, 80000, taxa=0.0)
    assert pos2.recomprar(80000, 62000, taxa=0.0) == pytest.approx(80000 / 62000 - 1.0)   # +0,29 BTC
    pos3 = PosicaoInversa(); pos3.vender(80000, 80000, taxa=0.0)
    assert pos3.pnl_nao_realizado(86000) < 0   # preço subindo: perda em BTC


def test_proposta_range():
    piv = [{"preco": 85000, "tipo": "H", "confirmado": True, "data": "2026-01-01"},
           {"preco": 61000, "tipo": "L", "confirmado": True, "data": "2026-03-01"}]
    p = propor_range(piv, 70000, {"regime": "compressao", "eficiencia": 0.1}, {"fase": "correcao_b"})
    assert p["valido"] and p["low"] == 61000 and p["high"] == 85000
    assert propor_range(piv, 90000)["valido"] is False
