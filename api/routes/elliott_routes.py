from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.get_candles import get_candles
from api.database import get_db

from api.elliott_schemas import (
    ContagemCandidataSchema, ContagemValidadaSchema, OndaSchema, RevisaoSchema
)
from services.elliott_persistence_service import ElliottPersistenceService

router = APIRouter()

# --- CRUD CONTAGENS CANDIDATAS ---
@router.post("/candidata", response_model=ContagemCandidataSchema)
def criar_candidata(contagem: ContagemCandidataSchema, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    id_cad = service.salvar_contagem_candidata(**contagem.dict(exclude={"id"}))
    obj = db.query(service.model_candidata).get(id_cad)
    return obj

@router.get("/candidata/{id}", response_model=ContagemCandidataSchema)
def obter_candidata(id: int, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    obj = db.query(service.model_candidata).get(id)
    if not obj:
        raise HTTPException(status_code=404, detail="Contagem candidata não encontrada")
    return obj

@router.get("/candidatas", response_model=list[ContagemCandidataSchema])
def listar_candidatas(par: str = None, timeframe: str = None, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    query = db.query(service.model_candidata)
    if par:
        query = query.filter_by(par=par)
    if timeframe:
        query = query.filter_by(timeframe=timeframe)
    return query.all()

@router.delete("/candidata/{id}", status_code=204)
def deletar_candidata(id: int, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    obj = db.query(service.model_candidata).get(id)
    if not obj:
        raise HTTPException(status_code=404, detail="Contagem candidata não encontrada")
    db.delete(obj)
    db.commit()
    return

# --- CRUD CONTAGENS VALIDADAS ---
@router.post("/validada", response_model=ContagemValidadaSchema)
def criar_validada(contagem: ContagemValidadaSchema, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    id_val = service.salvar_contagem_validada(**contagem.dict(exclude={"id"}))
    obj = db.query(service.model_validada).get(id_val)
    return obj

@router.get("/validada/{id}", response_model=ContagemValidadaSchema)
def obter_validada(id: int, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    obj = db.query(service.model_validada).get(id)
    if not obj:
        raise HTTPException(status_code=404, detail="Contagem validada não encontrada")
    return obj

@router.get("/validadas", response_model=list[ContagemValidadaSchema])
def listar_validadas(par: str = None, timeframe: str = None, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    query = db.query(service.model_validada)
    if par:
        query = query.filter_by(par=par)
    if timeframe:
        query = query.filter_by(timeframe=timeframe)
    return query.all()

@router.delete("/validada/{id}", status_code=204)
def deletar_validada(id: int, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    obj = db.query(service.model_validada).get(id)
    if not obj:
        raise HTTPException(status_code=404, detail="Contagem validada não encontrada")
    db.delete(obj)
    db.commit()
    return

# --- CRUD ONDAS ---
@router.post("/onda", response_model=OndaSchema)
def criar_onda(onda: OndaSchema, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    id_onda = service.salvar_onda(**onda.dict(exclude={"id"}))
    obj = db.query(service.model_onda).get(id_onda)
    return obj

@router.get("/ondas", response_model=list[OndaSchema])
def listar_ondas(contagem_id: int = Query(None), db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    query = db.query(service.model_onda)
    if contagem_id:
        query = query.filter_by(contagem_id=contagem_id)
    return query.all()

# --- CRUD REVISÕES ---
@router.post("/revisao", response_model=RevisaoSchema)
def criar_revisao(revisao: RevisaoSchema, db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    id_rev = service.salvar_revisao(**revisao.dict(exclude={"id"}))
    obj = db.query(service.model_revisao).get(id_rev)
    return obj

@router.get("/revisoes", response_model=list[RevisaoSchema])
def listar_revisoes(contagem_id: int = Query(None), db: Session = Depends(get_db)):
    service = ElliottPersistenceService(db)
    query = db.query(service.model_revisao)
    if contagem_id:
        query = query.filter_by(contagem_id=contagem_id)
    return query.all()

# --- ANÁLISE MULTI-TIMEFRAME (disparo do engine institucional) ---
@router.post("/analise")
def analisar_multi_timeframe(par: str, timeframes: list[str], modo_execucao: str = "simulador", db: Session = Depends(get_db)):
    from services.elliott_service import ElliottService
    candles_dict = {}
    for tf in timeframes:
        candles_dict[tf] = get_candles(par, tf, limite=1000, modo_execucao=modo_execucao)
    service = ElliottService(db)
    service.analisar_multi_timeframe(par, timeframes, candles_dict)
    return {"detail": "Análise disparada com sucesso!"}

# --- CONSULTA ESTRUTURA ATUAL (drilldown) ---
@router.get("/estrutura_atual")
def consultar_estrutura(par: str, timeframe: str, db: Session = Depends(get_db)):
    from services.elliott_service import ElliottService
    service = ElliottService(db)
    return service.consultar_estruturas_atuais(par, timeframe)
