"""TPO por dia/sessão/merge, como no TradingView e como o Tradeiros usa."""
import pytest

from conselho.tpo import (
    BLOCO_MS, DIA_MS, Perfil, blocos_30m, dias, merge, naked_pocs, sessoes, tick_para,
)

T0 = 1_780_000_000_000 - (1_780_000_000_000 % DIA_MS)


def _bloco(i, h, l, dia=0, v=10.0):
    ts = T0 + dia * DIA_MS + i * BLOCO_MS
    return (ts, (h + l) / 2, h, l, (h + l) / 2, v)


def test_tick_e_0_1_por_cento_arredondado():
    assert tick_para(80_000) == 80.0
    assert tick_para(76_543) == 80.0
    assert tick_para(30_000) == 30.0


def test_candles_de_15m_viram_blocos_de_30m():
    c = [[T0, 100, 101, 99, 100.5, 1], [T0 + 900_000, 100.5, 103, 100, 102, 2], [T0 + 1_800_000, 102, 102, 98, 99, 3]]
    b = blocos_30m(c)
    assert len(b) == 2 and b[0][2] == 103 and b[0][3] == 99 and b[0][5] == 3


def test_poc_e_area_de_valor():
    # 10 blocos em 100-101, 2 em 101-103, 2 em 97-100: o valor fica em volta de 100-101
    bl = [_bloco(i, 101.0, 100.0) for i in range(10)] + [_bloco(10 + i, 103.0, 101.0) for i in range(2)] \
        + [_bloco(12 + i, 100.0, 97.0) for i in range(2)]
    p = Perfil(bl, tick=1.0)
    assert 100.0 <= p.poc() <= 101.0
    val, vah = p.area_valor()
    assert val <= 100.0 and vah >= 101.0 and (vah - val) < (p.maxima - p.minima)


def test_cauda_compradora_na_minima():
    # um bloco desceu sozinho até 95 e o preço nunca mais voltou: cauda compradora de 95 a 98
    bl = [_bloco(0, 101.0, 95.0)] + [_bloco(i, 101.0, 98.0) for i in range(1, 10)]
    p = Perfil(bl, tick=1.0)
    c = p.caudas()
    assert c["compradora"] == (95.0, 98.0) and c["vendedora"] is None


def test_sessoes_separam_asia_europa_america():
    bl = [_bloco(i, 101.0, 100.0) for i in range(48)]
    s = sessoes(Perfil(bl, tick=1.0))
    assert len(s["asia"].blocos) == 16 and len(s["europa"].blocos) == 11 and len(s["america"].blocos) == 13


def test_merge_junta_os_dias_no_mesmo_perfil():
    d1 = Perfil([_bloco(i, 101.0, 100.0, dia=0) for i in range(20)], tick=1.0)
    d2 = Perfil([_bloco(i, 103.0, 102.0, dia=1) for i in range(20)], tick=1.0)
    m = merge([d1, d2])
    assert m.minima == 100.0 and m.maxima == 103.0 and len(m.blocos) == 40


def test_naked_poc_so_quando_o_preco_nao_voltou():
    d1 = Perfil([_bloco(i, 101.0, 100.0, dia=0) for i in range(20)], tick=1.0)     # POC ~100,5
    d2 = Perfil([_bloco(i, 110.0, 105.0, dia=1) for i in range(20)], tick=1.0)     # não volta
    d3 = Perfil([_bloco(i, 106.0, 104.0, dia=2) for i in range(20)], tick=1.0)
    nk = naked_pocs([d1, d2, d3])
    assert [round(x["preco"], 1) for x in nk] == [100.5, 107.5]


def test_dias_em_utc():
    c = [[T0 + i * 900_000, 100, 101, 99, 100, 1] for i in range(96 * 2)]
    assert len(dias(c)) == 2
