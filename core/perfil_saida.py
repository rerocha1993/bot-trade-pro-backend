# core/perfil_saida.py
"""
PERFIL DE SAÍDA POR ESTILO: quanto o preço precisa andar antes do trailing colar, e a que distância ele cola.

Um único par de números para os três estilos não serve. O trailing tem que ficar FORA do ruído normal do
timeframe, senão o pavio de um candle qualquer tira a posição antes do movimento acontecer. O ruído de um candle
de 4h é umas 15 vezes o de um candle de 1m, então a distância acompanha:

    scalping  1m     ruído ~0,1%   -> cola a 0,30%
    daytrade  15/30m ruído ~0,4%   -> cola a 0,70%
    swing     4h     ruído ~1,5%   -> cola a 2,00%

REGRA QUE VALE PARA OS TRÊS: o ativador é sempre MAIOR que a distância. Assim, no instante em que o trailing
liga, o stop já está acima do preço de entrada (numa compra) e a posição nunca volta a valer menos que zero a
zero. Era o que quebrava com 0,50% / 0,30% no swing: ligava cedo demais e colava perto demais.

O escalonamento também muda de estilo: no scalp o alvo é curto e vale garantir cedo; no swing vale deixar correr.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PerfilSaida:
    ativador_trailing: float      # fração a favor para o trailing ligar
    distancia_trailing: float     # distância do stop ao preço depois de ligado
    saida_escalonada: str         # plano de realizações parciais ("avanço/fração, ...")

    def __post_init__(self):
        # a garantia de zero a zero: sem isso o trailing pode ligar travando prejuízo
        if self.ativador_trailing <= self.distancia_trailing:
            raise ValueError("ativador tem que ser maior que a distância, senão o trailing trava prejuízo")


PERFIS: Dict[str, PerfilSaida] = {
    "scalping": PerfilSaida(0.0040, 0.0030, "50/40, 80/30"),
    "daytrade": PerfilSaida(0.0100, 0.0070, "50/30, 75/30, 90/25"),
    "swing":    PerfilSaida(0.0300, 0.0200, "50/25, 75/25, 90/25"),
}

PADRAO = PERFIS["daytrade"]


def perfil(estilo_trade: str) -> PerfilSaida:
    """Perfil do estilo; estilo desconhecido ou vazio cai no daytrade, que é o meio termo."""
    return PERFIS.get((estilo_trade or "").strip().lower(), PADRAO)
