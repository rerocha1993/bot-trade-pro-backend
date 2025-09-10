from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from api.database import SessionLocal
from models.log_execucao import LogExecucaoBot

router = APIRouter()

@router.get("/{bot_id}")
def listar_logs(bot_id: int):
    session: Session = SessionLocal()
    try:
        logs = session.query(LogExecucaoBot).filter(LogExecucaoBot.bot_id == bot_id).all()
        return logs
    finally:
        session.close()

@router.get("/{bot_id}/ultimos")
def ultimos_logs(bot_id: int, limite: int = 10):
    session: Session = SessionLocal()
    try:
        logs = (session.query(LogExecucaoBot)
                      .filter(LogExecucaoBot.bot_id == bot_id)
                      .order_by(LogExecucaoBot.data_execucao.desc())
                      .limit(limite)
                      .all())
        return logs
    finally:
        session.close()