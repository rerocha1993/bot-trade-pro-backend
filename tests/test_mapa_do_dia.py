"""O mapa do dia (conselho/mapa_do_dia.py): níveis certos, só com candle fechado, dias completos no composto."""
import json

import pytest

from conselho.mapa_do_dia import (
    CANDLE_MS, DIA_MS, diarios_de, distancia_pct, mapa, posicao_no_composto,
)

# 1_780_012_800_000 = 2026-05-29 (sexta); T0 é a meia-noite UTC desse dia
T0 = 1_780_012_800_000 - (1_780_012_800_000 % DIA_MS)
POR_DIA = DIA_MS // CANDLE_MS


def dia_flat(d, preco, abertura=None, maximo=None, minimo=None, por_sessao=None):
    """
    288 candles de 5 min num dia: preço parado em `preco` (ou, com `por_sessao`, um preço por sessão
    {'asia': x, 'europa': y, 'america': z, 'noite': w}); o 1º candle abre em `abertura`; `maximo`/`minimo`
    põem UMA espetada no meio do dia para fixar os extremos sem mexer no POC.
    """
    out = []
    for i in range(POR_DIA):
        ts = T0 + d * DIA_MS + i * CANDLE_MS
        minuto = i * 5
        p = preco
        if por_sessao:
            p = por_sessao["asia"] if minuto < 480 else por_sessao["europa"] if minuto < 810 else \
                por_sessao["america"] if minuto < 1200 else por_sessao.get("noite", por_sessao["america"])
        o = abertura if (i == 0 and abertura is not None) else p
        h = l = p
        if i == 144:
            h = maximo if maximo is not None else p
            l = minimo if minimo is not None else p
        out.append([ts, float(o), float(max(h, o)), float(min(l, o)), float(p), 10.0])
    return out


def candles_base(dias=12, preco=80_000.0):
    c = []
    for d in range(dias):
        c += dia_flat(d, preco, maximo=preco + 1_000, minimo=preco - 1_000)
    return c


# ------------------------------------------------------------------ peças
def test_posicao_no_composto():
    assert posicao_no_composto(None) == "sem_composto"
    assert posicao_no_composto(-0.1) == "fora_abaixo" and posicao_no_composto(1.2) == "fora_acima"
    assert posicao_no_composto(0.1) == "fundo" and posicao_no_composto(0.5) == "meio" and posicao_no_composto(0.9) == "topo"


def test_distancia_em_pct_com_sinal():
    assert distancia_pct(80_160, 80_000) == pytest.approx(0.2)
    assert distancia_pct(79_840, 80_000) == pytest.approx(-0.2)


def test_diarios_a_partir_do_5m():
    d = diarios_de(dia_flat(0, 100.0, abertura=99.0, maximo=105.0, minimo=95.0) + dia_flat(1, 101.0))
    assert len(d) == 2 and d[0][1] == 99.0 and d[0][2] == 105.0 and d[0][3] == 95.0 and d[0][4] == 100.0


# ------------------------------------------------------------------ o mapa
def test_sem_candle_fechado_nao_ha_mapa():
    c = candles_base(2)
    m = mapa(c, T0)                                      # o 1º candle só fecha às 00:05
    assert m.preco == 0.0 and m.niveis == [] and m.posicao == "sem_composto"


def test_candle_em_formacao_nao_entra():
    c = candles_base(12)
    agora = T0 + 11 * DIA_MS + 10 * CANDLE_MS + 60_000   # 00:51 do dia 11: o candle das 00:50 ainda está aberto
    c[-POR_DIA + 10][4] = 99_000.0                       # candle das 00:50 do dia 11 fecha em 99.000
    m = mapa(c, agora)
    assert m.preco == 80_000.0


