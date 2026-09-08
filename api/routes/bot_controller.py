from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from services.bot_service import BotService
from api.database import get_db
from models.bot import Bot

import logging

from api.database import SessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)


# ---- Helpers ---------------------------------------------------------------

def _encode_payload(obj):
    """
    Converte ORM -> dict e garante tipos serializáveis via jsonable_encoder.
    Aceita único objeto ou lista.
    """
    def _to_dict(o):
        if hasattr(o, "as_dict"):
            return o.as_dict()
        if isinstance(o, dict):
            return o
        # fallback: mapeia colunas do SQLAlchemy
        return {c.name: getattr(o, c.name) for c in o.__table__.columns}

    if isinstance(obj, list):
        return jsonable_encoder([_to_dict(o) for o in obj])
    return jsonable_encoder(_to_dict(obj))


def _to_float_if_present(d: dict, key: str):
    if key in d and d[key] is not None and d[key] != "":
        d[key] = float(d[key])


# ---- Rotas -----------------------------------------------------------------

@router.post("/", summary="Criar bot")
async def criar_bot(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    try:
        # validações obrigatórias
        for campo in ["banca", "risco_pct", "max_alocacao_pct"]:
            if campo not in data or data[campo] is None:
                raise HTTPException(status_code=400, detail=f"Campo obrigatório ausente: {campo}")

        # normalizações numéricas
        _to_float_if_present(data, "banca")
        _to_float_if_present(data, "risco_pct")
        _to_float_if_present(data, "max_alocacao_pct")
        _to_float_if_present(data, "min_quantidade")
        _to_float_if_present(data, "max_quantidade")

        # normalização textual
        if data.get("confluencia_tipo"):
            data["confluencia_tipo"] = str(data["confluencia_tipo"]).lower()
        else:
            data["confluencia_tipo"] = "conservador"

        service = BotService(db)
        bot = service.create_bot(data)  # deve retornar o ORM do Bot
        return JSONResponse(content=_encode_payload(bot))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro ao criar bot")
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar bot: {str(e)}")


@router.put("/{bot_id}", summary="Editar bot")
async def editar_bot(bot_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    try:
        # normalizações numéricas
        for k in ["banca", "risco_pct", "max_alocacao_pct", "min_quantidade", "max_quantidade"]:
            _to_float_if_present(data, k)

        if "confluencia_tipo" in data and data["confluencia_tipo"]:
            data["confluencia_tipo"] = str(data["confluencia_tipo"]).lower()

        service = BotService(db)
        bot = service.update_bot(bot_id, data)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot não encontrado")
        return JSONResponse(content=_encode_payload(bot))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro ao editar bot")
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao editar bot: {str(e)}")

@router.get("/opcoes/alavancagem", summary="Opções de alavancagem e distância até a liquidação")
def opcoes_alavancagem(margem: str = "isolated"):
    """
    Cada opção com a distância que o preço pode andar contra antes da liquidação e o stop máximo que ainda cabe.
    Em margem cruzada a distância real depende de quanto da banca a posição usa; estes números são o pior caso.
    """
    from core.alavancagem import ALAVANCAGENS, FOLGA_PADRAO, MMR_PADRAO, tabela
    return {"opcoes": list(ALAVANCAGENS), "margem": margem, "margem_manutencao": MMR_PADRAO,
            "folga": FOLGA_PADRAO, "tabela": tabela()}


@router.get("/ativos")
def listar_bots_ativos(db: Session = Depends(get_db)):
    bots = db.query(Bot).filter(Bot.ativo_bot == True).all()  # noqa: E712
    return JSONResponse(content=_encode_payload(bots))

@router.get("/{bot_id}", summary="Obter bot por ID")
def get_bot(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    bot = service.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot não encontrado")
    return JSONResponse(content=_encode_payload(bot))


@router.get("/", summary="Listar bots")
def listar_bots(db: Session = Depends(get_db)):
    service = BotService(db)
    bots = service.get_bots()
    return JSONResponse(content=_encode_payload(bots))


@router.post("/{bot_id}/ativar_trailing", summary="Ativar trailing stop manual")
def ativar_trailing(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    bot = service.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot não encontrado")

    # campo booleano no model (garanta que exista)
    setattr(bot, "trailing_manual", True)
    db.commit()
    db.refresh(bot)
    return JSONResponse(content={"message": "Trailing stop ativado manualmente"})


@router.post("/{bot_id}/desativar_trailing", summary="Desativar trailing stop manual")
def desativar_trailing(bot_id: int, db: Session = Depends(get_db)):
    service = BotService(db)
    bot = service.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot não encontrado")

    setattr(bot, "trailing_manual", False)
    db.commit()
    db.refresh(bot)
    return JSONResponse(content={"message": "Trailing stop desativado manualmente"})
