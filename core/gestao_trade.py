# core/gestao_trade.py
"""
GESTÃO DE TRADE DO USUÁRIO, em forma testável:

1. ENTRADA FRACIONADA — nunca de uma vez. `n_entradas` fatias iguais: a primeira no sinal (a mercado), as outras
   como ordens limitadas escalonadas entre o preço do sinal e o stop (a `espacamento` x risco, 2x, 3x...),
   formando um preço médio melhor quando o preço recua antes de andar.
2. TIRAR O RISCO — quando o preço anda a favor a distância entre o preço MÉDIO e o stop (1 R do que executou),
   realiza `fracao_realizar` (50%) do executado e cancela as fatias que não executaram. O stop continua onde
   estava: se o resto for stopado, o trade fica 0 a 0. "Stop de 50 e alvo de 300: andou 50, realizo o valor do
   stop e não perco mais."
3. O resto vai para o alvo ou sai por tempo.

O tamanho total é calculado para que o PIOR caso (todas as fatias executadas e stop) perca exatamente 1 R — o
mesmo risco da entrada única. Assim a comparação com o teste de entrada única é justa.

Ordem dentro de um candle (pior caso, porque o candle não diz a ordem dos preços): primeiro o stop; depois
realização e alvo com o preço médio de ANTES do candle; por último as fatias novas que o candle executou.
"""
from __future__ import annotations

from typing import Dict, Sequence

from core.executor_real import TAXA_MAKER, TAXA_TAKER

SLIPPAGE = 0.0002


def trade_gestao(lado: int, i0: int, preco: float, risco: float, close: Sequence[float], high: Sequence[float],
                 low: Sequence[float], horizonte: int = 24, mult_alvo: float = 3.0, n_entradas: int = 5,
                 espacamento: float = 0.2, fracao_realizar: float = 0.5, folga_execucao: float = 0.0) -> Dict:
    """
    Um trade com a gestão do usuário. Resultado em R (1 R = perda máxima planejada).
    `folga_execucao`: quanto o preço precisa ATRAVESSAR o nível para a ordem limitada contar como executada
    (encostar não garante execução: há fila no livro). 0 = encostou, executou.
    """
    s = lado
    stop = preco - s * risco
    alvo = preco + s * mult_alvo * risco
    niveis = [preco - s * k * espacamento * risco for k in range(n_entradas)]
    # tamanho: se TODAS executarem e o stop bater, a perda é 1 (R)
    medio_todas = sum(niveis) / n_entradas
    q_total = 1.0 / abs(medio_todas - stop)
    q = q_total / n_entradas
    exec_q = [q]                                   # a 1ª fatia, a mercado no sinal
    exec_p = [preco]
    custo = preco * q * (TAXA_TAKER + SLIPPAGE)
    pendentes = list(range(1, n_entradas))
    realizado = 0.0
    parcial_feita = False
    qtd = q
    fim = min(i0 + horizonte, len(close) - 1)
    motivo = "tempo"
    for i in range(i0 + 1, fim + 1):
        medio = sum(p * x for p, x in zip(exec_p, exec_q)) / sum(exec_q)
        # 1) stop, antes de tudo
        if (low[i] <= stop) if s == 1 else (high[i] >= stop):
            saida = stop * (1 - s * SLIPPAGE)
            realizado += (saida - medio) * qtd * s
            custo += saida * qtd * TAXA_TAKER
            motivo = "stop" if not parcial_feita else "zero_a_zero"
            return _fim(realizado, custo, motivo, i, exec_q, n_entradas)
        # 2) tirar o risco: andou a distância média->stop a favor
        gatilho = medio + s * abs(medio - stop)
        if not parcial_feita and ((high[i] >= gatilho * (1 + folga_execucao)) if s == 1 else (low[i] <= gatilho * (1 - folga_execucao))):
            q_real = qtd * fracao_realizar
            realizado += (gatilho - medio) * q_real * s
            custo += gatilho * q_real * TAXA_MAKER
            qtd -= q_real
            parcial_feita = True
            pendentes = []                          # o resto das entradas é cancelado
        # 3) alvo
        if (high[i] >= alvo * (1 + folga_execucao)) if s == 1 else (low[i] <= alvo * (1 - folga_execucao)):
            realizado += (alvo - medio) * qtd * s
            custo += alvo * qtd * TAXA_MAKER
            return _fim(realizado, custo, "alvo", i, exec_q, n_entradas)
        # 4) fatias que este candle executou
        if pendentes:
            for k in list(pendentes):
                nivel = niveis[k]
                if (low[i] <= nivel * (1 - folga_execucao)) if s == 1 else (high[i] >= nivel * (1 + folga_execucao)):
                    exec_q.append(q)
                    exec_p.append(nivel)
                    qtd += q
                    custo += nivel * q * TAXA_MAKER
                    pendentes.remove(k)
    medio = sum(p * x for p, x in zip(exec_p, exec_q)) / sum(exec_q)
    saida = close[fim]
    realizado += (saida - medio) * qtd * s
    custo += saida * qtd * TAXA_TAKER
    return _fim(realizado, custo, motivo, fim, exec_q, n_entradas)


def _fim(bruto: float, custo: float, motivo: str, i_saida: int, exec_q, n_entradas: int) -> Dict:
    return {"bruto_r": bruto, "custo_r": custo, "liquido_r": bruto - custo, "motivo": motivo, "i_saida": i_saida,
            "fatias": len(exec_q), "de": n_entradas}
