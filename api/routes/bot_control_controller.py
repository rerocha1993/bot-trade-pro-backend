from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.database import get_db
from models.bot import Bot
from models.log_execucao import LogExecucaoBot
from services.bot_manager import BotManager

router = APIRouter()

@router.post("/{bot_id}/ativar")
def ativar_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if bot:
        bot.ativo_bot = True
        db.commit()
        return {"status": "ativado"}
    return {"erro": "bot não encontrado"}

@router.post("/{bot_id}/desativar")
def desativar_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if bot:
        bot.ativo_bot = False
        db.commit()
        return {"status": "desativado"}
    return {"erro": "bot não encontrado"}

@router.get("/")
def listar_bots_com_status(db: Session = Depends(get_db)):
    bots = db.query(Bot).all()
    resposta = []
    for bot in bots:
        ultimo_log = (
            db.query(LogExecucaoBot)
            .filter(LogExecucaoBot.bot_id == bot.id)
            .order_by(LogExecucaoBot.data_execucao.desc())
            .first()
        )
        resposta.append({
            "id": bot.id,
            "nome": bot.nome,
            "ativo": bot.ativo_bot,
            "ativo_nome": bot.ativo,
            "timeframe": bot.timeframe,
            "ultimo_status": ultimo_log.acao if ultimo_log else None,
            "ultima_execucao": ultimo_log.data_execucao if ultimo_log else None,
        })
    return resposta

@router.get("/{bot_id}/historico")
def historico_execucoes(bot_id: int, limite: int = 100, db: Session = Depends(get_db)):
    logs = (
        db.query(LogExecucaoBot)
        .filter(LogExecucaoBot.bot_id == bot_id)
        .order_by(LogExecucaoBot.data_execucao.desc())
        .limit(limite)
        .all()
    )
    return [
        {
            "data": log.data_execucao,
            "acao": log.acao,
            "preco": log.preco,
            "motivo": log.motivo,
            "resultado": log.resultado,
            "erro": log.erro
        }
        for log in logs
    ]

@router.put("/executar/{bot_nome}")
async def executar_bot(bot_nome: str):
    sucesso = BotManager.start_bot(bot_nome)
    return {"executando": sucesso}

@router.put("/parar/{bot_nome}")
async def parar_bot(bot_nome: str):
    sucesso = BotManager.stop_bot(bot_nome)
    return {"executando": not sucesso}
