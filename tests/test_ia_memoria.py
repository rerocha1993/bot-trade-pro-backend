"""Memória de situações (RAG): vetor da leitura, desfecho e busca de vizinhos sem olhar o futuro."""
import numpy as np
import pytest

from core.ia.memoria import NOMES, Memoria, Situacao, desfecho, normalizar_cenarios, vetor_situacao

CEN = [{"direcao_trade": "buy", "probabilidade": 0.6, "invalidacao": 95.0, "alvos": [110.0], "fase": "onda_2"},
       {"direcao_trade": "sell", "probabilidade": 0.4, "invalidacao": 104.0, "alvos": [90.0], "fase": "correcao_b"}]


def test_aceita_o_formato_do_motor_ao_vivo_e_o_do_historico():
    vivo = normalizar_cenarios(CEN)
    hist = normalizar_cenarios([{"direcao": "buy", "prob": 0.6, "inv": 95.0, "alvos": [110.0], "fase": "onda_2"}])
    assert vivo[0] == hist[0]


def test_vetor_tem_os_pesos_das_contagens_e_as_distancias_em_atr():
    v = vetor_situacao(CEN, [100.0] * 41, atr=2.0, atr_longo=2.0)
    assert len(v) == len(NOMES)
    d = dict(zip(NOMES, v))
    assert d["peso_compra"] == pytest.approx(0.6) and d["peso_venda"] == pytest.approx(0.4)
    assert d["dist_inv_atr"] == pytest.approx(2.5) and d["dist_alvo_atr"] == pytest.approx(5.0)
    assert d["fase_onda_2"] == 1.0 and d["dir_primario"] == 1


def test_desfecho_em_percentual_e_em_atr():
    fut = [[0, 100, 104, 99, 103, 1], [0, 103, 106, 97, 102, 1]]
    d = desfecho(fut, 100.0, atr=2.0)
    assert d["ret_pct"] == pytest.approx(2.0) and d["max_pct"] == pytest.approx(6.0) and d["min_pct"] == pytest.approx(-3.0)
    assert d["ret_atr"] == pytest.approx(1.0)


def _sit(ts, x, conhecido):
    v = np.zeros(len(NOMES))
    v[0] = x
    return Situacao(ts, v, 100.0, "", {"ret_pct": x, "max_pct": 1, "min_pct": -1, "ret_atr": 0, "candles": 1}, conhecido)


def test_vizinhos_so_enxergam_o_que_ja_era_conhecido():
    mem = Memoria([_sit(1, 0.50, 10), _sit(2, 0.51, 50), _sit(3, 0.90, 20)])
    alvo = np.zeros(len(NOMES))
    alvo[0] = 0.51
    assert mem.vizinhos(alvo, k=1)[0]["ts"] == 2
    assert mem.vizinhos(alvo, k=1, ate_ts=30)[0]["ts"] == 1, "a situação 2 só teria desfecho em 50"


def test_agregado_dos_vizinhos():
    viz = [{"desfecho": {"ret_pct": r, "max_pct": 2.0, "min_pct": -1.0}} for r in (1.0, -2.0, 3.0)]
    ag = Memoria.agregado(viz)
    assert ag["n"] == 3 and ag["subiram"] == pytest.approx(0.67) and ag["ret_mediano_pct"] == 1.0
