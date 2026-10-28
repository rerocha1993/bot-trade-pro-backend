# api/main.py
"""
API do conselho de avisos (Bot Trade Pro, a partir de 20/10/2026).

    uvicorn api.main:app --host 127.0.0.1 --port 8000

Não opera e não guarda nada em banco: lê dados públicos da Bybit e o livro gravado pelo coletor
(dados/livro/), monta o mapa do dia, gera avisos (data/avisos.jsonl, e Telegram quando configurado) e serve o
painel em /painel. SERVICO_AVISOS=0 no .env desliga o serviço de avisos e ROBOS=0 os 4 robôs em simulação
(os dois ligados por padrão).

O sistema de robôs antigo foi apagado em 20/10/2026; está no histórico do git até o commit 017692d7.
"""
import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.routes import avisos_routes, fluxo_routes, grafico_routes, mercado_routes, nuvens_routes, robos_routes  # noqa: E402
from conselho.console import preparar_console_servidor  # noqa: E402

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")
preparar_console_servidor(logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    avisos = None
    if os.getenv("SERVICO_AVISOS", "1") != "0":
        try:
            from conselho.servico_avisos import get_avisos_service
            avisos = get_avisos_service()
            avisos.iniciar()
        except Exception as e:
            # sem o serviço o painel continua de pé: as nuvens e o mapa ainda respondem
            logger.exception("falha ao ligar o serviço de avisos: %s", e)
    robos = None
    if os.getenv("ROBOS", "1") != "0":
        try:
            from conselho.servico_robos import get_servico_robos
            robos = get_servico_robos()
            robos.iniciar()
        except Exception as e:
            logger.exception("falha ao ligar os robôs: %s", e)
    yield
    if robos is not None:
        robos.parar()
    if avisos is not None:
        avisos.parar()


app = FastAPI(title="Conselho de avisos BTC", version="3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def sem_cache_no_painel(request, call_next):
    """A página do painel sempre vem fresca (o celular guardava a versão antiga); os arquivos de assets/ mudam de nome
    a cada build e podem ficar em cache à vontade."""
    resposta = await call_next(request)
    caminho = request.url.path
    if caminho.startswith("/painel") and "/assets/" not in caminho:
        resposta.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif caminho.startswith("/painel/assets/"):
        resposta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resposta

app.include_router(avisos_routes.router, prefix="/api/avisos", tags=["Avisos"])
app.include_router(nuvens_routes.router, prefix="/api/nuvens", tags=["Nuvens"])
app.include_router(mercado_routes.router, prefix="/api/mercado", tags=["Mercado"])
app.include_router(fluxo_routes.router, prefix="/api/fluxo", tags=["Fluxo"])
app.include_router(robos_routes.router, prefix="/api/robos", tags=["Robôs"])
app.include_router(grafico_routes.router, prefix="/api/grafico", tags=["Gráfico"])

# painel (React + Lightweight Charts): `cd frontend && npm run build` gera frontend/dist, servido em /painel
_painel = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(_painel):
    app.mount("/painel", StaticFiles(directory=_painel, html=True), name="painel")


@app.get("/", tags=["Status"])
def raiz():
    return {"app": "Conselho de avisos BTC", "versao": "3.0", "painel": "/painel/", "docs": "/docs"}
