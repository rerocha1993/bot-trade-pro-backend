"""Portal Tradeiros — rotas do painel: replay de uma data, JSON puro e o resumo do backtest."""
import json
import os

import pytest
from fastapi import HTTPException

from api.routes import tradeiros_routes as rotas

TEM_DADOS = os.path.exists(os.path.join("data", "historico", "BTCUSDT_binance_15m.csv"))


@pytest.mark.skipif(not TEM_DADOS, reason="sem os CSVs de histórico")
def test_replay_de_uma_live_traz_leitura_mapa_e_os_dois_planos():
    r = rotas.plano(data="2025-04-07", hora=13)
    json.dumps(r)                                                   # nada de numpy nem NaN
    assert set(r["planos"]) == {"shaka", "maroja"}
    assert r["leitura"]["range"]["val"] < r["leitura"]["range"]["vah"]
    assert r["dados_ate"]["candles"] <= r["ts"], "o replay não pode ver o futuro"
    for p in r["planos"].values():
        assert 0 < p["hedge_alvo"] <= 1 and p["decisoes"]


def test_data_invalida_vira_400():
    with pytest.raises(HTTPException) as e:
        rotas.plano(data="07/04/2025", hora=13)
    assert e.value.status_code == 400


def test_backtest_sem_estudo_responde_indisponivel(tmp_path, monkeypatch):
    monkeypatch.setattr(rotas, "ESTUDO", str(tmp_path / "nao_existe.json"))
    assert rotas.backtest()["disponivel"] is False


def test_backtest_resume_sorteios_por_ano(tmp_path, monkeypatch):
    estudo = {"anos": {"maroja": {"2025": {"carteira": {"btc_final": 1.05, "trades": 3}, "fixo_btc": 1.01,
                                           "sorteios_btc": [0.9, 1.0, 1.02, 1.1]}}},
              "periodos": {"maroja": {"holdout": {"btc": 1.05, "vantagem": False}}}}
    caminho = tmp_path / "estudo.json"
    caminho.write_text(json.dumps(estudo), encoding="utf-8")
    monkeypatch.setattr(rotas, "ESTUDO", str(caminho))
    r = rotas.backtest()
    linha = r["anos"]["maroja"][0]
    assert r["disponivel"] and linha["ano"] == 2025 and linha["percentil"] == 0.75
    assert linha["sorteio_mediana"] == pytest.approx(1.01)
