from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database import get_db
from services.indicador_service import IndicadorService

router = APIRouter()

@router.on_event("startup")
def seed():
    from api.database import SessionLocal
    IndicadorService(SessionLocal()).seed_indicadores()

@router.get("/")
def listar(db: Session = Depends(get_db)):
    return IndicadorService(db).listar()

@router.post("/")
def criar(data: dict, db: Session = Depends(get_db)):
    return IndicadorService(db).criar(data)

@router.put("/{id}")
def atualizar(id: int, data: dict, db: Session = Depends(get_db)):
    atualizado = IndicadorService(db).atualizar(id, data)
    if not atualizado:
        raise HTTPException(status_code=404, detail="Indicador não encontrado")
    return atualizado

@router.delete("/{id}")
def deletar(id: int, db: Session = Depends(get_db)):
    removido = IndicadorService(db).deletar(id)
    if not removido:
        raise HTTPException(status_code=404, detail="Indicador não encontrado")
    return {"status": "ok"}
