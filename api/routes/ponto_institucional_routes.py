# api/routes/ponto_institucional_routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database import get_db
from services.ponto_institucional_service import PontoInstitucionalService

router = APIRouter()

@router.post("/pontos-institucionais")
def criar_ponto(ponto: dict, db: Session = Depends(get_db)):
    ponto_criado = PontoInstitucionalService.criar_ponto(db, ponto)
    return ponto_criado

@router.get("/pontos-institucionais")
def listar_pontos(
    par: str = None,
    exchange: str = None,
    status: str = None,
    tipo: str = None,
    preco_atual: float = None,   # <- novo parâmetro
    db: Session = Depends(get_db)
):
    pontos = PontoInstitucionalService.listar_pontos(db, par, exchange, status, tipo)
    if preco_atual:
        pontos = [p for p in pontos if (preco_atual - 20000) <= float(p.preco) <= (preco_atual + 20000)]
    return pontos


@router.patch("/pontos-institucionais/{ponto_id}/testar")
def testar_ponto(ponto_id: int, db: Session = Depends(get_db)):
    ponto = PontoInstitucionalService.atualizar_status(db, ponto_id, "testar")
    if not ponto:
        raise HTTPException(status_code=404, detail="Ponto não encontrado")
    return ponto

@router.patch("/pontos-institucionais/{ponto_id}/romper")
def romper_ponto(ponto_id: int, db: Session = Depends(get_db)):
    ponto = PontoInstitucionalService.atualizar_status(db, ponto_id, "romper")
    if not ponto:
        raise HTTPException(status_code=404, detail="Ponto não encontrado")
    return ponto

@router.get("/pontos-institucionais/historico")
def historico_pontos(par: str = None, exchange: str = None, db: Session = Depends(get_db)):
    return PontoInstitucionalService.historico(db, par, exchange)
