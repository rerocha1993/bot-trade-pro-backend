"""
Gestão de trade do usuário: entrada fracionada em 5 e tirar o risco (realizar metade quando andar 1 R sobre o
preço médio; se o resto for stopado, o trade fica 0 a 0).
"""
import pytest

from core.gestao_trade import trade_gestao


def _serie(candles):
    close = [c[2] for c in candles]
    high = [c[0] for c in candles]
    low = [c[1] for c in candles]
    return close, high, low


def test_andou_1r_realiza_metade_e_o_stop_depois_da_zero_a_zero():
    # compra a 100, stop 90 (risco 10). Sobe a 110 (1 R) sem recuar, depois despenca no stop
    close, high, low = _serie([(100, 100, 100), (110.5, 100.5, 110), (110, 85, 86)])
    r = trade_gestao(1, 0, 100.0, 10.0, close, high, low, n_entradas=5, espacamento=0.2)
    assert r["motivo"] == "zero_a_zero" and r["fatias"] == 1
    assert r["bruto_r"] == pytest.approx(-0.0, abs=0.02), "o realizado paga a perda do resto (fora a slippage)"
    assert r["liquido_r"] < 0 and r["liquido_r"] > -0.05, "só as taxas"


def test_recuo_executa_as_fatias_e_melhora_o_preco_medio():
    # recua até 93 (executa as fatias a 98, 96 e 94), depois sobe até o alvo de 130
    close, high, low = _serie([(100, 100, 100), (100, 93, 94), (131, 94, 130)])
    r = trade_gestao(1, 0, 100.0, 10.0, close, high, low, n_entradas=5, espacamento=0.2)
    assert r["fatias"] == 4 and r["motivo"] == "alvo"
    assert r["liquido_r"] > 0


def test_stop_direto_com_todas_as_fatias_perde_1r():
    close, high, low = _serie([(100, 100, 100), (100, 91, 92), (92, 89, 89)])
    r = trade_gestao(1, 0, 100.0, 10.0, close, high, low, n_entradas=5, espacamento=0.2)
    assert r["fatias"] == 5 and r["motivo"] == "stop"
    assert r["bruto_r"] == pytest.approx(-1.0, abs=0.03), "o tamanho é calculado para o pior caso perder 1 R"


def test_stop_direto_so_com_a_primeira_fatia_perde_menos():
    close, high, low = _serie([(100, 100, 100), (100, 97.5, 98), (98, 89, 89)])
    r = trade_gestao(1, 0, 100.0, 10.0, close, high, low, n_entradas=5, espacamento=0.2)
    assert r["motivo"] == "stop" and -1.0 < r["bruto_r"] < -0.3


def test_mesmo_candle_com_stop_e_alvo_conta_o_stop():
    close, high, low = _serie([(100, 100, 100), (140, 80, 100)])
    r = trade_gestao(1, 0, 100.0, 10.0, close, high, low)
    assert r["motivo"] == "stop"


def test_venda_espelhada():
    close, high, low = _serie([(100, 100, 100), (100, 89.5, 90), (116, 90, 115)])
    r = trade_gestao(-1, 0, 100.0, 10.0, close, high, low)
    assert r["motivo"] == "zero_a_zero"
    assert r["bruto_r"] == pytest.approx(0.0, abs=0.02)


def test_ordem_limitada_so_executa_se_o_preco_atravessar_o_nivel():
    """Encostar no nível não garante execução (fila no livro): com folga, o toque exato não executa."""
    close, high, low = _serie([(100, 100, 100), (100, 98.0, 99), (99, 98.0, 99)])
    sem = trade_gestao(1, 0, 100.0, 10.0, close, high, low, n_entradas=5, espacamento=0.2)
    com = trade_gestao(1, 0, 100.0, 10.0, close, high, low, n_entradas=5, espacamento=0.2, folga_execucao=0.0005)
    assert sem["fatias"] == 2 and com["fatias"] == 1
