# conselho/tradeiros/ao_vivo.py
"""
PLANO AO VIVO do portal: os CSVs do projeto + os candles recentes da Bybit, refeitos a cada 5 min e compartilhados
entre o painel (api/routes/tradeiros_routes.py) e os robôs da demo (core/tradeiros_executor.py).

O plano do dia é feito como no backtest (tradeiros/carteira.py): à 00:00 UTC, só com o que tinha fechado até ali.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional

import pandas as pd

from conselho.tpo import DIA_MS
from conselho.tradeiros.elliott_mapa import MapaElliott
from conselho.tradeiros.leitura import Dados, LeituraDiaria
from conselho.tradeiros.regras import Perfil, Plano, planejar

COLS = ["timestamp", "open", "high", "low", "close", "volume"]
VALIDADE_S = 300


def candles_recentes(con, par: str = "BTCUSDT", agora_ms: Optional[int] = None) -> Dict[str, pd.DataFrame]:
    agora = agora_ms or int(time.time() * 1000)
    recentes: Dict[str, pd.DataFrame] = {}
    for tf, dias in (("1d", 400), ("4h", 400), ("30m", 25)):
        c = con.obter_ohlcv_historico(par, tf, agora - dias * DIA_MS)
        if c:
            recentes[tf] = pd.DataFrame([list(x[:6]) for x in c], columns=COLS)
    return recentes


class FontesAoVivo:
    def __init__(self, validade_s: int = VALIDADE_S):
        self.validade_s = validade_s
        self._trava = threading.Lock()
        self._fontes: Optional[Dict] = None
        self._t = 0.0

    def obter(self, con) -> Dict:
        """Dados, leitura e mapa. Sem a Bybit (`con` None ou fora do ar), segue só com os CSVs."""
        with self._trava:
            if self._fontes and time.time() - self._t < self.validade_s:
                return self._fontes
            fonte = "CSVs do projeto + candles recentes da Bybit"
            try:
                recentes = candles_recentes(con)
            except Exception as e:
                recentes, fonte = {}, f"só CSVs do projeto (Bybit indisponível: {type(e).__name__})"
            d = Dados.do_projeto(".", recentes=recentes, intraday_dias=45)
            self._fontes = {"dados": d, "leitura": LeituraDiaria(d), "mapa": MapaElliott(d), "fonte": fonte}
            self._t = time.time()
            return self._fontes


FONTES = FontesAoVivo()


def plano_do_dia(con, perfil: Perfil, hedge_atual: Optional[float], agora_ms: Optional[int] = None) -> Plano:
    agora = agora_ms or int(time.time() * 1000)
    fontes = FONTES.obter(con)
    ts = (agora // DIA_MS) * DIA_MS
    return planejar(fontes["leitura"].ler(ts), fontes["mapa"].ler(ts), perfil, hedge_atual)


def resumo_do_plano(plano: Plano) -> Dict:
    """Tipos puros para o status do robô (a thread da API lê isto)."""
    d = plano.as_dict()
    return {"hedge_alvo": d["hedge_alvo"], "hedge_regras": d["hedge_regras"],
            "decisoes": [{k: x.get(k) for k in ("tipo", "regras", "motivo", "zona", "stop", "alvo", "risco", "fracao_hedge",
                                                "exige_reacao", "rr")} for x in d["decisoes"]]}
