"""
Preenche os minutos de negócios que o coletor ao vivo perdeu (PC desligado, janela fechada) na Binance (à vista) e na
Coinbase, pelas APIs públicas de negociações, sem chave. A Bybit tem o arquivo diário (scripts/baixar_negocios_bybit.py).

    .venv\\Scripts\\python.exe scripts\\preencher_negocios.py --horas 30

Olha as últimas ``--horas`` horas, acha os minutos sem registro e grava só eles, no mesmo formato do coletor
(conselho/coletor_negocios.py). O livro de ordens não tem como ser recuperado: as corretoras não guardam histórico dele.
    binance   GET /api/v3/aggTrades (startTime/endTime, até 1 h por janela; m = o comprador era o maker)
    coinbase  GET /products/BTC-USD/trades (1000 por página, do mais novo para o mais velho; side = lado do maker)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Set, Tuple

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from conselho.coletor_livro import gravar_snapshot  # noqa: E402
from conselho.coletor_negocios import PASTA_NEGOCIOS, AgregadorMinuto, Negocio, _iso_para_s  # noqa: E402
from conselho.livro_historico import carregar_periodo  # noqa: E402

TIMEOUT_S = 15


def minutos_faltando(exchange: str, ini_s: int, fim_s: int, raiz: str) -> List[int]:
    ja_tem: Set[int] = {int(r["ts"]) for r in carregar_periodo(exchange, ini_s, fim_s, raiz)}
    return [m for m in range(ini_s // 60 * 60, fim_s // 60 * 60, 60) if m not in ja_tem]


def trechos(minutos: List[int]) -> List[Tuple[int, int]]:
    """Minutos faltando em trechos contínuos [início, fim) em segundos."""
    saida: List[Tuple[int, int]] = []
    for m in minutos:
        if saida and saida[-1][1] == m:
            saida[-1] = (saida[-1][0], m + 60)
        else:
            saida.append((m, m + 60))
    return saida


def negocios_binance(ini_s: int, fim_s: int) -> Iterable[Negocio]:
    t = ini_s * 1000
    while t < fim_s * 1000:
        fim_janela = min(t + 3_600_000, fim_s * 1000) - 1
        de_id = None
        while True:
            params = {"symbol": "BTCUSDT", "limit": 1000}
            params.update({"fromId": de_id} if de_id is not None else {"startTime": t, "endTime": fim_janela})
            r = requests.get("https://api.binance.com/api/v3/aggTrades", params=params, timeout=TIMEOUT_S)
            r.raise_for_status()
            lote = r.json()
            dentro = [x for x in lote if x["T"] <= fim_janela]
            for x in dentro:
                yield (x["T"] / 1000.0, float(x["p"]), float(x["q"]), not x["m"])
            if len(lote) < 1000 or len(dentro) < len(lote):
                break
            de_id = lote[-1]["a"] + 1
            time.sleep(0.05)
        t = fim_janela + 1


def negocios_coinbase(ini_s: int, fim_s: int) -> Iterable[Negocio]:
    """Pagina do mais novo para o mais velho até passar de ini_s; devolve só o que cai em [ini_s, fim_s)."""
    depois = None
    while True:
        params = {"limit": 1000}
        if depois is not None:
            params["after"] = depois
        r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/trades", params=params, timeout=TIMEOUT_S)
        if r.status_code == 429:
            time.sleep(1.0)
            continue
        r.raise_for_status()
        lote = r.json()
        if not lote:
            return
        for x in lote:
            ts = _iso_para_s(x["time"])
            if ini_s <= ts < fim_s:
                yield (ts, float(x["price"]), float(x["size"]), x["side"] == "sell")   # side é o maker
        if _iso_para_s(lote[-1]["time"]) < ini_s:
            return
        depois = r.headers.get("cb-after") or lote[-1]["trade_id"]
        time.sleep(0.12)


BUSCAS = {"binance": negocios_binance, "coinbase": negocios_coinbase}


def preencher(exchange: str, horas: float, raiz: str = PASTA_NEGOCIOS, agora_s: float | None = None) -> int:
    agora = int(agora_s if agora_s is not None else time.time())
    fim = agora // 60 * 60 - 120                 # os 2 últimos minutos ainda são do coletor ao vivo
    ini = fim - int(horas * 3600)
    faltam = minutos_faltando(exchange, ini, fim, raiz)
    if not faltam:
        print(f"{exchange}: nada faltando nas últimas {horas:g} h")
        return 0
    n = 0
    for a, b in trechos(faltam):
        de = datetime.fromtimestamp(a, timezone.utc).strftime("%d/%m %H:%M")
        ate = datetime.fromtimestamp(b, timezone.utc).strftime("%H:%M")
        ag = AgregadorMinuto(exchange)
        ag.adicionar(BUSCAS[exchange](a, b))
        gravados = 0
        for registro in ag.fechados(float("inf")):
            if a <= int(registro["ts"]) < b:
                gravar_snapshot(registro, raiz)
                gravados += 1
        print(f"{exchange}: {de}–{ate} UTC, {gravados} de {(b - a) // 60} minutos gravados")
        n += gravados
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Preenche os minutos de negócios que o coletor perdeu (Binance e Coinbase).")
    ap.add_argument("--horas", type=float, default=30.0, help="quantas horas para trás olhar (padrão 30)")
    ap.add_argument("--exchanges", default="binance,coinbase")
    ap.add_argument("--pasta", default=PASTA_NEGOCIOS)
    args = ap.parse_args(argv)
    for ex in [e.strip() for e in args.exchanges.split(",") if e.strip() in BUSCAS]:
        preencher(ex, args.horas, args.pasta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
