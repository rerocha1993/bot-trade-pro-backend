# conselho/tpo_grafico.py
"""
TPO de 30 minutos por dia (UTC) para a tela Gráfico, em qualquer moeda — com as mesmas regras do resto do sistema
(conselho/tpo.py): cada bloco de 30 min marca as faixas de preço que tocou, POC = faixa com mais blocos, área de
valor de 70% a partir do POC.

Para o painel desenhar e JUNTAR dias (composto), cada dia vai com a contagem por faixa numa grade única: todas as
faixas são múltiplos do mesmo `tick`, então somar dois dias é só somar as contagens na mesma posição.

A área de valor usa o desempate da TradingView (a vizinha mais perto do POC; na mesma distância, a de cima), para
o gráfico bater com o TPO dela. O resto do sistema (robôs e avisos) segue com a regra antiga.

Além disso, para cada POC, VAH e VAL, a hora em que o preço voltou a tocar o nível depois do fim do dia (`toques`);
None = ainda não voltou (nível virgem: a linha segue até agora).

`composto()` junta dias seguidos escolhidos no gráfico (o "merge" do Tradeiros) e devolve o mesmo formato de um dia,
com os toques contados depois do último dia da junção.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from conselho.tpo import DIA_MS, Perfil, blocos_30m, expandir_area, tick_para

PASSOS_BONITOS = (1.0, 2.0, 2.5, 5.0, 10.0)
#: desempate da área de valor no gráfico (ver conselho.tpo.expandir_area)
EMPATE = "tradingview"
#: o composto aceita a faixa que o painel recebeu do /tpo, mesmo que o preço tenha andado; menor que 1/10 da atual, não
TICK_MENOR_ACEITO = 10


def tick_grafico(preco: float) -> float:
    """BTC e o que vale mais de US$ 10 mil: a faixa do sistema (0,1% arredondado a US$ 10). O resto: 0,1% do preço
    arredondado para um número redondo (1, 2, 2,5 ou 5 vezes uma potência de 10)."""
    if preco >= 10_000:
        return tick_para(preco)
    if preco <= 0:
        return 1e-8
    alvo = preco * 0.001
    escala = 10 ** math.floor(math.log10(alvo))
    passo = min(PASSOS_BONITOS, key=lambda p: abs(p * escala - alvo))
    return passo * escala


def _primeiro_toque(nivel: float, blocos: Sequence[tuple], desde_ms: int) -> Optional[int]:
    for b in blocos:
        if b[0] >= desde_ms and b[3] <= nivel <= b[2]:
            return b[0] // 1000
    return None


def perfis_por_dia(velas_s: Sequence[Sequence[float]], agora_s: int, dias: int = 10,
                   tick: Optional[float] = None) -> Dict:
    """
    `velas_s`: velas de 30 min ou menores, [início_s, o, h, l, c, v], em ordem. Devolve os últimos `dias` dias
    completos e o de hoje (em formação), o mais velho primeiro. O primeiro dia só entra se começou à 00:00 UTC.
    """
    blocos = blocos_30m([[int(v[0]) * 1000, *v[1:6]] for v in velas_s])
    if not blocos:
        return {"tick": tick, "dias": []}
    tick = tick or tick_grafico(blocos[-1][4])
    por_dia: Dict[int, list] = {}
    for b in blocos:
        por_dia.setdefault(b[0] // DIA_MS, []).append(b)
    chaves = sorted(por_dia)
    if por_dia[chaves[0]][0][0] % DIA_MS != 0:          # dia cortado no começo da janela
        chaves = chaves[1:]
    chaves = chaves[-(dias + 1):]
    hoje = (agora_s * 1000) // DIA_MS
    saida: List[Dict] = []
    for d in chaves:
        p = Perfil(por_dia[d], tick)
        base, cont, _ = p._grade()
        val, vah = p.area_valor(empate=EMPATE)
        poc = p.poc()
        fim_ms = (d + 1) * DIA_MS
        niveis = {"poc": poc, "vah": vah, "val": val}
        saida.append({
            "inicio": d * DIA_MS // 1000,
            "fim": fim_ms // 1000,
            "aberto": d >= hoje,
            "base_i": int(round(base / tick)),
            "contagens": [int(c) for c in cont],
            **niveis,
            "maxima": p.maxima, "minima": p.minima,
            "toques": {k: _primeiro_toque(v, blocos, fim_ms) for k, v in niveis.items()},
        })
    return {"tick": tick, "dias": saida}


def juntar(dias: Sequence[Dict], tick: float) -> Dict:
    """Composto de vários dias da resposta acima: soma as contagens na grade e recalcula POC e área de valor
    (o mesmo que conselho.tpo.merge, mas a partir das contagens e com o desempate da TradingView)."""
    if not dias:
        raise ValueError("nada para juntar")
    i0 = min(d["base_i"] for d in dias)
    i1 = max(d["base_i"] + len(d["contagens"]) for d in dias)
    cont = [0] * (i1 - i0)
    for d in dias:
        for k, c in enumerate(d["contagens"]):
            cont[d["base_i"] - i0 + k] += c
    mx = max(cont)
    meio = (len(cont) - 1) / 2
    i_poc = min((i for i, c in enumerate(cont) if c == mx), key=lambda i: abs(i - meio))
    lo, hi = expandir_area(cont, i_poc, empate=EMPATE)
    return {"poc": (i0 + i_poc + 0.5) * tick, "val": (i0 + lo) * tick, "vah": (i0 + hi + 1) * tick,
            "base_i": i0, "contagens": cont}



def composto(velas_s: Sequence[Sequence[float]], agora_s: int, de_s: int, ate_s: int,
             tick: Optional[float] = None) -> Dict:
    """Junta os dias que começam entre `de_s` e `ate_s` (inclusive). Mesmo formato de um dia de `perfis_por_dia`,
    mais `n_dias`; `inicio`/`fim` vão do começo do primeiro ao fim do último."""
    if tick is not None and velas_s and tick < tick_grafico(float(velas_s[-1][4])) / TICK_MENOR_ACEITO:
        raise ValueError("faixa pequena demais para esse preço")       # milhões de faixas por dia: estoura a memória
    r = perfis_por_dia(velas_s, agora_s, dias=len(velas_s), tick=tick)
    escolhidos = [d for d in r["dias"] if de_s <= d["inicio"] <= ate_s]
    if not escolhidos:
        raise ValueError("nenhum dia nesse intervalo")
    tick = r["tick"]
    c = juntar(escolhidos, tick)
    fim_ms = escolhidos[-1]["fim"] * 1000
    blocos = blocos_30m([[int(v[0]) * 1000, *v[1:6]] for v in velas_s])
    niveis = {k: c[k] for k in ("poc", "vah", "val")}
    return {
        "tick": tick,
        "n_dias": len(escolhidos),
        "inicio": escolhidos[0]["inicio"],
        "fim": escolhidos[-1]["fim"],
        "aberto": escolhidos[-1]["aberto"],
        "base_i": c["base_i"],
        "contagens": c["contagens"],
        **niveis,
        "maxima": max(d["maxima"] for d in escolhidos),
        "minima": min(d["minima"] for d in escolhidos),
        "toques": {k: _primeiro_toque(v, blocos, fim_ms) for k, v in niveis.items()},
    }
