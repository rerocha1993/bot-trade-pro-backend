# Arquivo: core/fibonacci.py

class Fibonacci:
    def __init__(self, high: float, low: float):
        self.high = high
        self.low = low
        self.levels = self.calcular_niveis()
        self._validar_niveis()

    def calcular_niveis(self):
        diff = self.high - self.low
        return {
            '0.0%': round(self.low, 2),
            '23.6%': round(self.low + 0.236 * diff, 2),
            '38.2%': round(self.low + 0.382 * diff, 2),
            '50.0%': round(self.low + 0.5 * diff, 2),
            '61.8%': round(self.low + 0.618 * diff, 2),
            '78.6%': round(self.low + 0.786 * diff, 2),
            '100.0%': round(self.high, 2),
            '161.8%': round(self.low + 1.618 * diff, 2),
            '261.8%': round(self.low + 2.618 * diff, 2)
        }

    def _validar_niveis(self):
        """Garante que todos os níveis fiquem dentro do range institucional."""
        # Tolerância para aceitar levemente fora do range, ex: extensões de alvo
        max_limit = self.high * 1.02
        min_limit = self.low * 0.98
        # Só mantém níveis dentro do range permitido, exceto extensões (161.8%, 261.8%)
        for k, v in list(self.levels.items()):
            if k in ('161.8%', '261.8%'):
                continue  # Permite extensões além do topo
            if not (min_limit <= v <= max_limit):
                del self.levels[k]

    def exibir_niveis(self):
        print("Níveis de Fibonacci:")
        for nivel, valor in self.levels.items():
            print(f"{nivel}: {valor}")

# Exemplo de uso permanece igual ao original
if __name__ == "__main__":
    high = float(input("Digite o valor máximo (High): "))
    low = float(input("Digite o valor mínimo (Low): "))

    fib = Fibonacci(high, low)
    fib.exibir_niveis()
