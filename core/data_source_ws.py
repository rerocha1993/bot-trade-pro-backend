import threading
import time
import queue
import json

# pip install websocket-client
import websocket

class DataSourceWebsocket:
    def __init__(self, symbol='btcusdt', url=None, trades_buffer=1000):
        """
        symbol: símbolo da moeda, ex: btcusdt (sempre minúsculo)
        url: endpoint websocket
        trades_buffer: tamanho do cache de trades
        """
        self.symbol = symbol.lower()
        self.trades_buffer = trades_buffer
        self.trades = queue.deque(maxlen=trades_buffer)
        self.ohlcv = []  # pode implementar OHLCV rolante se quiser
        self.running = False
        self.ws = None

        # Exemplo: url da Binance Spot para trades
        self.url = url or f"wss://stream.binance.com:9443/ws/{self.symbol}@trade"

    def _on_message(self, ws, message):
        data = json.loads(message)
        # Para Binance: campo 'm' == True (market maker é comprador) => SELL
        trade = {
            'price': float(data['p']),
            'qty': float(data['q']),
            'side': 'sell' if data['m'] else 'buy',
            'timestamp': int(data['T'])
        }
        self.trades.append(trade)
        # Pode atualizar OHLCV aqui se quiser candles em tempo real

    def _on_error(self, ws, error):
        print(f"[WS ERROR] {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print("[WS CLOSED]", close_msg)

    def _on_open(self, ws):
        print("[WS OPEN] Conectado ao stream de trades!")

    def start(self):
        self.running = True
        self.ws = websocket.WebSocketApp(
            self.url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        wst = threading.Thread(target=self.ws.run_forever, daemon=True)
        wst.start()
        print(f"[WS] Thread iniciada para {self.symbol} - {self.url}")

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
            print("[WS] Parou o stream!")

    def get_trades(self):
        return list(self.trades)  # cópia dos últimos trades

    # Para OHLCV rolante: pode implementar candles aqui (agregando os trades por minuto)
    # Ou use um fetcher separado para candles de referência

    # Exemplo de método simples:
    def wait_until_buffered(self, min_trades=10, timeout=10):
        """Espera até o cache de trades atingir tamanho mínimo (ou timeout)."""
        start = time.time()
        while len(self.trades) < min_trades and time.time() - start < timeout:
            time.sleep(0.1)
        return len(self.trades) >= min_trades
