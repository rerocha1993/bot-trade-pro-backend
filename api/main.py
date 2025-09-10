import os
from dotenv import load_dotenv
from types import SimpleNamespace
load_dotenv() 

from fastapi import FastAPI
from api.routes import bot_routes, coins_routes, log_routes, log_chart_routes
from api.routes import bot_controller, indicador_controller, bot_control_controller
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import threading
from services.bot_manager import BotManager
from api.database import get_db
from api.routes import ponto_institucional_routes
from api.routes import institucional_routes
from api.routes import elliott_routes

app = FastAPI(title="Bot Trader API")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:8000", "http://127.0.0.1:8000"],  # Troque para sua origem em prod, se desejar
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas
app.include_router(bot_routes.router, prefix="/bots", tags=["Bots"])
app.include_router(log_routes.router, prefix="/logs", tags=["Logs"])
app.include_router(coins_routes.router, prefix="/coins", tags=["Coins"])
app.include_router(log_chart_routes.router, tags=["Gráfico"])
app.include_router(bot_controller.router, prefix="/bots", tags=["Bots"])
app.include_router(indicador_controller.router, prefix="/indicadores", tags=["Indicadores"])
app.include_router(bot_control_controller.router, prefix="/bot-control", tags=["Bot Control"])
app.mount("/grafico", StaticFiles(directory="frontend", html=True), name="grafico")
app.include_router(ponto_institucional_routes.router, tags=["Pontos Institucionais"])
app.include_router(institucional_routes.router, tags=["Institucional"])
app.include_router(elliott_routes.router, prefix="/api/elliott", tags=["Elliott"])



# --------- BLOCO BOTMANAGER MULTI-ROBÔ ---------

def carregar_configs_bots(db):
    # Exemplo: busca bots ativos no banco (ajuste conforme ORM)
    from models.bot import Bot
    bots = db.query(Bot).filter_by(ativo_bot=True).all()

    defaults = {
        "usar_elliott": False,
        "usar_fibonacci": False,
        "usar_volume_profile": False,
        "usar_orderblock": False,
        "usar_tpo": False,
        "usar_orderflow": False,
        "usar_vwap": False,        
        "banca": 0,
        "risco_pct": 0.01,
        "max_alocacao_pct": 0.5,
        # Adicione TODOS os outros campos obrigatórios que o executor espera
    }

    bots = db.query(Bot).filter_by(ativo_bot=True).all()
    bots_configs = []
    for bot in bots:
        bot_dict = {
            "nome": bot.nome,
            "exchange": bot.exchange,
            "ativo": bot.ativo,
            "quantidade": bot.quantidade,
            "modo_execucao": bot.modo_execucao,
            "timeframe": bot.timeframe,
            "usar_elliott": bot.usar_elliott,
            "usar_fibonacci": bot.usar_fibonacci,
            "usar_tpo": bot.usar_tpo,
            "usar_orderflow": bot.usar_orderflow,
            "usar_vwap": bot.usar_vwap,
            "usar_volume_profile": bot.usar_volume_profile,
            "usar_orderblock": bot.usar_orderblock,
            "banca": float(bot.banca) if hasattr(bot, 'banca') else 0,
            "risco_pct": float(bot.risco_pct) if hasattr(bot, 'risco_pct') else 0.01,
            "max_alocacao_pct": float(bot.max_alocacao_pct) if hasattr(bot, 'max_alocacao_pct') else 0.5,
            # Inclua TODOS os campos esperados pelo BotExecutor!
        }
        # Une defaults com os campos do banco
        bot_data = {**defaults, **bot_dict}
        bots_configs.append(SimpleNamespace(**bot_data))
    return bots_configs

def start_bots_background():
    db = next(get_db())
    bots_configs = carregar_configs_bots(db)
    if not bots_configs:
        print("Nenhum bot ativo encontrado.")
        return
    global manager
    manager = BotManager(bots_configs, db)
    manager.start_all()
    print(f"[BotManager] Iniciou {len(bots_configs)} bots em paralelo.")

# FastAPI startup event (roda junto com a API, mas só uma vez!)
@app.on_event("startup")
def on_startup():
    print("Iniciando API e bots...")
    t = threading.Thread(target=start_bots_background, daemon=True)
    t.start()

# ------------------------------------------------

# Pronto!  
# Basta rodar normalmente com uvicorn:
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
