"""
O /status/ junta o estado de todos os robôs: um tipo do numpy em um deles derrubava a resposta inteira com 500.
"""
import json
import threading

import numpy as np
from fastapi.encoders import jsonable_encoder

from core.bot_executor import BotExecutor


def _executor(estado):
    ex = BotExecutor.__new__(BotExecutor)
    ex.estado = estado
    ex._rodando = threading.Event()
    ex.bot_id, ex.nome, ex.ordem_pendente = 10, "Range Tradeiros 30m", None
    return ex


def test_status_com_numpy_sai_em_tipos_puros():
    """O caso real do robô 10: a leitura do range guardava numpy.bool_ e numpy.float64."""
    ex = _executor({"range": {"leitura": {"range": {"valido": np.bool_(False), "val": np.float64(76480.0), "dias": np.int64(1)},
                                          "toques": {1: 0, -1: 0}},
                              "precos_pendentes": [np.float64(77066.0), np.float64(76807.0)]}})
    s = ex.status()
    json.dumps(jsonable_encoder(s))                  # antes: ValueError dentro do FastAPI -> 500
    faixa = s["range"]["leitura"]["range"]
    assert faixa["valido"] is False and type(faixa["val"]) is float and type(faixa["dias"]) is int
    assert all(type(x) is float for x in s["range"]["precos_pendentes"])


def test_status_normal_nao_muda():
    ex = _executor({"modo": "demo", "ciclos": 3, "posicao": None, "pnl_dia": 1.5})
    s = ex.status()
    assert s["modo"] == "demo" and s["ciclos"] == 3 and s["pnl_dia"] == 1.5 and s["nome"] == "Range Tradeiros 30m"
