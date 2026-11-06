"""Velas de delta e de volume (conselho/velas_fluxo.py) com minutos montados à mão."""
import gzip
import json
import os
from datetime import datetime, timezone

from conselho import velas_fluxo as vf


def _min(ts, preco, compra, venda):
    return (ts, preco, preco + 1, preco - 1, preco, compra, venda, (compra + venda) / preco)


def test_delta_fecha_no_limiar_e_continua_a_aberta():
    m = [_min(0, 100.0, 4e6, 0), _min(60, 101.0, 4e6, 0), _min(120, 102.0, 3e6, 0),   # +11M: fecha
         _min(180, 101.0, 0, 6e6), _min(240, 100.0, 0, 5e6),                           # -11M: fecha
         _min(300, 100.0, 1e6, 0)]                                                    # aberta
    fechadas, aberta = vf.montar(m, "delta", 10e6)
    assert [(v["t"], v["fim"]) for v in fechadas] == [(0, 120), (180, 240)]
    assert fechadas[0]["o"] == 100.0 and fechadas[0]["c"] == 102.0 and fechadas[0]["h"] == 103.0
    assert round(fechadas[1]["compra"] - fechadas[1]["venda"]) == -11e6
    assert aberta["t"] == 300
    # continuar de onde parou dá o mesmo que montar tudo de uma vez
    a1, ab1 = vf.montar(m[:4], "delta", 10e6)
    a2, ab2 = vf.montar(m[4:], "delta", 10e6, ab1)
    assert [v["t"] for v in a1 + a2] == [0, 180] and ab2["t"] == 300


def test_delta_que_vai_e_volta_nao_fecha():
    m = [_min(0, 100.0, 8e6, 0), _min(60, 100.0, 0, 8e6), _min(120, 100.0, 8e6, 0)]
    fechadas, aberta = vf.montar(m, "delta", 10e6)
    assert fechadas == [] and aberta["t"] == 0


def test_volume_soma_os_dois_lados():
    m = [_min(0, 100.0, 3e6, 3e6), _min(60, 100.0, 2e6, 2e6), _min(120, 100.0, 1e6, 0)]
    fechadas, aberta = vf.montar(m, "volume", 10e6)
    assert [v["fim"] for v in fechadas] == [60] and aberta["t"] == 120


def test_velas_lidas_do_disco_com_origem_comum(tmp_path):
    dia = int(datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp())
    for ex, preco in (("binance", 100.0), ("bybit", 101.0)):
        os.makedirs(tmp_path / ex)
        with gzip.open(tmp_path / ex / "2026-10-20.jsonl.gz", "wt", encoding="utf-8") as f:
            for i in range(3):
                f.write(json.dumps({"ts": dia + 60 * i, "compra": 40000.0 / preco, "venda": 0.0, "abertura": preco,
                                    "maxima": preco, "minima": preco, "fechamento": preco, "niveis": []}) + "\n")
    v = vf.velas(["bybit", "binance"], "delta", 150000.0, agora_s=dia + 3 * 86400, raiz=str(tmp_path))
    # 80 mil US$ por minuto somando as duas: fecha no 2º minuto; o 3º fica aberto. O preço é o da Binance.
    assert [(x["t"], x.get("aberta")) for x in v] == [(dia, None), (dia + 120, True)]
    assert v[0]["c"] == 100.0
    assert vf.linha_api(v[0])[6] == 160000
