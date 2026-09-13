# api/routes/tradeiros_routes.py
"""
PORTAL TRADEIROS no painel (tradeiros/): a leitura do dia, o mapa de Elliott com várias contagens e o plano do Shaka
e do Maroja — e o resultado do backtest da carteira. Só leitura: nada aqui envia ordem nem mexe nos robôs.

    GET /api/tradeiros/plano                    ao vivo: CSVs do projeto + candles recentes da Bybit (refeito a cada 5 min)
    GET /api/tradeiros/plano?data=2025-04-07    replay: o plano daquele dia às 13:00 UTC, só com o que tinha fechado
    GET /api/tradeiros/backtest                 resumo de data/estudo_tradeiros.json (scripts/backtest_tradeiros.py)
"""
import datetime as dt
import json
import math
import os
import threading
import time
from typing import Dict, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from core.tpo_sessao import BLOCO_MS, DIA_MS
from tradeiros.elliott_mapa import MapaElliott
from tradeiros.leitura import Dados, LeituraDiaria
from tradeiros.regras import PERFIS, planejar

router = APIRouter()

ESTUDO = os.path.join("data", "estudo_tradeiros.json")
VALIDADE_VIVO_S = 300
COLS = ["timestamp", "open", "high", "low", "close", "volume"]
CAMPOS_ANO = ("btc_final", "ganho_btc_pct", "retorno_usd_pct", "hodl_usd_pct", "dd_btc_pct", "dd_usd_pct", "dd_hodl_pct",
              "hedge_medio_pct", "trades", "r_total", "stops_hedge", "funding_btc", "taxas_btc")
_trava = threading.Lock()
_historico: Dict[str, object] = {}
_vivo: Dict[str, object] = {}


def _puro(x):
    """numpy e NaN não serializam em JSON: sai tipo puro (bool antes de int: bool é subclasse de int)."""
    if isinstance(x, dict):
        return {str(k): _puro(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_puro(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    return x


def _com_historico() -> Dict[str, object]:
    """Todos os CSVs, carregados uma vez: serve o replay de qualquer data."""
    with _trava:
        if "dados" not in _historico:
            d = Dados.do_projeto(".")
            _historico.update(dados=d, leitura=LeituraDiaria(d), mapa=MapaElliott(d), fonte="replay com os CSVs do projeto")
        return _historico


def _ao_vivo() -> Dict[str, object]:
    with _trava:
        if _vivo.get("t") and time.time() - _vivo["t"] < VALIDADE_VIVO_S:
            return _vivo
        agora = int(time.time() * 1000)
        recentes: Dict[str, pd.DataFrame] = {}
        fonte = "CSVs do projeto + candles recentes da Bybit"
        try:
            from services.bot_manager import get_manager
            con = get_manager().servicos["connectors"]["simulador"]
            for tf, dias in (("1d", 400), ("4h", 400), ("30m", 25)):
                c = con.obter_ohlcv_historico("BTCUSDT", tf, agora - dias * DIA_MS)
                if c:
                    recentes[tf] = pd.DataFrame([list(x[:6]) for x in c], columns=COLS)
        except Exception as e:                                      # sem a Bybit, o portal segue com os CSVs
            fonte = f"só CSVs do projeto (Bybit indisponível: {type(e).__name__})"
        d = Dados.do_projeto(".", recentes=recentes, intraday_dias=45)
        _vivo.update(t=time.time(), dados=d, leitura=LeituraDiaria(d), mapa=MapaElliott(d), fonte=fonte)
        return _vivo


def _resposta(fontes: Dict[str, object], ts: int) -> Dict:
    dados: Dados = fontes["dados"]
    lt = fontes["leitura"].ler(ts)
    mp = fontes["mapa"].ler(ts)
    leitura = lt.as_dict()
    return _puro({
        "ts": ts, "fonte": fontes["fonte"], "preco": lt.preco,
        "dados_ate": {"candles": (dados.blocos_ate(ts)[-1][0] + BLOCO_MS) if dados.blocos_ate(ts) else None,
                      "derivativos": dados.oi[0][-1] if dados.oi[0] else None},
        "leitura": {k: v for k, v in leitura.items() if k not in ("ts", "preco")},
        "mapa": {**mp, "contagens": (mp.get("contagens") or [])[:12]},
        "planos": {nome: planejar(lt, mp, pf).as_dict() for nome, pf in PERFIS.items()},
    })


@router.get("/plano")
def plano(data: Optional[str] = Query(None, description="AAAA-MM-DD para o replay; vazio = ao vivo"),
          hora: int = Query(13, ge=0, le=23, description="hora UTC do replay")) -> Dict:
    if data:
        try:
            ts = int(dt.datetime.fromisoformat(f"{data}T{hora:02d}:00").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        except ValueError:
            raise HTTPException(400, "data no formato AAAA-MM-DD")
        fontes = _com_historico()
    else:
        ts = int(time.time() * 1000)
        fontes = _ao_vivo()
    try:
        return _resposta(fontes, ts)
    except ValueError as e:
        raise HTTPException(404, f"sem dados até esse momento: {e}")


@router.get("/backtest")
def backtest() -> Dict:
    if not os.path.exists(ESTUDO):
        return {"disponivel": False, "gerado_em": None, "periodos": {}, "anos": {}}
    with open(ESTUDO, encoding="utf-8") as f:
        est = json.load(f)
    anos = {}
    for nome, por_ano in (est.get("anos") or {}).items():
        linhas = []
        for ano, r in sorted(por_ano.items(), key=lambda kv: int(kv[0])):
            c, s = r["carteira"], sorted(r.get("sorteios_btc") or [])
            linhas.append({"ano": int(ano), **{k: c.get(k) for k in CAMPOS_ANO}, "fixo_btc": r.get("fixo_btc"),
                           "sorteio_mediana": float(np.median(s)) if s else None,
                           "sorteio_p95": float(np.percentile(s, 95)) if s else None,
                           "percentil": (sum(x < c["btc_final"] for x in s) / len(s)) if s else None})
        anos[nome] = linhas
    return _puro({"disponivel": True, "gerado_em": int(os.path.getmtime(ESTUDO) * 1000),
                  "periodos": est.get("periodos") or {}, "anos": anos})
