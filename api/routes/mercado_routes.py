# api/routes/mercado_routes.py
"""
Candles públicos da Bybit para o painel e o estado do conselho (Telegram, serviço de avisos, coletor do livro).

Substitui /status/mercado/candles e /status/ do sistema de robôs apagado em 20/10/2026.
"""
import glob
import os
import time

from fastapi import APIRouter, HTTPException, Query

from conselho import mercado

router = APIRouter()

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA_LIVRO = os.path.join(RAIZ, "dados", "livro")
LIMITE_MAX = 2000


@router.get("/candles")
def candles(par: str = Query("BTCUSDT"), timeframe: str = Query("5m"), limite: int = Query(300, ge=2, le=LIMITE_MAX)):
    """Os últimos `limite` candles (timestamp em ms), do mais velho para o mais novo."""
    minutos = mercado.INTERVALO_MIN.get(timeframe)
    if minutos is None:
        raise HTTPException(400, f"timeframe sem suporte: {timeframe}")
    agora = int(time.time() * 1000)
    try:
        dados = mercado.candles(par.upper(), timeframe, agora - limite * minutos * 60_000, agora, pausa_s=0)
    except Exception as e:
        raise HTTPException(502, f"Bybit indisponível: {e}")
    return {"par": par.upper(), "timeframe": timeframe, "candles": dados[-limite:]}


def _idade_coletor():
    """Segundos desde a última gravação do coletor, por exchange (None = nunca gravou)."""
    saida = {}
    for ex in ("coinbase", "binance", "bybit"):
        arquivos = glob.glob(os.path.join(PASTA_LIVRO, ex, "*.jsonl.gz"))
        saida[ex] = int(time.time() - max(os.path.getmtime(a) for a in arquivos)) if arquivos else None
    return saida


@router.get("/status")
def status():
    from conselho.servico_avisos import get_avisos_service
    try:
        avisos = get_avisos_service().status()
    except Exception as e:
        avisos = {"ativo": False, "ultimo_erro": str(e)}
    return {"avisos": avisos, "telegram": bool(avisos.get("telegram")), "coletor_idade_s": _idade_coletor()}
