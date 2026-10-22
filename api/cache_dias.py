# api/cache_dias.py
"""
Cache por dia UTC para as leituras pesadas do painel (mapa de calor, livro inteiro, absorção).

O gráfico pode mostrar até 7 dias; recalcular tudo a cada minuto levaria mais de um minuto. Um dia que já acabou
não muda mais, então ele é calculado uma vez e guardado na memória da API; só o dia de hoje é recalculado em cada
pedido. Cada dia é calculado INTEIRO (00:00 a 24:00 UTC) e o resultado é cortado em ``inicio`` depois, para o
começo do gráfico (que anda de 5 em 5 min) não invalidar o cache.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Callable, Dict, Hashable, List, Tuple

DIA_S = 86400
FOLGA_S = 600            # um dia só entra no cache 10 min depois de acabar (o coletor grava com atraso)
HOJE_S = 50              # o dia de hoje vale por 50 s: o painel pede de novo a cada 60 s
MAX_ITENS = 64

_cache: "OrderedDict[Hashable, Dict]" = OrderedDict()
_hoje: Dict[Hashable, Tuple[float, Dict]] = {}
_trava = threading.Lock()
_travas_chave: Dict[Hashable, threading.Lock] = {}


def _trava_da(k: Hashable) -> threading.Lock:
    """Uma trava por pedaço: dois pedidos iguais ao mesmo tempo fazem UM cálculo, o segundo espera e reaproveita."""
    with _trava:
        return _travas_chave.setdefault(k, threading.Lock())


def dias(inicio_s: int, fim_s: int) -> List[Tuple[int, int]]:
    """Os dias UTC que cobrem [inicio_s, fim_s], como (00:00 do dia, fim do trecho); o último termina em fim_s."""
    saida = []
    d = inicio_s // DIA_S * DIA_S
    while d <= fim_s:
        saida.append((d, min(d + DIA_S - 1, fim_s)))
        d += DIA_S
    return saida


def por_dia(chave: Hashable, inicio_s: int, fim_s: int, calcular: Callable[[int, int], Dict],
            agora_s: float | None = None) -> List[Dict]:
    """
    Resultado de ``calcular(a, b)`` para cada dia de [inicio_s, fim_s], na ordem. Dias que já acabaram vêm do cache
    (guardados com ``chave``); o dia de hoje é recalculado se o último cálculo tiver mais de ``HOJE_S`` segundos.
    Quem chama junta os pedaços e corta em inicio_s.
    """
    agora = time.time() if agora_s is None else agora_s
    pedacos = []
    for a, b in dias(inicio_s, fim_s):
        fechado = a + DIA_S - 1 <= agora - FOLGA_S
        k = (chave, a)
        with _trava_da(k):
            if fechado:
                with _trava:
                    r = _cache.get(k)
                    if r is not None:
                        _cache.move_to_end(k)
                if r is None:
                    r = calcular(a, a + DIA_S - 1)
                    with _trava:
                        _cache[k] = r
                        while len(_cache) > MAX_ITENS:
                            _cache.popitem(last=False)
            else:
                guardado = _hoje.get(k)
                if guardado is not None and agora - guardado[0] < HOJE_S:
                    r = guardado[1]
                else:
                    r = calcular(a, b)
                    _hoje[k] = (agora, r)
        pedacos.append(r)
    return pedacos


def limpar() -> None:
    with _trava:
        _cache.clear()
        _hoje.clear()
