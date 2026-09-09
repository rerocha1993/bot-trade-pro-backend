import json
import time
import queue
import threading

import pandas as pd
import websocket

class DataSourceWebsocketUniversal:
    def __init__(self, exchange, symbol_spot, websocket_url=None, trades_buffer=1000, ob_buffer=100):
        """
        exchange: 'bybit' ou 'coinbase'
        symbol_spot: par padrão do seu bot ('BTC/USDT', 'ETH/USDT', etc)
        """
        self.exchange = exchange.lower().split("-")[0]
        self.testnet = "testnet" in exchange.lower()
        self.symbol_spot = symbol_spot.upper()
        self.websocket_url = websocket_url

        self.trades = queue.deque(maxlen=trades_buffer)
        self.order_book = {}  # {'bids': [(price, qty)], 'asks': [(price, qty)]}
        self.ws = None
        self.ob_buffer = int(ob_buffer)
        # livro mantido por instancia: como dict de classe, dois robos compartilhariam o mesmo livro
        self._niveis_bid: dict = {}
        self._niveis_ask: dict = {}
        self._erro_ob = None
        self._erro_trades = None

        # Convert symbols
        if self.exchange == 'bybit':
            self.symbol_ws = self.symbol_spot.replace('/', '')    # BTC/USDT → BTCUSDT
            self.url_trades = websocket_url or ("wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear")
            self.url_ob = self.url_trades  # mesma url para OB
            self.topic_trades = f"publicTrade.{self.symbol_ws}"
            self.topic_ob = f"orderbook.50.{self.symbol_ws}"
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
            try:
                data = json.loads(message)
                if not str(data.get("topic", "")).startswith("publicTrade."):
                    return
                itens = data.get("data")
                itens = itens if isinstance(itens, list) else [itens] if isinstance(itens, dict) else []
                for t in itens:
                    self.trades.append({
                        'price': float(t['p']),
                        'qty': float(t['v']),
                        'side': 'buy' if t['S'] == 'Buy' else 'sell',
                        'timestamp': int(t['T']),
                    })
            except Exception as e:
                self._erro_trades = str(e)[:120]
        ws = websocket.WebSocketApp(
            self.url_trades, on_open=on_open, on_message=on_message, on_error=lambda w, e: None)
        self._ws_trades = ws
        while not self._stop_flag.is_set():
            ws.run_forever(reconnect=5)
            if self._stop_flag.is_set():
                break
            time.sleep(2)

    def _run_bybit_ob(self):
        def on_open(ws):
            sub_msg = {"op": "subscribe", "args": [self.topic_ob]}
            ws.send(json.dumps(sub_msg))
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if not str(data.get("topic", "")).startswith("orderbook."):
                    return
                # a Bybit v5 manda `data` como OBJETO no orderbook (e como lista no publicTrade).
                # Tratar sempre como lista fazia [0] estourar KeyError a cada mensagem.
                d = data.get("data")
                ob = (d[0] if d else {}) if isinstance(d, list) else (d if isinstance(d, dict) else {})
                # a Bybit manda um SNAPSHOT (livro inteiro) e depois DELTAS (só os níveis que mudaram, com
                # tamanho 0 = nível removido). Substituir o livro a cada mensagem deixava só o último delta,
                # e o order flow passava a ler um livro de um nível só.
                if str(data.get("type", "")).lower() == "snapshot" or not self._niveis_bid:
                    self._niveis_bid, self._niveis_ask = {}, {}
                for lado, destino in (("b", self._niveis_bid), ("a", self._niveis_ask)):
                    for nivel in (ob.get(lado) or []):
                        if len(nivel) < 2:
                            continue
                        preco, tam = float(nivel[0]), float(nivel[1])
                        if tam <= 0:
                            destino.pop(preco, None)
                        else:
                            destino[preco] = tam
                bids = sorted(self._niveis_bid.items(), key=lambda x: -x[0])[:self.ob_buffer]
                asks = sorted(self._niveis_ask.items(), key=lambda x: x[0])[:self.ob_buffer]
                if bids or asks:
                    self.order_book = {'bids': bids, 'asks': asks}
            except Exception as e:
                # uma mensagem malformada não pode virar enxurrada de log a noite inteira
                self._erro_ob = str(e)[:120]
        ws = websocket.WebSocketApp(
            self.url_ob, on_open=on_open, on_message=on_message, on_error=lambda w, e: None)
        self._ws_ob = ws
        while not self._stop_flag.is_set():
            ws.run_forever(reconnect=5)
            if self._stop_flag.is_set():
                break
            time.sleep(2)

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
        ws = websocket.WebSocketApp(
            self.url_trades, on_open=on_open, on_message=on_message)
        ws.run_forever()

    def get_trades(self):
        return list(self.trades)

    def get_order_book(self):
        return self.order_book if self.order_book else {'bids': [], 'asks': []}
