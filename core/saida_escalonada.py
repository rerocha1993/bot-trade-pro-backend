# core/saida_escalonada.py
"""
SAÍDA ESCALONADA: realizar em pedaços conforme o preço avança rumo ao alvo.

A régua NÃO é o preço absoluto, é quanto do caminho entre a entrada e o alvo já foi percorrido. Assim o mesmo
plano vale para qualquer par, timeframe e tamanho de alvo:

    avanço = (preço - entrada) / (alvo - entrada)      numa compra
    avanço = (entrada - preço) / (entrada - alvo)      numa venda

Plano padrão: realiza 30% da mão aos 50% do caminho, mais 30% aos 75%, mais 25% aos 90%, e deixa o resto correr
até o alvo (ou até o trailing tirar). São três realizações mais o restante, ou seja, quatro saídas.

O NÚMERO DE SAÍDAS SE ADAPTA AO TAMANHO DA MÃO. Cada fatia precisa respeitar a quantidade mínima da corretora, e
o que sobra para o alvo também. Numa posição pequena o plano encolhe sozinho para duas saídas, ou para nenhuma,
em vez de gerar ordens que a corretora recusaria.

Nada aqui envia ordem: devolve o que deve ser realizado e quem chama executa.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

# (avanço até o alvo, fração da posição inicial a realizar)
PLANO_PADRAO: Tuple[Tuple[float, float], ...] = ((0.50, 0.30), (0.75, 0.30), (0.90, 0.25))


def analisar_plano(texto: Optional[str]) -> Optional[Tuple[Tuple[float, float], ...]]:
    """
    '50/30, 75/30, 90/25' -> ((0.5, 0.3), (0.75, 0.3), (0.9, 0.25)). None quando o texto não é um plano válido.

    Quem escreve o plano (o painel) usa esta versão, para recusar o texto e mostrar o erro. Quem só precisa
    operar usa `ler_plano`, que cai no padrão em vez de parar o robô por causa de uma configuração torta.
    """
    if not texto or not str(texto).strip():
        return None
    fatias: List[Tuple[float, float]] = []
    for parte in str(texto).replace(";", ",").split(","):
        parte = parte.strip()
        if not parte:
            continue
        try:
            a, f = parte.split("/")
            avanco, fracao = float(a.strip()) / 100.0, float(f.strip()) / 100.0
        except (ValueError, AttributeError):
            return None
        if not (0 < avanco <= 1.0) or not (0 < fracao < 1.0):
            return None
        fatias.append((avanco, fracao))
    if not fatias or sum(f for _, f in fatias) >= 1.0:
        return None                  # tem que sobrar posição para o alvo
    if len({a for a, _ in fatias}) != len(fatias):
        return None                  # o mesmo avanço duas vezes só realizaria uma
    return tuple(sorted(fatias))


def ler_plano(texto: Optional[str]) -> Tuple[Tuple[float, float], ...]:
    """Igual a `analisar_plano`, mas texto inválido cai no padrão em vez de devolver None."""
    return analisar_plano(texto) or PLANO_PADRAO


def escrever_plano(plano: Sequence[Tuple[float, float]]) -> str:
    return ", ".join(f"{a * 100:g}/{f * 100:g}" for a, f in plano)


def avanco(entrada: float, alvo: Optional[float], preco: float, direcao: str) -> Optional[float]:
    """Quanto do caminho até o alvo já foi percorrido (0..1+). None quando não dá para medir."""
    if not entrada or not alvo or entrada == alvo:
        return None
    if direcao == "buy":
        if alvo <= entrada:
            return None
        return (preco - entrada) / (alvo - entrada)
    if alvo >= entrada:
        return None
    return (entrada - preco) / (entrada - alvo)


def _arredondar(qty: float, step: float) -> float:
    if not step or step <= 0:
        return qty
    return int(qty / step) * step


def montar_fatias(quantidade_inicial: float, plano: Sequence[Tuple[float, float]] = PLANO_PADRAO,
                  min_qty: float = 0.0, step: float = 0.0) -> List[Dict]:
    """
    Traduz o plano em fatias executáveis para ESTA posição, respeitando o mínimo da corretora.

    Devolve [{'avanco', 'fracao', 'quantidade'}]. Lista vazia = a mão não comporta escalonar; sai tudo no alvo.
    O que sobra para o alvo também precisa alcançar o mínimo, senão a última fatia é descartada.
    """
    q0 = float(quantidade_inicial or 0)
    if q0 <= 0:
        return []
    candidatas = sorted(plano)
    while candidatas:
        fatias, soma = [], 0.0
        for av, fr in candidatas:
            qty = _arredondar(q0 * fr, step)
            if qty <= 0 or (min_qty and qty < min_qty):
                fatias = []
                break
            fatias.append({"avanco": round(av, 4), "fracao": round(fr, 4), "quantidade": qty})
            soma += qty
        resto = q0 - soma
        if fatias and (not min_qty or resto >= min_qty):
            return fatias
        candidatas = candidatas[:-1]     # a mão não comporta tantas saídas: tenta com uma a menos
    return []


def pendentes(fatias: Sequence[Dict], feitas: Sequence[float], avanco_atual: Optional[float]) -> List[Dict]:
    """Fatias que o avanço atual já disparou e que ainda não foram realizadas."""
    if avanco_atual is None:
        return []
    ja = {round(float(a), 4) for a in (feitas or [])}
    return [f for f in fatias if f["avanco"] not in ja and avanco_atual >= f["avanco"]]


def ler_feitas(texto: Optional[str]) -> List[float]:
    if not texto:
        return []
    out = []
    for p in str(texto).split(","):
        p = p.strip()
        if p:
            try:
                out.append(round(float(p), 4))
            except ValueError:
                continue
    return out


def escrever_feitas(feitas: Sequence[float]) -> str:
    return ",".join(f"{float(a):g}" for a in feitas)
