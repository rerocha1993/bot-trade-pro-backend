from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database import get_db
from models.log_execucao import LogExecucaoBot

router = APIRouter()


@router.get("/{bot_id}")
def listar_logs(bot_id: int, limite: int = 500, db: Session = Depends(get_db)):
    logs = (db.query(LogExecucaoBot).filter(LogExecucaoBot.bot_id == bot_id)
            .order_by(LogExecucaoBot.data_execucao.desc()).limit(limite).all())
    return [l.as_dict() for l in logs]


@router.get("/{bot_id}/ultimos")
def ultimos_logs(bot_id: int, limite: int = 10, db: Session = Depends(get_db)):
    logs = (db.query(LogExecucaoBot).filter(LogExecucaoBot.bot_id == bot_id)
            .order_by(LogExecucaoBot.data_execucao.desc()).limit(limite).all())
    return [l.as_dict() for l in logs]
