"""
Baixa os negócios diários do perpétuo BTCUSDT da Bybit (public.bybit.com, sem chave) e grava o footprint por minuto
no mesmo formato do coletor ao vivo (conselho/coletor_negocios.py): dados/negocios/bybit/<AAAA-MM-DD>.jsonl.gz.

    .venv\\Scripts\\python.exe scripts\\baixar_negocios_bybit.py --dias 3

Só baixa dias já fechados (a Bybit publica o arquivo do dia seguinte). Num dia que já tem arquivo (o coletor ao vivo
gravou parte dele), grava só os minutos que faltam, sem duplicar nem sobrescrever. O arquivo bruto (~40–180 MB) é lido
em fluxo e descartado.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from conselho.coletor_livro import gravar_snapshot  # noqa: E402
from conselho.livro_historico import carregar_dia  # noqa: E402
from conselho.coletor_negocios import PASTA_NEGOCIOS, AgregadorMinuto  # noqa: E402

URL = "https://public.bybit.com/trading/BTCUSDT/BTCUSDT{dia}.csv.gz"
LOTE = 20_000


def baixar_dia(dia: str, raiz: str = PASTA_NEGOCIOS) -> int:
    """Lê o arquivo do dia em fluxo, agrega por minuto e grava os minutos que ainda não existem. Devolve quantos."""
    ja_tem = {int(r["ts"]) for r in carregar_dia("bybit", dia, raiz)}
    ag = AgregadorMinuto("bybit")
    with requests.get(URL.format(dia=dia), stream=True, timeout=60) as r:
        if r.status_code == 404:
            print(f"{dia}: a Bybit ainda não publicou o arquivo")
            return 0
        r.raise_for_status()
        r.raw.decode_content = False
        texto = io.TextIOWrapper(gzip.GzipFile(fileobj=r.raw), encoding="utf-8")
        leitor = csv.DictReader(texto)
        lote = []
        for linha in leitor:
            lote.append((float(linha["timestamp"]), float(linha["price"]), float(linha["size"]), linha["side"] == "Buy"))
            if len(lote) >= LOTE:
                ag.adicionar(lote)
                lote = []
        ag.adicionar(lote)
    n = 0
    for registro in ag.fechados(float("inf")):
        if int(registro["ts"]) in ja_tem:
            continue
        gravar_snapshot(registro, raiz)
        n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Footprint por minuto a partir dos negócios diários da Bybit.")
    ap.add_argument("--dias", type=int, default=2, help="quantos dias fechados para trás (padrão 2)")
    ap.add_argument("--pasta", default=PASTA_NEGOCIOS)
    args = ap.parse_args(argv)
    hoje = datetime.now(timezone.utc).date()
    for k in range(args.dias, 0, -1):
        dia = (hoje - timedelta(days=k)).strftime("%Y-%m-%d")
        print(f"{dia}: {baixar_dia(dia, args.pasta)} minutos gravados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
