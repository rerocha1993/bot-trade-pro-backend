# api/routes/bot_control_controller.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from models.bot import Bot
from models.log_execucao import LogExecucaoBot
from services.bot_manager import get_manager

router = APIRouter()


@router.post("/{bot_id}/ativar")
def ativar_bot(bot_id: int, forcar: bool = False, db: Session = Depends(get_db)):
    """Ativa o bot. Em testnet/real exige backtest aprovado nos últimos 30 dias (POST /backtest/bots/{id}); `forcar=true` ignora."""
    from services.backtest_service import BacktestService
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot não encontrado")
    ok, motivo = BacktestService.pode_ativar(db, bot)
    if not ok and not forcar:
        raise HTTPException(409, f"Backtest obrigatório antes de ativar: {motivo}")
    bot.ativo_bot = True
    db.commit()
    iniciado = get_manager().start_bot(bot_id, forcar=forcar)
    return {"status": "ativado", "executando": iniciado or get_manager().status_bot(bot_id) is not None, "validacao": motivo}


@router.post("/{bot_id}/desativar")
def desativar_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot não encontrado")
    bot.ativo_bot = False
    db.commit()
    get_manager().stop_bot(bot_id)
    return {"status": "desativado"}


@router.get("/")
def listar_bots_com_status(db: Session = Depends(get_db)):
    m = get_manager()
    resposta = []
    for bot in db.query(Bot).all():
        ultimo = db.query(LogExecucaoBot).filter(LogExecucaoBot.bot_id == bot.id).order_by(LogExecucaoBot.data_execucao.desc()).first()
        st = m.status_bot(bot.id)
        resposta.append({
            "id": bot.id, "nome": bot.nome, "ativo": bot.ativo_bot, "rodando": bool(st and st.get("thread_viva")),
            "ativo_nome": bot.ativo, "timeframe": bot.timeframe, "modo_execucao": bot.modo_execucao,
            "estilo_trade": bot.estilo_trade, "confluencia_tipo": bot.confluencia_tipo,
            "ultimo_status": ultimo.acao if ultimo else None, "ultima_execucao": ultimo.data_execucao if ultimo else None,
            "ultima_decisao": (st or {}).get("ultima_decisao"), "pnl_dia": (st or {}).get("pnl_dia"),
        })
    return resposta


@router.get("/{bot_id}/historico")
def historico_execucoes(bot_id: int, limite: int = 100, db: Session = Depends(get_db)):
    logs = (db.query(LogExecucaoBot).filter(LogExecucaoBot.bot_id == bot_id)
            .order_by(LogExecucaoBot.data_execucao.desc()).limit(limite).all())
    return [log.as_dict() for log in logs]


@router.put("/executar/{bot_id}")
def executar_bot(bot_id: int, forcar: bool = False):
    m = get_manager()
    ok = m.start_bot(bot_id, forcar=forcar)
    return {"executando": ok, "motivo": None if ok else getattr(m, "ultimo_bloqueio", {}).get(bot_id)}


@router.put("/parar/{bot_id}")
def parar_bot(bot_id: int):
    return {"parado": get_manager().stop_bot(bot_id)}
