from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database import get_db
from models.pair_institucional import PairInstitucional
from models.exchange_institucional import ExchangeInstitucional

router = APIRouter()

@router.get("/institucional/config")
def get_institucional_config(db: Session = Depends(get_db)):
    pairs = db.query(PairInstitucional).filter(PairInstitucional.ativo == True).all()
    exchanges = db.query(ExchangeInstitucional).filter(ExchangeInstitucional.ativa == True).all()
    data = []
    for pair in pairs:
        exchange = next((e for e in exchanges if e.id == pair.exchange_id), None)
        if exchange:
            data.append({
                "exchange": exchange.nome,
                "par": pair.par,
                "timeframe": pair.timeframe
            })
    return data

@router.post("/institucional/pairs")
def add_pair(pair: dict, db: Session = Depends(get_db)):
    exchange = db.query(ExchangeInstitucional).filter(ExchangeInstitucional.id == pair["exchange_id"]).first()
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange não encontrada.")
    novo = PairInstitucional(
        exchange_id=pair["exchange_id"],
        par=pair["par"],
        timeframe=pair["timeframe"],
        ativo=True
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@router.post("/institucional/exchanges")
def add_exchange(exchange: dict, db: Session = Depends(get_db)):
    novo = ExchangeInstitucional(
        nome=exchange["nome"],
        ativa=True
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo
