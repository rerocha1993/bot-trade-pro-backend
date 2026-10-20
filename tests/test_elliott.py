import pytest

from conselho.elliott.patterns import Leg, ajustar_diagonal, ajustar_flat, ajustar_impulso, ajustar_todos, ajustar_triangulo, ajustar_wxy, ajustar_zigzag
from conselho.elliott.pivots import zigzag_atr
from conselho.elliott.scenarios import ScenarioEngine
from conselho.elliott.multidegree import AnaliseMultiGrau, analisar_serie, timeframes_do_perfil
from tests.conftest import gerar_candles, impulso_5_ondas


def legs(*pontos):
    return [Leg(pontos[i], pontos[i + 1]) for i in range(len(pontos) - 1)]


def test_impulso_valido_e_invalido():
    fit = ajustar_impulso(legs(100, 110, 103.8, 120, 114, 124))
    assert fit and fit.padrao == "impulso" and fit.direcao == "up" and fit.score > 0.8
    assert fit.extras["extensao"] == "3"
    # onda 4 invade onda 1
    assert ajustar_impulso(legs(100, 110, 103.8, 120, 108, 124)) is None
    # onda 3 mais curta
    assert ajustar_impulso(legs(100, 110, 105, 112, 108, 125)) is None
    # impulso de baixa
    fit_d = ajustar_impulso(legs(100, 90, 96.2, 80, 86, 76))
    assert fit_d and fit_d.direcao == "down"


def test_diagonal_e_truncada():
    # cunha: 3 < 1, 5 < 3, 4 sobrepõe 1
    fit = ajustar_diagonal(legs(100, 110, 104, 112, 108, 113), "ending")
    assert fit and fit.padrao == "diagonal_ending"
    fit_imp = ajustar_impulso(legs(100, 110, 104, 120, 114, 119))  # onda 5 truncada
    assert fit_imp and fit_imp.extras["truncada"] is True


def test_corretivos():
    zz = ajustar_zigzag(legs(100, 90, 96, 84))
    assert zz and zz.padrao == "zigzag" and zz.direcao == "down"
    assert ajustar_zigzag(legs(100, 90, 101, 84)) is None      # B além do início de A
    fr = ajustar_flat(legs(100, 90, 99.5, 89))
    assert fr and fr.padrao == "flat_regular"
    fe = ajustar_flat(legs(100, 90, 102, 84))
    assert fe and fe.padrao == "flat_expandido"
    frun = ajustar_flat(legs(100, 90, 102, 93))
    assert frun and frun.padrao == "flat_running"
    tri = ajustar_triangulo(legs(100, 90, 97, 91, 95.5, 92.5))
    assert tri and tri.padrao.startswith("triangulo")
    wxy = ajustar_wxy(legs(100, 90, 95, 85))
    assert wxy and wxy.padrao == "duplo_tres"
    assert {f.padrao for f in ajustar_todos(legs(100, 90, 96, 84))} >= {"zigzag"}


def test_zigzag_pivots_e_cenarios(candles_impulso):
    c, alvos = candles_impulso
    piv, limiar = zigzag_atr(c, fator_atr=2.0)
    conf = [p for p in piv if p.confirmado]
    assert len(conf) >= 5
    tipos = [p.tipo for p in conf]
    assert all(tipos[i] != tipos[i - 1] for i in range(1, len(tipos)))  # alternância
    res = analisar_serie(c, 2.0)
    assert res["n_cenarios"] >= 1
    assert res["prob_bull"] + res["prob_bear"] + res["prob_indefinido"] == pytest.approx(1.0, abs=0.01)
    assert res["prob_bull"] + res["prob_bear"] < 1.0
    assert res["primario"]["invalidacao"] is not None
    # após 5 ondas completas de alta, o cenário primário espera correção (bear) ou onda 5 estendendo
    assert res["primario"]["fase"] in ("correcao_a", "onda_5", "final_onda_3", "meio_onda_3")


def test_cenario_onda3_em_andamento():
    # onda 1 (100->110), onda 2 (110->104), onda 3 em andamento (104->114 e subindo)
    precos = [100 + 0.1 * (i % 3) for i in range(30)]
    for alvo in (110, 104, 114):
        ini = precos[-1]
        precos += [ini + (alvo - ini) * s / 8 for s in range(1, 9)]
    c = gerar_candles(precos)
    res = analisar_serie(c, 2.0)
    fases = {x["fase"] for x in res["cenarios"]}
    assert fases & {"inicio_onda_3", "meio_onda_3", "final_onda_3"}
    assert res["prob_bull"] > res["prob_bear"]
    prim = [x for x in res["cenarios"] if x["fase"].endswith("onda_3")][0]
    assert prim["invalidacao"] == pytest.approx(104, abs=0.5)
    assert prim["alvos"] and prim["alvos"][0] > 114


def test_scenario_engine_invalidacao_remove_cenarios():
    c = gerar_candles([100 + i for i in range(60)])
    piv, limiar = zigzag_atr(c, 2.0)
    eng = ScenarioEngine(piv, preco_atual=c[-1][4], limiar=limiar)
    cen = eng.gerar()
    for x in cen:
        if x.vies == "bull" and x.invalidacao is not None:
            assert c[-1][4] >= x.invalidacao


def test_multigrau_timeframes_e_alinhamento():
    cfg = timeframes_do_perfil("scalping", "1m")
    assert cfg["operacional"] == "1m" and cfg["contexto"] == "15m" and cfg["macro"] == "1h"
    cfg2 = timeframes_do_perfil("daytrade", "4h")  # contexto padrão (4h) não pode ser <= operacional
    assert cfg2["contexto"] != "4h"
    precos, _ = impulso_5_ondas(passos=10)
    c = gerar_candles([100] * 40 + precos, dur_ms=60_000)
    an = AnaliseMultiGrau(lambda tf, n: c[-n:], "BTCUSDT", "scalping", "1m", "conservador")
    r = an.analisar(ohlcv_operacional=c)
    assert set(r["graus"]) == {"operacional", "contexto", "macro"}
    assert r["alinhamento"]["direcao"] in ("buy", "sell", "hold")
    s = an.sinal_saida("buy")
    assert "sair" in s
