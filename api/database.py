# api/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import urllib
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
# Sua string de conexão
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=(localdb)\\MSSQLLocalDB;"
    "DATABASE=dbo_trading_bot;"
    "Trusted_Connection=yes"
)

engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 🔥 ESTA FUNÇÃO É FUNDAMENTAL
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
