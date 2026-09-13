"""Scalp de volatilidade: detector, single prints e as duas jogadas, com as regras de execução do backtest."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from core.scalp_volatilidade import (BARRA_MS, EstudoScalpVol, ParametrosScalpVol, escolher_zona, simular,
                                     zonas_single_print)

SEGUNDA = int(dt.datetime(2026, 9, 14, tzinfo=dt.timezone.utc).timestamp() * 1000)
P = ParametrosScalpVol()


def test_a_data_base_e_segunda_feira():
    assert pd.Timestamp(SEGUNDA, unit="ms").dayofweek == 0


# ------------------------------------------------------------------ detector
def _mercado_parado(n, pico_em=None):
    ts = SEGUNDA + np.arange(n) * BARRA_MS
    df = pd.DataFrame({"timestamp": ts, "open": 100.0, "high": 100.05, "low": 99.95, "close": 100.0, "volume": 10.0})
    if pico_em is not None:
        df.loc[pico_em, ["high", "low", "volume"]] = [100.5, 99.5, 100.0]
    return df


def test_detector_acende_no_pico_de_volatilidade_e_volume():
    p = ParametrosScalpVol(base_barras=288)
    est = EstudoScalpVol(_mercado_parado(1000, pico_em=700), p)         # 700 = quarta-feira
    cand = est.candidatos("volatil")
    assert 700 in cand and all(700 <= i <= 702 for i in cand)


def test_detector_nao_opera_no_fim_de_semana():
    p = ParametrosScalpVol(base_barras=288)
    est = EstudoScalpVol(_mercado_parado(1700, pico_em=1500), p)        # 1500 = sábado de manhã
    assert pd.Timestamp(int(est.ts[1500]), unit="ms").dayofweek == 5
    assert len(est.candidatos("volatil")) == 0


# ------------------------------------------------------------------ single prints
def test_zona_single_print_no_meio_do_impulso_e_sem_as_caudas():
    p = ParametrosScalpVol(tick_pct=0.001)                              # faixa de 0,1 no preço 100
    altos = [100.2, 100.3, 110.0, 115.0, 114.0, 116.0]
    baixos = [95.0, 97.0, 100.0, 109.8, 110.0, 111.0]
    zonas = zonas_single_print(altos, baixos, 100.0, p)
    assert len(zonas) == 1, "as pontas (95-97 e 115-116) são caudas, não single print"
    lo, hi = zonas[0]
    assert lo == pytest.approx(100.3, abs=0.2) and hi == pytest.approx(109.8, abs=0.2)


def test_escolhe_o_vacuo_atras_do_preco():
    zonas = [(100.0, 105.0), (108.0, 110.0), (120.0, 125.0)]
    assert escolher_zona(zonas, 115.0, 1) == (108.0, 110.0)
    assert escolher_zona(zonas, 115.0, -1) == (120.0, 125.0)
    assert escolher_zona(zonas, 99.0, 1) is None


# ------------------------------------------------------------------ jogadas
def _barras(linhas, fds=None):
    """linhas: (alto, baixo, fechamento) a partir do candle da detecção (índice 0)."""
    ts = SEGUNDA + np.arange(len(linhas)) * BARRA_MS
    h = np.array([x[0] for x in linhas], dtype=float)
    l = np.array([x[1] for x in linhas], dtype=float)
    c = np.array([x[2] for x in linhas], dtype=float)
    return ts, h, l, c, np.array(fds if fds is not None else [False] * len(linhas))


ZONA = (100.0, 105.0)       # impulso de alta deixou o vácuo entre 100 e 105; preço em 108


def test_a_favor_tira_o_risco_em_1r_e_sai_no_alvo():
    ts, h, l, c, fds = _barras([(108, 107, 108), (108, 106, 107), (107, 104.9, 105.5), (111, 105.2, 110), (116, 110, 115)])
    r = simular(0, ts, h, l, c, fds, ZONA, 1, "A", P)
    assert r["motivo"] == "alvo" and r["lado"] == 1
    assert r["bruto_r"] == pytest.approx(1.5, abs=0.01), "metade em 1R + metade em 2R"
    assert r["liquido_r"] == pytest.approx(1.49, abs=0.01)


def test_stop_e_alvo_no_mesmo_candle_conta_o_stop():
    ts, h, l, c, fds = _barras([(108, 107, 108), (108, 106, 107), (107, 104.9, 105.5), (116, 99, 110)])
    r = simular(0, ts, h, l, c, fds, ZONA, 1, "A", P)
    assert r["motivo"] == "stop" and -1.05 < r["liquido_r"] < -1.0


def test_no_candle_da_entrada_so_vale_o_stop():
    ts, h, l, c, fds = _barras([(108, 107, 108), (108, 106, 107), (107, 99, 100)])
    r = simular(0, ts, h, l, c, fds, ZONA, 1, "A", P)
    assert r["motivo"] == "stop"


def test_preenchimento_vende_na_borda_e_sai_na_outra():
    ts, h, l, c, fds = _barras([(108, 107, 108), (108, 106, 107), (107, 104.9, 105.5), (106, 99.8, 100.5)])
    r = simular(0, ts, h, l, c, fds, ZONA, 1, "B", P)
    assert r["motivo"] == "alvo" and r["lado"] == -1
    assert r["bruto_r"] == pytest.approx(1.0, abs=0.001)


def test_ordem_que_executaria_no_fim_de_semana_nao_opera():
    ts, h, l, c, fds = _barras([(108, 107, 108), (108, 106, 107), (107, 104.9, 105.5)], fds=[False, False, True])
    assert simular(0, ts, h, l, c, fds, ZONA, 1, "A", P) is None


def test_ordem_que_nao_executa_vence():
    ts, h, l, c, fds = _barras([(108, 107, 108)] + [(109, 106, 108)] * 30)
    assert simular(0, ts, h, l, c, fds, ZONA, 1, "A", P) is None
