# conselho/niveis.py
"""
Níveis de referência do mapa do dia que não são perfil de TPO: a posição do preço dentro do valor e o pivô virgem.

Vieram do antigo tradeiros/leitura.py, sem mudar o cálculo, quando o código de robô foi apagado (20/10/2026).
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence


def posicao_no_range(preco: float, val: float, vah: float) -> Optional[float]:
    """Posição do preço entre o VAL (0) e o VAH (1); fora do valor fica abaixo de 0 ou acima de 1."""
    largura = vah - val
    return None if largura <= 0 else (preco - val) / largura


def pivo_virgem(diarios: Sequence[Sequence[float]], preco: float, janela: int = 30) -> Dict[str, Optional[float]]:
    """Abertura de um dia que nenhum dia seguinte voltou a tocar (gente presa ali); o mais perto acima e abaixo."""
    ult = list(diarios)[-janela:]
    virgens = []
    for i, d in enumerate(ult):
        abertura = float(d[1])
        if all(not (float(x[3]) <= abertura <= float(x[2])) for x in ult[i + 1:]) and i < len(ult) - 1:
            virgens.append(abertura)
    acima = [v for v in virgens if v > preco]
    abaixo = [v for v in virgens if v < preco]
    return {"acima": min(acima) if acima else None, "abaixo": max(abaixo) if abaixo else None}
