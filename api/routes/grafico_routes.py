# api/routes/grafico_routes.py
"""
Tela Gráfico: velas de qualquer moeda em Coinbase, Binance, Bybit e OKX (conselho/velas.py), a lista de pares e o
TPO de 30 min por dia e a junção de dias escolhidos no gráfico (conselho/tpo_grafico.py).

Velas que já fecharam não mudam: guardadas 30 min. A janela que termina agora vale 2 s, para o painel poder perguntar
a vela aberta a cada poucos segundos sem martelar a corretora. A lista de pares vale 12 h.
"""
import threading
import time
from collections import OrderedDict

import requests
from fastapi import APIRouter, HTTPException, Query

from conselho import tpo_grafico
from conselho import velas as V

router = APIRouter()

CACHE_FECHADAS_S = 1800
CACHE_AO_VIVO_S = 2
CACHE_LISTA_S = 12 * 3600
CACHE_TPO_S = 30
DIAS_TPO_MAX = 30
MAX_ITENS = 256

_http = requests.Session()
_cache: "OrderedDict[tuple, tuple]" = OrderedDict()
_travas: dict = {}
_trava_global = threading.Lock()


def _guardado(chave: tuple, validade_s: float, calcular):
    """Devolve o valor em cache ou calcula uma vez só, mesmo com pedidos iguais chegando juntos."""
    with _trava_global:
        item = _cache.get(chave)
        if item and time.time() - item[0] < validade_s:
            _cache.move_to_end(chave)
            return item[1]
        trava = _travas.setdefault(chave, threading.Lock())
    with trava:
        with _trava_global:
            item = _cache.get(chave)
            if item and time.time() - item[0] < validade_s:
                return item[1]
        valor = calcular()
        with _trava_global:
            _cache[chave] = (time.time(), valor)
            _cache.move_to_end(chave)
            while len(_cache) > MAX_ITENS:
                velha, _ = _cache.popitem(last=False)
                _travas.pop(velha, None)
        return valor


@router.get("/corretoras")
def corretoras():
    """Corretoras, mercados e tempos gráficos que a tela oferece."""
    return {"corretoras": {c: list(m) for c, m in V.CORRETORAS.items()}, "tempos": list(V.TEMPOS)}


@router.get("/velas")
def velas(simbolo: str = Query("COINBASE:BTC-USD"), tempo: str = Query("30m"),
          ate: int = Query(None, description="início (s) da vela mais nova; sem ele, até agora"),
          n: int = Query(500, ge=1, le=V.N_MAX)):
    """As `n` velas até `ate` ([início_s, o, h, l, c, v], crescente) e se o símbolo tem nuvem (só COINBASE:BTC-USD)."""
    try:
        s = V.ler_simbolo(simbolo)
        if tempo not in V.TEMPOS:
            raise ValueError(f"tempo sem suporte: {tempo}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    passo = V.TEMPOS[tempo]
    agora = int(time.time())
    fechadas = ate is not None and ate + passo <= agora
    ate_alinhado = (ate if ate is not None else agora) // passo * passo
    chave = ("velas", s.texto, tempo, ate_alinhado if fechadas else None, n)
    try:
        dados = _guardado(chave, CACHE_FECHADAS_S if fechadas else CACHE_AO_VIVO_S,
                          lambda: V.velas(s.texto, tempo, ate if fechadas else None, n, _http))
    except requests.HTTPError as e:
        codigo = e.response.status_code if e.response is not None else 502
        raise HTTPException(404 if codigo in (400, 404) else 502, f"{s.corretora} recusou {s.texto}: {e}")
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(502, f"{s.corretora} indisponível: {e}")
    return {"simbolo": s.texto, "tempo": tempo, "nuvem": V.tem_nuvem(s), "velas": dados}


@router.get("/tpo")
def tpo(simbolo: str = Query("COINBASE:BTC-USD"), dias: int = Query(10, ge=1, le=DIAS_TPO_MAX)):
    """TPO de 30 min dos últimos `dias` dias e de hoje: contagem por faixa, POC/VAH/VAL e quando cada nível foi tocado."""
    try:
        s = V.ler_simbolo(simbolo)
    except ValueError as e:
        raise HTTPException(400, str(e))

    def calcular():
        velas_30m = V.velas(s.texto, "30m", None, (dias + 2) * 48, _http)
        return tpo_grafico.perfis_por_dia(velas_30m, int(time.time()), dias)

    try:
        perfis = _guardado(("tpo", s.texto, dias), CACHE_TPO_S, calcular)
    except requests.HTTPError as e:
        codigo = e.response.status_code if e.response is not None else 502
        raise HTTPException(404 if codigo in (400, 404) else 502, f"{s.corretora} recusou {s.texto}: {e}")
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(502, f"{s.corretora} indisponível: {e}")
    return {"simbolo": s.texto, **perfis}


@router.get("/tpo/composto")
def tpo_composto(simbolo: str = Query("COINBASE:BTC-USD"),
                 de: int = Query(..., description="início (s, 00:00 UTC) do primeiro dia"),
                 ate: int = Query(..., description="início (s, 00:00 UTC) do último dia"),
                 tick: float = Query(None, gt=0, description="a mesma faixa do /tpo, para a grade bater")):
    """Junção (composto) dos dias de `de` até `ate`: contagem somada, POC/VAH/VAL próprios e toques depois do fim."""
    try:
        s = V.ler_simbolo(simbolo)
    except ValueError as e:
        raise HTTPException(400, str(e))
    agora = int(time.time())
    de, ate = min(de, ate), max(de, ate)
    if agora - de > (DIAS_TPO_MAX + 1) * 86400:
        raise HTTPException(400, f"só dá para juntar dias dos últimos {DIAS_TPO_MAX}")

    def calcular():
        n = (agora - de) // 1800 + 96
        velas_30m = V.velas(s.texto, "30m", None, n, _http)
        return tpo_grafico.composto(velas_30m, agora, de, ate, tick)

    try:
        return {"simbolo": s.texto, **_guardado(("composto", s.texto, de, ate, tick), CACHE_TPO_S, calcular)}
    except requests.HTTPError as e:
        codigo = e.response.status_code if e.response is not None else 502
        raise HTTPException(404 if codigo in (400, 404) else 502, f"{s.corretora} recusou {s.texto}: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except requests.RequestException as e:
        raise HTTPException(502, f"{s.corretora} indisponível: {e}")


@router.get("/simbolos")
def simbolos(corretora: str = Query("COINBASE"), mercado: str = Query("spot", pattern="^(spot|perp)$")):
    """Pares negociando na corretora (USD, USDT, USDC), os mais negociados primeiro."""
    try:
        lista = _guardado(("lista", corretora.upper(), mercado), CACHE_LISTA_S,
                          lambda: V.listar(corretora, mercado == "perp", _http))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except requests.RequestException as e:
        raise HTTPException(502, f"{corretora} indisponível: {e}")
    return {"corretora": corretora.upper(), "mercado": mercado, "simbolos": lista}
