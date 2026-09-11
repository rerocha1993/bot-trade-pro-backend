"""
RANKING OBJETIVO DOS INDICADORES: qual deles, sozinho, tem mais informação sobre o que vem depois?

    python scripts/ranking_indicadores.py --tf 4h
    python scripts/ranking_indicadores.py --tf 1h --passo 2

Para cada candle fechado do histórico, calcula o sinal de CADA indicador com a mesma função que o robô usa
(VWAP.sinal, TPOProfile.sinal_estrategico, VolumeProfilePRO.price_signal, OrderBlockDetector.sinal, a zona de
Fibonacci da última perna, o regime de Kaufman, o consenso de Elliott já reconstruído) e compara com o retorno
dos próximos `horizonte` candles.

Métricas (por indicador e por horizonte):
    sinais        quantos buy/sell ele deu
    acerto        % das vezes em que o lado do sinal foi o lado do movimento seguinte
    base          o mesmo % apostando sempre no lado mais comum do período (o que precisa ser batido)
    retorno       retorno médio a favor do sinal, em %, e o líquido depois do custo de ida e volta
    IC            correlação entre o sinal (+1/−1/0) e o retorno seguinte
    t             quantos desvios-padrão o retorno médio está de zero, já descontando a sobreposição das
                  janelas (amostras vizinhas não são independentes). Abaixo de 2 é ruído.

Sem olhar o futuro: cada sinal usa só candles fechados até ele.
"""
import argparse
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.executor_real import TAXA_TAKER  # noqa: E402
from core.order_block import OrderBlockDetector  # noqa: E402
from core.regime import analisar_regime  # noqa: E402
from core.tpo import TPOProfile  # noqa: E402
from core.volume_profile_pro import VolumeProfilePRO  # noqa: E402
from core.vwap import VWAPCalculator  # noqa: E402

FONTES = {"4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv", "15m": "BTCUSDT_binance_15m.csv"}
DUR = {"4h": 14_400_000, "1h": 3_600_000, "15m": 900_000}
JANELA = 200
CUSTO_PCT = 2 * TAXA_TAKER * 100        # ida e volta a mercado, em %
LADO = {"buy": 1, "sell": -1, "hold": 0}


def sinal_fibonacci(win, preco):
    """Zona clássica de entrada: recuo entre 50% e 78,6% da última perna, a favor da perna."""
    highs = [c[2] for c in win[-100:]]
    lows = [c[3] for c in win[-100:]]
    i_alto, i_baixo = int(np.argmax(highs)), int(np.argmin(lows))
    alto, baixo = highs[i_alto], lows[i_baixo]
    if alto <= baixo:
        return 0
    faixa = alto - baixo
    if i_baixo < i_alto:                                  # perna de alta: recuo compra
        return 1 if alto - 0.786 * faixa <= preco <= alto - 0.5 * faixa else 0
    return -1 if baixo + 0.5 * faixa <= preco <= baixo + 0.786 * faixa else 0


