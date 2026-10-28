"""Portal Tradeiros — leitura diária: peças puras e a garantia de não olhar o futuro."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from conselho.elliott.pivots import Pivot
from conselho.tpo import DIA_MS
from conselho.tradeiros.leitura import (Dados, LeituraDiaria, ParametrosLeitura, estrutura_dos_pivos, fib_do_ultimo_movimento,
                               pivo_virgem, posicao_no_range, zona_do_range)

T0 = int(dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)


def test_posicao_e_zona_do_range_seguem_as_regras_1_e_3():
    assert posicao_no_range(100, 100, 110) == 0 and posicao_no_range(110, 100, 110) == 1
    assert zona_do_range(0.1) == "fundo" and zona_do_range(0.9) == "topo"
    assert zona_do_range(0.5) == "meio" and zona_do_range(0.62) == "meio"
    assert zona_do_range(-0.2) == "abaixo_do_valor" and zona_do_range(1.3) == "acima_do_valor"
    assert zona_do_range(None) == "sem_range"


def _piv(tipo, preco, i):
    return Pivot(idx=i, ts=i, preco=preco, tipo=tipo, confirmado=True)


def test_estrutura_de_alta_baixa_e_quebra():
    alta = [_piv("L", 90, 1), _piv("H", 100, 2), _piv("L", 95, 3), _piv("H", 105, 4)]
    e = estrutura_dos_pivos(alta, [103, 106])
    assert e["tendencia"] == "alta" and e["quebra"] == "alta" and e["ultimo_topo"] == 105
    baixa = [_piv("H", 110, 1), _piv("L", 100, 2), _piv("H", 105, 3), _piv("L", 95, 4)]
    e = estrutura_dos_pivos(baixa, [97, 94])
    assert e["tendencia"] == "baixa" and e["quebra"] == "baixa"


def test_fibonacci_do_ultimo_movimento():
    f = fib_do_ultimo_movimento([_piv("L", 100, 1), _piv("H", 200, 2)])
    assert f["direcao"] == "up"
    assert f["niveis"]["0.5"] == pytest.approx(150) and f["niveis"]["0.618"] == pytest.approx(138.2)


def test_pivo_virgem_e_a_abertura_que_ninguem_voltou_a_tocar():
    # dia 0 abre em 120 e cai; os dias seguintes ficam entre 100 e 110: 120 fica virgem acima
    dias = [[0, 120, 121, 105, 106, 1]] + [[i, 105, 110, 100, 104, 1] for i in range(1, 6)]
    v = pivo_virgem(dias, preco=104)
    assert v["acima"] == 120


# ------------------------------------------------------------------ leitura completa sem olhar o futuro
def _mercado(dias, pico_depois_de=None):
    """Range lateral 95–105 em candles de 15 min; opcionalmente um pico de +30% depois de `pico_depois_de`.
    A oscilação dura ~9 h: cada dia varre o range inteiro, então as áreas de valor dos dias se sobrepõem (lateral)."""
    ts = T0 + np.arange(dias * 96) * 15 * 60 * 1000
    base = 100 + 5 * np.sin(np.arange(len(ts)) / 6)
    if pico_depois_de is not None:
        base = np.where(ts >= pico_depois_de, base * 1.3, base)
    m15 = pd.DataFrame({"timestamp": ts, "open": base, "high": base + 0.3, "low": base - 0.3, "close": base, "volume": 1.0})

    def agrupa(ms):
        g = m15.assign(k=(m15.timestamp // ms) * ms).groupby("k")
        return pd.DataFrame({"timestamp": g.timestamp.first().index, "open": g.open.first().values,
                             "high": g.high.max().values, "low": g.low.min().values, "close": g.close.last().values,
                             "volume": g.volume.sum().values})
    fear = pd.DataFrame({"timestamp": [T0 + i * DIA_MS for i in range(dias)], "valor": [20 + i for i in range(dias)]})
    return Dados(agrupa(DIA_MS), agrupa(4 * 3_600_000), m15, fear=fear)


def test_leitura_nao_enxerga_o_futuro():
    momento = T0 + 20 * DIA_MS + 6 * 3_600_000
    sem_pico = LeituraDiaria(_mercado(30)).ler(momento)
    com_pico = LeituraDiaria(_mercado(30, pico_depois_de=momento + 3_600_000)).ler(momento)
    assert sem_pico.as_dict() == com_pico.as_dict(), "um movimento DEPOIS do momento não pode mudar a leitura"


def test_leitura_monta_range_zona_e_sentimento():
    lt = LeituraDiaria(_mercado(30)).ler(T0 + 20 * DIA_MS + 6 * 3_600_000)
    assert lt.range is not None and lt.range["dias"] >= 3 and lt.range["val"] < lt.range["vah"]
    assert lt.zona != "sem_range" and lt.p is not None
    assert lt.sentimento == 40, "o Fear & Greed do dia é publicado à 00:00 UTC: às 06:00 do dia 20 já vale o do dia 20"
    assert lt.ciclo["estado"] in ("esticado", "intermediario", "descontado")


def test_juntar_candles_poe_os_recentes_por_cima_do_historico():
    from conselho.tradeiros.leitura import juntar_candles
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    base = pd.DataFrame([[1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 2, 2]], columns=cols)
    rec = pd.DataFrame([[2, 9, 9, 9, 9, 9], [3, 3, 3, 3, 3, 3]], columns=cols)
    j = juntar_candles(base, rec)
    assert j["timestamp"].tolist() == [1, 2, 3] and j.loc[j.timestamp == 2, "close"].item() == 9
    assert juntar_candles(base, None) is base and juntar_candles(None, rec)["timestamp"].tolist() == [2, 3]


def test_historico_longo_tambem_so_entrega_o_que_fechou():
    dados = _mercado(30)
    longo = pd.DataFrame({"timestamp": [T0 - 400 * DIA_MS + i * DIA_MS for i in range(430)], "open": 1.0, "high": 2.0,
                          "low": 0.5, "close": 1.5, "volume": 1.0})
    dados_longos = Dados(pd.DataFrame(dados.d1, columns=["timestamp", "open", "high", "low", "close", "volume"]),
                         pd.DataFrame(dados.h4, columns=["timestamp", "open", "high", "low", "close", "volume"]),
                         d1_longo=longo)
    momento = T0 + 10 * DIA_MS + 3_600_000
    serie = dados_longos.diarios_longos_ate(momento)
    assert serie[-1][0] == T0 + 9 * DIA_MS, "o dia 10 ainda está aberto às 01:00"
    assert len(serie) == 410
    assert dados.diarios_longos_ate(momento) == dados.diarios_ate(momento), "sem histórico longo, usa o diário normal"
