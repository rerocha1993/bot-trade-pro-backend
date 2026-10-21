# api/routes/robos_routes.py
"""Os 4 robôs do conselho em simulação (conselho/servico_robos.py): placar, posições e trades."""
from typing import Dict

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("")
def status() -> Dict:
    from conselho.servico_robos import get_servico_robos
    return get_servico_robos().status()


@router.get("/trades")
def trades(n: int = Query(200, ge=1, le=5000)) -> Dict:
    from conselho.servico_robos import get_servico_robos
    return {"trades": list(reversed(get_servico_robos().trades(n)))}
