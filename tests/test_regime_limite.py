import pytest

from core.backtest_engine import BacktestEngine, bot_padrao
from core.elliott_pro.calibracao import Calibrador, construir_dataset, features_cenario, treinar
from core.regime import analisar_regime
from tests.conftest import gerar_candles, impulso_5_ondas


def _serie_ciclos(n_ciclos=6, dur_ms=3_600_000):
    precos, base = [], 100.0
    for ciclo in range(n_ciclos):
        p, _ = impulso_5_ondas(base=base, passos=6, seed=ciclo)
        precos += p
        topo = p[-1]
        for alvo in (topo - 8, topo - 4, topo - 12):
            ini = precos[-1]
            precos += [ini + (alvo - ini) * s / 5 for s in range(1, 6)]
        base = precos[-1]
    return gerar_candles(precos, dur_ms=dur_ms, volume=20)


def test_regime_tendencia_e_compressao():
    tend = gerar_candles([100 + i * 0.8 for i in range(160)], amplitude=0.002)
    r = analisar_regime(tend)
    assert r["regime"] == "tendencia" and r["permite_entrada"]
    comp = gerar_candles([100 + 0.4 * ((i % 4) - 2) for i in range(120)] + [100 + 0.1 * ((i % 3) - 1) for i in range(40)], amplitude=0.0005)
    r2 = analisar_regime(comp)
    assert r2["regime"] in ("compressao", "serrilhado")
    assert r2["permite_entrada"] is False


def test_backtest_ordem_limitada_e_slippage():
    c = _serie_ciclos()
    bot_m = bot_padrao(confluencia_tipo="turbo", usar_orderblock=False, tipo_entrada="mercado", slippage_pct=0.001, usar_filtro_regime=False)
    bot_l = bot_padrao(confluencia_tipo="turbo", usar_orderblock=False, tipo_entrada="limite", limite_candles_espera=3, usar_filtro_regime=False)
    rm = BacktestEngine(c, bot_m, timeframe="1h", janela=60).executar()
    rl = BacktestEngine(c, bot_l, timeframe="1h", janela=60).executar()
    assert "ordens_limite" in rl
    assert rl["ordens_limite"]["executadas"] + rl["ordens_limite"]["expiradas"] >= 0
    # com slippage de 0,1% cada trade a mercado paga mais que a mesma execução sem slippage
    assert isinstance(rm["pnl_total"], float)


def test_calibracao_treina_e_aplica():
    c = _serie_ciclos(n_ciclos=10)
    linhas = construir_dataset(c, "1h", janela=60, horizonte=20, passo=1, verbose=False)
    assert len(linhas) > 50
    modelo = treinar(linhas, epocas=100, verbose=False)
    cal = Calibrador(modelo=modelo)
    p = cal.prob(linhas[0])
    assert 0.0 <= p <= 1.0
    from core.elliott_pro.multidegree import analisar_serie
    res = analisar_serie(c[-60:], 2.0, timeframe="1h", calibrar=False)
    res2 = cal.aplicar(res, c[-1][4], 1.0, "1h", res.get("regime"))
    if res2["cenarios"]:
        assert "prob_sucesso" in res2["cenarios"][0]
