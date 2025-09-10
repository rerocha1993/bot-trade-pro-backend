# db/inserir_logs_falsos.py

import sys, os, random
from datetime import datetime, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import sessionmaker
from models.log_execucao import LogExecucaoBot
from api.database import engine
from models.bot import Bot  # Adicione isso também

SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Criar bot de teste se não existir
bot = Bot(
    nome="Bot de Teste",
    ativo="BTC/USDT",
    timeframe="1m",
    estilo_trade="Scalping",
    quantidade=0.01
)
session.add(bot)
session.commit()

bot_id = bot.id  # Pega o ID real gerado
preco_base = 25000
agora = datetime.utcnow()

for i in range(5):
    data = agora - timedelta(minutes=5 * (4 - i))
    preco = preco_base + random.randint(-200, 200)
    acao = random.choice(["buy", "sell", "hold"])
    resultado = random.uniform(-50, 50) if acao != "hold" else None

    log = LogExecucaoBot(
        bot_id=bot_id,
        data_execucao=data,
        preco=preco,
        acao=acao,
        motivo="Teste manual",
        resultado=resultado,
        erro=None
    )

    session.add(log)

session.commit()
session.close()

print("✅ Logs falsos inseridos com sucesso.")
