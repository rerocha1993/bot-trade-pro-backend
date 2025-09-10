# core/exchange_factory.py

from core.conexoes.conexao_bybit import BybitConnector
from core.conexoes.conexao_binance import BinanceConnector
from core.conexoes.conexao_coinbase import CoinbaseConnector

def get_exchange_connector(exchange_name: str, modo_execucao: str = "simulador"):
    exchange_name = exchange_name.lower()
    if exchange_name == "bybit":
        return BybitConnector(modo_execucao = modo_execucao)
    elif exchange_name == "binance":
        return BinanceConnector(modo_execucao = modo_execucao)
    elif exchange_name == "coinbase":
        return CoinbaseConnector(modo_execucao = modo_execucao)
    else:
        raise ValueError(f"Exchange não suportada: {exchange_name}")
