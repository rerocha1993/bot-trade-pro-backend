# api/routes/carteira_routes.py
"""A carteira do Tradeiros em simulação (conselho/servico_carteira.py) e o resultado do backtest dela."""
import json
import os
from typing import Dict, Optional

from fastapi import APIRouter

router = APIRouter()

ESTUDO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                      "data", "estudo_tradeiros.json")


def _backtest() -> Optional[Dict]:
    """Só o resumo por período (scripts/backtest_tradeiros.py): BTC final, hedge fixo, p95 dos sorteios."""
    try:
        with open(ESTUDO, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return {"periodos": d.get("periodos"), "gerado_em": os.path.getmtime(ESTUDO)}


@router.get("")
def status() -> Dict:
    from conselho.servico_carteira import get_servico_carteira
    return {**get_servico_carteira().status(), "backtest": _backtest()}
