import math

import pytest

from core.fibonacci import Fibonacci
from core.fibonacci_elliott import FibonacciElliott
from core.fibonacci_strategies import FibonacciStrategies
from core.order_block import OrderBlockDetector
from core.order_flow import OrderFlowAnalyzerPro
from core.tpo import TPOProfile
from core.utils_indicadores import arredondar_para_step, atr, timeframe_ms, ultimo_candle_fechado
from core.volume_profile_pro import VolumeProfilePRO
from core.vwap import VWAPCalculator
from tests.conftest import gerar_candles


def test_fibonacci_direcional():
    up = Fibonacci(high=110, low=100, direcao="up")
    assert up.retracao(0.5) == 105.0
    assert up.retracao(0.618) == pytest.approx(103.82, abs=0.01)
    assert up.extensao(1.618) == pytest.approx(116.18, abs=0.01)
    down = Fibonacci(high=110, low=100, direcao="down")
    assert down.retracao(0.5) == 105.0
    assert down.retracao(0.618) == pytest.approx(106.18, abs=0.01)   # acima do fundo
    assert down.extensao(1.618) == pytest.approx(93.82, abs=0.01)    # abaixo do fundo
    assert Fibonacci.de_swing(100, 110).direcao == "up"
    assert Fibonacci.de_swing(110, 100).direcao == "down"


def test_fibonacci_elliott_regras():
    ondas = [{"preco_inicio": 100, "preco_fim": 110}, {"preco_inicio": 110, "preco_fim": 103.82},
             {"preco_inicio": 103.82, "preco_fim": 120}, {"preco_inicio": 120, "preco_fim": 114},
             {"preco_inicio": 114, "preco_fim": 124}]
    fe = FibonacciElliott(ondas)
    assert fe.validar_onda2()["ok"] and fe.validar_onda2()["ideal"]
    assert fe.validar_onda3()["ok"] and fe.validar_onda3()["razao"] == pytest.approx(1.618, abs=0.01)
    assert fe.validar_onda4()["ok"]
    assert fe.validar_onda5()["ok"]
    assert fe.score_impulso() > 0.8
    # onda 4 invadindo a onda 1 -> falha
    ondas_ruins = list(ondas)
    ondas_ruins[3] = {"preco_inicio": 120, "preco_fim": 108}
    assert FibonacciElliott(ondas_ruins).validar_onda4()["ok"] is False
    # onda 2 além do início da 1 -> falha
    ondas_ruins2 = list(ondas)
    ondas_ruins2[1] = {"preco_inicio": 110, "preco_fim": 99}
    assert FibonacciElliott(ondas_ruins2).validar_onda2()["ok"] is False


def test_fibonacci_strategies_coerencia_direcional():
    precos = [100 + i * 0.5 for i in range(60)]           # tendência de alta
    c = gerar_candles(precos)
    r_buy = FibonacciStrategies(c).generico("buy")
    assert r_buy["sl"] < c[-1][4]
    assert r_buy["tp"] is None or r_buy["tp"] > c[-1][4]
    precos_d = [130 - i * 0.5 for i in range(60)]
    cd = gerar_candles(precos_d)
    r_sell = FibonacciStrategies(cd).generico("sell")
    assert r_sell["sl"] > cd[-1][4]
    assert r_sell["tp"] is None or r_sell["tp"] < cd[-1][4]


def test_vwap_e_bandas():
    c = [[i, 100, 101, 99, 100, 10] for i in range(10)]
    v = VWAPCalculator(c)
    assert v.vwap() == pytest.approx(100.0)
    b = v.vwap_bandas()
    assert b["stddev"] == pytest.approx(0.0)
    c2 = [[0, 100, 101, 99, 100, 10], [1, 100, 121, 119, 120, 30]]
    v2 = VWAPCalculator(c2)
    # preços típicos 100 e 120, volumes 10 e 30 -> 115
    assert v2.vwap() == pytest.approx(115.0)
    s = v2.sinal(preco_atual=130)
    assert s["acao"] == "buy" and s["z"] > 0


