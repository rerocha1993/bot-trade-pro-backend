# conselho/velas_fluxo.py
"""
Velas que não são de tempo: cada vela fecha quando o FLUXO soma um valor, não quando o relógio anda.

    delta   a vela fecha quando o saldo da agressão (compra a mercado − venda a mercado, em US$) chega a ±limiar
            desde a abertura dela. É o gráfico que o Shaka usa no Exocharts (live 4Z91SpHDIAk, 05/11/2026, 1:08:28):
            "só vai abrir outra vela se ele conseguir ficar positivo e meter 10 milhões de delta positivo".
            Mercado parado = uma vela leva horas; agressão forte = várias velas em minutos.
    volume  a vela fecha quando o volume negociado (compra + venda, em US$) chega ao limiar.

Os negócios vêm dos minutos gravados pelo coletor (conselho/coletor_negocios.py), não negócio a negócio: a vela fecha
no fim do minuto em que o limiar foi alcançado, e um minuto com muito mais que o limiar vira UMA vela só (não é
repartido). O Exocharts fecha no negócio exato; aqui a diferença é de no máximo um minuto por vela.

As velas são contadas sempre a partir do mesmo começo (``origem``), para a mesma vela ter o mesmo início em todo
pedido (carregar o histórico para trás e a atualização ao vivo não deslocam as velas).

Leitura para o olho: nada disso foi medido contra sorteio.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from conselho import livro_historico as lh
from conselho.coletor_negocios import PASTA_NEGOCIOS

FONTES_FLUXO = ("binance", "bybit", "coinbase")       # o inverse da Bybit só existe desde 04/11: fica fora
# preço das velas: a primeira desta ordem que estiver na lista (Binance à vista = o par padrão do Gráfico)
ORDEM_PRECO = ("binance", "bybit", "coinbase")
# começo mais antigo das contas (a Bybit tem arquivo desde 2020 na máquina local; o servidor grava desde 13/10/2026)
ORIGEM_MINIMA_S = int(datetime(2026, 10, 13, tzinfo=timezone.utc).timestamp())
DIA_S = 86400

# minuto somado: (ts, abertura, máxima, mínima, fechamento, compra_usd, venda_usd, volume_btc)
Minuto = Tuple[int, float, float, float, float, float, float, float]


def origem(exchanges: Sequence[str], raiz: str = PASTA_NEGOCIOS) -> Optional[int]:
    """00:00 UTC do primeiro dia em que TODAS as fontes têm arquivo (não antes de ``ORIGEM_MINIMA_S``)."""
    primeiros = []
    for ex in exchanges:
        pasta = os.path.join(raiz, ex)
        try:
            dias = sorted(n[:10] for n in os.listdir(pasta) if n.endswith(".jsonl.gz"))
        except FileNotFoundError:
            return None
        if not dias:
            return None
        primeiros.append(int(datetime.strptime(dias[0], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()))
    return max([ORIGEM_MINIMA_S, *primeiros]) if primeiros else None


def minutos_somados(exchanges: Sequence[str], inicio_s: int, fim_s: int, raiz: str = PASTA_NEGOCIOS,
                    preco_de: Optional[str] = None) -> List[Minuto]:
    """
    Um registro por minuto com a agressão de todas as fontes somada em US$ (BTC × fechamento do minuto daquela
    fonte) e o OHLC de ``preco_de`` (a corretora do gráfico; sem ela, a ordem de ``ORDEM_PRECO``); se ela faltou no
    minuto, a próxima que tiver.
    """
    por_ts: Dict[int, Dict[str, Dict]] = {}
    for ex in exchanges:
        for r in lh.carregar_periodo(ex, inicio_s, fim_s, raiz):
            por_ts.setdefault(int(r["ts"]), {})[ex] = r
    ordem = [e for e in ((preco_de,) if preco_de in exchanges else ()) + ORDEM_PRECO if e in exchanges]
    saida: List[Minuto] = []
    for ts in sorted(por_ts):
        regs = por_ts[ts]
        ref = next((regs[e] for e in ordem if e in regs), None)
        if ref is None:
            continue
        compra = venda = vol = 0.0
        for r in regs.values():
            p = float(r.get("fechamento") or 0.0)
            c, v = float(r.get("compra") or 0.0), float(r.get("venda") or 0.0)
            compra += c * p
            venda += v * p
            vol += c + v
        saida.append((ts, float(ref["abertura"]), float(ref["maxima"]), float(ref["minima"]), float(ref["fechamento"]),
                      compra, venda, vol))
    return saida


def montar(minutos: Sequence[Minuto], modo: str, limiar_usd: float,
           atual: Optional[Dict] = None) -> Tuple[List[Dict], Optional[Dict]]:
    """
    Junta os minutos em velas de ``limiar_usd`` de delta (modo "delta") ou de volume (modo "volume").
    Devolve (velas fechadas, vela aberta ou None). ``atual`` continua uma vela aberta de uma chamada anterior.
    """
    if modo not in ("delta", "volume") or limiar_usd <= 0:
        raise ValueError("modo: delta ou volume; limiar > 0")
    velas: List[Dict] = []
    atual = dict(atual) if atual else None
    for ts, o, h, l, c, compra, venda, vol in minutos:
        if atual is None:
            atual = {"t": ts, "o": o, "h": h, "l": l, "c": c, "compra": 0.0, "venda": 0.0, "v": 0.0, "fim": ts}
        atual["h"] = max(atual["h"], h)
        atual["l"] = min(atual["l"], l)
        atual["c"] = c
        atual["compra"] += compra
        atual["venda"] += venda
        atual["v"] += vol
        atual["fim"] = ts
        soma = atual["compra"] - atual["venda"] if modo == "delta" else atual["compra"] + atual["venda"]
        if abs(soma) >= limiar_usd:
            velas.append(atual)
            atual = None
    return velas, atual


# (fontes, modo, limiar) -> {"dia": 00:00 do 1º dia ainda não somado, "velas": fechadas, "aberta": vela em curso}
_guardado: Dict[Tuple, Dict] = {}
_trava = threading.Lock()
FOLGA_S = 600          # um dia só é dado por fechado 10 min depois de acabar (o coletor grava com atraso)
VALE_S = 10            # o resultado vale 10 s: o Gráfico pergunta a cada poucos segundos e o coletor grava por minuto
_ultimo: Dict[Tuple, Tuple[float, List[Dict]]] = {}


def velas(exchanges: Sequence[str], modo: str, limiar_usd: float, agora_s: Optional[float] = None,
          raiz: str = PASTA_NEGOCIOS, preco_de: Optional[str] = None) -> List[Dict]:
    """
    Todas as velas desde a ``origem``, a última aberta (``aberta`` = True). Os dias que já acabaram são somados uma
    vez e guardados (só as velas, não os minutos); o dia de hoje é refeito a cada pedido a partir da vela que
    estava aberta no fim de ontem.
    """
    agora = time.time() if agora_s is None else agora_s
    exs = tuple(e for e in FONTES_FLUXO if e in exchanges)
    ini = origem(exs, raiz)
    if not exs or ini is None:
        return []
    preco_de = preco_de if preco_de in exs else None
    k = (exs, modo, float(limiar_usd), raiz, preco_de)
    with _trava:
        pronto = _ultimo.get(k)
        if pronto is not None and 0 <= agora - pronto[0] < VALE_S:
            return pronto[1]
        g = _guardado.setdefault(k, {"dia": ini, "velas": [], "aberta": None})
        while g["dia"] + DIA_S - 1 <= agora - FOLGA_S:
            fechadas, g["aberta"] = montar(minutos_somados(exs, g["dia"], g["dia"] + DIA_S - 1, raiz, preco_de), modo, limiar_usd, g["aberta"])
            g["velas"].extend(fechadas)
            g["dia"] += DIA_S
        hoje, aberta = montar(minutos_somados(exs, g["dia"], int(agora), raiz, preco_de), modo, limiar_usd, g["aberta"])
        saida = g["velas"] + hoje
        if aberta is not None:
            saida.append({**aberta, "aberta": True})
        _ultimo[k] = (agora, saida)
    return saida


def linha_api(v: Dict) -> List[float]:
    """[início_s, o, h, l, c, volume_btc, delta_usd, volume_usd, fim_s, aberta] para o Gráfico."""
    return [v["t"], v["o"], v["h"], v["l"], v["c"], round(v["v"], 4), round(v["compra"] - v["venda"]),
            round(v["compra"] + v["venda"]), v["fim"], 1 if v.get("aberta") else 0]
