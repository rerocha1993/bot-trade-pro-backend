"""A tela do range: o endpoint devolve JSON puro (numpy não serializa) e a leitura do robô."""
import json
from types import SimpleNamespace

import api.routes.range_routes as rr
from core.tpo_sessao import BLOCO_MS, DIA_MS

T0 = 1_780_000_000_000 - (1_780_000_000_000 % DIA_MS)
CICLO = [0, 0.15, -0.15, 0, 0.85, 0.95, 0.85, 0.25, 0, -0.25, -0.85, -0.95]


def _candles(dias=12, meio=78_000.0, meia=2_000.0):
    out = []
    for d in range(dias):
        for i in range(48):
            m = meio + meia * CICLO[(i + d) % len(CICLO)]
            out.append([T0 + d * DIA_MS + i * BLOCO_MS, m, m + 50, m - 50, m, 10.0])
    return out


class _Con:
    def obter_ohlcv_historico(self, par, tf, desde):
        return _candles()

    def obter_preco_atual(self, par):
        return 78_000.0


def test_contexto_devolve_json_puro_com_range_perfis_e_naked(monkeypatch):
    monkeypatch.setattr(rr, "get_manager", lambda: SimpleNamespace(servicos={"connectors": {"simulador": _Con()}}))
    monkeypatch.setattr(rr._lsr, "contexto", lambda: None)
    monkeypatch.setattr(rr.time, "time", lambda: (T0 + 12 * DIA_MS) / 1000)
    rr._cache.clear()
    r = rr.contexto("BTCUSDT", 10)
    json.dumps(r)                                     # numpy float estouraria aqui
    assert r["range"]["valido"] is True and r["range"]["dias"] >= 3
    assert len(r["perfis"]) == 10 and r["perfis"][-1]["sessoes"]
    assert r["toques"].keys() == {"val", "vah"} and isinstance(r["motivo"], str)
    assert r["long_short"] is None                    # sem dado de long/short não inventa contexto


def test_cache_evita_refazer_a_leitura_a_cada_pedido(monkeypatch):
    chamadas = []

    class _Contado(_Con):
        def obter_ohlcv_historico(self, par, tf, desde):
            chamadas.append(1)
            return _candles()

    monkeypatch.setattr(rr, "get_manager", lambda: SimpleNamespace(servicos={"connectors": {"simulador": _Contado()}}))
    monkeypatch.setattr(rr._lsr, "contexto", lambda: None)
    rr._cache.clear()
    rr.contexto("BTCUSDT", 10)
    rr.contexto("BTCUSDT", 10)
    assert len(chamadas) == 1
