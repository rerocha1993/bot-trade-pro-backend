# conselho/coletor_negocios.py
"""
Coletor de NEGÓCIOS ao vivo (quem agrediu a mercado), para o footprint, a absorção e os presos.

O livro (conselho/coletor_livro.py) mostra as ordens paradas; ele não diz quem comprou ou vendeu a mercado. Este
coletor ouve o websocket público de cada corretora e agrega, por MINUTO:
    compra, venda       BTC agredidos por compradores e por vendedores (o agressor é quem cruzou o spread)
    n, maxima, minima   número de negócios e faixa de preço do minuto
    niveis              footprint: [preço da faixa de US$ 20, compra, venda] para cada faixa negociada

Fontes (sem chave, só leitura):
    bybit     perpétuo linear BTCUSDT   publicTrade   S = lado do agressor
    binance   à vista BTCUSDT           aggTrade      m = o comprador era o maker → o agressor vendeu
              (o perpétuo da Binance, fstream, não responde daqui; a alavancagem vem da Bybit e do open interest)
    coinbase  à vista BTC-USD           matches       side = lado da ordem MAKER → o agressor é o oposto

Grava um registro por minuto e por corretora em dados/negocios/<exchange>/<AAAA-MM-DD>.jsonl.gz (ts em segundos,
início do minuto UTC), no mesmo esquema de arquivo do livro. Um minuto só é gravado quando já passou
``ATRASO_S`` do fim dele, para negócios atrasados ainda entrarem.
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from conselho.coletor_livro import RAIZ_PROJETO, gravar_snapshot, logger


PASTA_NEGOCIOS = os.path.join(RAIZ_PROJETO, "dados", "negocios")
PASSO_USD = 20.0           # faixa de preço do footprint (a mesma do estudo dos presos)
ATRASO_S = 5               # espera depois do fim do minuto antes de gravar
PING_S = 20

# (url, mensagem de inscrição ou None)
FONTES = {
    "bybit": ("wss://stream.bybit.com/v5/public/linear", {"op": "subscribe", "args": ["publicTrade.BTCUSDT"]}),
    # o websocket de futuros (fstream.binance.com) não responde daqui (testado em 20/10/2026): usa o à vista
    "binance": ("wss://stream.binance.com:9443/ws/btcusdt@aggTrade", None),
    "coinbase": ("wss://ws-feed.exchange.coinbase.com",
                 {"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["matches"]}),
}

Negocio = Tuple[float, float, float, bool]     # (ts em segundos, preço, BTC, agressor comprou?)


# ----------------------------------------------------------------- leitura das mensagens
def ler_bybit(msg: Dict) -> List[Negocio]:
    if not str(msg.get("topic", "")).startswith("publicTrade"):
        return []
    return [(int(d["T"]) / 1000.0, float(d["p"]), float(d["v"]), d.get("S") == "Buy") for d in msg.get("data") or []]


def ler_binance(msg: Dict) -> List[Negocio]:
    if msg.get("e") != "aggTrade":
        return []
    return [(int(msg["T"]) / 1000.0, float(msg["p"]), float(msg["q"]), not bool(msg["m"]))]


def _iso_para_s(texto: str) -> float:
    # "2026-10-20T16:05:01.123456Z"
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).timestamp()


def ler_coinbase(msg: Dict) -> List[Negocio]:
    if msg.get("type") not in ("match", "last_match"):
        return []
    # `side` é o lado da ordem maker: maker vendendo = agressor comprando
    return [(_iso_para_s(msg["time"]), float(msg["price"]), float(msg["size"]), msg.get("side") == "sell")]


LEITORES: Dict[str, Callable[[Dict], List[Negocio]]] = {"bybit": ler_bybit, "binance": ler_binance, "coinbase": ler_coinbase}


# ----------------------------------------------------------------- agregação por minuto
class AgregadorMinuto:
    """Junta negócios por minuto UTC e devolve os minutos fechados como registros prontos para gravar."""

    def __init__(self, exchange: str, passo_usd: float = PASSO_USD):
        self.exchange = exchange
        self.passo = float(passo_usd)
        self.minutos: Dict[int, Dict] = {}
        self._lock = threading.Lock()

    def adicionar(self, negocios: Iterable[Negocio]) -> None:
        with self._lock:
            for ts, preco, qtd, comprou in negocios:
                if qtd <= 0 or preco <= 0:
                    continue
                m = int(ts // 60) * 60
                a = self.minutos.get(m)
                if a is None:
                    a = self.minutos[m] = {"compra": 0.0, "venda": 0.0, "n": 0, "maxima": preco, "minima": preco,
                                           "abertura": preco, "ts_ab": ts, "fechamento": preco, "ts_fe": ts, "niveis": {}}
                lado = "compra" if comprou else "venda"
                a[lado] += qtd
                a["n"] += 1
                a["maxima"] = max(a["maxima"], preco)
                a["minima"] = min(a["minima"], preco)
                if ts < a["ts_ab"]:
                    a["abertura"], a["ts_ab"] = preco, ts
                if ts >= a["ts_fe"]:
                    a["fechamento"], a["ts_fe"] = preco, ts
                faixa = math.floor(preco / self.passo) * self.passo
                nv = a["niveis"].setdefault(faixa, [0.0, 0.0])
                nv[0 if comprou else 1] += qtd

    def fechados(self, agora_s: float, atraso_s: float = ATRASO_S) -> List[Dict]:
        """Retira e devolve os minutos cujo fim já passou há ``atraso_s`` segundos."""
        with self._lock:
            prontos = sorted(m for m in self.minutos if m + 60 + atraso_s <= agora_s)
            saida = []
            for m in prontos:
                a = self.minutos.pop(m)
                saida.append({
                    "ts": m, "exchange": self.exchange, "passo_usd": self.passo,
                    "compra": round(a["compra"], 6), "venda": round(a["venda"], 6),
                    "delta": round(a["compra"] - a["venda"], 6), "n": a["n"],
                    "abertura": a["abertura"], "maxima": a["maxima"], "minima": a["minima"], "fechamento": a["fechamento"],
                    "niveis": [[f, round(b, 6), round(s, 6)] for f, (b, s) in sorted(a["niveis"].items())],
                })
            return saida


# ----------------------------------------------------------------- conexões
class ColetorNegocios:
    """Uma thread por corretora (websocket com reconexão) e uma que grava os minutos fechados."""

    def __init__(self, exchanges: Iterable[str] = tuple(FONTES), raiz: str = PASTA_NEGOCIOS,
                 parar: Optional[threading.Event] = None):
        self.exchanges = [e for e in exchanges if e in FONTES]
        self.raiz = raiz
        self.parar = parar or threading.Event()
        self.agregadores = {e: AgregadorMinuto(e) for e in self.exchanges}
        self.recebidos = {e: 0 for e in self.exchanges}
        self.threads: List[threading.Thread] = []

    def _ouvir(self, exchange: str) -> None:
        import websocket  # websocket-client

        url, inscricao = FONTES[exchange]
        ler = LEITORES[exchange]
        espera = 1.0
        while not self.parar.is_set():
            ws = None
            try:
                ws = websocket.create_connection(url, timeout=PING_S + 10)
                if inscricao:
                    ws.send(json.dumps(inscricao))
                logger.info("negócios %s: conectado", exchange)
                espera = 1.0
                ultimo_ping = time.time()
                while not self.parar.is_set():
                    if exchange == "bybit" and time.time() - ultimo_ping > PING_S:
                        ws.send(json.dumps({"op": "ping"}))
                        ultimo_ping = time.time()
                    try:
                        bruto = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not bruto:
                        continue
                    negocios = ler(json.loads(bruto))
                    if negocios:
                        self.agregadores[exchange].adicionar(negocios)
                        self.recebidos[exchange] += len(negocios)
            except Exception as e:
                logger.warning("negócios %s: conexão caiu (%s: %s); reconecto em %.0f s",
                               exchange, type(e).__name__, str(e)[:120], espera)
                self.parar.wait(espera)
                espera = min(60.0, espera * 2)
            finally:
                try:
                    if ws is not None:
                        ws.close()
                except Exception:
                    pass

    def _gravar(self) -> None:
        while not self.parar.wait(1.0):
            self.descarregar(time.time())
        self.descarregar(time.time() + 3600)      # ao parar, grava o que sobrou

    def descarregar(self, agora_s: float) -> int:
        n = 0
        for ex, ag in self.agregadores.items():
            for registro in ag.fechados(agora_s):
                try:
                    gravar_snapshot(registro, self.raiz)
                    n += 1
                except Exception as e:
                    logger.error("negócios %s: falha ao gravar o minuto %s: %s", ex, registro["ts"], e)
        return n

    def iniciar(self) -> None:
        for ex in self.exchanges:
            t = threading.Thread(target=self._ouvir, args=(ex,), name=f"negocios-{ex}", daemon=True)
            t.start()
            self.threads.append(t)
        g = threading.Thread(target=self._gravar, name="negocios-gravar", daemon=True)
        g.start()
        self.threads.append(g)
        logger.info("coletor de negócios iniciado: %s -> %s", ",".join(self.exchanges), self.raiz)
