import os

import pandas as pd
import pytest

from conselho.servico_carteira import ServicoCarteira, inicio_ms
from conselho.tpo import BLOCO_MS

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEM_HISTORICO = os.path.exists(os.path.join(RAIZ, "data", "historico", "BTCUSDT_binance_15m.csv"))


def _velas(ini, n):
    return pd.DataFrame([[ini + i * BLOCO_MS, 1.0, 2.0, 0.5, 1.5, 3.0] for i in range(n)],
                        columns=["timestamp", "open", "high", "low", "close", "volume"])


def test_velas_guardadas_somam_as_novas_e_a_nova_vale_no_mesmo_instante(tmp_path):
    ini = inicio_ms("2026-10-28")
    s = ServicoCarteira(pasta=str(tmp_path), inicio=ini, buscar=lambda agora: {})
    agora = ini + 10 * BLOCO_MS
    s._guardar_velas(_velas(ini - 2 * BLOCO_MS, 4), agora)
    nova = _velas(ini + BLOCO_MS, 3)
    nova.loc[0, "close"] = 9.0
    tudo = s._guardar_velas(nova, agora)
    assert list(tudo["timestamp"]) == [ini + k * BLOCO_MS for k in range(-2, 4)]
    assert tudo.loc[tudo["timestamp"] == ini + BLOCO_MS, "close"].item() == 9.0
    velhas = _velas(ini - 40 * 86_400_000, 2)                    # antes do início − 30 dias: descartadas
    assert s._guardar_velas(velhas, agora)["timestamp"].min() == ini - 2 * BLOCO_MS
    # a vela aberta (começou há menos de 30 min) não é gravada
    aberta = _velas(agora - BLOCO_MS // 2, 1)
    assert s._guardar_velas(aberta, agora)["timestamp"].max() == ini + 3 * BLOCO_MS


@pytest.mark.skipif(not TEM_HISTORICO, reason="sem data/historico (servidor)")
def test_calcular_roda_os_dois_operadores_ate_o_ultimo_bloco_fechado(tmp_path):
    ini = inicio_ms("2026-10-10")
    agora_s = (inicio_ms("2026-10-12") + 75 * 60 * 1000) / 1000      # 01:15 do dia 12: o bloco de 01:00 está aberto
    s = ServicoCarteira(pasta=str(tmp_path), raiz=RAIZ, inicio=ini, buscar=lambda agora: {"falhas": []},
                        relogio=lambda: agora_s)
    r = s.calcular()
    assert r["fim_ms"] == inicio_ms("2026-10-12") + 60 * 60 * 1000
    for nome in ("shaka", "maroja"):
        o = r["operadores"][nome]
        assert "erro" not in o and o["estado"] is not None
        assert o["estado"]["btc_patrimonio"] == pytest.approx(o["btc_final"])
    assert os.path.exists(os.path.join(str(tmp_path), "estado.json"))


@pytest.mark.skipif(not TEM_HISTORICO, reason="sem data/historico (servidor)")
def test_leitura_de_dia_ja_planejado_nao_muda_depois(tmp_path):
    ini = inicio_ms("2026-10-10")
    agora_s = (inicio_ms("2026-10-12") + 75 * 60 * 1000) / 1000
    s = ServicoCarteira(pasta=str(tmp_path), raiz=RAIZ, inicio=ini, buscar=lambda agora: {"falhas": []},
                        relogio=lambda: agora_s)
    primeiro = s.calcular()
    assert sorted(s.leituras) == [ini, ini + 86_400_000, ini + 2 * 86_400_000]
    # outro processo (reinício) lê as leituras do disco e chega ao mesmo resultado
    s2 = ServicoCarteira(pasta=str(tmp_path), raiz=RAIZ, inicio=ini, buscar=lambda agora: {"falhas": []},
                         relogio=lambda: agora_s)
    assert sorted(s2.leituras) == sorted(s.leituras)
    assert s2.calcular()["operadores"]["shaka"]["btc_final"] == primeiro["operadores"]["shaka"]["btc_final"]
    # com uma busca falhando, a leitura de dia novo não é guardada
    s3 = ServicoCarteira(pasta=str(tmp_path / "b"), raiz=RAIZ, inicio=ini, buscar=lambda agora: {"falhas": ["oi: Timeout"]},
                         relogio=lambda: agora_s)
    s3.calcular()
    assert s3.leituras == {}
