# scripts/baixar_historico.py
"""
Baixa o histórico completo de BTC para calibração/backtest, sem chave de API:
    Bitstamp (BTC/USD)  desde 2011-08-18: 1h, 4h, 1d      -> data/historico/BTCUSD_bitstamp_<tf>.csv
    Binance  (BTCUSDT)  desde 2017-08:    15m, 5m (zips mensais de data.binance.vision)
                                          -> data/historico/BTCUSDT_binance_<tf>.csv
Uso:
    python scripts/baixar_historico.py                 # tudo
    python scripts/baixar_historico.py --tf 1h 1d      # só esses
    python scripts/baixar_historico.py --tf 1m         # 1m da Binance (grande, ~4,5 milhões de candles)
Reexecutar continua de onde parou (lê o último timestamp do CSV).
"""
import argparse
import io
import os
import sys
import time
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PASTA = os.path.join("data", "historico")
COLS = ["timestamp", "open", "high", "low", "close", "volume"]
BITSTAMP_TFS = {"1h": 3600, "4h": 14400, "1d": 86400}
BINANCE_TFS = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")


def _ultimo_ts(caminho):
    if not os.path.exists(caminho):
        return None
    try:
        return int(pd.read_csv(caminho, usecols=["timestamp"]).timestamp.max())
    except Exception:
        return None


def _salvar(caminho, linhas):
    df = pd.DataFrame(linhas, columns=COLS)
    if os.path.exists(caminho):
        antigo = pd.read_csv(caminho)
        df = pd.concat([antigo, df], ignore_index=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df.to_csv(caminho, index=False)
    return len(df)


def baixar_bitstamp(tf: str, desde_ms: int = None):
    """API pública v2 da Bitstamp: /ohlc/btcusd?step=&limit=1000&start= (segundos)."""
    step = BITSTAMP_TFS[tf]
    caminho = os.path.join(PASTA, f"BTCUSD_bitstamp_{tf}.csv")
    ultimo = _ultimo_ts(caminho)
    inicio = (ultimo + step * 1000) // 1000 if ultimo else (desde_ms // 1000 if desde_ms else int(datetime(2011, 12, 1, tzinfo=timezone.utc).timestamp()))
    agora = int(time.time())
    buffer, total = [], 0
    print(f"[bitstamp {tf}] de {datetime.utcfromtimestamp(inicio)} ...")
    while inicio < agora - step:
        r = requests.get("https://www.bitstamp.net/api/v2/ohlc/btcusd/", params={"step": step, "limit": 1000, "start": inicio}, timeout=30)
        if r.status_code != 200:
            print("  erro", r.status_code, r.text[:100]); time.sleep(5); continue
        dados = r.json().get("data", {}).get("ohlc", [])
        if not dados:
            inicio += step * 1000   # buraco no histórico (ex.: antes de 2012): avança e continua
            continue
        for c in dados:
            ts = int(c["timestamp"])
            if ts * 1000 <= (ultimo or 0):
                continue
            buffer.append([ts * 1000, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"])])
        novo_inicio = int(dados[-1]["timestamp"]) + step
        if novo_inicio <= inicio:
            break
        inicio = novo_inicio
        if len(buffer) >= 20000:
            total = _salvar(caminho, buffer); buffer = []
            print(f"  ... {datetime.utcfromtimestamp(inicio)} ({total} candles)")
        time.sleep(0.15)
    if buffer:
        total = _salvar(caminho, buffer)
    print(f"[bitstamp {tf}] concluído: {total} candles em {caminho}")


def _linhas_do_zip(conteudo, ultimo):
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        with z.open(z.namelist()[0]) as f:
            df = pd.read_csv(f, header=None)
    linhas = []
    for row in df.itertuples(index=False):
        ts = int(row[0])
        if ts > 10**14:
            ts //= 1000
        if ultimo and ts <= ultimo:
            continue
        linhas.append([ts, float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])])
    return linhas


def baixar_binance(tf: str, desde=(2017, 8), forcar_desde: bool = False):
    """`forcar_desde` recomeça em `desde` mesmo com CSV existente (preenche buracos; duplicados são descartados)."""
    caminho = os.path.join(PASTA, f"BTCUSDT_binance_{tf}.csv")
    ultimo = None if forcar_desde else _ultimo_ts(caminho)
    ano, mes = desde
    if ultimo:
        d = datetime.utcfromtimestamp(ultimo / 1000)
        ano, mes = d.year, d.month
    hoje = datetime.utcnow()
    buffer, total = [], 0
    print(f"[binance {tf}] de {ano}-{mes:02d} ...")
    while (ano, mes) <= (hoje.year, hoje.month):
        nome = f"BTCUSDT-{tf}-{ano}-{mes:02d}.zip"
        url = f"https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/{tf}/{nome}"
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                buffer.extend(_linhas_do_zip(r.content, ultimo))
            else:
                # sem zip mensal (mês corrente OU mês recém-fechado que a Binance ainda não publicou): usa os diários.
                # Antes só o mês corrente caía aqui, e agosto/2026 ficou inteiro de fora de todos os CSVs.
                ultimo_dia = hoje.day - 1 if (ano, mes) == (hoje.year, hoje.month) else pd.Period(f"{ano}-{mes:02d}").days_in_month
                achados = 0
                for dia in range(1, ultimo_dia + 1):
                    nd = f"BTCUSDT-{tf}-{ano}-{mes:02d}-{dia:02d}.zip"
                    rd = requests.get(f"https://data.binance.vision/data/spot/daily/klines/BTCUSDT/{tf}/{nd}", timeout=60)
                    if rd.status_code != 200:
                        continue
                    achados += 1
                    buffer.extend(_linhas_do_zip(rd.content, ultimo))
                if achados < ultimo_dia:
                    print(f"  {nome}: sem mensal; {achados} de {ultimo_dia} diários")
        except Exception as e:
            print("  erro", nome, str(e)[:80])
        if len(buffer) >= 200000:
            total = _salvar(caminho, buffer); buffer = []
            print(f"  ... {ano}-{mes:02d} ({total} candles)")
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    if buffer:
        total = _salvar(caminho, buffer)
    print(f"[binance {tf}] concluído: {total} candles em {caminho}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", nargs="*", default=["1h", "4h", "1d", "15m", "5m"])
    ap.add_argument("--desde", help="AAAA-MM: rebaixa a Binance a partir desse mês (preenche buracos)")
    ap.add_argument("--so-binance", action="store_true")
    args = ap.parse_args()
    os.makedirs(PASTA, exist_ok=True)
    desde = tuple(int(x) for x in args.desde.split("-")) if args.desde else (2017, 8)
    for tf in args.tf:
        if tf in BITSTAMP_TFS and not args.so_binance:
            baixar_bitstamp(tf)
        if tf in BINANCE_TFS:   # 1h/4h/1d também da Binance (2017+), útil para comparar/validar
            baixar_binance(tf, desde, forcar_desde=bool(args.desde))


if __name__ == "__main__":
    main()
