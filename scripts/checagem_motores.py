"""
CHECAGEM DOS MOTORES DE BACKTEST: o resultado negativo é do mercado ou do meu teste?

    python scripts/checagem_motores.py

Usa os PRÓPRIOS motores (sem cópia) em três versões:
    1. direção SORTEADA, sem custo      um motor justo dá perto de zero; o quanto fica abaixo mede o viés das regras
                                        conservadoras (stop primeiro no candle, só stop no candle da entrada)
    2. direção sorteada, com custo      tem que dar negativo, mais ou menos o tamanho do custo
    3. direção que VÊ O FUTURO          tem que dar muito positivo; se não der, o motor tem bug

Motores:
    scalp  core/scalp_volatilidade.simular, nos 1.530 eventos do estudo, execução em 1 min; a zona é recolocada no
           preço do momento com a largura do evento (a entrada executa logo, sem escolher onde)
    lab    core/gestao_trade.trade_gestao (5 fatias + tirar o risco, o do robô 9), 4h de 2020 a 2026, entradas a cada
           24 h, stop 1,5 ATR, alvo 3R, 24 candles
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.gestao_trade as gt  # noqa: E402
from core.scalp_volatilidade import ParametrosScalpVol, simular  # noqa: E402
from scripts.scalp_vol_1m import CACHE, MIN_MS  # noqa: E402

SORTEIOS = 20


def faixa(medias):
    m = np.array(medias)
    return f"média {m.mean():+.3f}R  (20 sorteios: de {m.min():+.3f} a {m.max():+.3f})"


def estatistica(valores):
    v = np.array(valores)
    t = v.mean() / v.std(ddof=1) * np.sqrt(len(v)) if len(v) > 1 and v.std() > 0 else float("nan")
    return f"{v.mean():+.3f}R  (n={len(v)}, t {t:+.1f})"


# ------------------------------------------------------------------ scalp
def checar_scalp():
    ev = pd.read_csv(os.path.join("data", "estudo_scalp_vol.csv"))
    ev = ev[ev["jogada"] == "A"].drop_duplicates("ts")
    um = pd.read_csv(CACHE).reset_index(drop=True)
    ts, h, l, c = (um[k].to_numpy(np.int64 if k == "timestamp" else float) for k in ("timestamp", "high", "low", "close"))
    fds = pd.to_datetime(ts, unit="ms").dayofweek.to_numpy() >= 5
    pos = {int(t): i for i, t in enumerate(ts)}
    base = dataclasses.replace(ParametrosScalpVol(), janela_barras=120, tempo_barras=60)
    sem_custo = dataclasses.replace(base, maker=0.0, taker=0.0, slip_stop=0.0, slip_tempo=0.0)
    eventos = []
    for row in ev.itertuples():
        i = pos.get(int(row.ts) + 4 * MIN_MS)
        if i is not None and i + 60 < len(c) and ts[i + 60] - ts[i] == 60 * MIN_MS:
            eventos.append((i, row.zona_hi - row.zona_lo))

    def rodar(p, jogada, lado_de):
        out = []
        for i, w in eventos:
            lado = lado_de(i)
            zona = (c[i] - w, c[i]) if lado == 1 else (c[i], c[i] + w)
            r = simular(i, ts, h, l, c, fds, zona, lado, jogada, p, barra_ms=MIN_MS)
            if r is not None:
                out.append(r)
        return out

    print(f"\nSCALP (simular, 1 min) · {len(eventos)} eventos")
    for jogada, nome in (("A", "a favor, alvo 2R"), ("B", "1:1")):
        print(f"  jogada {jogada} ({nome})")
        for rot, p, chave in (("sorteado, sem custo", sem_custo, "bruto_r"), ("sorteado, com custo", base, "liquido_r")):
            medias = []
            for semente in range(SORTEIOS):
                rng = np.random.default_rng(semente)
                tr = rodar(p, jogada, lambda i: int(rng.choice([1, -1])))
                medias.append(np.mean([x[chave] for x in tr]))
            print(f"    {rot:<22} {faixa(medias)}")
        # vê o futuro: a direção é para onde o preço estava 60 min depois (na B a jogada é contra o "impulso")
        futuro = (lambda i: 1 if c[i + 60] > c[i] else -1) if jogada == "A" else (lambda i: -1 if c[i + 60] > c[i] else 1)
        tr = rodar(sem_custo, jogada, futuro)
        print(f"    {'VÊ O FUTURO, sem custo':<22} {estatistica([x['bruto_r'] for x in tr])}")


# ------------------------------------------------------------------ laboratório 4h
def checar_lab():
    df = pd.read_csv(os.path.join("data", "historico", "BTCUSDT_binance_4h.csv")).sort_values("timestamp")
    df = df[df["timestamp"] >= int(pd.Timestamp("2019-12-01", tz="UTC").timestamp() * 1000)].reset_index(drop=True)
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    tr_ = np.maximum(h - l, np.maximum(abs(h - np.roll(c, 1)), abs(l - np.roll(c, 1))))
    atr = pd.Series(tr_).rolling(14).mean().to_numpy()
    entradas = [i for i in range(20, len(c) - 25, 6)]                  # um trade a cada 24 h

    def rodar(lado_de):
        return [gt.trade_gestao(lado_de(i), i, c[i], 1.5 * atr[i], c, h, l, horizonte=24, mult_alvo=3.0) for i in entradas]

    custos = (gt.TAXA_TAKER, gt.TAXA_MAKER, gt.SLIPPAGE)
    print(f"\nLABORATÓRIO 4h (trade_gestao, 5 fatias + tirar o risco) · {len(entradas)} entradas")
    for rot, chave, zerar in (("sorteado, sem custo", "bruto_r", True), ("sorteado, com custo", "liquido_r", False)):
        if zerar:
            gt.TAXA_TAKER = gt.TAXA_MAKER = gt.SLIPPAGE = 0.0
        medias = []
        for semente in range(SORTEIOS):
            rng = np.random.default_rng(semente)
            medias.append(np.mean([x[chave] for x in rodar(lambda i: int(rng.choice([1, -1])))]))
        gt.TAXA_TAKER, gt.TAXA_MAKER, gt.SLIPPAGE = custos
        print(f"    {rot:<22} {faixa(medias)}")
    gt.TAXA_TAKER = gt.TAXA_MAKER = gt.SLIPPAGE = 0.0
    tr = rodar(lambda i: 1 if c[i + 24] > c[i] else -1)
    gt.TAXA_TAKER, gt.TAXA_MAKER, gt.SLIPPAGE = custos
    print(f"    {'VÊ O FUTURO, sem custo':<22} {estatistica([x['bruto_r'] for x in tr])}")
    so_compra = rodar(lambda i: 1)
    print(f"    {'sempre comprado, com custo':<22} {estatistica([x['liquido_r'] for x in so_compra])}  (BTC subiu no período)")


if __name__ == "__main__":
    checar_scalp()
    checar_lab()
