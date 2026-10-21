# conselho/coletor_liquidacoes.py
"""
Coletor de LIQUIDAÇÕES ao vivo (o painel "Liquidations (aggregation)" do TRDR, perpétuos).

Liquidação é a corretora fechando a mercado a posição alavancada que perdeu a margem: long liquidado vira venda a
mercado (empurra para baixo), short liquidado vira compra a mercado (empurra para cima). Agrega, por MINUTO e por
corretora:
    long_btc, short_btc    BTC liquidados de quem estava comprado e de quem estava vendido
    long_usd, short_usd    o mesmo em dólares (BTC × preço de falência)
    n                      número de ordens de liquidação

Fontes (sem chave, só leitura; testadas em 21/10/2026):
    bybit   allLiquidation.BTCUSDT (perpétuo linear)   S = "Buy" → long liquidado, "Sell" → short liquidado
    okx     liquidation-orders SWAP                     BTC-USDT-SWAP (0,01 BTC por contrato) e BTC-USD-SWAP
                                                        (US$ 100 por contrato); side "sell" → long liquidado
    (a Binance futuros, fstream, não responde daqui; as corretoras não guardam histórico público longo de
    liquidações, então o painel começa no dia em que este coletor foi ligado)

Grava em dados/liquidacoes/<exchange>/<AAAA-MM-DD>.jsonl.gz, no mesmo esquema do livro e dos negócios.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from conselho.coletor_livro import RAIZ_PROJETO, gravar_snapshot, logger

PASTA_LIQUIDACOES = os.path.join(RAIZ_PROJETO, "dados", "liquidacoes")
ATRASO_S = 5
PING_S = 20

FONTES = {
    "bybit": ("wss://stream.bybit.com/v5/public/linear", {"op": "subscribe", "args": ["allLiquidation.BTCUSDT"]}),
    "okx": ("wss://ws.okx.com:8443/ws/v5/public", {"op": "subscribe", "args": [{"channel": "liquidation-orders", "instType": "SWAP"}]}),
}

Liquidacao = Tuple[float, float, float, bool]     # (ts em segundos, preço, BTC, era long?)

OKX_CONTRATO = {"BTC-USDT-SWAP": ("btc", 0.01), "BTC-USD-SWAP": ("usd", 100.0)}


def ler_bybit(msg: Dict) -> List[Liquidacao]:
    if not str(msg.get("topic", "")).startswith("allLiquidation"):
        return []
    return [(int(d["T"]) / 1000.0, float(d["p"]), float(d["v"]), d.get("S") == "Buy") for d in msg.get("data") or []]


def ler_okx(msg: Dict) -> List[Liquidacao]:
    if (msg.get("arg") or {}).get("channel") != "liquidation-orders":
        return []
    saida: List[Liquidacao] = []
    for item in msg.get("data") or []:
        contrato = OKX_CONTRATO.get(item.get("instId"))
        if contrato is None:
            continue
        unidade, valor = contrato
        for d in item.get("details") or []:
            preco, sz = float(d.get("bkPx") or 0), float(d.get("sz") or 0)
            if preco <= 0 or sz <= 0:
                continue
            btc = sz * valor if unidade == "btc" else sz * valor / preco
            saida.append((int(d["ts"]) / 1000.0, preco, btc, d.get("side") == "sell"))
    return saida


LEITORES: Dict[str, Callable[[Dict], List[Liquidacao]]] = {"bybit": ler_bybit, "okx": ler_okx}


class AgregadorLiquidacoes:
    """Junta liquidações por minuto UTC e devolve os minutos fechados como registros prontos para gravar."""

    def __init__(self, exchange: str):
        self.exchange = exchange
        self.minutos: Dict[int, Dict] = {}
        self._lock = threading.Lock()

    def adicionar(self, liqs: Iterable[Liquidacao]) -> None:
        with self._lock:
            for ts, preco, btc, era_long in liqs:
                if btc <= 0 or preco <= 0:
                    continue
                m = int(ts // 60) * 60
                a = self.minutos.setdefault(m, {"long_btc": 0.0, "short_btc": 0.0, "long_usd": 0.0, "short_usd": 0.0, "n": 0})
                lado = "long" if era_long else "short"
                a[f"{lado}_btc"] += btc
                a[f"{lado}_usd"] += btc * preco
                a["n"] += 1

    def fechados(self, agora_s: float, atraso_s: float = ATRASO_S) -> List[Dict]:
        with self._lock:
            prontos = sorted(m for m in self.minutos if m + 60 + atraso_s <= agora_s)
            return [{"ts": m, "exchange": self.exchange,
                     **{k: (round(v, 6) if isinstance(v, float) else v) for k, v in self.minutos.pop(m).items()}}
                    for m in prontos]


class ColetorLiquidacoes:
    """Uma thread por corretora (websocket com reconexão) e uma que grava os minutos fechados."""

    def __init__(self, exchanges: Iterable[str] = tuple(FONTES), raiz: str = PASTA_LIQUIDACOES,
                 parar: Optional[threading.Event] = None):
        self.exchanges = [e for e in exchanges if e in FONTES]
        self.raiz = raiz
        self.parar = parar or threading.Event()
        self.agregadores = {e: AgregadorLiquidacoes(e) for e in self.exchanges}
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
                ws.send(json.dumps(inscricao))
                logger.info("liquidações %s: conectado", exchange)
                espera = 1.0
                ultimo_ping = time.time()
                while not self.parar.is_set():
                    if time.time() - ultimo_ping > PING_S:
                        ws.send(json.dumps({"op": "ping"}) if exchange == "bybit" else "ping")
                        ultimo_ping = time.time()
                    try:
                        bruto = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not bruto or bruto == "pong":
                        continue
                    liqs = ler(json.loads(bruto))
                    if liqs:
                        self.agregadores[exchange].adicionar(liqs)
            except Exception as e:
                logger.warning("liquidações %s: conexão caiu (%s: %s); reconecto em %.0f s",
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
        self.descarregar(time.time() + 3600)

    def descarregar(self, agora_s: float) -> int:
        n = 0
        for ex, ag in self.agregadores.items():
            for registro in ag.fechados(agora_s):
                try:
                    gravar_snapshot(registro, self.raiz)
                    n += 1
                except Exception as e:
                    logger.error("liquidações %s: falha ao gravar o minuto %s: %s", ex, registro["ts"], e)
        return n

    def iniciar(self) -> None:
        for ex in self.exchanges:
            t = threading.Thread(target=self._ouvir, args=(ex,), name=f"liquidacoes-{ex}", daemon=True)
            t.start()
            self.threads.append(t)
        g = threading.Thread(target=self._gravar, name="liquidacoes-gravar", daemon=True)
        g.start()
        self.threads.append(g)
        logger.info("coletor de liquidações iniciado: %s -> %s", ",".join(self.exchanges), self.raiz)
