import importlib.util
import os

from conselho.coletor_livro import gravar_snapshot

_spec = importlib.util.spec_from_file_location(
    "preencher_negocios", os.path.join(os.path.dirname(__file__), "..", "scripts", "preencher_negocios.py"))
pn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pn)


def test_trechos_junta_minutos_seguidos():
    assert pn.trechos([0, 60, 120, 600, 660]) == [(0, 180), (600, 720)]
    assert pn.trechos([]) == []


def test_preenche_so_o_que_falta(tmp_path):
    t0 = 1792540800
    for m in (t0, t0 + 60, t0 + 240):                    # o coletor gravou 3 minutos; faltam t0+120 e t0+180
        gravar_snapshot({"ts": m, "exchange": "binance", "compra": 1.0, "venda": 1.0}, str(tmp_path))
    assert pn.minutos_faltando("binance", t0, t0 + 300, str(tmp_path)) == [t0 + 120, t0 + 180]

    pedidos = []

    def falsa(a, b):
        pedidos.append((a, b))
        return [(a + 5, 100.0, 2.0, True), (a + 70, 101.0, 1.0, False), (t0 + 10, 99.0, 9.0, True)]   # o último já existe

    pn.BUSCAS["binance"] = falsa
    n = pn.preencher("binance", horas=300 / 3600, raiz=str(tmp_path), agora_s=t0 + 300 + 120)
    assert pedidos == [(t0 + 120, t0 + 240)] and n == 2
    assert pn.minutos_faltando("binance", t0, t0 + 300, str(tmp_path)) == []
