"""
Coletor do livro de ordens de BTC (Coinbase spot, Binance spot, Bybit linear).

A cada ciclo busca a profundidade nas três exchanges, agrega cada livro em
faixas de 0,1% do mid (de -5% a +5%, 50 faixas por lado, 100 no total) e grava um registro
por snapshot por exchange em ``dados/livro/<exchange>/<AAAA-MM-DD>.jsonl.gz``
(uma linha JSON por snapshot, arquivo gzip por dia UTC, em modo append).

Só leitura: este módulo nunca envia ordens nem usa credenciais.

Alcance REAL de cada livro (medido em 20/10/2026, BTC ~81k):
- Coinbase level 2: livro inteiro (~20 mil níveis por lado) -> as 50 faixas ficam cheias; é a única
  exchange em que uma parede a 1-5% do mid pode ser vista.
- Binance depth 5000 (máximo público): ~1% de distância por lado -> faixas 0-9 preenchidas, o resto zero.
- Bybit linear orderbook 500 (máximo da API v5): ~0,1% por lado -> só a faixa 0 (e às vezes a 1).
  Serve para liquidez no topo do livro, não para paredes distantes.
Por que não o websocket: o ``<symbol>@depth`` da Binance manda só DIFERENÇAS e precisa ser casado com um
snapshot REST, que continua limitado a 5000 níveis — níveis além disso só apareceriam quando mudassem, nunca
o livro inteiro; e o websocket da Bybit linear vai até 500 níveis, o mesmo do REST. Não há caminho simples
para 25% nessas duas; a Coinbase (level 2 = livro inteiro) é a única fonte das categorias 1–25%.
Falha de uma exchange não derruba as outras; tudo vai para logs/coletor_livro.log.

Formato de cada registro::

    {
      "ts": 1760960000,              # epoch em segundos (UTC)
      "exchange": "binance",
      "simbolo": "BTCUSDT",
      "mid": 108123.45,
      "melhor_bid": 108120.0,
      "melhor_ask": 108126.9,
      "faixa_pct": 0.001,            # largura de cada faixa (0,1% do mid)
      "limite_pct": 0.05,            # alcance por lado (5%)
      "bids": [q0, q1, ..., q49],    # BTC por faixa; q0 = 0 a 0,1% abaixo do mid
      "asks": [q0, q1, ..., q49],    # BTC por faixa; q0 = 0 a 0,1% acima do mid
      "total_bids": 123.4,           # BTC somado nas 50 faixas
      "total_asks": 98.7,
      "fora_bids": 5.0,              # BTC do livro além de -5% (ignorado nas faixas)
      "fora_asks": 3.0,
      "niveis_bids": 1000,           # quantos níveis de preço a exchange devolveu
      "niveis_asks": 1000,
      "latencia_ms": 312,
      # --- campos acrescentados em 20/10/2026 (as "nuvens" do TRDR); registros antigos não os têm ---
      "cat_pct": [0, 0.01, 0.025, 0.05, 0.10, 0.25],   # bordas das categorias de distância do TRDR
      "cat_bids": [b0, b1, b2, b3, b4],  # BTC por categoria, distância medida do MELHOR BID (0-1%, 1-2,5%, 2,5-5%, 5-10%, 10-25%)
      "cat_asks": [a0, a1, a2, a3, a4],  # idem, do melhor ask
      "alcance_bids_pct": 0.0102,        # até que distância (fração) do melhor bid o livro devolvido chega
      "alcance_asks_pct": 0.0099,        # (Binance 5000 ~1%, Bybit 500 ~0,1%, Coinbase o livro inteiro)
      "top_bids": [[preco, qtd], ...],   # os 10 maiores níveis do lado, por quantidade, até 25% do melhor preço
      "top_asks": [[preco, qtd], ...]
    }

As categorias e os top levels seguem o "Order Book Depth Overlay" e o "Order Book Top Levels" do TRDR.
Uma categoria só é confiável quando ``alcance_*_pct`` >= borda superior dela (ver ``categorias_alcancadas``).
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Callable, Dict, List, Optional, Tuple

import requests

Livro = Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]  # (bids, asks)

RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASTA_DADOS = os.path.join(RAIZ_PROJETO, "dados", "livro")
ARQUIVO_LOG = os.path.join(RAIZ_PROJETO, "logs", "coletor_livro.log")

FAIXA_PCT = 0.001       # 0,1% do mid por faixa
LIMITE_PCT = 0.05       # até 5% de distância do mid, por lado
N_FAIXAS = int(round(LIMITE_PCT / FAIXA_PCT))   # 50 por lado

# Categorias de distância do TRDR (Order Book Depth Overlay), medidas do melhor bid/ask, como fração.
CATEGORIAS_PCT = (0.0, 0.01, 0.025, 0.05, 0.10, 0.25)
ROTULOS_CATEGORIAS = ("0–1%", "1–2,5%", "2,5–5%", "5–10%", "10–25%")
N_CATEGORIAS = len(CATEGORIAS_PCT) - 1
N_TOP = 10              # Order Book Top Levels: os 10 maiores níveis de cada lado
LIMITE_TOP_PCT = 0.25   # só níveis até 25% do melhor preço entram no top (fora disso é lixo de livro vazio)

INTERVALO_PADRAO_S = 30
TIMEOUT_HTTP_S = 10.0
CABECALHOS = {"User-Agent": "bot-trade-pro/1.0 (coletor-livro)"}

EXCHANGES = ("coinbase", "binance", "bybit")
SIMBOLOS = {"coinbase": "BTC-USD", "binance": "BTCUSDT", "bybit": "BTCUSDT"}

logger = logging.getLogger("conselho.coletor_livro")


# ----------------------------------------------------------------- log
def configurar_log(arquivo: str = ARQUIVO_LOG, nivel: int = logging.INFO, console: bool = True) -> logging.Logger:
    """Log rotativo em logs/coletor_livro.log (5 MB x 5) e, opcionalmente, no console."""
    if getattr(logger, "_configurado", False):
        return logger
    os.makedirs(os.path.dirname(arquivo), exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = RotatingFileHandler(arquivo, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    logger.setLevel(nivel)
    logger.propagate = False
    logger._configurado = True  # type: ignore[attr-defined]
    return logger


# ----------------------------------------------------------------- busca por exchange
def _pares(lista) -> List[Tuple[float, float]]:
    out = []
    for item in lista:
        try:
            p, q = float(item[0]), float(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if p > 0 and q > 0:
            out.append((p, q))
    return out


def buscar_coinbase(simbolo: str = "BTC-USD", timeout: float = TIMEOUT_HTTP_S) -> Livro:
    """Livro level 2 da Coinbase Exchange (spot, em USD). Devolve todos os níveis agregados por preço."""
    r = requests.get(
        f"https://api.exchange.coinbase.com/products/{simbolo}/book",
        params={"level": 2}, headers=CABECALHOS, timeout=timeout,
    )
    r.raise_for_status()
    d = r.json()
    return _pares(d.get("bids", [])), _pares(d.get("asks", []))


def buscar_binance(simbolo: str = "BTCUSDT", limite: int = 5000, timeout: float = TIMEOUT_HTTP_S) -> Livro:
    """Livro spot da Binance (USDT), até 5000 níveis por lado (máximo da API pública; peso 250, 1 chamada/30 s)."""
    r = requests.get(
        "https://api.binance.com/api/v3/depth",
        params={"symbol": simbolo, "limit": limite}, headers=CABECALHOS, timeout=timeout,
    )
    r.raise_for_status()
    d = r.json()
    return _pares(d.get("bids", [])), _pares(d.get("asks", []))


def buscar_bybit(simbolo: str = "BTCUSDT", limite: int = 500, timeout: float = TIMEOUT_HTTP_S) -> Livro:
    """Livro do perpétuo linear da Bybit (USDT), REST v5 público, até 500 níveis por lado."""
    r = requests.get(
        "https://api.bybit.com/v5/market/orderbook",
        params={"category": "linear", "symbol": simbolo, "limit": limite},
        headers=CABECALHOS, timeout=timeout,
    )
    r.raise_for_status()
    d = r.json()
    if d.get("retCode") not in (0, None):
        raise RuntimeError(f"Bybit retCode={d.get('retCode')} {d.get('retMsg')}")
    res = d.get("result", {}) or {}
    return _pares(res.get("b", [])), _pares(res.get("a", []))


BUSCADORES: Dict[str, Callable[[], Livro]] = {
    "coinbase": lambda: buscar_coinbase(SIMBOLOS["coinbase"]),
    "binance": lambda: buscar_binance(SIMBOLOS["binance"]),
    "bybit": lambda: buscar_bybit(SIMBOLOS["bybit"]),
}


# ----------------------------------------------------------------- agregação
def agregar_livro(bids: List[Tuple[float, float]], asks: List[Tuple[float, float]],
                  faixa_pct: float = FAIXA_PCT, limite_pct: float = LIMITE_PCT) -> Dict:
    """
    Agrega um livro em faixas de ``faixa_pct`` do mid até ``limite_pct`` por lado.

    Faixa i do lado bid cobre distâncias [i*faixa_pct, (i+1)*faixa_pct) ABAIXO do mid;
    do lado ask, a mesma distância ACIMA do mid. Quantidades em BTC (unidade da exchange).
    Níveis além do limite são somados em ``fora_bids`` / ``fora_asks``.
    """
    if not bids or not asks:
        raise ValueError("livro vazio")
    melhor_bid = max(p for p, _ in bids)
    melhor_ask = min(p for p, _ in asks)
    if melhor_ask < melhor_bid:
        raise ValueError(f"livro cruzado: bid {melhor_bid} > ask {melhor_ask}")
    mid = (melhor_bid + melhor_ask) / 2.0
    n = int(round(limite_pct / faixa_pct))
    faixas_bid = [0.0] * n
    faixas_ask = [0.0] * n
    fora_bid = fora_ask = 0.0

    for p, q in bids:
        dist = (mid - p) / mid
        if dist < 0:
            continue
        i = int(dist / faixa_pct)
        if i < n:
            faixas_bid[i] += q
        else:
            fora_bid += q
    for p, q in asks:
        dist = (p - mid) / mid
        if dist < 0:
            continue
        i = int(dist / faixa_pct)
        if i < n:
            faixas_ask[i] += q
        else:
            fora_ask += q

    return {
        "mid": mid,
        "melhor_bid": melhor_bid,
        "melhor_ask": melhor_ask,
        "faixa_pct": faixa_pct,
        "limite_pct": limite_pct,
        "bids": [round(x, 6) for x in faixas_bid],
        "asks": [round(x, 6) for x in faixas_ask],
        "total_bids": round(sum(faixas_bid), 6),
        "total_asks": round(sum(faixas_ask), 6),
        "fora_bids": round(fora_bid, 6),
        "fora_asks": round(fora_ask, 6),
        "niveis_bids": len(bids),
        "niveis_asks": len(asks),
    }


def categorias_trdr(bids: List[Tuple[float, float]], asks: List[Tuple[float, float]],
                    bordas: Tuple[float, ...] = CATEGORIAS_PCT) -> Dict:
    """
    Totais em BTC por categoria de distância do TRDR, por lado, medidos a partir do MELHOR bid/ask
    (não do mid): categoria k cobre distâncias [bordas[k], bordas[k+1]).

    Devolve ``cat_bids``, ``cat_asks`` (listas de len(bordas)-1), ``cat_pct`` (as bordas) e o alcance real
    do livro devolvido em cada lado, ``alcance_bids_pct`` / ``alcance_asks_pct`` (distância do nível mais
    longe ao melhor preço, como fração). Alcance menor que a borda superior de uma categoria quer dizer
    que a categoria está INCOMPLETA nessa exchange (Binance 5000 níveis pára em ~1%, Bybit 500 em ~0,1%).
    """
    if not bids or not asks:
        raise ValueError("livro vazio")
    melhor_bid = max(p for p, _ in bids)
    melhor_ask = min(p for p, _ in asks)
    n = len(bordas) - 1
    cat_b = [0.0] * n
    cat_a = [0.0] * n
    alcance_b = alcance_a = 0.0
    for p, q in bids:
        dist = (melhor_bid - p) / melhor_bid
        if dist < 0:
            continue
        alcance_b = max(alcance_b, dist)
        for k in range(n):
            if bordas[k] <= dist < bordas[k + 1]:
                cat_b[k] += q
                break
    for p, q in asks:
        dist = (p - melhor_ask) / melhor_ask
        if dist < 0:
            continue
        alcance_a = max(alcance_a, dist)
        for k in range(n):
            if bordas[k] <= dist < bordas[k + 1]:
                cat_a[k] += q
                break
    return {
        "cat_pct": list(bordas),
        "cat_bids": [round(x, 6) for x in cat_b],
        "cat_asks": [round(x, 6) for x in cat_a],
        "alcance_bids_pct": round(alcance_b, 6),
        "alcance_asks_pct": round(alcance_a, 6),
    }


def top_niveis(bids: List[Tuple[float, float]], asks: List[Tuple[float, float]],
               n: int = N_TOP, limite_pct: float = LIMITE_TOP_PCT) -> Dict:
    """
    Os ``n`` maiores níveis de cada lado por quantidade (Order Book Top Levels do TRDR), só entre os níveis
    a até ``limite_pct`` do melhor preço do lado. Devolve {"top_bids": [[preco, qtd], ...], "top_asks": [...]}
    em ordem decrescente de quantidade.
    """
    if not bids or not asks:
        raise ValueError("livro vazio")
    melhor_bid = max(p for p, _ in bids)
    melhor_ask = min(p for p, _ in asks)
    perto_b = [(p, q) for p, q in bids if 0 <= (melhor_bid - p) / melhor_bid <= limite_pct]
    perto_a = [(p, q) for p, q in asks if 0 <= (p - melhor_ask) / melhor_ask <= limite_pct]
    perto_b.sort(key=lambda x: (-x[1], x[0]))
    perto_a.sort(key=lambda x: (-x[1], x[0]))
    return {
        "top_bids": [[p, round(q, 6)] for p, q in perto_b[:n]],
        "top_asks": [[p, round(q, 6)] for p, q in perto_a[:n]],
    }


def categorias_alcancadas(registro: Dict, lado: str, bordas: Tuple[float, ...] = CATEGORIAS_PCT) -> List[bool]:
    """
    Para cada categoria, se o livro gravado chegou até a borda superior dela nesse ``lado`` ('bids'/'asks').
    Registro antigo (sem ``alcance_*_pct``) não alcança nenhuma: as categorias dele saem das faixas de 0,1%
    e valem só como aproximação (ver ``livro_historico.categorias_do_registro``).
    """
    alcance = registro.get(f"alcance_{lado}_pct")
    if alcance is None:
        return [False] * (len(bordas) - 1)
    return [float(alcance) >= bordas[k + 1] for k in range(len(bordas) - 1)]


def preco_da_faixa(mid: float, lado: str, indice: int, faixa_pct: float = FAIXA_PCT) -> float:
    """Preço no centro da faixa ``indice`` do ``lado`` ('bids' ou 'asks'), dado o mid."""
    dist = (indice + 0.5) * faixa_pct
    return mid * (1 - dist) if lado == "bids" else mid * (1 + dist)


# ----------------------------------------------------------------- gravação
def dia_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def caminho_do_dia(exchange: str, dia: str, raiz: str = PASTA_DADOS) -> str:
    return os.path.join(raiz, exchange, f"{dia}.jsonl.gz")


def gravar_snapshot(registro: Dict, raiz: str = PASTA_DADOS) -> str:
    """Acrescenta um registro ao arquivo gzip do dia (UTC) da exchange. Devolve o caminho."""
    caminho = caminho_do_dia(registro["exchange"], dia_utc(registro["ts"]), raiz)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    linha = (json.dumps(registro, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    # gzip em modo append gera membros concatenados; gzip.open lê todos de uma vez.
    with gzip.open(caminho, "ab") as f:
        f.write(linha)
    return caminho


# ----------------------------------------------------------------- coletor
class ColetorLivro:
    """
    Coleta os livros em loop e grava um registro por snapshot por exchange.

    ``buscadores`` permite injetar funções falsas nos testes (sem internet).
    """

    def __init__(self, raiz: str = PASTA_DADOS, intervalo_s: float = INTERVALO_PADRAO_S,
                 buscadores: Optional[Dict[str, Callable[[], Livro]]] = None,
                 simbolos: Optional[Dict[str, str]] = None,
                 gravar: Callable[[Dict, str], str] = gravar_snapshot):
        self.raiz = raiz
        self.intervalo_s = float(intervalo_s)
        self.buscadores = dict(buscadores if buscadores is not None else BUSCADORES)
        self.simbolos = dict(simbolos if simbolos is not None else SIMBOLOS)
        self._gravar = gravar
        self.parar = threading.Event()
        self.contagem: Dict[str, int] = {ex: 0 for ex in self.buscadores}
        self.falhas: Dict[str, int] = {ex: 0 for ex in self.buscadores}
        self.ultimo: Dict[str, Dict] = {}

    def coletar_exchange(self, exchange: str) -> Optional[Dict]:
        """Busca, agrega e grava o livro de UMA exchange. Devolve o registro ou None se falhou."""
        inicio = time.time()
        try:
            bids, asks = self.buscadores[exchange]()
            agregado = agregar_livro(bids, asks)
            registro = {
                "ts": int(inicio),
                "exchange": exchange,
                "simbolo": self.simbolos.get(exchange, ""),
                **agregado,
                "latencia_ms": int((time.time() - inicio) * 1000),
                # campos novos (nuvens do TRDR); os antigos acima ficam iguais para os arquivos já gravados
                **categorias_trdr(bids, asks),
                **top_niveis(bids, asks),
            }
            self._gravar(registro, self.raiz)
            self.contagem[exchange] = self.contagem.get(exchange, 0) + 1
            self.ultimo[exchange] = registro
            logger.debug("%s mid=%.1f bids=%.2f asks=%.2f (%d ms)", exchange, registro["mid"],
                         registro["total_bids"], registro["total_asks"], registro["latencia_ms"])
            return registro
        except Exception as e:  # noqa: BLE001 - uma exchange não derruba as outras
            self.falhas[exchange] = self.falhas.get(exchange, 0) + 1
            logger.warning("%s falhou: %s: %s", exchange, type(e).__name__, str(e)[:200])
            return None

    def coletar_uma_vez(self) -> Dict[str, Optional[Dict]]:
        """Um ciclo: as exchanges em paralelo (threads), cada uma isolada da outra."""
        resultados: Dict[str, Optional[Dict]] = {}
        threads = []
        for ex in self.buscadores:
            t = threading.Thread(target=lambda e=ex: resultados.__setitem__(e, self.coletar_exchange(e)),
                                 name=f"livro-{ex}", daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=TIMEOUT_HTTP_S * 3)
        for ex in self.buscadores:
            resultados.setdefault(ex, None)
        return resultados

    def rodar(self, duracao_s: Optional[float] = None) -> None:
        """Loop até ``parar`` ser acionado (ou ``duracao_s`` esgotar). Nunca lança exceção."""
        logger.info("coletor iniciado: exchanges=%s intervalo=%ss pasta=%s",
                    ",".join(self.buscadores), self.intervalo_s, self.raiz)
        fim = time.time() + duracao_s if duracao_s else None
        ciclo = 0
        while not self.parar.is_set():
            inicio = time.time()
            try:
                res = self.coletar_uma_vez()
                ciclo += 1
                ok = [ex for ex, r in res.items() if r]
                mids = " ".join(f"{ex}={res[ex]['mid']:.0f}" for ex in ok)
                logger.info("ciclo %d: %d/%d ok %s", ciclo, len(ok), len(res), mids)
            except Exception as e:  # noqa: BLE001
                logger.error("ciclo falhou: %s: %s", type(e).__name__, e)
            if fim and time.time() >= fim:
                break
            espera = max(0.0, self.intervalo_s - (time.time() - inicio))
            if self.parar.wait(espera):
                break
        logger.info("coletor parado: gravados=%s falhas=%s", self.contagem, self.falhas)
