# scripts/backtest_bot.py
"""
Backtest de validação de um bot cadastrado (mesma rotina usada pela API antes de ativar).
    python scripts/backtest_bot.py <bot_id> [--dias 180]
    python scripts/backtest_bot.py --par SOLUSDT --tf 15m --estilo daytrade --perfil conservador --dias 180   (sem cadastrar)
"""
import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.database import SessionLocal  # noqa: E402
from core.backtest_engine import bot_padrao  # noqa: E402
from models.bot import Bot  # noqa: E402
from services.backtest_service import BacktestService  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot_id", type=int, nargs="?")
    ap.add_argument("--par"); ap.add_argument("--tf", default="15m"); ap.add_argument("--estilo", default="daytrade")
    ap.add_argument("--perfil", default="conservador"); ap.add_argument("--dias", type=int, default=None)
    args = ap.parse_args()
    svc = BacktestService(SessionLocal)
    db = SessionLocal()
    try:
        if args.bot_id:
            bot = db.query(Bot).filter(Bot.id == args.bot_id).first()
            if not bot:
                print("bot não encontrado"); return
        else:
            bot = bot_padrao(ativo=args.par.upper(), timeframe=args.tf, estilo_trade=args.estilo, confluencia_tipo=args.perfil, tipo_entrada="limite")
        reg = svc.rodar(bot, args.dias, session=db)
        print(f"#{reg.id} {reg.par} {reg.timeframe} {reg.status}: {'APROVADO' if reg.aprovado else 'REPROVADO'} | {reg.motivo}")
        print(f"   período {reg.data_inicio} -> {reg.data_fim} | candles {reg.candles} | trades {reg.trades} | acerto {reg.taxa_acerto} | "
              f"retorno {reg.retorno_pct}% | PF {reg.fator_lucro} | DD {reg.drawdown_max_pct}%")
    finally:
        db.close()


if __name__ == "__main__":
    main()
