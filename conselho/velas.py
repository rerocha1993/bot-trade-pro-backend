# conselho/velas.py
"""
Velas de qualquer moeda em Coinbase, Binance, Bybit e OKX (à vista e perpétuo), só com as APIs públicas, para a tela
Gráfico do painel.

Símbolo num formato só: CORRETORA:BASE-COTACAO, com :PERP no fim para o perpétuo — COINBASE:BTC-USD,
BINANCE:ETH-USDT, BYBIT:SOL-USDT:PERP. Vela = [início_s, open, high, low, close, volume], em ordem crescente,
a última pode estar aberta.

Cada API devolve um pedaço por chamada (Coinbase 350, Binance e Bybit 1000, OKX 100); `velas` pagina para trás até
juntar `n`. A Coinbase não tem 4 h: monta a partir de 1 h (blocos alinhados em 00, 04, 08... UTC).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import requests

TIMEOUT_S = 10.0
CABECALHOS = {"User-Agent": "bot-trade-pro/1.0 (conselho)"}
TEMPOS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
N_MAX = 2000
CORRETORAS = {"COINBASE": ("spot",), "BINANCE": ("spot", "perp"), "BYBIT": ("spot", "perp"), "OKX": ("spot", "perp")}
COTACOES = ("USD", "USDT", "USDC")
# ordem da lista de moedas: as mais negociadas primeiro, o resto em ordem alfabética
POPULARES = ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "SUI", "AVAX", "LINK", "TON", "TRX", "LTC", "DOT", "BCH",
             "NEAR", "APT", "ARB", "OP", "PEPE", "SHIB", "UNI", "AAVE", "HYPE", "ENA", "WIF", "TIA", "INJ", "SEI", "FIL")


@dataclass(frozen=True)
class Simbolo:
    corretora: str
    base: str
    cotacao: str
    perp: bool = False

    @property
    def texto(self) -> str:
        return f"{self.corretora}:{self.base}-{self.cotacao}" + (":PERP" if self.perp else "")


def ler_simbolo(texto: str) -> Simbolo:
    """'COINBASE:BTC-USD' → Simbolo. ValueError se a corretora, o mercado ou o formato não existirem."""
    partes = (texto or "").strip().upper().split(":")
    if len(partes) not in (2, 3) or (len(partes) == 3 and partes[2] != "PERP"):
        raise ValueError(f"símbolo inválido: {texto!r} (use CORRETORA:BASE-COTACAO[:PERP])")
    corretora, par = partes[0], partes[1]
    perp = len(partes) == 3
    if corretora not in CORRETORAS:
        raise ValueError(f"corretora sem suporte: {corretora}")
    if perp and "perp" not in CORRETORAS[corretora]:
        raise ValueError(f"{corretora} não tem perpétuo aqui")
    if par.count("-") != 1 or not all(par.split("-")):
        raise ValueError(f"par inválido: {par!r} (use BASE-COTACAO, ex.: BTC-USDT)")
    base, cotacao = par.split("-")
    return Simbolo(corretora, base, cotacao, perp)


def tem_nuvem(s: Simbolo) -> bool:
    """As nuvens do livro só existem para o BTC à vista da Coinbase (é o livro que o coletor grava)."""
    return s == Simbolo("COINBASE", "BTC", "USD")


# ---------------------------------------------------------------------------------------------- por corretora
# Cada função busca UMA página de velas que começam até `ate_s` (inclusive) e devolve [t, o, h, l, c, v] em
# qualquer ordem; lista vazia = não há mais histórico.

def _json(http, url: str, params: dict):
    r = http.get(url, params=params, headers=CABECALHOS, timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


COINBASE_GRAN = {"1m": "ONE_MINUTE", "5m": "FIVE_MINUTE", "15m": "FIFTEEN_MINUTE", "30m": "THIRTY_MINUTE",
                 "1h": "ONE_HOUR", "1d": "ONE_DAY"}


def _pagina_coinbase(s: Simbolo, tempo: str, ate_s: int, http) -> List[list]:
    passo = TEMPOS[tempo]
    dados = _json(http, f"https://api.coinbase.com/api/v3/brokerage/market/products/{s.base}-{s.cotacao}/candles",
                  {"granularity": COINBASE_GRAN[tempo], "start": ate_s - passo * 349, "end": ate_s, "limit": 350})
    return [[int(c["start"]), float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"])]
            for c in dados.get("candles") or []]


BINANCE_TEMPO = {t: t for t in TEMPOS}


def _pagina_binance(s: Simbolo, tempo: str, ate_s: int, http) -> List[list]:
    url = "https://fapi.binance.com/fapi/v1/klines" if s.perp else "https://api.binance.com/api/v3/klines"
    dados = _json(http, url, {"symbol": s.base + s.cotacao, "interval": tempo, "endTime": ate_s * 1000, "limit": 1000})
    return [[int(c[0]) // 1000, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in dados]


BYBIT_TEMPO = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D"}


def _pagina_bybit(s: Simbolo, tempo: str, ate_s: int, http) -> List[list]:
    dados = _json(http, "https://api.bybit.com/v5/market/kline",
                  {"category": "linear" if s.perp else "spot", "symbol": s.base + s.cotacao,
                   "interval": BYBIT_TEMPO[tempo], "end": ate_s * 1000, "limit": 1000})
    if dados.get("retCode") != 0:
        raise ValueError(f"Bybit: {dados.get('retMsg')}")
    return [[int(c[0]) // 1000, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
            for c in (dados.get("result") or {}).get("list") or []]


OKX_TEMPO = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1Dutc"}


def _pagina_okx(s: Simbolo, tempo: str, ate_s: int, http) -> List[list]:
    inst = f"{s.base}-{s.cotacao}" + ("-SWAP" if s.perp else "")
    # `after` traz as velas ANTERIORES ao instante (exclusivo); o +1 ms inclui a que começa em ate_s
    dados = _json(http, "https://www.okx.com/api/v5/market/history-candles",
                  {"instId": inst, "bar": OKX_TEMPO[tempo], "after": ate_s * 1000 + 1, "limit": 100})
    if str(dados.get("code")) != "0":
        raise ValueError(f"OKX: {dados.get('msg')}")
    # no perpétuo o volume em moeda é o 7º campo (o 6º é em contratos)
    iv = 6 if s.perp else 5
    return [[int(c[0]) // 1000, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[iv])]
            for c in dados.get("data") or []]


PAGINAS: Dict[str, Callable] = {"COINBASE": _pagina_coinbase, "BINANCE": _pagina_binance, "BYBIT": _pagina_bybit,
                                "OKX": _pagina_okx}
# o tempo que a corretora não tem sai de um menor, somando os blocos
MONTADOS = {"COINBASE": {"4h": "1h"}}


def agregar(velas: List[list], passo: int) -> List[list]:
    """Junta velas menores (ordem crescente) em blocos de `passo` segundos alinhados no UTC."""
    saida: List[list] = []
    for t, o, h, l, c, v in velas:
        b = t - t % passo
        if saida and saida[-1][0] == b:
            u = saida[-1]
            u[2], u[3], u[4], u[5] = max(u[2], h), min(u[3], l), c, u[5] + v
        else:
            saida.append([b, o, h, l, c, v])
    return saida


def velas(simbolo: str, tempo: str, ate_s: Optional[int] = None, n: int = 500, http=None) -> List[list]:
    """As `n` velas que começam até `ate_s` (padrão: agora), em ordem crescente, sem repetição."""
    s = ler_simbolo(simbolo)
    if tempo not in TEMPOS:
        raise ValueError(f"tempo sem suporte: {tempo} (use {', '.join(TEMPOS)})")
    n = max(1, min(int(n), N_MAX))
    http = http or requests
    ate_s = int(ate_s if ate_s is not None else time.time())
    passo = TEMPOS[tempo]
    menor = MONTADOS.get(s.corretora, {}).get(tempo)
    if menor:
        # pede um bloco a mais (o mais velho pode vir pela metade) e o fim alinhado no bloco grande
        filhas = velas(s.texto, menor, ate_s - ate_s % passo + passo - 1, (n + 1) * (passo // TEMPOS[menor]), http)
        juntas = agregar(filhas, passo)
        return juntas[1:][-n:] if len(juntas) > n else juntas
    pagina = PAGINAS[s.corretora]
    vistas: Dict[int, list] = {}
    cursor = ate_s - ate_s % passo
    while len(vistas) < n:
        lote = [v for v in pagina(s, tempo, cursor, http) if v[0] <= cursor]
        novas = [v for v in lote if v[0] not in vistas]
        if not novas:
            break
        for v in novas:
            vistas[v[0]] = v
        cursor = min(v[0] for v in novas) - passo
    return [vistas[t] for t in sorted(vistas)][-n:]


# ---------------------------------------------------------------------------------------------- lista de moedas

def _ordenar(itens: List[dict]) -> List[dict]:
    pos = {b: i for i, b in enumerate(POPULARES)}
    cot = {c: i for i, c in enumerate(COTACOES)}
    return sorted(itens, key=lambda x: (pos.get(x["base"], len(POPULARES)), x["base"], cot.get(x["cotacao"], 9)))


def listar(corretora: str, perp: bool = False, http=None) -> List[dict]:
    """Pares negociando agora na corretora, cotados em USD/USDT/USDC: [{simbolo, base, cotacao}]."""
    corretora = corretora.upper()
    if corretora not in CORRETORAS or (perp and "perp" not in CORRETORAS[corretora]):
        raise ValueError(f"mercado sem suporte: {corretora} {'perp' if perp else 'spot'}")
    http = http or requests
    pares = []
    if corretora == "COINBASE":
        for p in _json(http, "https://api.exchange.coinbase.com/products", {}):
            if p.get("status") == "online" and not p.get("trading_disabled"):
                pares.append((p["base_currency"], p["quote_currency"]))
    elif corretora == "BINANCE":
        # o exchangeInfo é grande (~6 MB à vista), mas traz o status; a lista de preços inclui par fora de negociação
        if perp:
            d = _json(http, "https://fapi.binance.com/fapi/v1/exchangeInfo", {})
        else:
            d = _json(http, "https://api.binance.com/api/v3/exchangeInfo", {"symbolStatus": "TRADING"})
        for i in d.get("symbols") or []:
            if i.get("status") == "TRADING" and (not perp or i.get("contractType") == "PERPETUAL"):
                pares.append((i["baseAsset"], i["quoteAsset"]))
    elif corretora == "BYBIT":
        cursor = ""
        while True:
            d = _json(http, "https://api.bybit.com/v5/market/instruments-info",
                      {"category": "linear" if perp else "spot", "limit": 1000, "cursor": cursor})
            res = d.get("result") or {}
            for i in res.get("list") or []:
                if i.get("status") == "Trading" and (not perp or i.get("contractType") == "LinearPerpetual"):
                    pares.append((i["baseCoin"], i["quoteCoin"]))
            cursor = res.get("nextPageCursor") or ""
            if not cursor:
                break
    else:
        d = _json(http, "https://www.okx.com/api/v5/public/instruments", {"instType": "SWAP" if perp else "SPOT"})
        for i in d.get("data") or []:
            if i.get("state") != "live":
                continue
            partes = i["instId"].split("-")
            pares.append((partes[0], partes[1]))
    vistos, itens = set(), []
    for base, cot in pares:
        if cot not in COTACOES or (base, cot) in vistos:
            continue
        vistos.add((base, cot))
        itens.append({"simbolo": Simbolo(corretora, base, cot, perp).texto, "base": base, "cotacao": cot})
    return _ordenar(itens)
