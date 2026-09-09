# api/database.py
"""
Conexão com o banco.

A string vem do ambiente, com os valores atuais como padrão para não quebrar quem já roda local:

    DATABASE_URL   = URL completa do SQLAlchemy (tem prioridade sobre tudo)
                     ex.: mssql+pyodbc:///?odbc_connect=<string ODBC codificada>
    DB_DRIVER      = ODBC Driver 17 for SQL Server
    DB_SERVER      = (localdb)\\MSSQLLocalDB
    DB_NAME        = dbo_trading_bot
    DB_TRUSTED     = yes            (autenticação do Windows; com 'no' usa DB_USER/DB_PASSWORD)
    DB_USER        / DB_PASSWORD
    DB_ENCRYPT     = no             (essencial para LocalDB)
    DB_TIMEOUT     = 30             segundos de espera no logon

O LocalDB desliga sozinho por ociosidade e leva alguns segundos para subir de novo. Com o tempo limite padrão,
a primeira conexão depois de um tempo parado falha com "o tempo limite do logon expirou". Daí o DB_TIMEOUT alto.

Antes isto era fixo no código, o que obrigava a editar o arquivo para trocar de servidor.
"""
import os
import urllib.parse as urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

Base = declarative_base()


def _url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    # só aceita uma URL de verdade: um valor solto (ex.: o próprio nome da variável) é ignorado
    if url and "://" in url:
        return url
    partes = [
        f"DRIVER={{{os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')}}}",
        f"SERVER={os.getenv('DB_SERVER', '(localdb)\\MSSQLLocalDB')}",
        f"DATABASE={os.getenv('DB_NAME', 'dbo_trading_bot')}",
    ]
    if (os.getenv("DB_TRUSTED", "yes") or "yes").lower() in ("yes", "true", "1"):
        partes.append("Trusted_Connection=yes")
    else:
        partes.append(f"UID={os.getenv('DB_USER', '')}")
        partes.append(f"PWD={os.getenv('DB_PASSWORD', '')}")
    partes.append(f"Encrypt={os.getenv('DB_ENCRYPT', 'no')}")
    # o LocalDB pode estar dormindo: dar tempo de ele subir em vez de falhar na primeira tentativa
    partes.append(f"Connection Timeout={os.getenv('DB_TIMEOUT', '30')}")
    return f"mssql+pyodbc:///?odbc_connect={urlparse.quote_plus(';'.join(partes) + ';')}"


engine = create_engine(_url(), pool_pre_ping=True, pool_recycle=1800, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
