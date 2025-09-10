# db/inserir_logs_falsos.py

import sys, os, random
from datetime import datetime, timedelta
from models import Base

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import sessionmaker
from models.log_execucao import LogExecucaoBot
from models.bot import Bot  # ✅ ESSENCIAL: registra a tabela 'Bots' no metadata
from models.bot_indicador import BotIndicador 
from models.indicador_disponivel import IndicadorDisponivel 
from api.database import engine


# ✅ Só funciona se ambas estiverem importadas antes do create_all
Base.metadata.create_all(bind=engine)

print("Tabelas criadas com sucesso.")
