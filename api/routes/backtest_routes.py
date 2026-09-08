# api/routes/backtest_routes.py
"""
Backtest de validação (obrigatório antes de ativar um bot em testnet/real).

    POST /backtest/bots/{id}?dias=180        roda em segundo plano com a configuração do bot
    GET  /backtest/bots/{id}                 histórico de backtests do bot + se pode ativar
    GET  /backtest/                          todos (filtro por par)
    GET  /backtest/{backtest_id}             detalhes (resumo, últimos trades, critérios)
    GET  /backtest/pares/validar?par=SOLUSDT confere se o par existe na Bybit linear
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from models.backtest_bot import BacktestBot
from models.bot import Bot
from services.backtest_service import BacktestService, CRITERIOS_PADRAO
from services.bot_manager import get_manager

router = APIRouter()


def _svc() -> BacktestService:
    return get_manager().backtests


@router.post("/bots/{bot_id}")
def rodar_backtest(bot_id: int, dias: Optional[int] = None, min_trades: int = CRITERIOS_PADRAO["min_trades"],
                   min_fator_lucro: float = CRITERIOS_PADRAO["min_fator_lucro"],
                   max_drawdown_pct: float = CRITERIOS_PADRAO["max_drawdown_pct"], db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot não encontrado")
    try:
        info = _svc().validar_par(bot.ativo)
    except Exception as e:
        raise HTTPException(400, f"Par {bot.ativo} não disponível na Bybit linear: {str(e)[:120]}")
    iniciado = _svc().rodar_em_background(bot_id, dias, {"min_trades": min_trades, "min_fator_lucro": min_fator_lucro,
                                                          "max_drawdown_pct": max_drawdown_pct})
    return {"iniciado": iniciado, "em_andamento": _svc().em_andamento(bot_id), "par": info["symbol"],
            "mensagem": "Backtest rodando em segundo plano; consulte GET /backtest/bots/{id}" if iniciado else "Já existe um backtest em andamento para este bot"}


@router.get("/bots/{bot_id}")
def backtests_do_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot não encontrado")
    ok, motivo = BacktestService.pode_ativar(db, bot)
    return {"bot_id": bot_id, "em_andamento": _svc().em_andamento(bot_id), "pode_ativar": ok, "motivo": motivo,
            "backtests": [b.as_dict() for b in BacktestService.listar(db, bot_id=bot_id)]}


@router.get("/")
def listar(par: Optional[str] = None, limite: int = Query(50, le=500), db: Session = Depends(get_db)):
    return [b.as_dict() for b in BacktestService.listar(db, par=par, limite=limite)]


@router.get("/pares/validar")
def validar_par(par: str):
    try:
        return {"ok": True, **_svc().validar_par(par)}
    except Exception as e:
        return {"ok": False, "erro": str(e)[:200]}


@router.get("/{backtest_id}")
def detalhe(backtest_id: int, db: Session = Depends(get_db)):
    b = db.query(BacktestBot).filter(BacktestBot.id == backtest_id).first()
    if not b:
        raise HTTPException(404, "Backtest não encontrado")
    d = b.as_dict()
    for k in ("detalhes", "parametros"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d
