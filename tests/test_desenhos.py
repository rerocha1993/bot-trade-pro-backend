"""Rotas de desenhos: grava e lê por moeda, apaga quando a lista fica vazia, recusa símbolo e lista ruins."""
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    from api.routes import desenhos_routes as R
    importlib.reload(R)
    monkeypatch.setattr(R, "PASTA", str(tmp_path))
    monkeypatch.setattr(R, "ARQ_MODELOS", str(tmp_path / "_modelos.json"))
    app = FastAPI()
    app.include_router(R.router, prefix="/api/desenhos")
    return TestClient(app), tmp_path


def test_grava_le_e_apaga(cliente):
    c, pasta = cliente
    d = [{"id": "a1", "tipo": "linha_tendencia", "pts": [{"t": 1, "p": 2}]}]
    assert c.put("/api/desenhos", params={"simbolo": "BINANCE:BTC-USDT"}, json={"desenhos": d}).status_code == 200
    r = c.get("/api/desenhos", params={"simbolo": "BINANCE:BTC-USDT"}).json()
    assert r["desenhos"] == d and r["atualizado"]
    assert (pasta / "BINANCE__BTC-USDT.json").exists()
    assert c.get("/api/desenhos", params={"simbolo": "COINBASE:BTC-USD"}).json()["desenhos"] == []
    c.put("/api/desenhos", params={"simbolo": "BINANCE:BTC-USDT"}, json={"desenhos": []})
    assert not (pasta / "BINANCE__BTC-USDT.json").exists()


def test_recusa_ruins(cliente):
    c, _ = cliente
    assert c.get("/api/desenhos", params={"simbolo": "../etc"}).status_code == 400
    assert c.put("/api/desenhos", params={"simbolo": "X"}, json={"desenhos": [{"tipo": "a"}]}).status_code == 422
    assert c.put("/api/desenhos", params={"simbolo": "X"}, json={"desenhos": "nada"}).status_code == 422


def test_modelos(cliente):
    c, _ = cliente
    assert c.get("/api/desenhos/modelos").json()["modelos"] == {}
    c.put("/api/desenhos/modelos", json={"modelos": {"fibo_retracao": {"cfg": {"fonte": 14}}}})
    assert c.get("/api/desenhos/modelos").json()["modelos"]["fibo_retracao"]["cfg"]["fonte"] == 14
