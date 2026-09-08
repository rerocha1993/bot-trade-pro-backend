"""Atalho: prepara o banco (scripts/setup_db.py) e mostra os bots cadastrados."""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([sys.executable, "scripts/setup_db.py"], check=False)
    from api.database import SessionLocal
    from models.bot import Bot

    db = SessionLocal()
    for b in db.query(Bot).all():
        print(b.as_dict())
    db.close()