def test_tpo_value_area_e_sinal():
    # 30 candles concentrados em 100-102 e alguns extremos
    precos = [100 + (i % 3) for i in range(30)] + [110, 90]
    c = gerar_candles(precos, amplitude=0.002)
    tpo = TPOProfile(c, bins=20)
    res = tpo.analisar()
    assert 99 <= res["POC"] <= 103
    assert res["VAL"] <= res["POC"] <= res["VAH"]
    assert tpo.sinal_estrategico(res["VAH"] + 5)["acao"] == "buy"
    assert tpo.sinal_estrategico(res["VAL"] - 5)["acao"] == "sell"
    assert tpo.sinal_estrategico(res["POC"])["acao"] == "hold"
    # compatibilidade: lista de preços
    assert TPOProfile([100, 101, 102, 101, 100]).analisar()["POC"] > 0


def test_volume_profile_distribui_volume():
    c = [[0, 100, 110, 100, 110, 100.0]]  # um candle cobrindo 100-110 com volume 100
    vp = VolumeProfilePRO(c, num_bins=10)
    assert vp.hist.sum() == pytest.approx(100.0)
    assert all(v > 0 for v in vp.hist)  # volume espalhado por todos os bins
    res = vp.analisar()
    assert res["VAL"] < res["VAH"]
    assert vp.price_signal(120)["acao"] == "buy"
    assert vp.price_signal(80)["acao"] == "sell"


def test_order_flow_delta_e_livro():
    ohlcv = [[0, 100, 101, 99, 100.5, 10]]
    trades = [{"price": 100.4, "qty": 5, "side": "buy", "timestamp": 10},
              {"price": 100.5, "qty": 1, "side": "sell", "timestamp": 20}]
    book = {"bids": [(100.4, 10)], "asks": [(100.6, 2)]}
    r = OrderFlowAnalyzerPro(book, trades, ohlcv, timeframe="1m").analisar()
    assert r["acao"] == "buy" and r["delta"] == 4
    r2 = OrderFlowAnalyzerPro(book, [], ohlcv, timeframe="1m").analisar()
    assert r2["acao"] == "buy"  # só livro: imbalance positivo
    r3 = OrderFlowAnalyzerPro({"bids": [(100, 5)], "asks": [(101, 5)]}, [], ohlcv).analisar()
    assert r3["acao"] == "hold"


def test_order_block_exige_deslocamento():
    # lateral + candle de baixa + deslocamento forte de alta
    precos = [100, 100.2, 99.9, 100.1, 100.0, 100.2, 99.8, 100.1, 100.0, 99.5, 103, 105, 106, 106.5, 106.2, 106.4, 106.1]
    c = gerar_candles(precos, amplitude=0.001)
    det = OrderBlockDetector(c, fator_atr=1.5)
    bull = det.identificar_blocks("bullish")
    assert len(bull) >= 1
    lo, hi = bull[0]["zona"]
    assert lo < hi
    # lateral pura não gera blocos
    lat = gerar_candles([100 + 0.1 * ((i % 4) - 2) for i in range(40)], amplitude=0.0005)
    assert OrderBlockDetector(lat).identificar_blocks("bullish") == []


def test_utils():
    assert timeframe_ms("15m") == 900_000 and timeframe_ms("1D") == 86_400_000
    assert arredondar_para_step(0.0123456, 0.001) == 0.012
    assert arredondar_para_step(80123.456, 0.1, "nearest") == pytest.approx(80123.5)
    c = gerar_candles([100, 101, 102, 101, 103])
    assert atr(c, 3) > 0
    agora = c[-1][0] + 100  # último candle ainda aberto
    assert len(ultimo_candle_fechado(c, "15m", agora)) == len(c) - 1
    assert len(ultimo_candle_fechado(c, "15m", c[-1][0] + 900_000 + 1)) == len(c)
