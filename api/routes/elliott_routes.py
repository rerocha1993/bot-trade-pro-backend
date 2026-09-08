# api/routes/elliott_routes.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.elliott_schemas import ContagemCandidataSchema, ContagemValidadaSchema, OndaSchema, RevisaoSchema
from core.get_candles import get_candles
from models.elliott_contagem_candidata import ElliottContagemCandidata
from models.elliott_contagem_validada import ElliottContagemValidada
from models.elliott_onda import ElliottOnda
from models.elliott_revisao import ElliottRevisao
from services.elliott_service import ElliottService

router = APIRouter()


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# --- análise ao vivo (cenários) ---
@router.get("/cenarios")
def cenarios(par: str = "BTCUSDT", timeframe: str = "15m", fator_atr: float = 2.0, limite: int = 300):
    return ElliottService().analisar(par, timeframe, fator_atr=fator_atr, limite=limite)


@router.get("/multigrau")
def multigrau(par: str = "BTCUSDT", estilo: str = "daytrade", timeframe: str = "15m", perfil: str = "conservador"):
    return ElliottService().analisar_multi_grau(par, estilo, timeframe, perfil)


# --- PLANO DE MERCADO: a saída do orquestrador (um plano por par, todos os bots leem daqui) ---
@router.get("/plano")
def plano_mercado(par: str = "BTCUSDT", forcar: bool = False, db: Session = Depends(get_db)):
    """Modo, direção por grau, risco permitido, barreira/suporte e zonas de compra e venda do par."""
    from services.bot_manager import get_manager
    from services.plano_service import PlanoService
    try:
        servicos = get_manager().servicos
    except Exception:
        servicos = {}
    return PlanoService(servicos, db=db).plano(par, forcar=forcar)


# --- o TRADER: superciclo (log) + contagens maduras (ciclo manda no primário) ---
@router.get("/trader")
def leitura_trader(par: str = "BTCUSDT", preco: Optional[float] = None):
    """Leitura do trader humano: estado de superciclo, direção, hipóteses vivas maduras e ciclo. Memória persistida em data/trader_<PAR>.pkl."""
    from services.trader_service import TraderService
    return TraderService().leitura(par, preco=preco)


@router.post("/trader/reconstruir")
def reconstruir_trader(par: str = "BTCUSDT"):
    """Apaga a memória persistida e evolui de novo desde 2011 (alguns minutos)."""
    from services.trader_service import TraderService
    return TraderService().reconstruir(par)


# --- contagem mestre (desde 2011) e trava de cenário ---
@router.get("/mestre")
def contagem_mestre(par: str = "BTCUSDT", db: Session = Depends(get_db)):
    """Graus ciclo (40%), primário (22%) e intermediário (12%) aninhados, com cenários, pivôs datados e a trava vigente."""
    from services.elliott_mestre_service import ElliottMestreService
    return ElliottMestreService(db).calcular(par)


@router.post("/mestre/travar")
def travar_cenario(par: str = "BTCUSDT", grau: str = "ciclo", cenario_id: str = Query(...), motivo: str = "escolha do usuário",
                   db: Session = Depends(get_db)):
    """Trava um cenário como trilho: o viés dele entra no alinhamento de todos os bots do par até a invalidação ser cruzada."""
    from services.elliott_mestre_service import ElliottMestreService
    try:
        return ElliottMestreService(db).travar(par, grau, cenario_id, motivo)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/mestre/destravar")
def destravar(par: str = "BTCUSDT", motivo: str = "destravada pelo usuário", db: Session = Depends(get_db)):
    from services.elliott_mestre_service import ElliottMestreService
    return {"destravadas": ElliottMestreService(db).destravar(par, motivo)}


@router.get("/mestre/trava")
def trava_atual(par: str = "BTCUSDT", db: Session = Depends(get_db)):
    from services.elliott_mestre_service import ElliottMestreService
    return ElliottMestreService(db).trava_ativa(par) or {"status": "sem trava"}


