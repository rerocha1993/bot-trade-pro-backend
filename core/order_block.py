# Arquivo: trading_bot/core/order_block.py

class OrderBlockDetector:
    def __init__(self, ohlcv: list):
        """
        ohlcv: lista de candles no formato [timestamp, open, high, low, close, volume]
        """
        self.ohlcv = ohlcv
        # range dos candles para filtro de validação
        self.highs = [c[2] for c in ohlcv]
        self.lows = [c[3] for c in ohlcv]
        self.max_high = max(self.highs)
        self.min_low = min(self.lows)
        self.tolerancia = 0.02  # 2%

    def identificar_blocks(self, tipo='bullish'):
        """
        tipo: 'bullish' ou 'bearish'
        Retorna uma lista com os candles identificados como blocos institucionais.
        """
        blocks = []

        for i in range(len(self.ohlcv) - 2):
            atual = self.ohlcv[i]
            prox = self.ohlcv[i + 1]

            open_atual, close_atual = atual[1], atual[4]
            high_atual, low_atual = atual[2], atual[3]
            open_prox, close_prox = prox[1], prox[4]

            if tipo == 'bullish':
                # Último candle vermelho seguido por verde forte
                if close_atual < open_atual and close_prox > open_prox and close_prox > close_atual:
                    zona = (open_atual, high_atual)
                    # Validação institucional: zona deve estar no range dos candles analisados
                    if self._zona_valida(zona):
                        blocks.append({
                            'index': i,
                            'tipo': 'bullish',
                            'zona': zona
                        })

            elif tipo == 'bearish':
                # Último candle verde seguido por vermelho forte
                if close_atual > open_atual and close_prox < open_prox and close_prox < close_atual:
                    zona = (open_atual, low_atual)
                    if self._zona_valida(zona):
                        blocks.append({
                            'index': i,
                            'tipo': 'bearish',
                            'zona': zona
                        })

        return blocks

    def _zona_valida(self, zona):
        """Só aceita blocks institucionais dentro do range dos candles do período analisado."""
        min_limit = self.min_low * (1 - self.tolerancia)
        max_limit = self.max_high * (1 + self.tolerancia)
        return all(min_limit <= preco <= max_limit for preco in zona)

# Exemplo de uso permanece igual ao original
if __name__ == "__main__":
    from core.conexoes.conexao_bybit import BybitConnector

    con = BybitConnector()
    par = input("Par de moedas (ex: BTC/USDT): ").strip().upper()
    ohlcv = con.obter_ohlcv(par, timeframe='15m', limite=200)

    detector = OrderBlockDetector(ohlcv)
    bullish_blocks = detector.identificar_blocks(tipo='bullish')
    bearish_blocks = detector.identificar_blocks(tipo='bearish')

    print("Order Blocks Bullish:")
    for block in bullish_blocks:
        print(block)

    print("\nOrder Blocks Bearish:")
    for block in bearish_blocks:
        print(block)
