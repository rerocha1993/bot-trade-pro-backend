# core/conexao_coinbase.py

import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

class CoinbaseConnector:
    def __init__(self, modo_execucao="simulador"):
        self.modo_execucao = modo_execucao
        if self.modo_execucao == "real":
            self.exchange = ccxt.coinbasepro({
                'apiKey': os.getenv("COINBASE_API_KEY"),
                'secret': os.getenv("COINBASE_API_SECRET"),
                'password': os.getenv("COINBASE_API_PASSWORD"),   # Coinbase exige password!
                'enableRateLimit': True
            })
        else:
            self.exchange = ccxt.coinbasepro({
                'enableRateLimit': True
            })

    def _normalize(self, par):
        return par.replace("/", "-")  # Coinbase usa traço

    def obter_preco_atual(self, par):
        par = self._normalize(par)
        ticker = self.exchange.fetch_ticker(par)
        return ticker['last']

    def obter_order_book(self, par, profundidade=10):
        par = self._normalize(par)
        book = self.exchange.fetch_order_book(par)
        return {
            "bids": book['bids'][:profundidade],
            "asks": book['asks'][:profundidade]
        }

    def obter_ohlcv(self, par, timeframe='15m', limite=100):
        par = self._normalize(par)
        return self.exchange.fetch_ohlcv(
            par,
            timeframe=timeframe,
            limit=limite
        )
