"""
Cadastra o robô "votação + fatias" (core/estrategia_votacao.py) em modo DEMO, na subconta principal.

    python scripts/criar_bot_fatias.py            # cria ativo (sobe no próximo início do servidor)
    python scripts/criar_bot_fatias.py --inativo

A subconta principal opera o hedge inverso em BTCUSD (outro contrato), então BTCUSDT fica livre nela. A banca
segue o saldo de demo dessa subconta (1.000 USDT em 11/09/2026): cada fatia sai com ~0,002 BTC.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.database import SessionLocal, aguardar_banco  # noqa: E402
from models.bot import Bot  # noqa: E402

NOME = "Swing Fatias 4h"
CONFIG = dict(
    nome=NOME, ativo="BTCUSDT", exchange="bybit", timeframe="4h", estilo_trade="swing", confluencia_tipo="conservador",
    estrategia="votacao_fatias", categoria="linear", modo_execucao="demo", subconta="principal",
    banca=1000.0, risco_pct=0.01, max_alocacao_pct=1.0, alavancagem=1, quantidade=0.001,
    max_trades_dia=10, max_perda_dia_pct=0.03, delay_execucao=30, tipo_entrada="mercado",
    position_mode="one-way", margin_mode="cross",
    usar_elliott=False, usar_vwap=True, usar_tpo=True, usar_volume_profile=True, usar_orderblock=True,
    usar_fibonacci=False, usar_orderflow=False, usar_sentimento=False, usar_tendencia_macro=False, usar_api_macro=False,
    usar_filtro_regime=True, usar_trailing_stop=False,
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
