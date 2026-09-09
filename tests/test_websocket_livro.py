"""
Livro de ofertas via websocket da Bybit.

A Bybit manda um SNAPSHOT (livro inteiro) e depois DELTAS (só os níveis que mudaram; tamanho 0 remove o nível).
O código antigo tratava `data` como lista e substituía o livro a cada mensagem: estourava KeyError a cada
mensagem e, quando não estourava, o Order Flow lia um livro de um nível só.
"""
import json

from core.datasource_ws_universal import DataSourceWebsocketUniversal


def _fonte():
    return DataSourceWebsocketUniversal("bybit", "BTCUSDT")


def _handler(ws_fonte):
    """Pega o on_message do livro sem abrir conexão de rede."""
    capturado = {}

    class WSFalso:
        def __init__(self, *a, **k):
            capturado["on_message"] = k.get("on_message")
        def run_forever(self, *a, **k):
            ws_fonte._stop_flag.set()

    import core.datasource_ws_universal as mod
    original = mod.websocket.WebSocketApp
    mod.websocket.WebSocketApp = WSFalso
    try:
        ws_fonte._run_bybit_ob()
    finally:
        mod.websocket.WebSocketApp = original
    return capturado["on_message"]


def _msg(tipo, bids, asks):
    return json.dumps({"topic": "orderbook.50.BTCUSDT", "type": tipo,
                       "data": {"b": [[str(p), str(q)] for p, q in bids],
                                "a": [[str(p), str(q)] for p, q in asks]}})


def test_snapshot_preenche_o_livro():
    f = _fonte()
    on_message = _handler(f)
    on_message(None, _msg("snapshot", [(100.0, 1.0), (99.0, 2.0)], [(101.0, 1.5), (102.0, 3.0)]))
    assert f.order_book["bids"] == [(100.0, 1.0), (99.0, 2.0)]
    assert f.order_book["asks"] == [(101.0, 1.5), (102.0, 3.0)]
    assert f._erro_ob is None


def test_delta_mantem_os_niveis_que_nao_mudaram():
    """O bug antigo: cada delta virava o livro inteiro, restando um nível só."""
    f = _fonte()
    on_message = _handler(f)
    on_message(None, _msg("snapshot", [(100.0, 1.0), (99.0, 2.0), (98.0, 5.0)], [(101.0, 1.5), (102.0, 3.0)]))
    on_message(None, _msg("delta", [(99.0, 7.0)], []))
    bids = dict(f.order_book["bids"])
    assert len(bids) == 3, "os níveis não tocados pelo delta têm que continuar no livro"
    assert bids[99.0] == 7.0, "o nível do delta tem que ser atualizado"
    assert bids[100.0] == 1.0 and bids[98.0] == 5.0
    assert len(f.order_book["asks"]) == 2, "delta sem asks não pode apagar os asks"


def test_tamanho_zero_remove_o_nivel():
    f = _fonte()
    on_message = _handler(f)
    on_message(None, _msg("snapshot", [(100.0, 1.0), (99.0, 2.0)], [(101.0, 1.5)]))
    on_message(None, _msg("delta", [(99.0, 0.0)], []))
    assert dict(f.order_book["bids"]) == {100.0: 1.0}


def test_livro_fica_ordenado():
    f = _fonte()
    on_message = _handler(f)
    on_message(None, _msg("snapshot", [(98.0, 1.0), (100.0, 1.0), (99.0, 1.0)], [(103.0, 1.0), (101.0, 1.0)]))
    assert [p for p, _ in f.order_book["bids"]] == [100.0, 99.0, 98.0], "compras da maior para a menor"
    assert [p for p, _ in f.order_book["asks"]] == [101.0, 103.0], "vendas da menor para a maior"


def test_mensagem_ruim_nao_derruba_nem_inunda_o_log():
    f = _fonte()
    on_message = _handler(f)
    on_message(None, "isto nao e json")
    on_message(None, json.dumps({"topic": "orderbook.50.BTCUSDT", "data": "formato inesperado"}))
    assert f._erro_ob is not None, "o erro deve ser guardado, não propagado"
    on_message(None, _msg("snapshot", [(100.0, 1.0)], [(101.0, 1.0)]))
    assert f.order_book["bids"] == [(100.0, 1.0)], "depois do erro o livro volta a funcionar"


def test_dois_robos_nao_compartilham_o_mesmo_livro():
    """O estado do livro precisa ser por instância: como atributo de classe, dois bots se misturariam."""
    a, b = _fonte(), _fonte()
    ha, hb = _handler(a), _handler(b)
    ha(None, _msg("snapshot", [(100.0, 1.0)], [(101.0, 1.0)]))
    hb(None, _msg("snapshot", [(200.0, 2.0)], [(201.0, 2.0)]))
    assert a.order_book["bids"] == [(100.0, 1.0)]
    assert b.order_book["bids"] == [(200.0, 2.0)]