def sinal_vwap_sessao(win, preco, tf):
    """VWAP ancorado na abertura do dia (como no TradingView), não no começo da janela."""
    dia = win[-1][0] // 86_400_000
    sessao = [c for c in win if c[0] // 86_400_000 == dia]
    if len(sessao) < 3:
        return 0
    return LADO[VWAPCalculator(sessao).sinal(preco)["acao"]]


def coletar(tf: str, passo: int, desde_ms: int):
    df = pd.read_csv(os.path.join("data", "historico", FONTES[tf])).sort_values("timestamp")
    c = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
    c = [[int(x[0])] + [float(v) for v in x[1:]] for x in c]
    elliott = {}
    caminho = os.path.join("data", "cenarios", f"{tf}.jsonl.gz")
    if os.path.exists(caminho):
        with gzip.open(caminho, "rt", encoding="utf-8") as f:
            for linha in f:
                x = json.loads(linha)
                tot = sum(s["prob"] for s in x["cenarios"]) or 1
                compra = sum(s["prob"] for s in x["cenarios"] if s["direcao"] == "buy") / tot
                venda = sum(s["prob"] for s in x["cenarios"] if s["direcao"] == "sell") / tot
                elliott[x["ts"]] = 1 if compra >= 0.6 else -1 if venda >= 0.6 else 0
    fg = {}
    cam_fg = os.path.join("data", "historico", "fear_greed.csv")
    if os.path.exists(cam_fg):
        d = pd.read_csv(cam_fg)
        fg = {int(r.timestamp) // 86_400_000: float(r.valor) for r in d.itertuples(index=False)}
    linhas = []
    for i in range(JANELA, len(c), passo):
        if c[i][0] < desde_ms:
            continue
        win = c[i - JANELA + 1:i + 1]
        preco = win[-1][4]
        s = {}
        try:
            s["VWAP (janela)"] = LADO[VWAPCalculator(win[-150:]).sinal(preco)["acao"]]
            s["VWAP (sessão)"] = sinal_vwap_sessao(win, preco, tf)
            s["TPO"] = LADO[TPOProfile(win, bins=30).sinal_estrategico(preco)["acao"]]
            s["Volume Profile"] = LADO[VolumeProfilePRO(win, num_bins=40).price_signal(preco)["acao"]]
            s["Order Block"] = LADO[OrderBlockDetector(win[-150:]).sinal(preco)["acao"]]
            s["Fibonacci"] = sinal_fibonacci(win, preco)
        except Exception:
            continue
        r = analisar_regime(win, 40)
        s["Regime (tendência)"] = 0 if r["regime"] == "serrilhado" else (1 if win[-1][4] > win[-20][4] else -1)
        s["Elliott (consenso)"] = elliott.get(win[-1][0], 0)
        v = fg.get(win[-1][0] // 86_400_000)
        s["Sentimento (contrário)"] = 0 if v is None else (-1 if v >= 75 else 1 if v <= 25 else 0)
        linhas.append({"i": i, "ts": win[-1][0], "preco": preco, **s})
    return c, pd.DataFrame(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="4h", choices=list(FONTES))
    ap.add_argument("--passo", type=int, default=1)
    ap.add_argument("--desde", default="2021-01-01")
    ap.add_argument("--horizontes", default="6,24")
    ap.add_argument("--salvar")
    a = ap.parse_args()
    import datetime as dt
    desde = int(dt.datetime.fromisoformat(a.desde).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    c, d = coletar(a.tf, a.passo, desde)
    fechos = np.array([x[4] for x in c])
    print(f"{a.tf}: {len(d)} candles avaliados desde {a.desde} (custo de ida e volta {CUSTO_PCT:.3f}%)")
    saida = {}
    for H in [int(x) for x in a.horizontes.split(",")]:
        idx = d["i"].values
        ok = idx + H < len(fechos)
        ret = np.full(len(d), np.nan)
        ret[ok] = (fechos[idx[ok] + H] / fechos[idx[ok]] - 1) * 100
        base = max(float(np.mean(ret[ok] > 0)), float(np.mean(ret[ok] < 0)))
        print(f"\n=== horizonte de {H} candles === (base do lado mais comum: {base:.1%})")
        print(f"  {'indicador':<24} {'sinais':>7} {'acerto':>7} {'retorno':>9} {'líquido':>9} {'IC':>7} {'t':>6}")
        linhas = []
        for nome in [k for k in d.columns if k not in ("i", "ts", "preco")]:
            s = d[nome].values.astype(float)
            m = ok & (s != 0) & ~np.isnan(ret)
            n = int(m.sum())
            if n < 30:
                continue
            r_sinal = s[m] * ret[m]
            acerto = float(np.mean(r_sinal > 0))
            medio = float(np.mean(r_sinal))
            # sobreposição: janelas vizinhas contam quase a mesma informação -> n efetivo = n / H
            t = medio / (np.std(r_sinal) / np.sqrt(max(n / H, 1))) if np.std(r_sinal) else 0.0
            ic = float(np.corrcoef(s[ok & ~np.isnan(ret)], ret[ok & ~np.isnan(ret)])[0, 1])
            linhas.append((nome, n, acerto, medio, medio - CUSTO_PCT, ic, t))
        for nome, n, acerto, medio, liq, ic, t in sorted(linhas, key=lambda x: -x[3]):
            print(f"  {nome:<24} {n:>7} {acerto:>6.1%} {medio:>+8.3f}% {liq:>+8.3f}% {ic:>+7.3f} {t:>+6.1f}")
        saida[H] = {"base": base, "linhas": [dict(zip(("indicador", "sinais", "acerto", "retorno_pct", "liquido_pct", "ic", "t"), x)) for x in linhas]}
    if a.salvar:
        with open(a.salvar, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
