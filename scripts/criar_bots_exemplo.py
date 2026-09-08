# scripts/criar_bots_exemplo.py
"""
Cadastra 4 bots de comparação (inativos, modo simulador, banca 10 000, risco 1%):
    Scalp Fluxo      scalping  1m   turbo        Order Flow + VWAP (websocket ligado, entrada limitada)
    Day TPO          daytrade  15m  conservador  TPO + Volume Profile + VWAP
    Swing Estrutura  swing     4h   conservador  Order Block + Fibonacci + VWAP
    Elliott Puro     daytrade  30m  turbo        só Elliott + Fibonacci
Uso: python scripts/criar_bots_exemplo.py [--ativar]
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.database import SessionLocal  # noqa: E402
from models.bot import Bot  # noqa: E402

BASE = dict(ativo="BTCUSDT", exchange="bybit", modo_execucao="simulador", alavancagem=1, quantidade=0.01, banca=10000, risco_pct=0.01,
            max_alocacao_pct=0.5, usar_elliott=True, usar_sentimento=True, usar_tendencia_macro=True, usar_api_macro=True,
            usar_filtro_regime=True, prob_sucesso_minima=0.45, ativo_bot=False, max_trades_dia=10, max_perda_dia_pct=0.03)

BOTS = [
    dict(nome="Scalp Fluxo", timeframe="1m", estilo_trade="scalping", confluencia_tipo="turbo", usar_fibonacci=True, usar_orderflow=True,
         usar_vwap=True, usar_tpo=False, usar_volume_profile=False, usar_orderblock=False, usar_websocket=True, tipo_entrada="limite",
         limite_candles_espera=2, delay_execucao=5),
    dict(nome="Day TPO", timeframe="15m", estilo_trade="daytrade", confluencia_tipo="conservador", usar_fibonacci=True, usar_tpo=True,
         usar_volume_profile=True, usar_vwap=True, usar_orderflow=False, usar_orderblock=False, tipo_entrada="limite", limite_candles_espera=3),
    dict(nome="Swing Estrutura", timeframe="4h", estilo_trade="swing", confluencia_tipo="conservador", usar_fibonacci=True, usar_orderblock=True,
         usar_vwap=True, usar_tpo=False, usar_volume_profile=False, usar_orderflow=False, tipo_entrada="limite", limite_candles_espera=2,
         usar_trailing_stop=True, delay_execucao=30),
    dict(nome="Elliott Puro", timeframe="30m", estilo_trade="daytrade", confluencia_tipo="turbo", usar_fibonacci=True, usar_tpo=False,
         usar_volume_profile=False, usar_vwap=False, usar_orderflow=False, usar_orderblock=False, tipo_entrada="mercado"),
]


def main():
    ativar = "--ativar" in sys.argv
    db = SessionLocal()
    try:
        for cfg in BOTS:
            existente = db.query(Bot).filter(Bot.nome == cfg["nome"]).first()
            dados = {**BASE, **cfg, "ativo_bot": ativar}
            if existente:
                for k, v in dados.items():
                    setattr(existente, k, v)
                print("atualizado:", cfg["nome"])
            else:
                db.add(Bot(**dados))
                print("criado:", cfg["nome"])
        db.commit()
        for b in db.query(Bot).order_by(Bot.id).all():
            print(f"  id={b.id:3d} {b.nome:18} {b.timeframe:4} {b.estilo_trade:9} {b.confluencia_tipo:12} {b.modo_execucao:10} ativo={b.ativo_bot}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
