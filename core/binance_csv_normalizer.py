# core/binance_csv_normalizer.py

import os
import pandas as pd

class BinanceCSVNormalizer:
    def __init__(self, pasta_csv_bruto, arquivo_saida):
        self.pasta_csv_bruto = pasta_csv_bruto
        self.arquivo_saida = arquivo_saida
        self.colunas_binance = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"
        ]

    def normalizar_e_unificar(self):
        arquivos = [f for f in os.listdir(self.pasta_csv_bruto) if f.endswith(".csv")]
        todos = []

        for arquivo in sorted(arquivos):
            caminho = os.path.join(self.pasta_csv_bruto, arquivo)
            try:
                df = pd.read_csv(caminho, header=None, names=self.colunas_binance)

                df["timestamp"] = df["open_time"] // 1000
                df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                todos.append(df)
            except Exception as e:
                print(f"Erro ao processar {arquivo}: {e}")

        df_final = pd.concat(todos, ignore_index=True)
        df_final.to_csv(self.arquivo_saida, index=False)
        print(f"✅ Arquivo unificado salvo em: {self.arquivo_saida}")
        return df_final
