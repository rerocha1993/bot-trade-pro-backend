# core/assimetria.py
"""
REGRA DE ASSIMETRIA DO USUÁRIO (Elliott com várias contagens vivas).

    "Existem 5 contagens, 3 bull e 2 bear, mas as 5 fazem o mesmo movimento inicial. É isso que diferencia:
     você cria as entradas e vai mantendo por invalidação."

Em vez de operar o cenário principal (stop e alvo de UMA contagem), opera o GRUPO de contagens que concorda com
o próximo movimento:

    entrada   no lado do movimento comum, quando o grupo pesa pelo menos `minimo_consenso` (60%, o mesmo
              consenso do motor)
    stop      onde o grupo morre:
                'grupo'   a invalidação mais distante do grupo — só lá TODAS as contagens do movimento morreram
                'maioria' a invalidação em que a maioria (50% do peso) do grupo já morreu
    alvo      onde as contagens começam a divergir: o 1º alvo mais próximo entre as do grupo. Até ali todas
              concordam; depois vira aposta
    manter    enquanto o grupo continuar sendo a maioria; sair no fechamento quando deixar de ser (opcional)

A assimetria vem da estrutura: o stop fica onde a leitura inteira está comprovadamente errada e o alvo onde ela
ainda é unânime. Só entra se o risco:retorno LÍQUIDO de custo compensar (`rr_minimo`).

Uma contagem só entra no grupo se os seus níveis fizerem sentido para o movimento: comprando, invalidação abaixo
do preço e alvo acima (e o contrário vendendo). O resto conta no peso total, mas não no grupo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from core.executor_real import TAXA_MAKER, TAXA_TAKER

SLIPPAGE = 0.0002


@dataclass(frozen=True)
class Grupo:
    lado: str                  # 'buy' | 'sell'
    peso: float                # fração do peso total das contagens que fazem este movimento
    contagens: tuple           # as contagens do grupo (dicts)
    n_total: int


@dataclass(frozen=True)
class PlanoAssimetrico:
    lado: str
    entrada: float
    stop: float
    alvo: float
    rr_liquido: float
    peso: float
    n_grupo: int
    motivo: str


def _coerente(c: Dict, preco: float, lado: str) -> bool:
    alvos = [a for a in (c.get("alvos") or []) if a]
    inv = c.get("inv")
    if not alvos or inv is None:
        return False
    if lado == "buy":
        return inv < preco < alvos[0]
    return alvos[0] < preco < inv


def grupo_do_movimento(cenarios: Sequence[Dict], preco: float, minimo_consenso: float = 0.6) -> Optional[Grupo]:
    """O grupo de contagens que faz o próximo movimento, se ele for maioria. None quando não há consenso."""
    total = sum(float(c.get("prob") or 0) for c in cenarios)
    if total <= 0:
        return None
    for lado in ("buy", "sell"):
        membros = [c for c in cenarios if c.get("direcao") == lado and _coerente(c, preco, lado)]
        peso = sum(float(c.get("prob") or 0) for c in membros) / total
        if membros and peso >= minimo_consenso:
            return Grupo(lado, round(peso, 4), tuple(membros), len(cenarios))
    return None


def stop_do_grupo(g: Grupo, preco: float, tipo: str = "grupo") -> float:
    """'grupo': onde TODAS morreram. 'maioria': onde a maioria do peso do grupo já morreu."""
    ordem = sorted(g.contagens, key=lambda c: abs(preco - float(c["inv"])))   # a mais próxima morre primeiro
    if tipo == "grupo":
        return float(ordem[-1]["inv"])
    peso_total = sum(float(c.get("prob") or 0) for c in ordem) or 1.0
    morto = 0.0
    for c in ordem:
        morto += float(c.get("prob") or 0)
        if morto / peso_total >= 0.5:
            return float(c["inv"])
    return float(ordem[-1]["inv"])


def alvo_comum(g: Grupo, preco: float) -> float:
    """O 1º alvo mais próximo do preço entre as contagens do grupo: até ali todas concordam."""
    return min((float(c["alvos"][0]) for c in g.contagens), key=lambda a: abs(a - preco))


def rr_liquido(entrada: float, stop: float, alvo: float) -> float:
    """Ganho no alvo (saída maker) sobre perda no stop (saída taker + slippage), com a entrada a mercado."""
    entrada_custo = entrada * (TAXA_TAKER + SLIPPAGE)
    ganho = abs(alvo - entrada) - entrada_custo - alvo * TAXA_MAKER
    perda = abs(entrada - stop) + entrada_custo + stop * (TAXA_TAKER + SLIPPAGE)
    return ganho / perda if perda > 0 else 0.0


def plano(cenarios: Sequence[Dict], preco: float, atr: float, tipo_stop: str = "grupo", rr_minimo: float = 1.0,
          minimo_consenso: float = 0.6, risco_minimo_atr: float = 0.3) -> Optional[PlanoAssimetrico]:
    """A entrada da regra, ou None. O stop colado no preço (menos de `risco_minimo_atr` ATR) é ruído, não estrutura."""
    g = grupo_do_movimento(cenarios, preco, minimo_consenso)
    if g is None:
        return None
    stop = stop_do_grupo(g, preco, tipo_stop)
    alvo = alvo_comum(g, preco)
    if atr and abs(preco - stop) < risco_minimo_atr * atr:
        return None
    rr = rr_liquido(preco, stop, alvo)
    if rr < rr_minimo:
        return None
    return PlanoAssimetrico(g.lado, preco, stop, alvo, round(rr, 3), g.peso, len(g.contagens),
                            f"{len(g.contagens)} de {g.n_total} contagens ({g.peso:.0%}) fazem o movimento de "
                            f"{'alta' if g.lado == 'buy' else 'baixa'}: stop onde o {tipo_stop} morre, "
                            f"alvo onde elas divergem, R:R líquido {rr:.2f}")


def grupo_vivo(cenarios: Sequence[Dict], preco: float, lado: str) -> float:
    """Peso atual das contagens que ainda fazem o movimento `lado` (para decidir se mantém a posição)."""
    total = sum(float(c.get("prob") or 0) for c in cenarios)
    if total <= 0:
        return 0.0
    return sum(float(c.get("prob") or 0) for c in cenarios if c.get("direcao") == lado) / total
