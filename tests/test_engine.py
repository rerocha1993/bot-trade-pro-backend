from types import SimpleNamespace

import pytest

from core.backtest_engine import BacktestEngine, bot_padrao
from core.executor_real import OrderExecutor, position_idx
from core.fase_onda_rules import direcao_permitida, indicadores_para_fase
from core.strategy_engine import StrategyEngine
from tests.conftest import gerar_candles, impulso_5_ondas


class ConectorFalso:
    """Conector mínimo para o executor em modo simulador (sem rede)."""
    modo_execucao = "simulador"
    pode_enviar_ordens = False

    def __init__(self, preco=100.0):
        self.preco = preco

    def arredondar_quantidade(self, par, qty):
        return round(int(qty / 0.001) * 0.001, 3)

    def obter_preco_atual(self, par):
        return self.preco


def bot_teste(**kw):
    return bot_padrao(**kw)


def test_regras_fase_perfil():
    assert direcao_permitida("meio_onda_3", "conservador") == "tendencia"
    assert direcao_permitida("final_onda_3", "conservador") is None
    assert direcao_permitida("final_onda_3", "turbo") == "tendencia"
    assert direcao_permitida("correcao_c", "conservador") == "contra"
    assert direcao_permitida("indefinido", "turbo") is None
    assert indicadores_para_fase("meio_onda_3", ["VWAP", "OrderBlock", "Fibonacci"]) == ["VWAP"]


def test_engine_onda3_gera_entrada_com_sl_tp():
    precos = [100 + 0.05 * (i % 4) for i in range(40)]
    for alvo in (110, 104, 115):
        ini = precos[-1]
        precos += [ini + (alvo - ini) * s / 10 for s in range(1, 11)]
    c = gerar_candles(precos, volume=50)
    bot = bot_teste(confluencia_tipo="turbo", usar_tpo=True, usar_vwap=True, usar_volume_profile=True, usar_orderblock=False)
    eng = StrategyEngine(c, bot, db=None, servicos={"fetch_ohlcv": lambda tf, n: c[-n:], "ohlcv_composto": c})
    d = eng.decidir()
    assert d["fase_onda"] in ("inicio_onda_3", "meio_onda_3", "final_onda_3", "onda_5")
    assert "cenarios" in d and d["cenarios"]
    if d["acao"] == "buy":
        assert d["sl"] < c[-1][4] < d["tp"]
        assert d["niveis"]["rr"] >= 1.0


def test_engine_sem_elliott_e_hold():
    c = gerar_candles([100 + (i % 2) * 0.1 for i in range(80)])
    bot = bot_teste(usar_elliott=False)
    d = StrategyEngine(c, bot, db=None, servicos={"fetch_ohlcv": lambda tf, n: c[-n:]}).decidir()
    assert d["acao"] == "hold"
    bot2 = bot_teste()
    d2 = StrategyEngine(c, bot2, db=None, servicos={"fetch_ohlcv": lambda tf, n: c[-n:]}).decidir()
    assert d2["acao"] == "hold"  # lateral sem impulso


def test_executor_simulado_nao_envia_ordem():
    ex = OrderExecutor(ConectorFalso(100.0))
    r = ex.abrir("BTCUSDT", "buy", 0.0123, 95, 110, preco_ref=100.0)
    assert r["simulado"] and r["quantidade"] == 0.012 and r["preco_exec"] == 100.0
    f = ex.fechar("BTCUSDT", "buy", 0.012, preco_ref=105.0)
    assert f["simulado"] and f["preco_exec"] == 105.0
    assert position_idx("one-way", "buy") == 0 and position_idx("hedged", "sell") == 2


def test_sizing_por_risco():
    from core.bot_executor import BotExecutor

    class DB:
        def add(self, *a): pass
        def commit(self): pass
        def rollback(self): pass
        def query(self, *a): raise RuntimeError("sem banco")

    bot = bot_teste(banca=10000, risco_pct=0.01, max_alocacao_pct=0.5, alavancagem=1)
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot, ex.db, ex.modo, ex.par = bot, DB(), "simulador", "BTCUSDT"
    ex.con = ConectorFalso(100.0)
    ex.estado = {"dia": "x", "pnl_dia": 0.0, "trades_dia": 0}
    # risco 100 USDT, distância 2 -> 50 unidades; teto 0.5*10000/100 = 50 -> 50
    assert ex.calcular_tamanho_ordem(100.0, 98.0) == pytest.approx(50.0, abs=0.001)
    # distância 0.5 -> 200 unidades, mas teto = 50
    assert ex.calcular_tamanho_ordem(100.0, 99.5) == pytest.approx(50.0, abs=0.001)
    assert ex.calcular_tamanho_ordem(100.0, None) == 0.0


def test_backtest_roda_em_dados_sinteticos():
    precos = []
    base = 100.0
    for ciclo in range(6):
        p, alvos = impulso_5_ondas(base=base, passos=6, seed=ciclo)
        precos += p
        # correção ABC
        topo = p[-1]
        for alvo in (topo - 8, topo - 4, topo - 12):
            ini = precos[-1]
            precos += [ini + (alvo - ini) * s / 5 for s in range(1, 6)]
        base = precos[-1]
    c = gerar_candles(precos, dur_ms=3_600_000, volume=20)
    bot = bot_teste(confluencia_tipo="turbo", usar_orderblock=False)
    bt = BacktestEngine(c, bot, timeframe="1h", janela=60, passo=1)
    r = bt.executar()
    assert r["candles"] == len(c)
    assert isinstance(r["trades"], int)
    assert "drawdown_max_pct" in r


def test_stop_nunca_fica_dentro_do_ruido_do_1m():
    """
    Regressão medida ao vivo: o scalp saiu com stop a 39 dólares da entrada (0,05%) e foi acionado por ruído
    em 1m39s. Já existia um piso — meio ATR —, mas no 1m isso dá uns 38 dólares e o stop passou raspando por
    cima. E o piso era medido do preço atual, não do preço da ordem limitada que de fato executa.
    """
    from core.strategy_engine import RISCO_MINIMO_PCT
    preco = 77000.0
    ohlcv = gerar_candles([preco] * 60, dur_ms=60_000, amplitude=0.00001)
    bot = bot_padrao(estilo_trade="scalping", timeframe="1m", tipo_entrada="limite", usar_fibonacci=False)
    eng = StrategyEngine(ohlcv, bot, servicos={"preco_atual": preco})
    assert eng.atr == pytest.approx(preco * 0.001)      # ATR do 1m no piso de 0,1%: meio ATR = 38,50
    # invalidação de Elliott colada no preço: sem o piso novo o stop nasceria a 39 dólares, como ao vivo
    inv = preco - 39.0 + 0.15 * eng.atr
    niveis = eng.calcular_tp_sl("buy", "meio_onda_3", [], {"invalidacao": inv, "alvos": []}, {})
    piso = preco * RISCO_MINIMO_PCT
    assert preco - niveis["sl"] >= piso - 1e-6, f"stop a {preco - niveis['sl']:.2f} do preço"
    assert niveis["preco_limite"] - niveis["sl"] >= piso - 1e-6, "o piso não valeu para onde a ordem executa"
