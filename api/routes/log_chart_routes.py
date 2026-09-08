import requests
import time
from datetime import timezone
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

    # 1. Candles reais da Bybit (timeframe no formato ccxt, ex.: 1m, 15m, 1h)
    from services.bot_manager import get_manager
    con = get_manager().servicos["connectors"]["simulador"]
    tf = timeframe if not timeframe.isdigit() else {"1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "1h", "240": "4h", "D": "1d"}.get(timeframe, "15m")
    candles = [{"time": int(c[0] // 1000), "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
               for c in con.obter_ohlcv(par, tf, 300)]

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
        if log.tipo_operacao not in ("entrada", "saida") or log.acao not in ("buy", "sell"):
            continue
        timestamp = int(log.data_execucao.replace(tzinfo=timezone.utc).timestamp())
        acoes.append({
            "tipo": log.acao,
            "operacao": log.tipo_operacao,
            "preco": float(log.preco or 0),
            "resultado": log.resultado,
            "timestamp": timestamp
        })

    return {
        "par": par,
        "exchange": exchange,
        "candles": candles,
        "acoes": acoes
    }
