"""Coletor do livro de ordens: agregação por faixa, gravação/leitura, paredes. Sem internet."""
import gzip
import json
import os

import numpy as np
import pytest

from conselho import coletor_livro as cl
from conselho import livro_historico as lh


# ----------------------------------------------------------------- livros falsos
def livro_uniforme(mid=100_000.0, passo=10.0, niveis=600, qtd=1.0):
    """Bid/ask simétricos: níveis a cada `passo` até ~6% (passa do limite de 5%)."""
    bids = [(mid - passo * (i + 0.5), qtd) for i in range(niveis)]
    asks = [(mid + passo * (i + 0.5), qtd) for i in range(niveis)]
    return bids, asks


def registro_falso(ts, exchange="binance", mid=100_000.0, bids=None, asks=None):
    bids = bids if bids is not None else [1.0] * cl.N_FAIXAS
    asks = asks if asks is not None else [1.0] * cl.N_FAIXAS
    return {
        "ts": ts, "exchange": exchange, "simbolo": "BTCUSDT", "mid": mid,
        "melhor_bid": mid - 5, "melhor_ask": mid + 5,
        "faixa_pct": cl.FAIXA_PCT, "limite_pct": cl.LIMITE_PCT,
        "bids": list(bids), "asks": list(asks),
        "total_bids": float(sum(bids)), "total_asks": float(sum(asks)),
        "fora_bids": 0.0, "fora_asks": 0.0, "niveis_bids": 100, "niveis_asks": 100, "latencia_ms": 1,
    }


# ----------------------------------------------------------------- agregação
def test_agregacao_faixas_basica():
    bids, asks = livro_uniforme(mid=100_000.0, passo=10.0, niveis=600, qtd=1.0)
    ag = cl.agregar_livro(bids, asks)
    assert ag["melhor_bid"] == 99_995.0 and ag["melhor_ask"] == 100_005.0
    assert ag["mid"] == 100_000.0
    assert len(ag["bids"]) == 50 and len(ag["asks"]) == 50
    # 0,1% de 100k = 100 USD = 10 níveis de 10 USD com 1 BTC cada → 10 BTC por faixa
    assert all(abs(q - 10.0) < 1e-9 for q in ag["bids"])
    assert all(abs(q - 10.0) < 1e-9 for q in ag["asks"])
    assert ag["total_bids"] == pytest.approx(500.0) and ag["total_asks"] == pytest.approx(500.0)
    # 600 níveis × 10 USD = 6% → 500 níveis dentro de 5%, o 1% final (100 níveis) cai fora
    assert ag["fora_bids"] == pytest.approx(100.0) and ag["fora_asks"] == pytest.approx(100.0)
    assert ag["niveis_bids"] == 600


def test_agregacao_parede_cai_na_faixa_certa():
    bids = [(99_995.0, 1.0), (98_050.0, 50.0)]       # 1,95% abaixo → faixa 19
    asks = [(100_005.0, 1.0), (103_010.0, 30.0)]     # 3,01% acima → faixa 30
    ag = cl.agregar_livro(bids, asks)
    assert ag["bids"][0] == 1.0 and ag["bids"][19] == 50.0
    assert ag["asks"][0] == 1.0 and ag["asks"][30] == 30.0
    assert sum(ag["bids"]) == 51.0 and sum(ag["asks"]) == 31.0


def test_agregacao_livro_vazio_ou_cruzado():
    with pytest.raises(ValueError):
        cl.agregar_livro([], [(1.0, 1.0)])
    with pytest.raises(ValueError):
        cl.agregar_livro([(101.0, 1.0)], [(100.0, 1.0)])


def test_preco_da_faixa():
    assert cl.preco_da_faixa(100_000.0, "bids", 0) == pytest.approx(99_950.0)
    assert cl.preco_da_faixa(100_000.0, "asks", 19) == pytest.approx(101_950.0)


def test_pares_ignora_lixo():
    assert cl._pares([["1", "2"], ["x", "1"], ["3", "0"], ["4"], ["5", "6", "extra"]]) == [(1.0, 2.0), (5.0, 6.0)]


