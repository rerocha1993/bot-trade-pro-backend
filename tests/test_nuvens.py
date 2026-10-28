"""Nuvens do TRDR: categorias e top levels no coletor, leitura mista (antigo + novo), overlay e top agregado, rotas."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conselho import coletor_livro as cl
from conselho import livro_historico as lh
from tests.test_coletor_livro import registro_falso

T0 = 1_760_918_400  # 2025-10-20 00:00 UTC


# ----------------------------------------------------------------- livros falsos
def livro_escada(mid=100_000.0, passo=10.0, niveis=3000, qtd=1.0):
    """1 BTC a cada 10 USD dos dois lados até ~30% (passa das cinco categorias)."""
    bids = [(mid - passo * (i + 0.5), qtd) for i in range(niveis)]
    asks = [(mid + passo * (i + 0.5), qtd) for i in range(niveis)]
    return bids, asks


# ----------------------------------------------------------------- coletor: categorias e top 10
def test_categorias_medidas_do_melhor_bid_ask():
    melhor_bid, melhor_ask = 99_995.0, 100_005.0
    bids = [(melhor_bid, 1.0), (melhor_bid * (1 - 0.005), 2.0), (melhor_bid * (1 - 0.02), 3.0),
            (melhor_bid * (1 - 0.04), 4.0), (melhor_bid * (1 - 0.07), 5.0), (melhor_bid * (1 - 0.20), 6.0),
            (melhor_bid * (1 - 0.30), 100.0)]           # 30%: fora das categorias
    asks = [(melhor_ask, 1.5), (melhor_ask * (1 + 0.0099), 2.5), (melhor_ask * (1 + 0.0251), 3.5),
            (melhor_ask * (1 + 0.049), 4.5), (melhor_ask * (1 + 0.1001), 5.5), (melhor_ask * (1 + 0.249), 6.5)]
    c = cl.categorias_trdr(bids, asks)
    assert c["cat_pct"] == [0.0, 0.01, 0.025, 0.05, 0.10, 0.25]
    assert c["cat_bids"] == [3.0, 3.0, 4.0, 5.0, 6.0]
    assert c["cat_asks"] == [4.0, 0.0, 8.0, 0.0, 12.0]
    assert c["alcance_bids_pct"] == pytest.approx(0.30, abs=1e-6)
    assert c["alcance_asks_pct"] == pytest.approx(0.249, abs=1e-6)


def test_categorias_escada_e_alcance():
    bids, asks = livro_escada()
    c = cl.categorias_trdr(bids, asks)
    # 1% de ~100k = ~1000 USD = ~100 níveis de 1 BTC; cada categoria tem (hi-lo)% × 1000 níveis
    assert c["cat_bids"] == pytest.approx([100, 150, 250, 500, 1500], abs=2)
    assert c["cat_asks"] == pytest.approx([100, 150, 250, 500, 1500], abs=2)
    assert c["alcance_bids_pct"] == pytest.approx(0.30, abs=0.001)


def test_binance_curto_nao_alcanca_alem_de_1pct():
    bids, asks = livro_escada(niveis=105)        # ~1,05% por lado, como o depth 5000 da Binance
    c = cl.categorias_trdr(bids, asks)
    assert c["cat_bids"][0] == 100 and c["cat_bids"][1] == 5 and c["cat_bids"][2:] == [0, 0, 0]
    reg = {"alcance_bids_pct": c["alcance_bids_pct"], "alcance_asks_pct": c["alcance_asks_pct"]}
    assert cl.categorias_alcancadas(reg, "bids") == [True, False, False, False, False]
    assert cl.categorias_alcancadas({}, "asks") == [False] * 5      # registro antigo: nada garantido


def test_top_10_por_quantidade_dentro_de_25pct():
    bids = [(99_995.0 - 10 * i, 1.0) for i in range(50)]
    bids[7] = (bids[7][0], 40.0)
    bids[20] = (bids[20][0], 25.0)
    bids.append((60_000.0, 999.0))                                   # 40% abaixo: lixo, não entra
    asks = [(100_005.0 + 10 * i, 1.0 + i * 0.01) for i in range(50)]
    t = cl.top_niveis(bids, asks)
    assert len(t["top_bids"]) == 10 and len(t["top_asks"]) == 10
    assert t["top_bids"][0] == [bids[7][0], 40.0] and t["top_bids"][1] == [bids[20][0], 25.0]
    assert all(q == 1.0 for _, q in t["top_bids"][2:])
    assert 60_000.0 not in [p for p, _ in t["top_bids"]]
    # asks: quantidades crescentes com o preço → os 10 mais longe (e empate resolvido pelo preço)
    assert [p for p, _ in t["top_asks"]] == [asks[49 - i][0] for i in range(10)]


def test_coletor_grava_campos_novos_sem_mexer_nos_antigos(tmp_path):
    bids, asks = livro_escada()
    col = cl.ColetorLivro(raiz=str(tmp_path), buscadores={"coinbase": lambda: (bids, asks)})
    r = col.coletar_uma_vez()["coinbase"]
    antigos = ["ts", "exchange", "simbolo", "mid", "melhor_bid", "melhor_ask", "faixa_pct", "limite_pct", "bids", "asks",
               "total_bids", "total_asks", "fora_bids", "fora_asks", "niveis_bids", "niveis_asks", "latencia_ms"]
    assert list(r)[:len(antigos)] == antigos                        # ordem e nomes antigos intactos
    assert len(r["bids"]) == 50 and len(r["asks"]) == 50
    assert len(r["cat_bids"]) == 5 and len(r["top_bids"]) == 10 and len(r["top_asks"]) == 10
    assert r["alcance_bids_pct"] > 0.25
    lido = lh.carregar_dia("coinbase", cl.dia_utc(r["ts"]), str(tmp_path))[0]
    assert lido["cat_bids"] == r["cat_bids"] and lido["top_asks"] == r["top_asks"]


# ----------------------------------------------------------------- leitura mista e overlay
def registro_novo(ts, exchange, mid, cat_b, cat_a, alcance=0.30, top_b=None, top_a=None):
    r = registro_falso(ts, exchange, mid)
    r.update({"cat_pct": list(cl.CATEGORIAS_PCT), "cat_bids": cat_b, "cat_asks": cat_a,
              "alcance_bids_pct": alcance, "alcance_asks_pct": alcance,
              "top_bids": top_b or [], "top_asks": top_a or []})
    return r


def test_categorias_de_registro_antigo_saem_das_faixas():
    bids = [0.0] * 50
    bids[0], bids[9], bids[10], bids[24], bids[25], bids[49] = 1, 2, 3, 4, 5, 6
    asks = [1.0] * 12 + [0.0] * 38                                  # como a Binance antiga: ~1,2%
    c = lh.categorias_do_registro(registro_falso(T0, "binance", 100_000.0, bids, asks))
    assert c["aproximado"] is True
    assert c["bids"] == [3, 7, 11, 0, 0]
    assert c["asks"] == [10, 2, 0, 0, 0]
    assert c["alcance"]["bids"] == [True, True, True, False, False]    # chegou à faixa 49 = 5%
    assert c["alcance"]["asks"] == [True, False, False, False, False]  # parou em 1,2%
    novo = lh.categorias_do_registro(registro_novo(T0, "coinbase", 100_000.0, [1, 2, 3, 4, 5], [5, 4, 3, 2, 1]))
    assert novo["aproximado"] is False and novo["bids"] == [1, 2, 3, 4, 5]
    assert novo["alcance"]["asks"] == [True] * 5


def test_serie_overlay_mistura_antigo_e_novo_e_soma_exchanges(tmp_path):
    raiz = str(tmp_path)
    # passo 0 (T0..T0+299): coinbase nova + binance antiga, 2 snapshots cada (média dentro do passo)
    for k in range(2):
        cl.gravar_snapshot(registro_novo(T0 + 30 * k, "coinbase", 100_000.0, [10, 20, 30, 40, 50], [5, 20, 10, 40, 10]), raiz)
        bids = [1.0] * 12 + [0.0] * 38
        asks = [2.0] * 12 + [0.0] * 38
        cl.gravar_snapshot(registro_falso(T0 + 30 * k, "binance", 100_100.0, bids, asks), raiz)
    # passo 1: só bybit, nova, mas com alcance curto (0,1%)
    cl.gravar_snapshot(registro_novo(T0 + 300, "bybit", 100_000.0, [3, 0, 0, 0, 0], [1, 0, 0, 0, 0], alcance=0.001), raiz)
    # fora do período
    cl.gravar_snapshot(registro_novo(T0 + 900, "bybit", 100_000.0, [9, 0, 0, 0, 0], [9, 0, 0, 0, 0]), raiz)

    s = lh.serie_overlay(T0, T0 + 600, ("coinbase", "binance", "bybit"), raiz, passo_s=300)
    assert s["passo_s"] == 300 and [c["rotulo"] for c in s["categorias"]] == list(cl.ROTULOS_CATEGORIAS)
    assert [p["ts"] for p in s["pontos"]] == [T0, T0 + 300]
    p0 = s["pontos"][0]
    assert p0["exchanges"] == ["coinbase", "binance"] and p0["aproximado"] is True
    assert p0["bids"] == pytest.approx([20, 22, 30, 40, 50])       # 10 + 10 faixas da binance; 20 + 2 faixas
    assert p0["asks"] == pytest.approx([25, 24, 10, 40, 10])
    assert p0["razao"][2] == pytest.approx(3.0) and p0["vantagem"][2] == "bids"
    assert p0["vantagem"][0] == "asks" and p0["forca"][0] == pytest.approx((20 - 25) / 45, abs=1e-4)
    assert p0["vantagem"][3] is None and p0["forca"][3] == 0.0
    assert p0["cobertura"] == [["coinbase", "binance"], ["coinbase"], ["coinbase"], ["coinbase"], ["coinbase"]]
    assert p0["mid"] == pytest.approx(100_050.0)
    p1 = s["pontos"][1]
    assert p1["exchanges"] == ["bybit"] and p1["aproximado"] is False
    assert p1["cobertura"] == [[], [], [], [], []]
    assert p1["razao"][1] is None and p1["total_bids"] == 3 and p1["forca_total"] == pytest.approx(0.5)
    f = s["fontes"]
    assert f["coinbase"]["snapshots"] == 2 and f["coinbase"]["aproximados"] == 0 and f["coinbase"]["alcance_bids_pct"] == 0.30
    assert f["binance"]["aproximados"] == 2 and f["binance"]["alcance_asks_pct"] == pytest.approx(0.012)
    assert f["bybit"]["snapshots"] == 1 and f["bybit"]["ultimo_ts"] == T0 + 300
    # regra do TRDR: só o snapshot do fechamento do candle (o último do passo) conta
    cl.gravar_snapshot(registro_novo(T0 + 290, "coinbase", 100_000.0, [7, 7, 7, 7, 7], [1, 2, 3, 4, 5]), raiz)
    fe = lh.serie_overlay(T0, T0 + 600, ("coinbase",), raiz, passo_s=300, amostra="fechamento")["pontos"][0]
    assert fe["bids"] == pytest.approx([7] * 5) and fe["asks"] == pytest.approx([1, 2, 3, 4, 5])
    me = lh.serie_overlay(T0, T0 + 600, ("coinbase",), raiz, passo_s=300)["pontos"][0]
    assert me["bids"][0] == pytest.approx((10 + 10 + 7) / 3)
    # exchange escolhida sem dados no período: ponto não a lista, fonte zerada
    s2 = lh.serie_overlay(T0, T0 + 100, ("bybit",), raiz)
    assert s2["pontos"] == [] and s2["fontes"]["bybit"]["snapshots"] == 0 and s2["fontes"]["bybit"]["alcance_bids_pct"] is None


def test_top_agregado_junta_precos_na_grade_de_0_05pct(tmp_path):
    raiz = str(tmp_path)
    cl.gravar_snapshot(registro_novo(T0, "coinbase", 100_000.0, [1] * 5, [1] * 5,
                                     top_b=[[99_000.0, 10.0], [98_000.0, 4.0]], top_a=[[101_000.0, 7.0]]), raiz)
    cl.gravar_snapshot(registro_novo(T0 + 1, "binance", 100_000.0, [1] * 5, [1] * 5,
                                     top_b=[[99_020.0, 6.0], [97_000.0, 5.0]], top_a=[[101_500.0, 2.0]]), raiz)
    t = lh.top_agregado(None, ("coinbase", "binance"), raiz)
    assert t["ts"] == T0 + 1 and t["mid"] == 100_000.0 and t["aproximado"] is False
    assert sorted(t["exchanges"]) == ["binance", "coinbase"]
    # 99 000 (coinbase) e 99 020 (binance) distam 0,02% < grade de 0,05% → um nível só, preço médio ponderado
    assert t["bids"][0]["qtd"] == 16.0 and t["bids"][0]["exchanges"] == ["coinbase", "binance"]
    assert t["bids"][0]["preco"] == pytest.approx((99_000 * 10 + 99_020 * 6) / 16, abs=0.01)
    assert [b["qtd"] for b in t["bids"]] == [16.0, 5.0, 4.0]
    assert [a["qtd"] for a in t["asks"]] == [7.0, 2.0]
    # com ts no passado, respeita a tolerância
    assert lh.top_agregado(T0 - 1000, ("coinbase",), raiz)["bids"] == []
    assert lh.top_agregado(T0 + 100, ("coinbase",), raiz)["bids"][0]["qtd"] == 10.0


def test_top_agregado_registro_antigo_usa_faixas(tmp_path):
    raiz = str(tmp_path)
    bids = [1.0] * 50
    bids[19] = 50.0
    cl.gravar_snapshot(registro_falso(T0, "coinbase", 100_000.0, bids, [1.0] * 50), raiz)
    t = lh.top_agregado(None, ("coinbase",), raiz)
    assert t["aproximado"] is True
    assert t["bids"][0]["qtd"] == 50.0 and t["bids"][0]["preco"] == pytest.approx(98_050.0)
    assert len(t["bids"]) == 10 and len(t["asks"]) == 10
    assert lh.top_agregado(None, ("bybit",), raiz) == {"ts": None, "mid": None, "bids": [], "asks": [], "exchanges": [], "aproximado": False}


# ----------------------------------------------------------------- rotas
@pytest.fixture
def cliente(tmp_path, monkeypatch):
    raiz = str(tmp_path)
    import api.routes.nuvens_routes as nr
    serie, top_ag, ult = lh.serie_overlay, lh.top_agregado, lh.ultimo_ts
    monkeypatch.setattr(nr.lh, "serie_overlay", lambda *a, **k: serie(*a, raiz=raiz, **k))
    monkeypatch.setattr(nr.lh, "top_agregado", lambda ts, exs: top_ag(ts, exs, raiz))
    monkeypatch.setattr(nr.lh, "ultimo_ts", lambda exs: ult(exs, raiz))
    calor = lh.mapa_calor
    monkeypatch.setattr(nr.lh, "mapa_calor", lambda *a, **k: calor(*a, raiz=raiz, **k))
    for k in range(3):
        cl.gravar_snapshot(registro_novo(T0 + 300 * k, "coinbase", 100_000.0, [1, 2, 3, 4, 5], [5, 4, 3, 2, 1],
                                         top_b=[[99_000.0, 10.0]], top_a=[[101_000.0, 7.0]]), raiz)
    app = FastAPI()
    app.include_router(nr.router, prefix="/api/nuvens")
    return TestClient(app)


def test_rota_overlay(cliente):
    r = cliente.get("/api/nuvens/overlay", params={"inicio": T0, "fim": T0 + 700, "exchanges": "coinbase"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["inicio"] == T0 and d["fim"] == T0 + 700 and d["exchanges"] == ["coinbase"] and d["passo_s"] == 300
    assert len(d["pontos"]) == 3 and d["pontos"][0]["vantagem"] == ["asks", "asks", None, "bids", "bids"]
    assert d["ultimo_ts"] == T0 + 600 and list(d["limitacoes"]) == ["coinbase"]
    assert d["fontes"]["coinbase"]["snapshots"] == 3
    assert cliente.get("/api/nuvens/overlay", params={"exchanges": "kraken"}).status_code == 400
    assert cliente.get("/api/nuvens/overlay", params={"inicio": T0 + 10, "fim": T0}).status_code == 400
    assert cliente.get("/api/nuvens/overlay", params={"inicio": T0, "fim": T0 + 8 * 86400}).status_code == 400


def test_rota_top(cliente):
    r = cliente.get("/api/nuvens/top", params={"exchanges": "coinbase,binance"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ts"] == T0 + 600 and d["exchanges"] == ["coinbase"] and d["exchanges_pedidas"] == ["coinbase", "binance"]
    assert d["bids"] == [{"preco": 99_000.0, "qtd": 10.0, "exchanges": ["coinbase"]}]
    assert d["asks"][0]["preco"] == 101_000.0


def test_mapa_calor_acende_parede_parada_e_ignora_spoof(tmp_path):
    raiz = str(tmp_path)
    # 30 snapshots de 30 s = 3 colunas de 5 min; livro de 1 BTC por faixa (o "normal")
    for k in range(30):
        bids = [1.0] * cl.N_FAIXAS
        if k >= 20:
            bids[5] = 10.0          # parede parada na 3ª coluna inteira
        if k == 12:
            bids[8] = 10.0          # spoof: aparece num snapshot só da 2ª coluna
        cl.gravar_snapshot(registro_falso(T0 + 30 * k, "coinbase", 100_000.0, bids), raiz)
    m = lh.mapa_calor(T0, T0 + 899, ("coinbase",), raiz, passo_s=300, janela_base_s=0)
    assert m["grade_usd"] == 100.0 and [c["ts"] for c in m["colunas"]] == [T0, T0 + 300, T0 + 600]
    assert m["colunas"][0]["celulas"] == [] and m["colunas"][1]["celulas"] == []   # o spoof dilui para 1,9x
    (cel,) = m["colunas"][2]["celulas"]
    assert cel[0] == 99_400.0 and cel[1] == 99_500.0 and cel[2] == 0 and cel[3] == 10.0 and cel[4] == 10.0


def test_mapa_calor_sem_base_suficiente_nao_acende(tmp_path):
    raiz = str(tmp_path)
    for k in range(5):
        cl.gravar_snapshot(registro_falso(T0 + 30 * k, "coinbase", 100_000.0, [50.0] * cl.N_FAIXAS), raiz)
    m = lh.mapa_calor(T0, T0 + 299, ("coinbase",), raiz, janela_base_s=0)
    assert m["colunas"] == [] and m["base"] == {"coinbase": 5}


def test_rota_calor(cliente):
    r = cliente.get("/api/nuvens/calor", params={"inicio": T0, "fim": T0 + 700, "exchanges": "coinbase", "fator": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["fator_min"] == 3 and d["exchanges"] == ["coinbase"] and d["colunas"] == []   # 3 snapshots: sem base
    assert cliente.get("/api/nuvens/calor", params={"fator": 0.5}).status_code == 422
