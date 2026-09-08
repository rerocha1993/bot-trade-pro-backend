"""Camada 1: cada indicador independente devolve uma Leitura padronizada, sem exceção e sem saber dos outros."""
import pytest

from conftest import gerar_candles
from core.leituras import (
    Leitura, Nivel, leitura_elliott, leitura_fibonacci, leitura_order_block, leitura_order_flow, leitura_regime,
    leitura_sentimento, leitura_tpo, leitura_volume_profile, leitura_vwap, niveis_de,
)

ADAPTADORES_OHLCV = ["tpo", "volume_profile", "vwap", "order_block", "regime"]


def _ler_todos(ohlcv, preco):
    return [
        leitura_tpo(ohlcv, preco),
        leitura_volume_profile(ohlcv, preco),
        leitura_vwap(ohlcv, preco),
        leitura_order_block(ohlcv, preco),
        leitura_regime(ohlcv),
    ]


def test_leitura_tem_contrato_estavel(candles_impulso):
    ohlcv, _ = candles_impulso
    preco = ohlcv[-1][4]
    for l in _ler_todos(ohlcv, preco):
        assert isinstance(l, Leitura)
        assert l.vies in ("bull", "bear", "neutro")
        assert 0.0 <= l.forca <= 1.0
        assert l.acao in ("buy", "sell", "hold")
        assert l.ts > 0
        assert all(isinstance(n, Nivel) for n in l.niveis)
        d = l.dict()
        assert set(("fonte", "vies", "forca", "acao", "niveis", "motivo", "valida")) <= set(d)


def test_nenhum_adaptador_levanta_com_entrada_ruim():
    """Entrada degenerada tem que virar leitura neutra com erro, nunca exceção: o orquestrador não pode quebrar."""
    lixo = [[0, 0, 0, 0, 0, 0]]
    leituras = _ler_todos(lixo, 0.0) + [
        leitura_order_flow({}, [], lixo),
        leitura_fibonacci(lixo, "meio_onda_3", "buy"),
        leitura_elliott(None, 0.0),
        leitura_sentimento(None),
    ]
    for l in leituras:
        assert isinstance(l, Leitura)
        assert l.vies in ("bull", "bear", "neutro")


def test_forca_fica_no_intervalo():
    l = Leitura("teste", forca=9.9)
    assert l.forca == 1.0
    assert Leitura("teste", forca=-3).forca == 0.0
    assert Leitura("teste", vies="inventado").vies == "neutro"


def test_niveis_saem_com_lado_correto(candles_impulso):
    ohlcv, _ = candles_impulso
    preco = ohlcv[-1][4]
    for l in _ler_todos(ohlcv, preco):
        for n in l.niveis:
            esperado = "resistencia" if n.preco > preco else "suporte" if n.preco < preco else "referencia"
            assert n.tipo == esperado, f"{l.fonte}: nível {n.preco} classificado como {n.tipo} com preço {preco}"


def test_niveis_de_ignora_leituras_com_erro():
    boa = Leitura("boa", niveis=[Nivel(100.0, "suporte", "x", 1.0)])
    ruim = Leitura("ruim", niveis=[Nivel(200.0, "resistencia", "y", 1.0)], erro="explodiu")
    saida = niveis_de([boa, ruim])
    assert [n["preco"] for n in saida] == [100.0]


def test_sentimento_e_contrario():
    """Euforia é viés de baixa e medo é viés de alta: a regra do usuário, não a do indicador."""
    assert leitura_sentimento({"score": 0.8, "zona": "ganancia"}).vies == "bear"
    assert leitura_sentimento({"score": -0.8, "zona": "medo"}).vies == "bull"
    assert leitura_sentimento({"score": 0.1, "zona": "neutro"}).vies == "neutro"


def test_elliott_vira_leitura_com_invalidacao_e_alvos():
    grau = {
        "fase": "meio_onda_3", "direcao": "buy", "prob_bull": 0.7, "prob_bear": 0.2,
        "primario": {"nome": "Impulso de alta", "invalidacao": 90.0, "alvos": [120.0, 130.0], "vies": "bull"},
        "alternativos": [],
    }
    l = leitura_elliott(grau, preco=100.0)
    assert l.vies == "bull" and l.forca == pytest.approx(0.7)
    fontes = {n.fonte for n in l.niveis}
    assert "elliott_invalidacao" in fontes and "elliott_alvo" in fontes
    inval = next(n for n in l.niveis if n.fonte == "elliott_invalidacao")
    assert inval.tipo == "suporte"


def test_leitura_expira():
    l = Leitura("teste", validade_s=0, ts=1)
    assert not l.valida


def test_vwap_reage_a_preco_esticado():
    """Indicador independente de verdade: só olha os próprios candles e o preço, mais nada."""
    ohlcv = gerar_candles([100.0] * 60)
    perto = leitura_vwap(ohlcv, 100.0)
    longe = leitura_vwap(ohlcv, 130.0)
    assert longe.forca >= perto.forca
    assert longe.vies == "bull"
