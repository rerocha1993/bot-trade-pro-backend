from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from models.bot import Bot, Base
from api.database import SessionLocal

router = APIRouter()

@router.post("/")
def criar_bot(bot: dict):
    session = SessionLocal()
    try:
        novo_bot = Bot(**bot)
        session.add(novo_bot)
        session.commit()
        return {"mensagem": "Bot criado com sucesso", "id": novo_bot.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.get("/ativos")
def listar_bots_ativos():
    session = SessionLocal()
    try:
        bots = session.query(Bot).filter(Bot.ativo_bot == True).all()
        return bots
    finally:
        session.close()