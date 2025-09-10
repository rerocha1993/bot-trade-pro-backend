import pandas as pd

try:
    import ccxt
except ImportError:
    ccxt = None

class DataSource:
    def __init__(
        self,
        modo='csv',                 # 'csv' ou 'api'
        path_trades=None,
        path_ohlcv=None,
        symbol=None,
        exchange_id='bybit',
        api_key=None,
        secret=None
    ):
        self.modo = modo
        self.path_trades = path_trades
        self.path_ohlcv = path_ohlcv
        self.symbol = symbol
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.secret = secret

        if self.modo == 'api':
            if not ccxt:
                raise ImportError("ccxt não instalado! Use pip install ccxt")
            exchange_class = getattr(ccxt, self.exchange_id)
            if self.api_key and self.secret:
                self.exchange = exchange_class({'apiKey': self.api_key, 'secret': self.secret})
            else:
                self.exchange = exchange_class()
        else:
            self.exchange = None

    def get_trades(self, limit=1000):
        if self.modo == 'csv':
            return self._carregar_trades_csv(self.path_trades)
        else:
            return self._fetch_trades_ccxt(self.symbol, limit=limit)

    def get_ohlcv(self, timeframe='1m', limit=500):
        if self.modo == 'csv':
            return self._carregar_ohlcv_csv(self.path_ohlcv)
        else:
            return self._fetch_ohlcv_ccxt(self.symbol, timeframe, limit=limit)

    @staticmethod
    def _carregar_trades_csv(path_csv):
        df = pd.read_csv(path_csv)
        trades = []
        for _, row in df.iterrows():
            trade = {
                'price': float(row['price']),
                'qty': float(row['qty']),
                'side': 'sell' if row['isBuyerMaker'] else 'buy',
                'timestamp': int(row['time'])
            }
            trades.append(trade)
        return trades

    @staticmethod
    def _carregar_ohlcv_csv(path_csv):
        df = pd.read_csv(path_csv)
        ohlcv = []
        for _, row in df.iterrows():
            ohlcv.append([
                int(row['timestamp']),
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['volume'])
            ])
        return ohlcv

    def _fetch_trades_ccxt(self, symbol, limit=1000):
        trades_raw = self.exchange.fetch_trades(symbol, limit=limit)
        trades = []
        for t in trades_raw:
            trade = {
                'price': float(t['price']),
                'qty': float(t['amount']),
                'side': t['side'] if 'side' in t and t['side'] else ('buy' if t['maker'] else 'sell'),
                'timestamp': int(t['timestamp'])
            }
            trades.append(trade)
        return trades

    def _fetch_ohlcv_ccxt(self, symbol, timeframe='1m', limit=500):
        ohlcv_raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return ohlcv_raw
