# core/alavancagem.py
"""
Alavancagem e distância até a liquidação.

Alavancagem não muda o tamanho da posição neste robô: o tamanho vem do risco por trade e da distância do stop
(`BotExecutor.calcular_tamanho_ordem`). O que a alavancagem muda é QUANTO O PREÇO PODE ANDAR CONTRA antes da
exchange liquidar a posição. Esse é o risco real de 50x e 100x, e é o que este módulo calcula.

Em margem ISOLADA, a margem da posição é `notional / alavancagem`, então a liquidação acontece quando a perda
consome essa margem menos a margem de manutenção:

    distância até a liquidação ≈ 1/alavancagem − margem_de_manutenção

    10x  -> ~9,5%      20x -> ~4,5%      30x -> ~2,8%
    50x  -> ~1,5%     100x -> ~0,5%

Em margem CRUZADA a banca inteira sustenta a posição, então a distância depende de quanto da banca a posição usa:

    distância ≈ banca/notional − margem_de_manutenção

REGRA DO ROBÔ: o stop tem que caber dentro da distância de liquidação com folga. Se não couber, a posição seria
liquidada ANTES do stop, e a perda deixaria de ser o risco por trade para virar a margem inteira. Nesse caso a
entrada é recusada e o log diz qual é a alavancagem máxima segura para aquele stop.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

# opções oferecidas no painel
ALAVANCAGENS: Sequence[int] = (1, 2, 3, 5, 10, 20, 30, 50, 100)

# margem de manutenção do primeiro tier da Bybit em BTCUSDT (0,5%). Pares menores exigem mais.
MMR_PADRAO = 0.005

# o stop precisa caber em 80% da distância até a liquidação: sobra para taxas, funding e slippage do gatilho
FOLGA_PADRAO = 0.80


def normalizar(valor, maximo_exchange: Optional[float] = None) -> int:
    """Encaixa o valor pedido na opção válida mais próxima para baixo, respeitando o teto da exchange."""
    try:
        v = int(float(valor))
    except (TypeError, ValueError):
        v = 1
    v = max(v, 1)
    if maximo_exchange:
        v = min(v, int(maximo_exchange))
    permitidas = [a for a in ALAVANCAGENS if a <= v] or [1]
    return permitidas[-1]


def distancia_liquidacao(alavancagem: float, mmr: float = MMR_PADRAO, margin_mode: str = "isolated",
                         banca: Optional[float] = None, notional: Optional[float] = None) -> float:
    """Fração do preço que o mercado pode andar contra antes da liquidação. 1x isolado ≈ 99,5%."""
    alav = max(float(alavancagem or 1), 1.0)
    if (margin_mode or "isolated").lower() in ("cross", "cruzada") and banca and notional and notional > 0:
        return max(banca / notional - mmr, 0.0)
    return max(1.0 / alav - mmr, 0.0)


def alavancagem_maxima(distancia_sl: float, mmr: float = MMR_PADRAO, folga: float = FOLGA_PADRAO) -> int:
    """Maior alavancagem da lista em que um stop a `distancia_sl` (fração do preço) ainda cabe antes da liquidação."""
    if distancia_sl is None or distancia_sl <= 0:
        return 1
    seguras = [a for a in ALAVANCAGENS if distancia_sl <= distancia_liquidacao(a, mmr) * folga]
    return seguras[-1] if seguras else 1


def validar_stop(preco_entrada: float, sl: float, alavancagem: float, margin_mode: str = "isolated",
                 mmr: float = MMR_PADRAO, folga: float = FOLGA_PADRAO, banca: Optional[float] = None,
                 quantidade: Optional[float] = None) -> Dict:
    """
    O stop cabe antes da liquidação?

    Devolve {ok, distancia_sl, distancia_liquidacao, preco_liquidacao, alavancagem_maxima, motivo}.
    Distâncias são frações do preço de entrada.
    """
    if not preco_entrada or sl is None or preco_entrada <= 0:
        return {"ok": True, "motivo": "sem stop para validar", "distancia_sl": None,
                "distancia_liquidacao": None, "preco_liquidacao": None, "alavancagem_maxima": None}
    dist_sl = abs(preco_entrada - sl) / preco_entrada
    notional = (quantidade or 0) * preco_entrada or None
    dist_liq = distancia_liquidacao(alavancagem, mmr, margin_mode, banca, notional)
    limite = dist_liq * folga
    comprado = sl < preco_entrada
    preco_liq = preco_entrada * (1 - dist_liq) if comprado else preco_entrada * (1 + dist_liq)
    alav_max = alavancagem_maxima(dist_sl, mmr, folga)
    ok = dist_sl <= limite
    if ok:
        motivo = (f"stop a {dist_sl:.2%} cabe antes da liquidação a {dist_liq:.2%} "
                  f"({alavancagem:g}x, {margin_mode})")
    else:
        motivo = (f"stop a {dist_sl:.2%} fica ALÉM da liquidação a {dist_liq:.2%} com {alavancagem:g}x "
                  f"({margin_mode}): a posição seria liquidada antes do stop. "
                  f"Alavancagem máxima segura para este stop: {alav_max}x")
    return {"ok": ok, "motivo": motivo, "distancia_sl": round(dist_sl, 5),
            "distancia_liquidacao": round(dist_liq, 5), "preco_liquidacao": round(preco_liq, 2),
            "alavancagem_maxima": alav_max, "limite_com_folga": round(limite, 5)}


def tabela(mmr: float = MMR_PADRAO, folga: float = FOLGA_PADRAO) -> list:
    """Para o painel: cada opção com a distância de liquidação e o stop máximo que ainda cabe."""
    linhas = []
    for a in ALAVANCAGENS:
        d = distancia_liquidacao(a, mmr)
        linhas.append({"alavancagem": a, "distancia_liquidacao_pct": round(d * 100, 2),
                       "stop_maximo_pct": round(d * folga * 100, 2)})
    return linhas