# ----------------------------------------------------------------- gravação e leitura
def test_grava_le_e_append_por_dia(tmp_path):
    raiz = str(tmp_path)
    ts0 = 1_760_918_400  # 2025-10-20 00:00 UTC
    r1 = registro_falso(ts0, mid=100_000.0)
    r2 = registro_falso(ts0 + 30, mid=100_010.0)
    r3 = registro_falso(ts0 + 86_400, mid=100_020.0)   # dia seguinte
    c1 = cl.gravar_snapshot(r1, raiz)
    c2 = cl.gravar_snapshot(r2, raiz)
    c3 = cl.gravar_snapshot(r3, raiz)
    assert c1 == c2 and c1 != c3
    assert c1.endswith(os.path.join("binance", "2025-10-20.jsonl.gz"))
    assert c3.endswith("2025-10-21.jsonl.gz")
    # append gzip: dois membros no mesmo arquivo, lidos de uma vez
    with gzip.open(c1, "rt", encoding="utf-8") as f:
        linhas = [json.loads(l) for l in f if l.strip()]
    assert [l["mid"] for l in linhas] == [100_000.0, 100_010.0]

    regs = lh.carregar_dia("binance", "2025-10-20", raiz)
    assert [r["ts"] for r in regs] == [ts0, ts0 + 30]
    assert lh.dias_disponiveis("binance", raiz) == ["2025-10-20", "2025-10-21"]
    periodo = lh.carregar_periodo("binance", ts0 + 10, ts0 + 86_400, raiz)
    assert [r["ts"] for r in periodo] == [ts0 + 30, ts0 + 86_400]
    assert lh.carregar_dia("coinbase", "2025-10-20", raiz) == []


def test_matriz_tempo_por_faixa(tmp_path):
    raiz = str(tmp_path)
    ts0 = 1_760_918_400
    for k in range(5):
        bids = [float(k)] * cl.N_FAIXAS
        asks = [float(10 + k)] * cl.N_FAIXAS
        cl.gravar_snapshot(registro_falso(ts0 + 30 * k, "bybit", 100_000.0 + k, bids, asks), raiz)
    m = lh.carregar_matrizes("2025-10-20", raiz)
    assert set(m) == set(cl.EXCHANGES)
    assert m["bybit"]["bids"].shape == (5, 50) and m["bybit"]["asks"].shape == (5, 50)
    assert m["bybit"]["ts"].tolist() == [ts0 + 30 * k for k in range(5)]
    assert np.allclose(m["bybit"]["bids"][:, 0], [0, 1, 2, 3, 4])
    assert np.allclose(m["bybit"]["asks"][3], 13.0)
    assert m["coinbase"]["bids"].shape == (0, 50)
    # registro com menos faixas é completado com zero
    curto = lh.matriz([registro_falso(ts0, bids=[5.0] * 10, asks=[1.0] * 100)])
    assert curto["bids"][0, 9] == 5.0 and curto["bids"][0, 10] == 0.0


# ----------------------------------------------------------------- paredes
def test_paredes_marca_faixa_3x_mediana_24h():
    ts_ref = 1_760_918_400 + 86_400
    historico = []
    for k in range(200):   # 200 snapshots nas 24 h anteriores, 1 BTC por faixa, ruído leve
        bids = [1.0 + 0.01 * (k % 3)] * cl.N_FAIXAS
        asks = [2.0 + 0.01 * (k % 3)] * cl.N_FAIXAS
        historico.append(registro_falso(ts_ref - 86_400 + 400 * k, bids=bids, asks=asks))
    # snapshot antigo (fora da janela) com valores absurdos NÃO deve entrar na mediana
    historico.append(registro_falso(ts_ref - 2 * 86_400, bids=[1000.0] * cl.N_FAIXAS, asks=[1000.0] * cl.N_FAIXAS))

    bids = [1.0] * cl.N_FAIXAS
    asks = [2.0] * cl.N_FAIXAS
    bids[19] = 3.5        # 3,5× a mediana (~1,01) → parede
    bids[40] = 2.9        # < 3× → não
    asks[5] = 6.1         # 3,05× (mediana ~2,01) → parede
    snap = registro_falso(ts_ref, mid=100_000.0, bids=bids, asks=asks)

    p = lh.paredes(snap, historico, fator=3.0)
    assert [x["faixa"] for x in p["bids"]] == [19]
    assert [x["faixa"] for x in p["asks"]] == [5]
    pb = p["bids"][0]
    assert pb["qtd"] == 3.5 and pb["distancia_pct"] == pytest.approx(1.95)
    assert pb["preco"] == pytest.approx(98_050.0)
    assert pb["razao"] >= 3.0
    # fator menor marca também a faixa 40
    p2 = lh.paredes(snap, historico, fator=2.5)
    assert sorted(x["faixa"] for x in p2["bids"]) == [19, 40]


