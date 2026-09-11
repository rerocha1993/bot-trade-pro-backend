"""
O backtest do inverse tem que testar a MESMA estratégia que roda ao vivo: grade que só vende acima do preço de
aprovação, pesos do inverse e a regra de rompimento do usuário. Antes ele rodava a lógica antiga (grade nascendo
com todos os níveis ativos e sem rompimento) e aprovava uma estratégia que não era a do robô.
"""
import pytest

import core.backtest_grade as bg
from core.backtest_grade import BacktestGrade

H4 = 4 * 3600 * 1000
T0 = 1_700_000_000_000 - (1_700_000_000_000 % 86_400_000)


def _velas(precos):
    out, ant = [], precos[0]
    for i, c in enumerate(precos):
        out.append([T0 + i * H4, ant, max(ant, c) * 1.001, min(ant, c) * 0.999, c, 10.0])
        ant = c
    return out


@pytest.fixture
def range_fixo(monkeypatch):
    """Proposta de range fixa (57.000–82.000) e leitura neutra: o que se testa é a execução, não a contagem."""
    monkeypatch.setattr(bg, "propor_range", lambda *a, **k: {"valido": True, "low": 57000.0, "high": 82000.0,
                                                             "motivo": "teste"})
    monkeypatch.setattr(BacktestGrade, "_leitura", lambda self, ts: {"pivots": [], "regime": {}, "primario": {},
                                                                      "ciclo": {}})


def test_aprovacao_no_meio_do_range_nao_vende_o_que_ficou_abaixo(range_fixo):
    """O defeito que o robô tinha: aprovar a 76.810 vendia 60% da carteira de uma vez no primeiro candle."""
    bt = BacktestGrade(_velas([76810.0] * 6), banca_btc=1.0)
    r = bt.executar()
    assert r["grades"] == 1
    assert r["vendas"] == 0, "nenhum nível abaixo do preço de aprovação pode vender"
    assert r["fracao_em_dolar_no_fim"] == 0.0


def test_subida_vende_em_escada_e_nada_acima_do_topo(range_fixo):
    subida = [70000.0 + 500 * i for i in range(24)]            # 70k -> 81.5k, dentro do range
    bt = BacktestGrade(_velas(subida), banca_btc=1.0)
    r = bt.executar()
    assert r["vendas"] > 0
    assert 0 < r["fracao_em_dolar_no_fim"] <= 1.0
    assert all(e["preco"] <= 82000.0 * 1.0001 for e in r["eventos"] if e.get("tipo") == "venda")


def test_topo_rompido_de_verdade_zera_o_short_e_encerra(range_fixo):
    """Regra do usuário: rompeu o topo de verdade, fecha tudo (0% de short) e deixa subir."""
    precos = [70000.0 + 600 * i for i in range(20)] + [83500.0, 84500.0, 85000.0, 85500.0]
    bt = BacktestGrade(_velas(precos), banca_btc=1.0)
    r = bt.executar()
    assert r["ranges_encerrados_topo"] >= 1
    fim = next(e for e in r["eventos"] if e.get("evento") == "range_encerrado")
    depois = [e for e in r["eventos"] if e.get("ts", 0) > fim["ts"] and e.get("tipo") == "venda"]
    assert not depois or r["grades"] > 1, "depois de encerrar, só vende numa grade nova"


def test_topo_rompido_em_falso_mantem_o_short(range_fixo):
    """Rompeu e voltou para dentro: não fecha, deixa descer."""
    precos = [70000.0 + 600 * i for i in range(20)] + [82500.0, 80500.0, 80000.0, 79500.0]
    bt = BacktestGrade(_velas(precos), banca_btc=1.0)
    r = bt.executar()
    assert r["ranges_encerrados_topo"] == 0
    assert r["fracao_em_dolar_no_fim"] > 0


def test_usa_o_mesmo_passo_do_robo(range_fixo, monkeypatch):
    chamadas = []
    original = bg.passo_inverse
    monkeypatch.setattr(bg, "passo_inverse", lambda *a, **k: chamadas.append(1) or original(*a, **k))
    BacktestGrade(_velas([76000.0] * 5), banca_btc=1.0).executar()
    assert len(chamadas) == 5


def test_funding_entra_no_resultado_de_quem_esta_vendido(range_fixo):
    """
    No perpétuo inverse quem está VENDIDO recebe o funding na maioria das vezes (80–92% dos pagamentos por ano,
    dados da Bybit). O backtest ignorava isso e subestimava a grade.
    """
    precos = [70000.0 + 500 * i for i in range(20)]        # sobe dentro do range: a grade vende em escada
    velas = _velas(precos)
    # o funding é cobrado no fim de um candle de 4h; taxa alta de propósito para o efeito aparecer
    fund = {v[0] + 4 * 3_600_000: 0.001 for v in velas}
    sem = BacktestGrade(velas, banca_btc=1.0).executar()
    com = BacktestGrade(velas, banca_btc=1.0, funding=fund).executar()
    assert com["funding_btc"] > 0 and sem["funding_btc"] == 0
    assert com["btc_realizado"] > sem["btc_realizado"]


def test_funding_negativo_tira_de_quem_esta_vendido(range_fixo):
    velas = _velas([70000.0 + 500 * i for i in range(20)])
    fund = {v[0] + 4 * 3_600_000: -0.001 for v in velas}
    r = BacktestGrade(velas, banca_btc=1.0, funding=fund).executar()
    assert r["funding_btc"] < 0
