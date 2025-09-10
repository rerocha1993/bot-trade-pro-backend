import requests
import time
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from api.database import get_db
from models.log_execucao import LogExecucaoBot
from models.bot import Bot  # ⬅️ Certifique-se que esse caminho está correto

router = APIRouter()

@router.get("/logs/{bot_id}/grafico-dados")
def obter_dados_grafico(
    bot_id: int,
    timeframe: str = Query("1"),  # padrão 1 minuto
    db: Session = Depends(get_db)
):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        return {"error": "Bot não encontrado"}

    par = bot.ativo.replace("/", "")
    exchange = "Bybit"

    # 1. Candles reais da Bybit
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": par, "interval": timeframe, "limit": 100}
    candles_raw = requests.get(url, params=params).json()
    lista = candles_raw.get("result", {}).get("list", [])

    candles = []
    for c in lista:
        candles.append({
            "time": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
        })

    # 2. Logs de ações
    logs = (
        db.query(LogExecucaoBot)
        .filter(LogExecucaoBot.bot_id == bot_id)
        .order_by(LogExecucaoBot.data_execucao.desc())
        .limit(100)
        .all()
    )

    acoes = []
    for log in reversed(logs):
        if log.acao not in ["buy", "sell"]:
            continue
        timestamp = int(time.mktime(log.data_execucao.timetuple()))
        acoes.append({
            "tipo": log.acao,
            "preco": log.preco or 0,
            "timestamp": timestamp
        })

    return {
        "par": par,
        "exchange": exchange,
        "candles": candles,
        "acoes": acoes
    }
