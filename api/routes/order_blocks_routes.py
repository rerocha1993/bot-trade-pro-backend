from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.database import get_db
from models.orderblocks_institucionais import OrderBlockInstitucional

router = APIRouter()

@router.post("/orderblocks/atualizar")
def atualizar_orderblocks(par: str = "BTCUSDT", db: Session = Depends(get_db)):
    """Lê os livros (Bitstamp, Coinbase, Bitfinex, Kraken, Bybit) e persiste os blocos de liquidez."""
    from services.bot_manager import get_manager
    return get_manager().servicos["orderblocks"].atualizar_blocos(db, par)


@router.get("/orderblocks/")
def listar_orderblocks(par: str = "BTCUSDT", status: str = "ativo", db: Session = Depends(get_db)):
    query = db.query(OrderBlockInstitucional).filter_by(par=par)
    if status:
        query = query.filter_by(status=status)
    return [
        {
            "id": b.id,
            "par": b.par,
            "direcao": b.direcao,
            "preco": b.preco,
            "volume": b.volume,
            "exchange_origem": b.exchange_origem,
            "status": b.status,
            "usado_como": b.usado_como,
            "rompido_em": b.rompido_em,
            "criado_em": b.criado_em,
            "atualizado_em": b.atualizado_em,
            "info_extra": b.info_extra
        }
        for b in query.all()
    ]
