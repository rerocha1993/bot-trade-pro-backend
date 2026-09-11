"""
Histórico público de derivativos da Bybit para BTCUSDT (o contexto de order flow que o Tradeiros lê):

    open interest (1h)          contratos abertos — entrando (posição nova) ou saindo (stop/realização)
    long/short de contas (1h)   proporção de contas compradas x vendidas (quem pode ficar preso)
    funding                     já baixado em data/historico/funding_bybit.json

    python scripts/baixar_derivativos.py --desde 2020-06-01

Saída: data/historico/oi_bybit_1h.json e data/historico/lsr_bybit_1h.json ({timestamp_ms: valor}).
Só leitura de dados públicos.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ccxt  # noqa: E402


def ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def paginar(fn, params, chave_ts, chave_valor, desde_ms, passo_ms, limite):
    """Busca de trás para a frente pela janela [start, end], de `limite` em `limite` pontos."""
    out = {}
    fim = int(time.time() * 1000)
    while fim > desde_ms:
        ini = max(desde_ms, fim - passo_ms * limite)
        try:
            r = fn({**params, "startTime": ini, "endTime": fim, "limit": limite})
        except Exception as e:
            print("  erro, nova tentativa:", str(e)[:100])
            time.sleep(2)
            continue
        lista = (r.get("result") or {}).get("list") or []
        for x in lista:
            out[int(x[chave_ts])] = float(x[chave_valor]) if not isinstance(chave_valor, tuple) else \
                float(x[chave_valor[0]]) / max(float(x[chave_valor[1]]), 1e-9)
        fim = ini - 1
        time.sleep(0.12)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2020-06-01")
    a = ap.parse_args()
    ex = ccxt.bybit({"enableRateLimit": True})
    pasta = os.path.join("data", "historico")
    oi = paginar(ex.publicGetV5MarketOpenInterest, {"category": "linear", "symbol": "BTCUSDT", "intervalTime": "1h"},
                 "timestamp", "openInterest", ms(a.desde), 3_600_000, 200)
    print(f"open interest: {len(oi)} pontos, de {dt.datetime.fromtimestamp(min(oi) / 1000, dt.timezone.utc):%Y-%m-%d}")
    with open(os.path.join(pasta, "oi_bybit_1h.json"), "w") as f:
        json.dump(oi, f)
    lsr = paginar(ex.publicGetV5MarketAccountRatio, {"category": "linear", "symbol": "BTCUSDT", "period": "1h"},
                  "timestamp", ("buyRatio", "sellRatio"), ms(a.desde), 3_600_000, 500)
    if lsr:
        print(f"long/short: {len(lsr)} pontos, de {dt.datetime.fromtimestamp(min(lsr) / 1000, dt.timezone.utc):%Y-%m-%d}")
    else:
        print("long/short: sem dados")
    with open(os.path.join(pasta, "lsr_bybit_1h.json"), "w") as f:
        json.dump(lsr, f)


if __name__ == "__main__":
    main()
