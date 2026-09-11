"""
Cadastra o robô do JOGO DO RANGE do Tradeiros (core/range_executor.py) no SIMULADOR.

    python scripts/criar_bot_range.py            # cria ativo (sobe no próximo início do servidor)
    python scripts/criar_bot_range.py --inativo

Simulador porque as quatro subcontas do demo já têm um robô em BTCUSDT (scalp, day, swing e principal) e a Bybit
tem uma posição por símbolo por conta. Para levar ao demo: uma subconta nova (chaves BYBIT_SUB_<NOME>_API_KEY_DEMO
e _SECRET_KEY_DEMO no .env) ou uma das atuais liberada — e trocar modo_execucao e subconta deste robô.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.database import SessionLocal, aguardar_banco  # noqa: E402
from models.bot import Bot  # noqa: E402

NOME = "Range Tradeiros 30m"
CONFIG = dict(
    nome=NOME, ativo="BTCUSDT", exchange="bybit", timeframe="30m", estilo_trade="day", confluencia_tipo="conservador",
    estrategia="range_tradeiros", categoria="linear", modo_execucao="simulador", subconta="principal",
    banca=10000.0, risco_pct=0.01, max_alocacao_pct=1.0, alavancagem=1, quantidade=0.001,
    max_trades_dia=10, max_perda_dia_pct=0.03, delay_execucao=30, tipo_entrada="limite",
    position_mode="one-way", margin_mode="cross",
    usar_elliott=False, usar_vwap=False, usar_tpo=True, usar_volume_profile=False, usar_orderblock=False,
    usar_fibonacci=False, usar_orderflow=True, usar_sentimento=False, usar_tendencia_macro=False, usar_api_macro=False,
    usar_filtro_regime=False, usar_trailing_stop=False,
)


def main():
    if not aguardar_banco():
        sys.exit("banco indisponível")
    db = SessionLocal()
    try:
        existente = db.query(Bot).filter(Bot.nome == NOME).first()
        if existente:
            print(f"já existe: bot {existente.id} ({existente.nome}), estratégia {existente.estrategia}, ativo={existente.ativo_bot}")
            return
        bot = Bot(**CONFIG, ativo_bot="--inativo" not in sys.argv)
        db.add(bot)
        db.commit()
        print(f"criado: bot {bot.id} ({bot.nome}) | {bot.modo_execucao} | subconta {bot.subconta} | ativo={bot.ativo_bot}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
