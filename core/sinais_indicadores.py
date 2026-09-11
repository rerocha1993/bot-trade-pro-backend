# core/sinais_indicadores.py
"""
O sinal de CADA indicador em CADA candle fechado do histórico, com a mesma função que o robô usa ao vivo.

    +1 compra, −1 venda, 0 sem opinião

É a matéria-prima de dois usos: o ranking (scripts/ranking_indicadores.py) e o laboratório de combinações
(scripts/lab_indicadores.py). Calcular isso é caro (TPO, Volume Profile e order blocks numa janela por candle),
então o resultado fica em cache em data/sinais/<tf>.csv.gz e as combinações depois são só contas.

Sem olhar o futuro: o sinal do candle i usa apenas candles fechados até i.
"""
from __future__ import annotations

import gzip
import json
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from core.order_block import OrderBlockDetector
from core.regime import analisar_regime
from core.tpo import TPOProfile
from core.volume_profile_pro import VolumeProfilePRO
from core.vwap import VWAPCalculator

FONTES = {"4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv", "15m": "BTCUSDT_binance_15m.csv"}
JANELA = 200
LADO = {"buy": 1, "sell": -1, "hold": 0}
# os indicadores de mercado (o que entra nas combinações) e os dois filtros de contexto
MERCADO = ["VWAP_janela", "VWAP_sessao", "TPO", "Volume_Profile", "Order_Block", "Fibonacci"]
FILTROS = ["Regime", "Elliott"]
PASTA = os.path.join("data", "sinais")


def sinal_fibonacci(win: Sequence, preco: float) -> int:
    """Zona clássica de entrada: recuo entre 50% e 78,6% da última perna, a favor da perna."""
    highs = [c[2] for c in win[-100:]]
    lows = [c[3] for c in win[-100:]]
    i_alto, i_baixo = int(np.argmax(highs)), int(np.argmin(lows))
    alto, baixo = highs[i_alto], lows[i_baixo]
    if alto <= baixo:
        return 0
    faixa = alto - baixo
    if i_baixo < i_alto:                                   # perna de alta: recuo é compra
        return 1 if alto - 0.786 * faixa <= preco <= alto - 0.5 * faixa else 0
    return -1 if baixo + 0.5 * faixa <= preco <= baixo + 0.786 * faixa else 0


def sinal_vwap_sessao(win: Sequence, preco: float) -> int:
    """VWAP ancorado na abertura do dia UTC (como no TradingView), não no começo da janela."""
    dia = win[-1][0] // 86_400_000
    sessao = [c for c in win if c[0] // 86_400_000 == dia]
    if len(sessao) < 3:
        return 0
    return LADO[VWAPCalculator(sessao).sinal(preco)["acao"]]


def _elliott(tf: str) -> Dict[int, int]:
    """Consenso das contagens reconstruídas (scripts/cenarios_historicos.py), se existir."""
    caminho = os.path.join("data", "cenarios", f"{tf}.jsonl.gz")
    if not os.path.exists(caminho):
        return {}
    out = {}
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        for linha in f:
            x = json.loads(linha)
            tot = sum(s["prob"] for s in x["cenarios"]) or 1
            compra = sum(s["prob"] for s in x["cenarios"] if s["direcao"] == "buy") / tot
            venda = sum(s["prob"] for s in x["cenarios"] if s["direcao"] == "sell") / tot
            out[int(x["ts"])] = 1 if compra >= 0.6 else -1 if venda >= 0.6 else 0
    return out


def candles(tf: str) -> List[list]:
    df = pd.read_csv(os.path.join("data", "historico", FONTES[tf])).sort_values("timestamp")
    v = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
    return [[int(x[0])] + [float(k) for k in x[1:]] for x in v]


def atr_simples(win: Sequence) -> float:
    """Média simples do true range dos últimos 14 candles — a régua de stop/alvo do laboratório e do robô."""
    return float(np.mean([max(x[2] - x[3], abs(x[2] - win[j - 1][4]), abs(x[3] - win[j - 1][4]))
                          for j, x in enumerate(win[-15:], start=len(win) - 15)]))


def sinais_do_candle(win: Sequence) -> Dict[str, int]:
    """
    Os sinais de um candle fechado (o último de `win`, com JANELA candles). A MESMA função serve ao histórico
    (`calcular`) e ao robô ao vivo (core/estrategia_votacao.py): o que roda é o que foi testado.
    Levanta exceção se algum indicador não conseguir calcular.
    """
    preco = win[-1][4]
    s = {
        "VWAP_janela": LADO[VWAPCalculator(win[-150:]).sinal(preco)["acao"]],
        "VWAP_sessao": sinal_vwap_sessao(win, preco),
        "TPO": LADO[TPOProfile(win, bins=30).sinal_estrategico(preco)["acao"]],
        "Volume_Profile": LADO[VolumeProfilePRO(win, num_bins=40).price_signal(preco)["acao"]],
        "Order_Block": LADO[OrderBlockDetector(win[-150:]).sinal(preco)["acao"]],
        "Fibonacci": sinal_fibonacci(win, preco),
    }
    r = analisar_regime(win, 40)
    s["Regime"] = 0 if r["regime"] == "serrilhado" else (1 if win[-1][4] > win[-20][4] else -1)
    return s


def calcular(tf: str, passo: int = 1, desde_ms: int = 0, verbose: bool = True) -> pd.DataFrame:
    c = candles(tf)
    ell = _elliott(tf)
    linhas = []
    for i in range(JANELA, len(c), passo):
        if c[i][0] < desde_ms:
            continue
        win = c[i - JANELA + 1:i + 1]
        preco = win[-1][4]
        try:
            s = sinais_do_candle(win)
        except Exception:
            continue
        s["Elliott"] = ell.get(win[-1][0], 0)
        linhas.append({"i": i, "ts": win[-1][0], "preco": preco, "atr": atr_simples(win), **s})
        if verbose and len(linhas) % 5000 == 0:
            print(f"  {tf}: {len(linhas)} candles", flush=True)
    return pd.DataFrame(linhas)


def carregar(tf: str, passo: int = 1, desde_ms: int = 0, recalcular: bool = False, verbose: bool = True) -> pd.DataFrame:
    os.makedirs(PASTA, exist_ok=True)
    caminho = os.path.join(PASTA, f"{tf}_p{passo}.csv.gz")
    if os.path.exists(caminho) and not recalcular:
        d = pd.read_csv(caminho)
    else:
        d = calcular(tf, passo, 0, verbose)
        d.to_csv(caminho, index=False, compression="gzip")
    return d[d["ts"] >= desde_ms].reset_index(drop=True)
