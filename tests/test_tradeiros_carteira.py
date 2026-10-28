"""Portal Tradeiros — carteira em BTC: hedge no inverse, fatias, 1 R, stop pessimista, reação, funding."""
import pytest

from conselho.tpo import DIA_MS
from conselho.tradeiros.carteira import Carteira, pnl_btc
from conselho.tradeiros.regras import MAROJA, Decisao, Plano

H = 30 * 60 * 1000


def _planos(por_dia):
    """Planejador falso: {dia: (hedge_alvo, [decisões])}."""
    def f(ts, hedge_atual):
        hedge, decs = por_dia.get(ts // DIA_MS, (0.0, []))
        return Plano("teste", ts, 0.0, hedge, [], {}, decs)
    return f


def _velas(precos, dia=0):
    """(o, h, l, c) → blocos de 30 min a partir do início do dia."""
    return [(dia * DIA_MS + i * H, o, h, l, c, 1.0) for i, (o, h, l, c) in enumerate(precos)]


def _compra(zona=(99, 101), stop=90.0, alvo=140.0, risco=0.01, exige=False):
    return Decisao("compra", ["R2"], "teste", zona=zona, pesos_fatias=[1.0], stop=stop, alvo=alvo, risco=risco,
                   exige_reacao=exige)


def test_pnl_inverse_tem_o_sinal_certo():
    assert pnl_btc(1, 10_000, 50_000, 100_000) == pytest.approx(0.1)
    assert pnl_btc(-1, 10_000, 100_000, 50_000) == pytest.approx(0.1)
    assert pnl_btc(-1, 10_000, 50_000, 100_000) == pytest.approx(-0.1)


def test_sem_hedge_e_sem_trade_e_o_mesmo_que_segurar():
    r = Carteira(_velas([(100, 100, 50, 50)]), _planos({}), MAROJA).executar(0, DIA_MS)
    assert r["btc_final"] == 1.0 and r["retorno_usd_pct"] == pytest.approx(r["hodl_usd_pct"])


def test_hedge_de_50_por_cento_perde_metade_da_queda_em_usd():
    r = Carteira(_velas([(100, 100, 50, 50)]), _planos({0: (0.5, [])}), MAROJA).executar(0, DIA_MS)
    assert r["btc_final"] == pytest.approx(1.5, abs=0.001)          # o short de 50 USD rende 0,5 BTC
    assert r["retorno_usd_pct"] == pytest.approx(-25, abs=0.2) and r["hodl_usd_pct"] == -50


def test_compra_tira_o_risco_em_1r_e_sai_no_zero_a_zero():
    velas = [(105, 105, 104, 104), (104, 104, 99.5, 100), (100, 110.5, 100, 110), (110, 110, 99, 99)]
    r = Carteira(_velas(velas), _planos({0: (0.0, [_compra()])}), MAROJA).executar(0, DIA_MS)
    t = r["lista_trades"][0]
    assert t["saida"] == "zero_a_zero" and t["medio"] == pytest.approx(100)
    assert 0 < t["r"] < 0.3, "realizou 25% em 1 R e o resto saiu no médio"


def test_stop_no_mesmo_candle_das_fatias_e_pessimista():
    velas = [(105, 105, 104, 104), (104, 104, 89, 95)]
    r = Carteira(_velas(velas), _planos({0: (0.0, [_compra()])}), MAROJA).executar(0, DIA_MS)
    t = r["lista_trades"][0]
    assert t["saida"] == "stop" and t["r"] == pytest.approx(-1.0, abs=0.05)
    assert r["btc_final"] == pytest.approx(0.99, abs=0.001)


class _Sempre:
    """Sorteio que sempre troca a direção."""
    def random(self):
        return 0.0


def test_sorteio_entra_nos_mesmos_candles_com_a_direcao_trocada():
    velas = [(105, 105, 104, 104), (104, 104, 89, 95)]           # o original é stopado aqui
    r = Carteira(_velas(velas), _planos({0: (0.0, [_compra()])}), MAROJA, sortear=_Sempre()).executar(0, DIA_MS)
    t = r["lista_trades"][0]
    assert t["lado"] == -1 and t["medio"] == pytest.approx(100) and t["stop"] == pytest.approx(110)
    assert t["saida"] == "fim" and t["r"] == pytest.approx(0.5, abs=0.05), "vendido em 100, fecha em 95 com stop de 10"


def test_sorteio_troca_a_acao_da_escada_de_hedge():
    escada = Decisao("hedge_realizar", ["R28"], "teste", zona=(90, 90), pesos_fatias=[1.0], fracao_hedge=0.3)
    velas = [(100, 100, 100, 100), (91, 91, 89, 90)]              # máxima abaixo do pedágio (90 × 1,02)
    r = Carteira(_velas(velas), _planos({0: (0.0, [escada])}), MAROJA, sortear=_Sempre()).executar(0, DIA_MS)
    assert r["hedge_final_pct"] > 0, "a recompra na VAL virou venda na VAL"


def test_ordem_que_exige_reacao_so_entra_depois_do_candle_de_reacao():
    velas = [(105, 105, 104, 104),
             (104, 104, 99, 99.2),        # tocou e fechou embaixo: sem reação
             (99.2, 101, 98, 100.8),      # tocou e fechou na metade de cima: arma e entra no fechamento
             (100.8, 150, 100.5, 150)]
    r = Carteira(_velas(velas), _planos({0: (0.0, [_compra(zona=(99, 101), exige=True)])}), MAROJA).executar(0, DIA_MS)
    t = r["lista_trades"][0]
    assert t["medio"] == pytest.approx(100.8) and t["saida"] == "alvo"


def test_ordens_do_dia_sao_canceladas_na_virada():
    velas = _velas([(105, 105, 104, 104)]) + _velas([(104, 104, 50, 60)], dia=1)
    r = Carteira(velas, _planos({0: (0.0, [_compra(zona=(59, 61), stop=55.0, alvo=90.0)])}), MAROJA).executar(0, 2 * DIA_MS)
    assert r["trades"] == 0 and r["btc_final"] == 1.0


def test_short_recebe_funding():
    velas = _velas([(100, 100, 100, 100)] * 2)
    r = Carteira(velas, _planos({0: (0.5, [])}), MAROJA, funding={H + H: 0.0001}).executar(0, DIA_MS)
    assert r["funding_btc"] == pytest.approx(50 / 100 * 0.0001)


def test_escada_de_hedge_executa_e_o_stop_e_pedagio():
    escada = Decisao("hedge_aumentar", ["R28"], "teste", zona=(110, 110), pesos_fatias=[1.0], stop=120.0, fracao_hedge=0.3)
    velas = [(100, 100, 100, 100), (100, 111, 100, 110), (110, 121, 110, 121)]
    r = Carteira(_velas(velas), _planos({0: (0.0, [escada])}), MAROJA).executar(0, DIA_MS)
    assert r["stops_hedge"] == 1 and r["hedge_final_pct"] == 0
    assert r["btc_final"] < 1.0, "o pedágio custa BTC"
