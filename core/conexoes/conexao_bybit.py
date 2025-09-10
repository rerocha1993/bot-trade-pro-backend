import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

class BybitConnector:
    def __init__(self, modo_execucao="simulador"):
        self.modo_execucao = modo_execucao
        if self.modo_execucao == "real":
            self.api_key = os.getenv("BYBIT_API_KEY_REAL")
            self.api_secret = os.getenv("BYBIT_SECRET_KEY_REAL")
            self.exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap', 'sandboxMode': False, 
                'recvWindow': 20000,},
            })            
            self.exchange.set_sandbox_mode(False)
        else:
            self.api_key = os.getenv("BYBIT_API_KEY_TESTNET")
            self.api_secret = os.getenv("BYBIT_SECRET_KEY_TESTNET")
            self.exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'spot', 'sandboxMode': True,
                            'recvWindow': 20000,},
            })
            
            self.exchange.set_sandbox_mode(True) 

    def _normalize(self, par):
        return par.replace("/", "")

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
            limit=limite,
            params={"category": "linear"}
        )
    
    def obter_trades(self, par, limit=100):
        # Aqui deve vir a implementação real de consulta de trades
        # Por enquanto, retorna vazio para não travar:
        return []

# Exemplo interativo
if __name__ == "__main__":
    con = BybitConnector(modo_execucao="simulador")
    par = input("Digite o par de moedas (ex: BTC/USDT): ").strip().upper()
    print("Preço atual:", con.obter_preco_atual(par))
    print("Order Book:", con.obter_order_book(par))
    print("OHLCV:", con.obter_ohlcv(par))
