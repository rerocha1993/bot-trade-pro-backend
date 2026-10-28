import pytest

from conselho import velas as V


class Resposta:
    def __init__(self, dados):
        self.dados = dados

    def raise_for_status(self):
        pass

    def json(self):
        return self.dados


class HttpFalso:
    """Responde como a corretora: velas de `passo` em `passo` desde `inicio`, cortadas pelo fim e pelo limite."""

    def __init__(self, inicio, passo, total):
        self.velas = [[inicio + i * passo, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1.0] for i in range(total)]
        self.pedidos = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.pedidos.append((url, dict(params or {})))
        p = params or {}
        if "binance" in url:
            ate, lim = p["endTime"] // 1000, p["limit"]
            sel = [v for v in self.velas if v[0] <= ate][-lim:]
            return Resposta([[v[0] * 1000, str(v[1]), str(v[2]), str(v[3]), str(v[4]), str(v[5])] for v in sel])
        if "okx" in url:
            ate, lim = (p["after"] - 1) // 1000, p["limit"]
            sel = [v for v in self.velas if v[0] <= ate][-lim:][::-1]
            return Resposta({"code": "0", "data": [[str(v[0] * 1000), *map(str, v[1:5]), "50", str(v[5])] for v in sel]})
        if "coinbase" in url:
            sel = [v for v in self.velas if p["start"] <= v[0] <= p["end"]][::-1]
            return Resposta({"candles": [{"start": str(v[0]), "open": str(v[1]), "high": str(v[2]), "low": str(v[3]),
                                          "close": str(v[4]), "volume": str(v[5])} for v in sel]})
        raise AssertionError(url)


def test_ler_simbolo():
    s = V.ler_simbolo("binance:eth-usdt:perp")
    assert (s.corretora, s.base, s.cotacao, s.perp) == ("BINANCE", "ETH", "USDT", True)
    assert s.texto == "BINANCE:ETH-USDT:PERP"
    for ruim in ("BTCUSDT", "KRAKEN:BTC-USD", "COINBASE:BTC-USD:PERP", "BINANCE:BTCUSDT", "BINANCE:BTC-USDT:X"):
        with pytest.raises(ValueError):
            V.ler_simbolo(ruim)


def test_nuvem_so_no_btc_da_coinbase():
    assert V.tem_nuvem(V.ler_simbolo("COINBASE:BTC-USD"))
    assert not V.tem_nuvem(V.ler_simbolo("COINBASE:ETH-USD"))
    assert not V.tem_nuvem(V.ler_simbolo("BINANCE:BTC-USDT"))


def test_binance_pagina_para_tras_sem_repetir():
    http = HttpFalso(1_000_000_200, 60, 2500)            # 1000 por página: 2 páginas para 2000
    v = V.velas("BINANCE:BTC-USDT", "1m", ate_s=http.velas[-1][0] + 30, n=2000, http=http)
    assert len(v) == 2000 and len(http.pedidos) == 2
    assert v[-1][0] == http.velas[-1][0] and all(b[0] - a[0] == 60 for a, b in zip(v, v[1:]))


def test_okx_inclui_a_vela_de_ate_e_acaba_no_inicio_do_historico():
    http = HttpFalso(1_000_000_200, 300, 250)            # só 250 velas existem; OKX manda 100 por vez
    ate = http.velas[120][0]
    v = V.velas("OKX:BTC-USDT:PERP", "5m", ate_s=ate, n=500, http=http)
    assert v[-1][0] == ate and len(v) == 121
    assert v[0][5] == 1.0                                  # volume em moeda (7º campo), não em contratos


def test_coinbase_monta_4h_a_partir_de_1h():
    inicio = 1_000_008_000 - 1_000_008_000 % 14400        # alinhado em bloco de 4 h
    http = HttpFalso(inicio, 3600, 4 * 10)                 # 10 blocos de 4 h
    v = V.velas("COINBASE:BTC-USD", "4h", ate_s=http.velas[-1][0], n=3, http=http)
    assert [x[0] for x in v] == [inicio + 14400 * k for k in (7, 8, 9)]
    o = http.velas[36]
    assert v[-1][1] == o[1] and v[-1][4] == http.velas[39][4] and v[-1][5] == 4.0
    assert all("ONE_HOUR" == p["granularity"] for _, p in http.pedidos)


def test_agregar_junta_por_bloco_utc():
    v = [[0, 1, 2, 0.5, 1.5, 1], [60, 1.5, 3, 1, 2, 2], [120, 2, 2.5, 0.2, 1, 3]]
    assert V.agregar(v, 120) == [[0, 1, 3, 0.5, 2, 3], [120, 2, 2.5, 0.2, 1, 3]]
