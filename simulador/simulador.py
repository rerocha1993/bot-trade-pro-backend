# Arquivo: trading_bot/simulador/simulador.py

import csv
import os
from datetime import datetime

class SimuladorTrade:
    def __init__(self, nome_carteira="carteira1"):
        self.nome_carteira = nome_carteira
        self.resultados = []

    def registrar_ordem(self, direcao, preco_entrada, preco_saida):
        lucro = round(preco_saida - preco_entrada, 2) if direcao == 'buy' else round(preco_entrada - preco_saida, 2)
        resultado = {
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "carteira": self.nome_carteira,
            "direcao": direcao,
            "entrada": preco_entrada,
            "saida": preco_saida,
            "lucro": lucro
        }
        self.resultados.append(resultado)
        print("Trade registrado:", resultado)

    def salvar_csv(self):
        path = f"trading_bot/data/{self.nome_carteira}_simulacao.csv"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.resultados[0].keys())
            writer.writeheader()
            writer.writerows(self.resultados)
        print("Resultados salvos em:", path)

# Exemplo de uso:
if __name__ == "__main__":
    sim = SimuladorTrade("carteira_demo")
    sim.registrar_ordem("buy", 24500, 24980)
    sim.registrar_ordem("sell", 25200, 24900)
    sim.salvar_csv()
