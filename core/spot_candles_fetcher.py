# core/spot_candles_fetcher.py

import ccxt
import time
import logging
from datetime import datetime, timedelta, timezone

class SpotCandlesFetcher:
    def __init__(self, exchange_id="bybit", rate_limit=1.2):
        exchange_class = getattr(ccxt, exchange_id)
        # GARANTE QUE ESTÁ NA SPOT!
        self.exchange = exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self.rate_limit = rate_limit  # segundos entre requests

    def fetch_all_candles(self, symbol, timeframe, since, until, logger=None):
        """
        Busca TODOS os candles SPOT de symbol/timeframe no intervalo [since, until].
        since/until: datetime.datetime
        Retorna lista [ [timestamp, open, high, low, close, volume], ... ]
        """
        all_candles = []
        limit = 1000  # limite máximo da Bybit SPOT

        since_ms = int(since.replace(tzinfo=timezone.utc).timestamp() * 1000)
        until_ms = int(until.replace(tzinfo=timezone.utc).timestamp() * 1000)

        last_time = since_ms
        while last_time < until_ms:
            try:
                candles = self.exchange.fetch_ohlcv(symbol, timeframe, since=last_time, limit=limit)
                if not candles:
                    if logger:
                        logger.warning(f"Nenhum candle retornado para {symbol} em {last_time}.")
                    break
                all_candles.extend(candles)
                # Atualiza o ponteiro para o próximo bloco
                last_candle_time = candles[-1][0]
                last_time = last_candle_time + 1  # próximo ms após o último candle

                # Para evitar rate limit/exchange ban
                time.sleep(self.rate_limit)
                if logger:
                    logger.info(f"{len(candles)} candles baixados para {symbol} em {timeframe} até {datetime.utcfromtimestamp(last_candle_time/1000)}")

                # Early stop se já chegou no until_ms
                if last_candle_time >= until_ms or len(candles) < limit:
                    break
            except Exception as e:
                msg = f"Erro ao buscar candles {symbol} {timeframe} {datetime.utcfromtimestamp(last_time/1000)}: {e}"
                if logger:
                    logger.error(msg)
                else:
                    print(msg)
                time.sleep(self.rate_limit * 2)  # aguarda um pouco mais e tenta de novo

        # Filtra candles exatamente no intervalo desejado
        candles_filtrados = [c for c in all_candles if since_ms <= c[0] <= until_ms]
        return candles_filtrados

# Exemplo de uso profissional (não é mock, é só documentação):
# from core.spot_candles_fetcher import SpotCandlesFetcher
# fetcher = SpotCandlesFetcher(exchange_id="bybit")
# inicio = datetime(2023,1,1)
# fim = datetime(2023,6,1)
# candles = fetcher.fetch_all_candles("BTC/USDT", "1h", inicio, fim)

