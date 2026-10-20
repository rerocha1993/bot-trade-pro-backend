"""
O conselho de avisos no painel (conselho/mapa_do_dia.py, conselho/avisos.py, services/avisos_service.py).

    GET /api/avisos/mapa          o mapa do dia de agora: níveis com rótulo e distância % ao preço, posição no composto
    GET /api/avisos/ultimos?n=50  os últimos avisos gravados em data/avisos.jsonl (mapa e proximidade)

Só informação: nenhum nível traz probabilidade, stop ou alvo. Funciona com a thread desligada (o mapa é montado
na hora); com SERVICO_AVISOS=1 a thread grava e envia os avisos sozinha.
"""
from typing import Dict

from fastapi import APIRouter, Query

from conselho.avisos import RESSALVA
from conselho.servico_avisos import get_avisos_service

router = APIRouter()


@router.get("/mapa")
def mapa() -> Dict:
    s = get_avisos_service()
    m = s.mapa_atual()
    return {**m.as_dict(), "ressalva": RESSALVA, "servico": s.status()}


@router.get("/ultimos")
def ultimos(n: int = Query(50, ge=1, le=500)) -> Dict:
    s = get_avisos_service()
    return {"avisos": s.ultimos(n), "servico": s.status()}