def test_composto_de_10_dias_completos_e_dia_anterior():
    c = []
    for d in range(10):                                  # dias 0–9 em 80.000 com extremos ±1.000
        c += dia_flat(d, 80_000.0, maximo=81_000.0, minimo=79_000.0)
    c += dia_flat(10, 82_000.0, maximo=83_000.0, minimo=81_500.0)     # ontem: outro valor
    c += dia_flat(11, 82_000.0)[:60]                                    # hoje, 5 h
    m = mapa(c, T0 + 11 * DIA_MS + 60 * CANDLE_MS)
    assert m.dias_no_composto == 10
    tick = 80.0
    assert abs(m.composto["poc"] - 80_000.0) <= tick, "9 de 10 dias parados em 80.000: o POC composto é ali"
    assert m.composto["val"] <= 80_000.0 <= m.composto["vah"]
    assert m.composto["maxima"] == 83_000.0 and m.composto["minima"] == 79_000.0
    assert abs(m.ontem["poc"] - 82_000.0) <= tick and m.ontem["maxima"] == 83_000.0 and m.ontem["minima"] == 81_500.0
    assert m.nivel("ontem.poc").dia_ms == T0 + 10 * DIA_MS
    assert m.posicao == "fora_acima" and m.p > 1, "preço em 82.000, acima do VAH do composto"


def test_sem_3_dias_completos_nao_ha_composto_mas_ha_ontem():
    c = candles_base(3)
    m = mapa(c, T0 + 2 * DIA_MS + 12 * CANDLE_MS)       # 2 dias completos + 1 h de hoje
    assert m.composto is None and m.posicao == "sem_composto" and m.dias_no_composto == 0
    assert m.ontem is not None and m.nivel("composto.poc") is None and m.nivel("ontem.poc") is not None


def test_sessoes_de_ontem_e_as_de_hoje_ja_fechadas():
    c = candles_base(10)
    c += dia_flat(10, 0, por_sessao={"asia": 80_100.0, "europa": 80_300.0, "america": 80_500.0, "noite": 80_200.0})
    c += dia_flat(11, 0, por_sessao={"asia": 80_700.0, "europa": 80_900.0, "america": 81_100.0, "noite": 81_000.0})
    tick = 80.0
    # 10:00 de hoje: Ásia fechou, Europa não
    m = mapa(c, T0 + 11 * DIA_MS + 10 * 3_600_000)
    assert set(m.sessoes_ontem) == {"asia", "europa", "america"}
    assert abs(m.sessoes_ontem["asia"]["poc"] - 80_100.0) <= tick and abs(m.sessoes_ontem["america"]["poc"] - 80_500.0) <= tick
    assert set(m.sessoes_hoje) == {"asia"} and abs(m.sessoes_hoje["asia"]["poc"] - 80_700.0) <= tick
    assert m.nivel("sessao.hoje.asia.maxima").preco == 80_700.0 and m.nivel("sessao.hoje.europa.poc") is None
    # 13:30: Europa fechou
    m = mapa(c, T0 + 11 * DIA_MS + 13 * 3_600_000 + 30 * 60_000)
    assert set(m.sessoes_hoje) == {"asia", "europa"}
    # 20:00: América fechou
    m = mapa(c, T0 + 11 * DIA_MS + 20 * 3_600_000)
    assert set(m.sessoes_hoje) == {"asia", "europa", "america"} and abs(m.sessoes_hoje["america"]["poc"] - 81_100.0) <= tick


def test_naked_pocs_os_5_mais_proximos_e_o_tocado_some():
    c = []
    c += dia_flat(0, 70_000.0)                           # POC 70.000, nunca mais tocado
    for d in range(1, 7):
        c += dia_flat(d, 80_000.0 + d * 10, maximo=80_500.0, minimo=79_500.0)   # 6 dias ~80.000, todos tocam uns aos outros
    for d in range(7, 11):
        c += dia_flat(d, 90_000.0 + d * 1_000)           # 93.000, 94.000... POCs sem toque depois
    c += dia_flat(11, 95_000.0)[:60]
    m = mapa(c, T0 + 11 * DIA_MS + 60 * CANDLE_MS)
    precos = sorted(x["preco"] for x in m.naked_pocs)
    assert len(m.naked_pocs) == 5 and sum(p > 96_000 for p in precos) == 4 and 79_900 < precos[0] < 80_200,         "os 5 mais próximos de 95.000: os de 97–100k e o do último dia em ~80.000 (os outros ~80k foram tocados entre si)"
    assert m.nivel("naked.%d" % (T0 + 0 * DIA_MS)) is None, "70.000 é naked, mas está longe demais para entrar nos 5"
    # o preço volta e toca o POC do dia 10 (100.000): deixa de ser naked
    c2 = c + dia_flat(11, 95_000.0)[60:120]
    c2[-1][2] = 100_100.0
    m2 = mapa(c2, T0 + 11 * DIA_MS + 120 * CANDLE_MS)
    assert all(abs(x["preco"] - 100_000.0) > 80 for x in m2.naked_pocs)


