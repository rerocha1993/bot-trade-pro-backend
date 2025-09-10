from multiprocessing import Process
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.bot import Bot
from core.bot_executor import BotExecutor
import urllib

# Conexão com o banco SQL Server
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=(localdb)\\MSSQLLocalDB;"
    "DATABASE=dbo_trading_bot;"
    "Trusted_Connection=yes"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
SessionLocal = sessionmaker(bind=engine)

def executar_bot(bot_id):
    session = SessionLocal()
    bot = session.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        print(f"[BOT {bot_id}] não encontrado.")
        return

    executor = BotExecutor(bot=bot, db=session)
    executor.executar()

def main():
    session = SessionLocal()
    bots = session.query(Bot).filter(Bot.ativo_bot == True).all()

    processos = []
    for bot in bots:
        p = Process(target=executar_bot, args=(bot.id,))
        p.start()
        processos.append(p)

    for p in processos:
        p.join()

if __name__ == "__main__":
    main()
