"""
Cadastra os 4 robôs do PORTAL TRADEIROS na demo (core/tradeiros_executor.py) — DESLIGADOS.

    python scripts/criar_bots_tradeiros.py

    Tradeiros Shaka · trades    BTCUSDT linear   subconta shaka_trades
    Tradeiros Shaka · hedge     BTCUSD inverse   subconta shaka_hedge
    Tradeiros Maroja · trades   BTCUSDT linear   subconta maroja_trades
    Tradeiros Maroja · hedge    BTCUSD inverse   subconta maroja_hedge

Cada subconta precisa das chaves no .env (ex.: BYBIT_SUB_SHAKA_TRADES_API_KEY_DEMO e _SECRET_KEY_DEMO); sem elas o
conector falha em vez de usar a conta principal. As de hedge precisam de saldo em BTC. Ligue pelo painel depois.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.database import SessionLocal, aguardar_banco  # noqa: E402
from models.bot import Bot  # noqa: E402

COMUM = dict(
    exchange="bybit", timeframe="30m", estilo_trade="day", confluencia_tipo="conservador", modo_execucao="demo",
    banca=0, max_alocacao_pct=1.0, quantidade=0.001, max_trades_dia=10, delay_execucao=20, tipo_entrada="limite",
    position_mode="one-way", margin_mode="cross", usar_elliott=False, usar_vwap=False, usar_tpo=False,
    usar_volume_profile=False, usar_orderblock=False, usar_fibonacci=False, usar_orderflow=False, usar_sentimento=False,
    usar_tendencia_macro=False, usar_api_macro=False, usar_filtro_regime=False, usar_trailing_stop=False,
)
ROBOS = []
for op, risco, perda in (("shaka", 0.02, 0.06), ("maroja", 0.01, 0.03)):
    nome = op.capitalize()
    ROBOS.append(dict(COMUM, nome=f"Tradeiros {nome} · trades", ativo="BTCUSDT", categoria="linear", alavancagem=3,
                      estrategia=f"tradeiros_{op}", subconta=f"{op}_trades", risco_pct=risco, max_perda_dia_pct=perda))
    ROBOS.append(dict(COMUM, nome=f"Tradeiros {nome} · hedge", ativo="BTCUSD", categoria="inverse", alavancagem=1,
                      estrategia=f"tradeiros_{op}", subconta=f"{op}_hedge", risco_pct=risco, max_perda_dia_pct=1.0))


def main():
    if not aguardar_banco():
        sys.exit("banco indisponível")
    db = SessionLocal()
    try:
        for cfg in ROBOS:
            existente = db.query(Bot).filter(Bot.nome == cfg["nome"]).first()
            if existente:
                print(f"já existe: bot {existente.id} ({existente.nome}), subconta {existente.subconta}, ativo={existente.ativo_bot}")
                continue
            bot = Bot(**cfg, ativo_bot=False)
            db.add(bot)
            db.commit()
            print(f"criado: bot {bot.id} ({bot.nome}) | {bot.modo_execucao} | {bot.categoria} | subconta {bot.subconta} | desligado")
    finally:
        db.close()


if __name__ == "__main__":
    main()