def test_aberturas_do_dia_da_semana_e_do_mes():
    # T0 = sexta 29/05/2026; dia 3 = segunda 01/06 (abertura da semana E do mês); dia 5 = quarta 03/06
    c = []
    for d in range(6):
        c += dia_flat(d, 80_000.0 + d * 100, abertura=70_000.0 + d * 1_000)
    m = mapa(c, T0 + 5 * DIA_MS + 20 * CANDLE_MS)
    assert m.aberturas == {"dia": 75_000.0, "semana": 73_000.0, "mes": 73_000.0}
    assert m.nivel("abertura.semana").dia_ms == T0 + 3 * DIA_MS
    # na segunda-feira, a abertura da semana é a do próprio dia
    m2 = mapa(c, T0 + 3 * DIA_MS + 20 * CANDLE_MS)
    assert m2.aberturas["dia"] == m2.aberturas["semana"] == 73_000.0
    # ainda em maio (dia 2 = domingo 31/05): abertura do mês é a do dia 0? não — 01/05 não está nos dados: None
    m3 = mapa(c, T0 + 2 * DIA_MS + 20 * CANDLE_MS)
    assert m3.aberturas["mes"] is None and m3.nivel("abertura.mes") is None


def test_pivo_virgem_acima_e_abaixo():
    c = []
    c += dia_flat(0, 80_000.0, abertura=79_000.0, maximo=80_500.0, minimo=79_500.0)   # abertura 79.000 fora do range do dia
    c += dia_flat(1, 80_000.0, abertura=80_000.0, maximo=80_500.0, minimo=79_600.0)   # 79.000 nunca tocado: virgem abaixo
    c += dia_flat(2, 80_000.0, abertura=81_500.0, maximo=80_500.0, minimo=79_600.0)   # 81.500 acima, não tocado depois
    c += dia_flat(3, 80_000.0, abertura=80_000.0, maximo=80_500.0, minimo=79_600.0)
    c += dia_flat(4, 80_000.0)[:60]
    m = mapa(c, T0 + 4 * DIA_MS + 60 * CANDLE_MS)
    assert m.pivo_virgem == {"acima": 81_500.0, "abaixo": 79_000.0}
    assert m.nivel("pivo.acima").preco == 81_500.0 and m.nivel("pivo.abaixo").distancia_pct == pytest.approx(-1.25)


def test_niveis_ordenados_com_rotulo_e_distancia_e_serializaveis():
    c = candles_base(12)
    m = mapa(c, T0 + 11 * DIA_MS + 60 * CANDLE_MS)
    assert [n.preco for n in m.niveis] == sorted((n.preco for n in m.niveis), reverse=True)
    assert all(n.rotulo and isinstance(n.distancia_pct, float) for n in m.niveis)
    assert {n.grupo for n in m.niveis} >= {"composto", "ontem", "sessao", "abertura"}
    d = json.loads(json.dumps(m.as_dict()))
    assert d["posicao"] in ("fundo", "meio", "topo") and d["dias_no_composto"] == 10 and len(d["niveis"]) == len(m.niveis)
    assert not any(k in d for k in ("stop", "alvo", "prob", "probabilidade")), "o mapa não traz gatilho nem %"