def test_paredes_sem_historico_suficiente_nao_marca():
    ts_ref = 1_760_918_400
    hist = [registro_falso(ts_ref - 60 * k) for k in range(1, 5)]   # só 4 snapshots
    snap = registro_falso(ts_ref, bids=[100.0] * cl.N_FAIXAS)
    assert lh.paredes(snap, hist) == {"bids": [], "asks": []}
    # histórico só no futuro também não conta
    hist_futuro = [registro_falso(ts_ref + 60 * k) for k in range(1, 30)]
    assert lh.paredes(snap, hist_futuro) == {"bids": [], "asks": []}


def test_mediana_por_faixa_sem_dados_eh_nan():
    med = lh.mediana_por_faixa([], ts_ref=0)
    assert med["bids"].shape == (cl.N_FAIXAS,) and np.all(np.isnan(med["bids"]))


# ----------------------------------------------------------------- coletor (falha isolada)
def test_coletor_uma_exchange_falha_outras_gravam(tmp_path):
    raiz = str(tmp_path)
    bids, asks = livro_uniforme()

    def quebrado():
        raise ConnectionError("sem rede")

    buscadores = {"coinbase": lambda: (bids, asks), "binance": quebrado, "bybit": lambda: (bids, asks)}
    col = cl.ColetorLivro(raiz=raiz, intervalo_s=0.01, buscadores=buscadores)
    res = col.coletar_uma_vez()
    assert res["coinbase"] is not None and res["bybit"] is not None and res["binance"] is None
    assert col.contagem == {"coinbase": 1, "binance": 0, "bybit": 1}
    assert col.falhas == {"coinbase": 0, "binance": 1, "bybit": 0}
    assert res["coinbase"]["simbolo"] == "BTC-USD" and res["bybit"]["simbolo"] == "BTCUSDT"
    assert os.path.isdir(os.path.join(raiz, "coinbase")) and os.path.isdir(os.path.join(raiz, "bybit"))
    assert not os.path.exists(os.path.join(raiz, "binance"))
    dia = cl.dia_utc(res["coinbase"]["ts"])
    regs = lh.carregar_dia("coinbase", dia, raiz)
    assert len(regs) == 1 and regs[0]["total_bids"] == pytest.approx(500.0)


def test_coletor_rodar_com_duracao_para_sozinho(tmp_path):
    bids, asks = livro_uniforme()
    col = cl.ColetorLivro(raiz=str(tmp_path), intervalo_s=0.05,
                          buscadores={"bybit": lambda: (bids, asks)})
    col.rodar(duracao_s=0.3)
    assert col.contagem["bybit"] >= 3
    regs = lh.carregar_dia("bybit", cl.dia_utc(col.ultimo["bybit"]["ts"]), str(tmp_path))
    assert len(regs) == col.contagem["bybit"]


def test_coletor_falha_na_gravacao_nao_derruba(tmp_path):
    bids, asks = livro_uniforme()

    def gravar_quebrado(registro, raiz):
        raise OSError("disco cheio")

    col = cl.ColetorLivro(raiz=str(tmp_path), buscadores={"binance": lambda: (bids, asks)}, gravar=gravar_quebrado)
    assert col.coletar_uma_vez() == {"binance": None}
    assert col.falhas["binance"] == 1
