# api/main.py
"""
API do Bot Trade Pro.

    uvicorn api.main:app --host 0.0.0.0 --port 8000

Ao subir, inicia os bots com `ativo_bot = True` (um thread por bot) e a manutenção institucional
periódica. Defina INICIAR_BOTS=0 no .env para subir só a API.
"""
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.routes import (  # noqa: E402
    bot_control_controller, bot_controller, coins_routes, elliott_routes, indicador_controller,
    institucional_routes, log_chart_routes, log_routes, nuvens_endpoint, order_blocks_routes,
    ponto_institucional_routes, status_routes, backtest_routes, inverse_routes,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")

from core.console_servidor import preparar_console_servidor  # noqa: E402

preparar_console_servidor(logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.trava_instancia import TravaInstancia
    from services.bot_manager import get_manager
    from services.indicador_service import IndicadorService
    from api.database import SessionLocal, aguardar_banco, manter_banco_acordado, parar_keepalive

    # o LocalDB dorme por ociosidade: acorda e espera antes de qualquer coisa tocar o banco
    banco_ok = aguardar_banco()
    if not banco_ok:
        logger.error("SUBINDO SEM BANCO: os robôs não vão iniciar. A API e o painel continuam de pé para você "
                     "ver o problema. Verifique o SQL Server e reinicie.")

    if banco_ok:
        manter_banco_acordado()
        db = SessionLocal()
        try:
            IndicadorService(db).seed_indicadores()
        except Exception as e:
            logger.warning("seed de indicadores falhou: %s", e)
        finally:
            db.close()

    manager = get_manager()
    # o uvicorn roda ISTO antes de reservar a porta: numa segunda janela, os robos subiriam, falariam com a
    # corretora, e so entao a porta falharia. Por um instante haveria dois executores por subconta -- e a
    # Bybit tem UMA posicao por simbolo por conta. A trava vale para qualquer porta (core/trava_instancia.py)
    trava = TravaInstancia()
    if banco_ok and os.getenv("INICIAR_BOTS", "1") != "0" and trava.adquirir():
        try:
            n = manager.start_all()
            logger.info("BotManager iniciou %d bot(s)", n)
            if os.getenv("MANUTENCAO_INSTITUCIONAL", "1") != "0":
                manager.iniciar_manutencao(int(os.getenv("MANUTENCAO_MIN", "30")))
        except Exception as e:
            # um robô com problema não pode derrubar a API inteira: sem painel você fica cego
            logger.exception("falha ao iniciar os robôs: %s", e)
    yield
    parar_keepalive()
    try:
        manager.stop_all()
    except Exception:
        pass
    trava.liberar()


app = FastAPI(title="Bot Trade Pro API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(status_routes.router, prefix="/status", tags=["Status"])
app.include_router(bot_controller.router, prefix="/bots", tags=["Bots"])
app.include_router(bot_control_controller.router, prefix="/bot-control", tags=["Bot Control"])
app.include_router(backtest_routes.router, prefix="/backtest", tags=["Backtest"])
app.include_router(inverse_routes.router, prefix="/inverse", tags=["Inverse"])
app.include_router(log_routes.router, prefix="/logs", tags=["Logs"])
app.include_router(log_chart_routes.router, tags=["Gráfico"])
app.include_router(coins_routes.router, prefix="/coins", tags=["Coins"])
app.include_router(indicador_controller.router, prefix="/indicadores", tags=["Indicadores"])
app.include_router(nuvens_endpoint.router, tags=["Nuvens"])
app.include_router(ponto_institucional_routes.router, tags=["Pontos Institucionais"])
app.include_router(order_blocks_routes.router, tags=["Order Blocks"])
app.include_router(institucional_routes.router, tags=["Institucional"])
app.include_router(elliott_routes.router, prefix="/api/elliott", tags=["Elliott"])

# painel (React + Lightweight Charts): `cd frontend && npm run build` gera frontend/dist, servido em /painel
_painel = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(_painel):
    app.mount("/painel", StaticFiles(directory=_painel, html=True), name="painel")


@app.get("/", tags=["Status"])
def raiz():
    return {"app": "Bot Trade Pro", "versao": "2.0", "docs": "/docs"}
