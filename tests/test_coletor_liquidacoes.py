from conselho import livro_historico as lh
from conselho.coletor_liquidacoes import AgregadorLiquidacoes, ColetorLiquidacoes, ler_bybit, ler_okx


def test_bybit_buy_e_long_liquidado():
    msg = {"topic": "allLiquidation.BTCUSDT", "data": [
        {"T": 1792596000500, "s": "BTCUSDT", "S": "Buy", "v": "0.5", "p": "84000"},
        {"T": 1792596001000, "s": "BTCUSDT", "S": "Sell", "v": "0.2", "p": "84100"},
    ]}
    assert ler_bybit(msg) == [(1792596000.5, 84000.0, 0.5, True), (1792596001.0, 84100.0, 0.2, False)]
    assert ler_bybit({"op": "subscribe", "success": True}) == []


def test_okx_converte_contratos_e_ignora_outras_moedas():
    msg = {"arg": {"channel": "liquidation-orders", "instType": "SWAP"}, "data": [
        {"instId": "BTC-USDT-SWAP", "details": [{"side": "sell", "posSide": "long", "sz": "250", "bkPx": "84000", "ts": "1792596000000"}]},
        {"instId": "BTC-USD-SWAP", "details": [{"side": "buy", "posSide": "short", "sz": "84", "bkPx": "84000", "ts": "1792596000000"}]},
        {"instId": "ETH-USDT-SWAP", "details": [{"side": "sell", "sz": "10", "bkPx": "3000", "ts": "1792596000000"}]},
    ]}
    liqs = ler_okx(msg)
    assert len(liqs) == 2
    assert liqs[0] == (1792596000.0, 84000.0, 2.5, True)                 # 250 × 0,01 BTC, long liquidado
    assert liqs[1][2] == 84 * 100 / 84000 and liqs[1][3] is False         # 84 × US$ 100, short liquidado


def test_agregador_fecha_o_minuto_e_grava(tmp_path):
    ag = AgregadorLiquidacoes("bybit")
    ag.adicionar([(1792596000.5, 84000.0, 0.5, True), (1792596030.0, 84000.0, 0.25, False), (1792596061.0, 84000.0, 1.0, True)])
    assert ag.fechados(1792596060 + 4) == []                              # ainda dentro do atraso
    (m,) = ag.fechados(1792596060 + 5)
    assert (m["ts"], m["long_btc"], m["short_btc"], m["long_usd"], m["n"]) == (1792596000, 0.5, 0.25, 42000.0, 2)
    c = ColetorLiquidacoes(exchanges=["bybit"], raiz=str(tmp_path))
    c.agregadores["bybit"] = ag
    assert c.descarregar(1792596200) == 1
    (r,) = lh.carregar_periodo("bybit", 1792596000, 1792596200, str(tmp_path))
    assert r["ts"] == 1792596060 and r["long_btc"] == 1.0
