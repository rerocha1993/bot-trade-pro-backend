"""
Regra de assimetria do usuário: operar o GRUPO de contagens que faz o mesmo movimento, com stop onde o grupo morre
e alvo onde as contagens divergem.
"""
import pytest

from core.assimetria import alvo_comum, grupo_do_movimento, grupo_vivo, plano, rr_liquido, stop_do_grupo
from core.backtest_assimetria import BacktestAssimetria, avaliar

# 5 contagens: 3 bull e 2 bear, todas fazendo o mesmo movimento inicial de ALTA a partir de 100
CINCO = [
    {"vies": "bull", "direcao": "buy", "prob": 0.30, "inv": 96.0, "alvos": [112.0]},
    {"vies": "bull", "direcao": "buy", "prob": 0.20, "inv": 94.0, "alvos": [108.0]},
    {"vies": "bull", "direcao": "buy", "prob": 0.15, "inv": 97.0, "alvos": [115.0]},
    {"vies": "bear", "direcao": "buy", "prob": 0.15, "inv": 92.0, "alvos": [106.0]},   # correção de alta (onda B)
    {"vies": "bear", "direcao": "sell", "prob": 0.20, "inv": 104.0, "alvos": [90.0]},
]


def test_grupo_e_o_movimento_comum_mesmo_com_contagens_de_vieses_diferentes():
    g = grupo_do_movimento(CINCO, 100.0)
    assert g.lado == "buy" and len(g.contagens) == 4
    assert g.peso == pytest.approx(0.80)


def test_sem_maioria_nao_ha_grupo():
    metade = [dict(CINCO[0], prob=0.5), dict(CINCO[4], prob=0.5)]
    assert grupo_do_movimento(metade, 100.0) is None


def test_contagem_com_niveis_incoerentes_nao_entra_no_grupo():
    ruim = dict(CINCO[0], inv=101.0)            # invalidação ACIMA do preço numa compra
    g = grupo_do_movimento([ruim] + CINCO[1:], 100.0, minimo_consenso=0.4)
    assert all(c["inv"] < 100.0 for c in g.contagens)


def test_stop_onde_todo_o_grupo_morre_e_onde_a_maioria_morre():
    g = grupo_do_movimento(CINCO, 100.0)
    assert stop_do_grupo(g, 100.0, "grupo") == 92.0          # a invalidação mais distante
    # mais próximas primeiro: 97 (0,15) é 19% do grupo; com 96 (0,30) morrem 0,45 de 0,80 = 56%: a maioria
    assert stop_do_grupo(g, 100.0, "maioria") == 96.0


def test_alvo_e_onde_as_contagens_comecam_a_divergir():
    assert alvo_comum(grupo_do_movimento(CINCO, 100.0), 100.0) == 106.0


def test_rr_liquido_desconta_o_custo():
    # bruto 10 contra 5 = 2,0; com entrada taker, alvo maker e stop taker + slippage fica ~1,92
    assert rr_liquido(100.0, 95.0, 110.0) == pytest.approx(1.924, abs=0.01)


def test_plano_recusa_quando_o_retorno_nao_paga_o_risco():
    assert plano(CINCO, 100.0, atr=1.0, tipo_stop="grupo", rr_minimo=1.0) is None     # ganha 6 arriscando 8
    p = plano(CINCO, 100.0, atr=1.0, tipo_stop="maioria", rr_minimo=1.0)              # ganha 6 arriscando 4
    assert p is not None and p.lado == "buy" and p.stop == 96.0 and p.alvo == 106.0
    assert p.rr_liquido == pytest.approx(1.42, abs=0.02)


def test_stop_colado_no_preco_e_ruido():
    colado = [{"vies": "bull", "direcao": "buy", "prob": 1.0, "inv": 99.9, "alvos": [105.0]}]
    assert plano(colado, 100.0, atr=2.0) is None


def test_peso_vivo_do_movimento():
    assert grupo_vivo(CINCO, 100.0, "buy") == pytest.approx(0.80)
    assert grupo_vivo(CINCO, 100.0, "sell") == pytest.approx(0.20)


# ------------------------------------------------------------------ backtest
H = 14_400_000


def _serie(precos_hl, cenarios):
    linhas, candles = [], {}
    for i, (hi, lo, close) in enumerate(precos_hl):
        ts = i * H
        candles[ts] = (close, hi, lo, close)
        linhas.append({"ts": ts, "close": close, "atr": 1.0, "cenarios": cenarios})
    return linhas, candles


def test_backtest_entra_no_fechamento_e_sai_no_alvo():
    grupo = [{"vies": "bull", "direcao": "buy", "prob": 1.0, "inv": 95.0, "alvos": [110.0]}]
    linhas, candles = _serie([(100, 100, 100), (104, 99, 103), (111, 103, 110)], grupo)
    r = BacktestAssimetria(linhas, candles, rr_minimo=1.0).executar()
    assert r["trades"] >= 1 and r["lista"][0]["motivo_saida"] == "alvo"
    assert r["lista"][0]["liquido_r"] < r["lista"][0]["bruto_r"]


def test_stop_e_alvo_no_mesmo_candle_conta_o_stop():
    grupo = [{"vies": "bull", "direcao": "buy", "prob": 1.0, "inv": 95.0, "alvos": [110.0]}]
    linhas, candles = _serie([(100, 100, 100), (112, 94, 100)], grupo)
    r = BacktestAssimetria(linhas, candles).executar()
    assert r["lista"][0]["motivo_saida"] == "stop" and r["lista"][0]["bruto_r"] < -1.0


def test_sai_na_virada_quando_o_grupo_perde_a_maioria():
    compra = [{"vies": "bull", "direcao": "buy", "prob": 1.0, "inv": 95.0, "alvos": [110.0]}]
    virou = [{"vies": "bear", "direcao": "sell", "prob": 1.0, "inv": 106.0, "alvos": [90.0]}]
    linhas, candles = _serie([(100, 100, 100), (102, 99, 101)], compra)
    linhas[1]["cenarios"] = virou
    r = BacktestAssimetria(linhas, candles, sair_na_virada=True).executar()
    assert r["lista"][0]["motivo_saida"] == "virada"


def test_criterio_reprova_quem_perde_fora_do_treino():
    tr = {"trades": 100, "soma_r": 12.0, "fator_lucro": 1.3}
    ok, falhas = avaliar(tr, {"trades": 40, "soma_r": -3.0})
    assert not ok and any("validação" in f for f in falhas)
    assert avaliar(tr, {"trades": 40, "soma_r": 5.0})[0]
