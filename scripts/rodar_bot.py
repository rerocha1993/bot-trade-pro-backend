# scripts/rodar_bot.py
"""
Roda UM bot no terminal (sem a API), com log detalhado.
    python scripts/rodar_bot.py <bot_id> [--ciclos N] [--modo simulador|testnet|real]
"""
import argparse
import logging
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.database import SessionLocal  # noqa: E402
from core.bot_executor import BotExecutor  # noqa: E402
from models.bot import Bot  # noqa: E402
from services.bot_manager import BotManager  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot_id", type=int)
    ap.add_argument("--ciclos", type=int, default=0, help="0 = infinito")
    ap.add_argument("--modo", default=None, help="sobrescreve modo_execucao (simulador/testnet/real)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = SessionLocal()
    bot = db.query(Bot).filter(Bot.id == args.bot_id).first()
    if not bot:
        print("bot não encontrado")
        return
    if args.modo:
        bot.modo_execucao = args.modo
    servicos = BotManager()._montar_servicos()
    ex = BotExecutor(bot, db, servicos=servicos)
    ex.inicializar()
    n = 0
    while args.ciclos == 0 or n < args.ciclos:
        try:
            ex.ciclo()
        except Exception as e:
            logging.exception("erro no ciclo: %s", e)
            db.rollback()
        n += 1
        st = ex.status()
        print(f"[ciclo {n}] preco={st.get('preco')} decisao={st.get('ultima_decisao')} "
              f"posicao={'sim' if ex.posicao else 'nao'} pnl_dia={st.get('pnl_dia'):.2f}")
        if args.ciclos == 0 or n < args.ciclos:
            time.sleep(ex.delay)
    db.close()


if __name__ == "__main__":
    main()
