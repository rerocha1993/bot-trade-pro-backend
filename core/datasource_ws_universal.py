import websocket
import threading
import json
import queue

class DataSourceWebsocketUniversal:
    def __init__(self, exchange, symbol_spot, websocket_url=None, trades_buffer=1000, ob_buffer=100):
        """
        exchange: 'bybit' ou 'coinbase'
        symbol_spot: par padrão do seu bot ('BTC/USDT', 'ETH/USDT', etc)
        """
        self.exchange = exchange.lower()
        self.symbol_spot = symbol_spot.upper()
        self.websocket_url = websocket_url

        self.trades = queue.deque(maxlen=trades_buffer)
        self.order_book = {}  # {'bids': [(price, qty)], 'asks': [(price, qty)]}
        self.ws = None

        # Convert symbols
        if self.exchange == 'bybit':
            self.symbol_ws = self.symbol_spot.replace('/', '')    # BTC/USDT → BTCUSDT
            self.url_trades = "wss://stream.bybit.com/v5/public/spot"
            self.url_ob = self.url_trades  # mesma url para OB
            self.topic_trades = f"publicTrade.{self.symbol_ws}"
            self.topic_ob = f"orderbook.{self.symbol_ws}"
        elif self.exchange == 'coinbase':
            self.symbol_ws = self.symbol_spot.replace('/', '-').upper()  # BTC/USDT → BTC-USD
            self.url_trades = "wss://ws-feed.pro.coinbase.com"
            self.url_ob = self.url_trades
            self.topic_trades = self.symbol_ws
            self.topic_ob = self.symbol_ws

        self._stop_flag = threading.Event()

    def start(self):
        if self.exchange == 'bybit':
            # Bybit: roda duas threads WS (trades e orderbook)
            threading.Thread(target=self._run_bybit_trades, daemon=True).start()
            threading.Thread(target=self._run_bybit_ob, daemon=True).start()
        elif self.exchange == 'coinbase':
            threading.Thread(target=self._run_coinbase, daemon=True).start()

    def stop(self):
        self._stop_flag.set()

    def _run_bybit_trades(self):
        def on_open(ws):
            sub_msg = {"op": "subscribe", "args": [self.topic_trades]}
            ws.send(json.dumps(sub_msg))
        def on_message(ws, message):
            data = json.loads(message)
            if data.get("topic", "").startswith("publicTrade."):
                for t in data.get("data", []):
                    trade = {
                        'price': float(t['p']),
                        'qty': float(t['v']),
                        'side': 'buy' if t['S'] == 'Buy' else 'sell',
                        'timestamp': int(t['T'])
                    }
                    self.trades.append(trade)
        ws = websocket.WebSocketApp(
            self.url_trades, on_open=on_open, on_message=on_message)
        ws.run_forever()

    def _run_bybit_ob(self):
        def on_open(ws):
            sub_msg = {"op": "subscribe", "args": [self.topic_ob]}
            ws.send(json.dumps(sub_msg))
        def on_message(ws, message):
            data = json.loads(message)
            if data.get("topic", "").startswith("orderbook."):
                ob = data.get("data", [{}])[0]
                self.order_book = {
                    'bids': [(float(b[0]), float(b[1])) for b in ob.get('b', [])],
                    'asks': [(float(a[0]), float(a[1])) for a in ob.get('a', [])],
                }
        ws = websocket.WebSocketApp(
            self.url_ob, on_open=on_open, on_message=on_message)
        ws.run_forever()

    def _run_coinbase(self):
        def on_open(ws):
            # subscrição em trades ("matches") e order book ("level2")
            sub_msg = {
                "type": "subscribe",
                "channels": [
                    {"name": "matches", "product_ids": [self.topic_trades]},
                    {"name": "level2", "product_ids": [self.topic_ob]}
                ]
            }
            ws.send(json.dumps(sub_msg))
        def on_message(ws, message):
            data = json.loads(message)
            if data.get("type") == "match":
                trade = {
                    'price': float(data['price']),
                    'qty': float(data['size']),
                    'side': 'buy' if data['side'] == 'buy' else 'sell',
                    'timestamp': int(pd.to_datetime(data['time']).timestamp() * 1000) if 'time' in data else 0
                }
                self.trades.append(trade)
            elif data.get("type") == "l2update":
                # Atualiza o order book (apenas exemplo, expanda se quiser full book)
                changes = data.get("changes", [])
                for side, price, qty in changes:
                    side = 'bids' if side == 'buy' else 'asks'
                    if qty == "0":
                        # remove
                        if side in self.order_book:
                            self.order_book[side] = [x for x in self.order_book.get(side, []) if x[0] != float(price)]
                    else:
                        self.order_book.setdefault(side, [])
                        self.order_book[side] = [x for x in self.order_book[side] if x[0] != float(price)]
                        self.order_book[side].append((float(price), float(qty)))
        import pandas as pd
        ws = websocket.WebSocketApp(
            self.url_trades, on_open=on_open, on_message=on_message)
        ws.run_forever()

    def get_trades(self):
        return list(self.trades)

    def get_order_book(self):
        return self.order_book if self.order_book else {'bids': [], 'asks': []}