# --- CRUD candidatas ---
@router.get("/candidatas")
def listar_candidatas(par: Optional[str] = None, timeframe: Optional[str] = None, status: Optional[str] = None,
                      limite: int = Query(200, le=2000), db: Session = Depends(get_db)):
    q = db.query(ElliottContagemCandidata)
    if par:
        q = q.filter_by(par=par)
    if timeframe:
        q = q.filter_by(timeframe=timeframe)
    if status:
        q = q.filter_by(status=status)
    return [_dict(o) for o in q.order_by(ElliottContagemCandidata.data_fim.desc()).limit(limite).all()]


@router.get("/candidata/{id}")
def obter_candidata(id: int, db: Session = Depends(get_db)):
    obj = db.get(ElliottContagemCandidata, id)
    if not obj:
        raise HTTPException(404, "Contagem candidata não encontrada")
    return _dict(obj)


@router.delete("/candidata/{id}", status_code=204)
def deletar_candidata(id: int, db: Session = Depends(get_db)):
    obj = db.get(ElliottContagemCandidata, id)
    if not obj:
        raise HTTPException(404, "Contagem candidata não encontrada")
    db.delete(obj)
    db.commit()


@router.post("/candidata/{id}/promover")
def promover(id: int, db: Session = Depends(get_db)):
    try:
        return {"validada_id": ElliottService(db).promover_e_validar(id)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- validadas ---
@router.get("/validadas")
def listar_validadas(par: Optional[str] = None, timeframe: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ElliottContagemValidada)
    if par:
        q = q.filter_by(par=par)
    if timeframe:
        q = q.filter_by(timeframe=timeframe)
    return [_dict(o) for o in q.order_by(ElliottContagemValidada.data_fim.desc()).all()]


@router.get("/validada/{id}")
def obter_validada(id: int, db: Session = Depends(get_db)):
    obj = db.get(ElliottContagemValidada, id)
    if not obj:
        raise HTTPException(404, "Contagem validada não encontrada")
    return _dict(obj)


@router.post("/validada/{id}/rollback")
def rollback(id: int, motivo: str = "revisão manual", db: Session = Depends(get_db)):
    try:
        return {"ok": ElliottService(db).revisar_rollback(id, motivo)}
    except ValueError as e:
        raise HTTPException(404, str(e))


# --- ondas / revisões ---
@router.get("/ondas")
def listar_ondas(contagem_id: int = Query(None), db: Session = Depends(get_db)):
    q = db.query(ElliottOnda)
    if contagem_id:
        q = q.filter_by(contagem_id=contagem_id)
    return [_dict(o) for o in q.order_by(ElliottOnda.contagem_id, ElliottOnda.numero_onda).limit(2000).all()]


@router.get("/revisoes")
def listar_revisoes(contagem_id: int = Query(None), db: Session = Depends(get_db)):
    q = db.query(ElliottRevisao)
    if contagem_id:
        q = q.filter_by(contagem_id=contagem_id)
    return [_dict(o) for o in q.order_by(ElliottRevisao.timestamp.desc()).limit(500).all()]


# --- varredura histórica (persistência) ---
@router.post("/analise")
def analisar_multi_timeframe(par: str = "BTCUSDT", timeframes: List[str] = Query(["1h", "4h", "1d"]), limite: int = 1000,
                             promover: bool = True, db: Session = Depends(get_db)):
    candles_dict = {tf: get_candles(par, tf, limite=limite) for tf in timeframes}
    svc = ElliottService(db)
    salvos = svc.analisar_multi_timeframe(par, timeframes, candles_dict)
    promovidas = {tf: svc.promover_candidatas(par, tf) for tf in timeframes} if promover else {}
    return {"candidatas_salvas": salvos, "promovidas": promovidas}


@router.get("/estrutura_atual")
def consultar_estrutura(par: str, timeframe: str, db: Session = Depends(get_db)):
    return ElliottService(db).consultar_estruturas_atuais(par, timeframe)
