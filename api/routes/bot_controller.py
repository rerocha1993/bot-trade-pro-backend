from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from services.bot_service import BotService
from api.database import get_db
from models.bot import Bot

router = APIRouter()

@router.post("/criar_bot")
def criar_bot(bot_data: dict, db: Session = Depends(get_db)):
    bot = Bot(
        nome=bot_data["nome"],
        ativo=bot_data["ativo"],
        timeframe=bot_data["timeframe"],
        modo_execucao=bot_data.get("modo_execucao", "simulador"), # aqui está o padrão
    )
    db.add(bot)
    db.commit()
    return bot

@router.post("/")
async def criar_bot(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    try:
        for campo in ["banca", "risco_pct", "max_alocacao_pct"]:
            if campo not in data or data[campo] is None:
                raise HTTPException(status_code=400, detail=f"Campo obrigatório ausente: {campo}")
        data["banca"] = float(data["banca"])
        data["risco_pct"] = float(data["risco_pct"])
        data["max_alocacao_pct"] = float(data["max_alocacao_pct"])
        data["confluencia_tipo"] = data.get("confluencia_tipo", "conservador").lower()
        if data.get("min_quantidade") is not None:
            data["min_quantidade"] = float(data["min_quantidade"])
        if data.get("max_quantidade") is not None:
            data["max_quantidade"] = float(data["max_quantidade"])

        service = BotService(db)
        bot = service.create_bot(data)
        return bot
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar bot: {str(e)}")

@router.put("/{bot_id}")
async def editar_bot(bot_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    try:
        if "banca" in data and data["banca"] is not None:
            data["banca"] = float(data["banca"])
        if "risco_pct" in data and data["risco_pct"] is not None:
            data["risco_pct"] = float(data["risco_pct"])
        if "max_alocacao_pct" in data and data["max_alocacao_pct"] is not None:
            data["max_alocacao_pct"] = float(data["max_alocacao_pct"])
        if "min_quantidade" in data and data["min_quantidade"] is not None:
            data["min_quantidade"] = float(data["min_quantidade"])
        if "max_quantidade" in data and data["max_quantidade"] is not None:
            data["max_quantidade"] = float(data["max_quantidade"])
        if "confluencia_tipo" in data and data["confluencia_tipo"]:
            data["confluencia_tipo"] = data["confluencia_tipo"].lower()

        service = BotService(db)
        bot = service.update_bot(bot_id, data)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot não encontrado")
        return bot
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao editar bot: {str(e)}")

@router.get("/{bot_id}")
def get_bot(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    bot = service.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot não encontrado")
    return bot

@router.get("/")
async def listar_bots(db: Session = Depends(get_db)):
    service = BotService(db)
    bots = service.get_bots()
    # Dica: serialize como quiser, exemplo simples abaixo:
    return JSONResponse(content=[bot.as_dict() for bot in bots])


@router.post("/{bot_id}/ativar_trailing")
def ativar_trailing(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    bot = service.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot não encontrado")
    # Aqui você marca o trailing ativo (pode ser um campo na posição aberta ou no bot)
    bot.trailing_manual = True
    db.commit()
    return {"message": "Trailing stop ativado manualmente"}

@router.post("/{bot_id}/desativar_trailing")
def desativar_trailing(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    bot = service.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot não encontrado")
    bot.trailing_manual = False
    db.commit()
    return {"message": "Trailing stop desativado manualmente"}