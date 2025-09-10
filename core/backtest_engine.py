# core/backtest_engine.py

import pandas as pd

class BacktestEngine:
    def __init__(self, arquivo_csv, estrategia_func=None):
        self.arquivo_csv = arquivo_csv
        self.dados = pd.read_csv(arquivo_csv)
        self.resultados = []
        self.estrategia_func = estrategia_func or self.estrategia_simples

    def estrategia_simples(self, candle_atual, candle_anterior):
        # Exemplo: compra se fechar acima do anterior, vende se fechar abaixo
        if candle_atual["close"] > candle_anterior["close"]:
            return "buy"
        elif candle_atual["close"] < candle_anterior["close"]:
            return "sell"
        else:
            return "hold"

    def executar(self):
        for i in range(1, len(self.dados)):
            anterior = self.dados.iloc[i - 1]
            atual = self.dados.iloc[i]

            acao = self.estrategia_func(atual, anterior)
            resultado = {
                "timestamp": atual["timestamp"],
                "acao": acao,
                "preco": atual["close"]
            }
            self.resultados.append(resultado)

        return pd.DataFrame(self.resultados)

    def salvar_resultado(self, caminho_saida):
        df_resultado = pd.DataFrame(self.resultados)
        df_resultado.to_csv(caminho_saida, index=False)
