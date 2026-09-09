# scripts/setup_db.py
"""
Prepara o banco (SQL Server LocalDB dbo_trading_bot):
    1. cria tabelas que faltam (PosicoesBot, DecisoesBot, ...)
    2. adiciona colunas novas na tabela Bots se não existirem
    3. normaliza bots antigos: exchange 'bybit-testnet' -> 'bybit' (o modo vem de modo_execucao)
    4. garante a exchange/pares institucionais da Bybit
Uso:  python scripts/setup_db.py
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect, text  # noqa: E402

from api.database import SessionLocal, engine  # noqa: E402
import models  # noqa: E402,F401  (registra todas as tabelas)
from models import Base  # noqa: E402
from models.bot import Bot  # noqa: E402
from models.exchange_institucional import ExchangeInstitucional  # noqa: E402
from models.pair_institucional import PairInstitucional  # noqa: E402

COLUNAS_NOVAS_POSICOES = {
    "quantidade_inicial": "FLOAT NULL",
    "saidas_feitas": "NVARCHAR(120) NULL",
    "pnl_parcial": "FLOAT NULL DEFAULT 0",
}

COLUNAS_NOVAS_BOTS = {
    "usar_saida_escalonada": "BIT NOT NULL DEFAULT 0",
    "saida_escalonada": "NVARCHAR(120) NULL DEFAULT '50/30, 75/30, 90/25'",
    "mover_stop_para_entrada": "BIT NOT NULL DEFAULT 1",
    "usar_sentimento": "BIT NOT NULL DEFAULT 1",
    "usar_tendencia_macro": "BIT NOT NULL DEFAULT 1",
    "max_trades_dia": "INT NOT NULL DEFAULT 10",
    "max_perda_dia_pct": "FLOAT NOT NULL DEFAULT 0.03",
    "delay_execucao": "INT NOT NULL DEFAULT 10",
    "ativador_trailing": "FLOAT NULL DEFAULT 0.005",
    "distancia_trailing": "FLOAT NULL DEFAULT 0.003",
    "trailing_manual": "BIT NULL DEFAULT 0",
    "usar_volume_profile": "BIT NULL DEFAULT 0",
    "usar_orderblock": "BIT NULL DEFAULT 0",
    "usar_filtro_regime": "BIT NOT NULL DEFAULT 1",
    "prob_sucesso_minima": "FLOAT NOT NULL DEFAULT 0.45",
    "tipo_entrada": "VARCHAR(10) NOT NULL DEFAULT 'mercado'",
    "limite_candles_espera": "INT NOT NULL DEFAULT 3",
    "usar_websocket": "BIT NOT NULL DEFAULT 0",
    "taxa_historica_minima": "FLOAT NOT NULL DEFAULT 0",
    "rr_minimo": "FLOAT NOT NULL DEFAULT 0",
    "estrategia": "VARCHAR(20) NOT NULL DEFAULT 'elliott'",
    "categoria": "VARCHAR(10) NOT NULL DEFAULT 'linear'",
    "range_low": "FLOAT NULL",
    "range_high": "FLOAT NULL",
    "range_status": "VARCHAR(12) NULL",
    "range_motivo": "VARCHAR(255) NULL",
    "short_base_max": "FLOAT NOT NULL DEFAULT 0.5",
    "folga_stop": "FLOAT NOT NULL DEFAULT 0.01",
    "escada_json": "VARCHAR(500) NULL",
    "grade_json": "NVARCHAR(MAX) NULL",
    "saida_estrutural": "BIT NOT NULL DEFAULT 0",
    "usar_motor_fluxo": "BIT NOT NULL DEFAULT 0",
    "barra_tipo": "VARCHAR(10) NOT NULL DEFAULT 'volume'",
    "barra_tamanho": "FLOAT NOT NULL DEFAULT 0",
    "barra_segundos_alvo": "FLOAT NOT NULL DEFAULT 30",
}


# Colunas de texto que nasceram estreitas demais para os valores que o código escreve. Um INSERT que não cabe
# não é só um log perdido: ele derruba a transação inteira, e junto vai o estado do robô que estava sendo gravado.
# Foi assim que uma realização parcial saiu três vezes na corretora: 'saida_parcial' não cabia em varchar(10).
LARGURAS_MINIMAS = [
    ("LogExecucaoBot", "acao", 30),
    ("LogExecucaoBot", "tipo_operacao", 30),
    ("LogExecucaoBot", "direcao", 10),
    ("DecisoesBot", "acao", 20),
    ("PosicoesBot", "direcao", 10),
    ("PosicoesBot", "status", 20),
]


def alargar_colunas(cn) -> int:
    q = text("""SELECT CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = :t AND COLUMN_NAME = :c""")
    mudou = 0
    for tabela, coluna, minimo in LARGURAS_MINIMAS:
        r = cn.execute(q, {"t": tabela, "c": coluna}).first()
        if not r or r[0] is None or r[0] < 0 or r[0] >= minimo:
            continue          # inexistente, já é MAX (-1), ou já cabe
        nulo = "NULL" if (r[1] or "YES").upper() == "YES" else "NOT NULL"
        print(f"   ~ {tabela}.{coluna} {r[2]}({r[0]}) -> {r[2]}({minimo})")
        cn.execute(text(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} {r[2]}({minimo}) {nulo}"))
        mudou += 1
    return mudou


def main():
    from api.database import aguardar_banco
    if not aguardar_banco():
        print("banco indisponível: o LocalDB não respondeu. Rode 'sqllocaldb start MSSQLLocalDB' e tente de novo.")
        raise SystemExit(1)
    print("1) create_all ...")
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    existentes = {c["name"] for c in insp.get_columns("Bots")}
    with engine.begin() as cn:
        for col, ddl in COLUNAS_NOVAS_BOTS.items():
            if col not in existentes:
                print(f"   + coluna Bots.{col}")
                cn.execute(text(f"ALTER TABLE Bots ADD {col} {ddl}"))
    existentes_pos = {c["name"] for c in inspect(engine).get_columns("PosicoesBot")}
    with engine.begin() as cn:
        for col, ddl in COLUNAS_NOVAS_POSICOES.items():
            if col not in existentes_pos:
                print(f"   + coluna PosicoesBot.{col}")
                cn.execute(text(f"ALTER TABLE PosicoesBot ADD {col} {ddl}"))
    # tipos de coluna que precisam ser BIGINT (timestamps em ms)
    with engine.begin() as cn:
        cols = {c["name"]: c for c in inspect(engine).get_columns("DecisoesBot")}
        if cols.get("candle_ts") and "BIG" not in str(cols["candle_ts"]["type"]).upper():
            print("   ~ DecisoesBot.candle_ts -> BIGINT")
            cn.execute(text("ALTER TABLE DecisoesBot ALTER COLUMN candle_ts BIGINT NULL"))
    with engine.begin() as cn:
        alargar_colunas(cn)
    print("2) normalizando bots ...")
    db = SessionLocal()
    try:
        for bot in db.query(Bot).all():
            ex = (bot.exchange or "bybit").lower()
            if "testnet" in ex:
                bot.exchange = "bybit"
                if (bot.modo_execucao or "simulador") == "simulador":
                    bot.modo_execucao = "simulador"   # paper trading (sem ordens)
            if bot.ativo:
                bot.ativo = bot.ativo.replace("/", "").upper()
            if bot.estilo_trade:
                e = bot.estilo_trade.lower()
                bot.estilo_trade = "scalping" if "scalp" in e else "swing" if "swing" in e else "daytrade"
            if bot.confluencia_tipo:
                bot.confluencia_tipo = bot.confluencia_tipo.lower()
            print(f"   bot {bot.id} {bot.nome}: {bot.ativo} {bot.timeframe} {bot.estilo_trade} modo={bot.modo_execucao} exchange={bot.exchange}")
        db.commit()
        print("3) exchange/pares institucionais ...")
        ex = db.query(ExchangeInstitucional).filter(ExchangeInstitucional.nome == "bybit").first()
        if not ex:
            ex = ExchangeInstitucional(nome="bybit", ativa=True)
            db.add(ex)
            db.flush()
        for tf in ("30m", "4h", "1d", "1w"):
            if not db.query(PairInstitucional).filter_by(exchange_id=ex.id, par="BTCUSDT", timeframe=tf).first():
                db.add(PairInstitucional(exchange_id=ex.id, par="BTCUSDT", timeframe=tf, ativo=True))
        db.commit()
        print("OK. Tabelas:", sorted(inspect(engine).get_table_names()))
    finally:
        db.close()


if __name__ == "__main__":
    main()
