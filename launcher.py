import sys
import os

# Garante que todos os módulos internos sejam visíveis
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.bot_service import BotService
from services.indicador_service import IndicadorService
from models import Base
from models.bot_indicador import BotIndicador
import urllib
from api.database import SessionLocal

session = SessionLocal()
# Testando serviços reais aqui
print("✅ Testando serviços...")

# 1. Popula indicadores disponíveis
IndicadorService(session).seed_indicadores()
print("✅ IndicadoresDisponiveis prontos.")

# 2. Lista bots (se já existirem)
bots = BotService(session).get_bots()
print(f"📦 Bots encontrados: {len(bots)}")

# 3. (Opcional) Cadastrar manualmente indicadores em um bot
if bots:
    bot_id = bots[0].id
    indicador = BotIndicador(bot_id=bot_id, nome="fibonacci", parametros={"nivel": 61.8})
    session.add(indicador)
    session.commit()
    print(f"✅ Indicador 'fibonacci' adicionado ao bot {bot_id}")
