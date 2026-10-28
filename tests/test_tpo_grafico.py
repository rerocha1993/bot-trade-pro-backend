import random

import pytest

from conselho.tpo import DIA_MS, Perfil, blocos_30m, merge
from conselho.tpo_grafico import composto, juntar, perfis_por_dia, tick_grafico

DIA = DIA_MS // 1000
T0 = 1_792_800_000 - 1_792_800_000 % DIA          # meia-noite UTC


def _velas(dias, inicio=T0, semente=1, preco=80_000.0):
    rnd = random.Random(semente)
    out, p = [], preco
    for i in range(dias * 48):
        o = p
        p = max(1.0, p + rnd.uniform(-1, 1) * preco * 0.003)
        h, l = max(o, p) + rnd.uniform(0, preco * 0.001), min(o, p) - rnd.uniform(0, preco * 0.001)
        out.append([inicio + i * 1800, o, h, l, p, 1.0])
    return out


def test_tick_grafico():
    assert tick_grafico(80_000) == 80.0                # regra do sistema para o BTC
    assert tick_grafico(2345) == 2.5
    assert tick_grafico(101) == pytest.approx(0.1)
    assert tick_grafico(0.0000046) == pytest.approx(0.000000005)


def test_cada_dia_igual_ao_perfil_do_sistema():
    velas = _velas(4)
    r = perfis_por_dia(velas, agora_s=T0 + 4 * DIA - 60, dias=10)
    assert len(r["dias"]) == 4 and r["dias"][-1]["aberto"] and not r["dias"][0]["aberto"]
    blocos = blocos_30m([[v[0] * 1000, *v[1:]] for v in velas])
    for k, d in enumerate(r["dias"]):
        p = Perfil([b for b in blocos if b[0] // DIA_MS == T0 // DIA + k], r["tick"])
        val, vah = p.area_valor()
        assert (d["poc"], d["val"], d["vah"]) == pytest.approx((p.poc(), val, vah))
        assert sum(d["contagens"]) == sum(f["tpo"] for f in p.perfil_por_faixa())
        assert d["base_i"] * r["tick"] == pytest.approx(p.perfil_por_faixa()[0]["lo"])


def test_toque_e_a_primeira_vela_depois_do_dia_que_passa_no_nivel():
    velas = _velas(3)
    r = perfis_por_dia(velas, agora_s=T0 + 3 * DIA, dias=10)
    for d in r["dias"]:
        for nome, t in d["toques"].items():
            nivel = d[nome]
            depois = [v for v in velas if v[0] >= d["fim"] and v[3] <= nivel <= v[2]]
            assert t == (depois[0][0] if depois else None)


def test_dia_cortado_no_comeco_fica_de_fora_e_dias_limita():
    velas = _velas(4, inicio=T0 + 6 * 3600)           # o 1º dia começa às 06:00
    r = perfis_por_dia(velas, agora_s=T0 + 5 * DIA, dias=2)
    assert [d["inicio"] for d in r["dias"]] == [T0 + DIA * k for k in (2, 3, 4)]


def test_juntar_igual_ao_merge_do_sistema():
    velas = _velas(5, semente=7)
    r = perfis_por_dia(velas, agora_s=T0 + 6 * DIA, dias=10)
    comp = juntar(r["dias"][1:4], r["tick"])
    blocos = blocos_30m([[v[0] * 1000, *v[1:]] for v in velas])
    perfis = [Perfil([b for b in blocos if b[0] // DIA_MS == T0 // DIA + k], r["tick"]) for k in (1, 2, 3)]
    m = merge(perfis, r["tick"])
    val, vah = m.area_valor()
    assert (comp["poc"], comp["val"], comp["vah"]) == pytest.approx((m.poc(), val, vah))


def test_composto_junta_os_dias_do_intervalo_e_conta_toques_depois_do_ultimo():
    velas = _velas(6, semente=3)
    agora = T0 + 6 * DIA - 60
    r = perfis_por_dia(velas, agora_s=agora, dias=10)
    c = composto(velas, agora, T0 + DIA, T0 + 3 * DIA, r["tick"])
    esperado = juntar(r["dias"][1:4], r["tick"])
    assert c["n_dias"] == 3 and (c["inicio"], c["fim"]) == (T0 + DIA, T0 + 4 * DIA) and not c["aberto"]
    assert (c["poc"], c["val"], c["vah"]) == pytest.approx((esperado["poc"], esperado["val"], esperado["vah"]))
    for nome, t in c["toques"].items():
        depois = [v for v in velas if v[0] >= c["fim"] and v[3] <= c[nome] <= v[2]]
        assert t == (depois[0][0] if depois else None)
    with pytest.raises(ValueError):
        composto(velas, agora, T0 + 20 * DIA, T0 + 21 * DIA, r["tick"])


def test_preco_na_borda_da_faixa_conta_com_tick_pequeno():
    # tick 0,001: 1,201 / 0,001 dá 1200,9999999999998 em ponto flutuante; a faixa 1201 tem de contar
    p = Perfil([(T0 * 1000, 1.201, 1.202, 1.201, 1.202, 1.0)], 0.001)
    base, cont, _ = p._grade()
    assert round(base / 0.001) == 1201 and list(cont) == [1, 1]
