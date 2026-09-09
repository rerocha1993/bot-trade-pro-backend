# core/bybit_trades_fetcher.py
"""
NEGÓCIOS HISTÓRICOS da Bybit (arquivos diários públicos), para validar o motor de fluxo.

    https://public.bybit.com/trading/BTCUSDT/BTCUSDT2026-09-05.csv.gz

Cada arquivo tem um dia inteiro de negócios executados — no BTCUSDT, perto de 600 mil por dia. É a matéria-
prima que falta para testar barra por volume: candle de 1m não serve, porque a barra de fluxo fecha por
quantidade negociada e precisa saber COMO o volume chegou, não só quanto chegou no minuto.

Colunas do arquivo: timestamp (segundos, com fração), symbol, side, size, price, tickDirection, trdMatchID,
grossValue, homeNotional, foreignNotional. `side` é o lado do AGRESSOR, que é exatamente o que o delta mede.

Os arquivos ficam em cache no disco: são ~20 MB por dia comprimidos e baixar de novo a cada teste seria
maltratar um serviço público de graça.
"""
from __future__ import annotations

import csv
import gzip
import io
import logging
import os
import urllib.request
from datetime import date, timedelta
from typing import Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

BASE = "https://public.bybit.com/trading"
PASTA_PADRAO = os.path.join("dados", "trades_bybit")


def url_do_dia(par: str, dia: date) -> str:
    p = par.replace("/", "").upper()
    return f"{BASE}/{p}/{p}{dia.isoformat()}.csv.gz"


def caminho_cache(par: str, dia: date, pasta: str = PASTA_PADRAO) -> str:
    p = par.replace("/", "").upper()
    return os.path.join(pasta, f"{p}{dia.isoformat()}.csv.gz")


def baixar_dia(par: str, dia: date, pasta: str = PASTA_PADRAO, timeout: int = 120) -> Optional[str]:
    """Baixa (ou reaproveita do cache) o arquivo de um dia. None quando a Bybit não publicou aquele dia."""
    destino = caminho_cache(par, dia, pasta)
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        return destino
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    url = url_do_dia(par, dia)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            dados = r.read()
    except Exception as e:
        logger.warning("não foi possível baixar %s: %s", url, e)
        return None
    # grava num temporário e só então renomeia: um download interrompido não pode virar cache válido
    parcial = destino + ".parcial"
    with open(parcial, "wb") as f:
        f.write(dados)
    os.replace(parcial, destino)
    logger.info("baixado %s (%.1f MB)", os.path.basename(destino), len(dados) / 1e6)
    return destino


def ler_arquivo(caminho: str) -> Iterator[Dict]:
    """Devolve os negócios do arquivo já no formato do websocket: price, qty, side, timestamp em ms."""
    with gzip.open(caminho, "rt", encoding="utf-8", newline="") as fh:
        for linha in csv.DictReader(fh):
            try:
                yield {"price": float(linha["price"]),
                       "qty": float(linha["size"]),
                       "side": "buy" if linha["side"].strip().lower() == "buy" else "sell",
                       "timestamp": int(float(linha["timestamp"]) * 1000)}
            except (KeyError, TypeError, ValueError):
                continue


def dias(inicio: date, fim: date) -> List[date]:
    return [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]


def carregar(par: str, inicio: date, fim: date, pasta: str = PASTA_PADRAO) -> List[Dict]:
    """
    Todos os negócios do período, em ordem. Um dia são centenas de milhares de linhas: pedir um mês de uma
    vez é pedir dezenas de milhões de dicionários na memória. Para períodos longos use `fluxo`.
    """
    return list(fluxo(par, inicio, fim, pasta))


def fluxo(par: str, inicio: date, fim: date, pasta: str = PASTA_PADRAO) -> Iterator[Dict]:
    """Mesma coisa, mas um negócio por vez: é assim que o backtest consome, sem carregar o mês inteiro."""
    for dia in dias(inicio, fim):
        caminho = baixar_dia(par, dia, pasta)
        if caminho is None:
            logger.warning("dia %s indisponível: pulando", dia.isoformat())
            continue
        for t in ler_arquivo(caminho):
            yield t


def resumo(par: str, dia: date, pasta: str = PASTA_PADRAO) -> Dict:
    """Quantos negócios e quanto volume naquele dia — para conferir a régua da barra antes de rodar o teste."""
    caminho = baixar_dia(par, dia, pasta)
    if caminho is None:
        return {"dia": dia.isoformat(), "erro": "indisponível"}
    n, vol, primeiro, ultimo = 0, 0.0, None, None
    for t in ler_arquivo(caminho):
        n += 1
        vol += t["qty"]
        primeiro = primeiro if primeiro is not None else t["timestamp"]
        ultimo = t["timestamp"]
    horas = (ultimo - primeiro) / 3_600_000 if primeiro and ultimo else 0.0
    return {"dia": dia.isoformat(), "negocios": n, "volume": round(vol, 2), "horas": round(horas, 2),
            "volume_por_minuto": round(vol / (horas * 60), 3) if horas else None}


if __name__ == "__main__":     # pragma: no cover
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    par = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    d = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today() - timedelta(days=3)
    print(resumo(par, d))
