import pytest

from core.inverse_grade import GradeInversa


def test_grade_monta_fatias_e_nunca_recompra_com_prejuizo():
    g = GradeInversa(61000, 85000)
    assert len(g.fatias) == 8 * 3
    assert sum(f.fracao for f in g.fatias) == pytest.approx(1.0)
    for f in g.fatias:
        assert f.preco_recompra < f.preco_venda           # toda recompra abaixo da venda
    # extensões acima do topo existem (sem stop, o range se estende)
    assert any(f.nivel > 1.0 for f in g.fatias)


def test_ciclo_completo_acumula_btc_sem_stop():
    g = GradeInversa(61000, 85000)
    caminho = [(70000, 62000, 69000), (78000, 69000, 77000), (86000, 77000, 85500), (90000, 84000, 89000),
               (89000, 80000, 81000), (82000, 70000, 71000), (72000, 61000, 61500)]
    for ts, (hi, lo, cl) in enumerate(caminho, 1):
        g.processar_candle(ts, hi, lo, cl, 1.0)
    assert g.btc_realizado > 0
    assert g.fracao_aberta() < 0.1
    # um rompimento que nunca volta: fatias ficam abertas, BTC realizado não cai
    g2 = GradeInversa(61000, 85000)
    for ts, (hi, lo, cl) in enumerate([(70000, 62000, 69000), (90000, 69000, 89000), (120000, 89000, 119000)], 1):
        g2.processar_candle(ts, hi, lo, cl, 1.0)
    assert g2.btc_realizado == 0.0
    assert g2.fracao_aberta() == pytest.approx(1.0)      # 100% em dólar, esperando
    assert g2.pnl_nao_realizado(119000) < 0               # marcado a mercado negativo, mas nada realizado


def test_short_de_base_segura_fatias_ate_alvo_elliott():
    g = GradeInversa(61000, 85000)
    mestre = {"vies": "bear", "alvos": [52000], "prob_sucesso": 0.8, "status": "ativa"}
    g.processar_candle(1, 86000, 62000, 85000, 1.0, mestre)
    g.processar_candle(2, 85000, 61000, 61200, 1.0, mestre)      # cai até o fundo
    assert g.fracao_aberta() == pytest.approx(0.4, abs=0.05)    # ~0.5*0.8 ficam abertas
    g.processar_candle(3, 61000, 51000, 52000, 1.0, mestre)      # atinge o alvo de Elliott
    assert g.fracao_aberta() == pytest.approx(0.0, abs=0.01)
