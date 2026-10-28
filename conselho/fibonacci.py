# core/fibonacci.py
"""
Fibonacci direcional.

Um swing é definido por (inicio, fim). Para um swing de ALTA (inicio < fim):
    retração X%  = fim - X * (fim - inicio)      -> níveis abaixo do topo
    extensão X%  = inicio + X * (fim - inicio)   -> projeção acima do topo
Para um swing de BAIXA (inicio > fim) as fórmulas são espelhadas.

Fibonacci nunca decide a entrada: fornece níveis para SL/TP e validação de ondas.
"""
from __future__ import annotations

from typing import Dict, Optional

RETRACOES = (0.236, 0.382, 0.5, 0.618, 0.786, 0.886)
EXTENSOES = (1.0, 1.272, 1.618, 2.0, 2.618)


def _rotulo(x: float) -> str:
    return f"{x * 100:.1f}%"


class Fibonacci:
    def __init__(self, high: float, low: float, direcao: str = "up", casas: int = 2):
        """
        Compatível com o uso antigo `Fibonacci(high, low)`:
        direcao='up'   -> swing de alta (low -> high): retrações abaixo do high, extensões acima.
        direcao='down' -> swing de baixa (high -> low): retrações acima do low, extensões abaixo.
        """
        if high is None or low is None:
            raise ValueError("high e low são obrigatórios")
        self.high = float(max(high, low))
        self.low = float(min(high, low))
        self.direcao = "down" if str(direcao).lower() in ("down", "sell", "baixa") else "up"
        self.casas = casas
        self.diff = self.high - self.low
        self.levels: Dict[str, float] = self.calcular_niveis()

    @classmethod
    def de_swing(cls, inicio: float, fim: float, casas: int = 2) -> "Fibonacci":
        direcao = "up" if fim >= inicio else "down"
        return cls(high=max(inicio, fim), low=min(inicio, fim), direcao=direcao, casas=casas)

    # ------------------------------------------------------------------ níveis
    def retracao(self, x: float) -> float:
        if self.direcao == "up":
            return round(self.high - x * self.diff, self.casas)
        return round(self.low + x * self.diff, self.casas)

    def extensao(self, x: float) -> float:
        if self.direcao == "up":
            return round(self.low + x * self.diff, self.casas)
        return round(self.high - x * self.diff, self.casas)

    def calcular_niveis(self) -> Dict[str, float]:
        niveis = {"0.0%": round(self.high if self.direcao == "up" else self.low, self.casas)}
        for r in RETRACOES:
            niveis[_rotulo(r)] = self.retracao(r)
        niveis["100.0%"] = round(self.low if self.direcao == "up" else self.high, self.casas)
        for e in EXTENSOES:
            if e == 1.0:
                continue
            niveis[_rotulo(e)] = self.extensao(e)
        return niveis

    def retracoes(self) -> Dict[str, float]:
        return {_rotulo(r): self.retracao(r) for r in RETRACOES}

    def extensoes(self) -> Dict[str, float]:
        return {_rotulo(e): self.extensao(e) for e in EXTENSOES}

    def nivel_mais_proximo(self, preco: float) -> Optional[str]:
        if not self.levels:
            return None
        return min(self.levels.items(), key=lambda kv: abs(kv[1] - preco))[0]

    def exibir_niveis(self):
        print(f"Níveis de Fibonacci ({'alta' if self.direcao == 'up' else 'baixa'}):")
        for nivel, valor in self.levels.items():
            print(f"  {nivel:>7}: {valor}")


def razao(tamanho_a: float, tamanho_b: float) -> Optional[float]:
    """tamanho_b / tamanho_a com proteção de divisão por zero."""
    if not tamanho_a:
        return None
    return abs(tamanho_b) / abs(tamanho_a)


if __name__ == "__main__":
    fib = Fibonacci(high=25500, low=24500, direcao="up")
    fib.exibir_niveis()
