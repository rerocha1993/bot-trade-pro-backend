# core/scalp_volatilidade.py
"""
SCALP DE VOLATILIDADE: só entra quando o mercado acorda, MEDIDO NOS DADOS (não numa agenda de notícias).

Regras combinadas com o usuário em 13/09/2026 e fixadas antes do backtest:

    detector   volatilidade dos últimos 15 min >= `vol_min` x a mediana dos 7 dias anteriores E volume dos últimos
               15 min >= `volume_min` x a mediana; sábado e domingo (UTC) não operam
    impulso    os 30 min até a detecção, num perfil TPO com colunas de 5 min (cada candle de 5 min é uma coluna)
    single     faixas de preço tocadas por UMA coluna só, contíguas, com pelo menos `sp_min_pct` do preço, atrás do
    print      preço (o vácuo que o impulso deixou) e fora das pontas do perfil (ponta é cauda, não single print)
    jogadas    A "a favor": o preço volta até a borda do single print e entra A FAVOR do impulso;
                 stop do outro lado do single print, alvo 2R, tira metade em 1R e leva o stop ao zero a zero
               B "preenchimento": no mesmo toque, entra CONTRA, apostando que o vácuo é preenchido;
                 alvo na outra borda do single print, stop à mesma distância (1:1)
    execução   candle de 5 min fechado, nunca no disparo; entrada limitada na borda (maker); no candle da entrada só
               vale o stop; stop primeiro quando stop e alvo caem no mesmo candle; saída por tempo em 60 min; a ordem
               vence no fim da janela de 120 min; uma jogada por janela
    custo      maker 0,02%; stop a mercado 0,055% + slippage de 0,05% (janela volátil); saída por tempo 0,055% + 0,02%

Resultado em R (1R = distância da entrada ao stop), líquido de custo.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

BARRA_MS = 5 * 60 * 1000


@dataclass(frozen=True)
class ParametrosScalpVol:
    barras_vol: int = 3             # 15 min de candles de 5 min
    base_barras: int = 2016         # 7 dias
    vol_min: float = 3.0
    volume_min: float = 3.0
    impulso_barras: int = 6         # 30 min
    janela_barras: int = 24         # 120 min para a ordem executar
    tempo_barras: int = 12          # 60 min de trade
    tick_pct: float = 0.0002        # faixa do perfil: 0,02% do preço
    sp_min_pct: float = 0.0015      # single print com pelo menos 0,15% do preço
    folga_stop_pct: float = 0.0005
    alvo_r: float = 2.0
    realizar: float = 0.5
    maker: float = 0.0002
    taker: float = 0.00055
    slip_stop: float = 0.0005
    slip_tempo: float = 0.0002
    fim_de_semana: bool = False     # False = não opera sábado e domingo


# ------------------------------------------------------------------ medidas
def medidas(h: np.ndarray, l: np.ndarray, c: np.ndarray, v: np.ndarray,
            p: ParametrosScalpVol = ParametrosScalpVol()) -> Tuple[np.ndarray, np.ndarray]:
    """
    (vol_rel, volume_rel) de cada candle: a janela de 15 min que TERMINA nele contra a mediana dos 7 dias
    anteriores a essa janela (a base não inclui a própria janela, senão o pico diluiria a si mesmo).
    """
    amp = pd.Series((h - l) / c)
    vol15 = amp.rolling(p.barras_vol).sum()
    base = vol15.shift(p.barras_vol).rolling(p.base_barras, min_periods=p.base_barras // 2).median()
    volu = pd.Series(v, dtype=float).rolling(p.barras_vol).sum()
    base_v = volu.shift(p.barras_vol).rolling(p.base_barras, min_periods=p.base_barras // 2).median()
    vol_rel = (vol15 / base).replace([np.inf, -np.inf], np.nan).to_numpy()
    volume_rel = (volu / base_v).replace([np.inf, -np.inf], np.nan).to_numpy()
    return vol_rel, volume_rel


# ------------------------------------------------------------------ single prints
def zonas_single_print(h: Sequence[float], l: Sequence[float], preco: float,
                       p: ParametrosScalpVol = ParametrosScalpVol()) -> List[Tuple[float, float]]:
    """Zonas (baixo, alto) tocadas por uma coluna só, contíguas, com tamanho mínimo e sem encostar nas pontas."""
    h, l = np.asarray(h, dtype=float), np.asarray(l, dtype=float)
    tick = preco * p.tick_pct
    base = math.floor(float(l.min()) / tick) * tick
    n = int(math.floor((float(h.max()) - base) / tick)) + 1
    cont = np.zeros(n, dtype=int)
    for alto, baixo in zip(h, l):
        a = max(int(math.floor((baixo - base) / tick)), 0)
        z = min(int(math.floor((alto - base) / tick)), n - 1)
        cont[a:z + 1] += 1
    zonas = []
    i = 0
    while i < n:
        if cont[i] != 1:
            i += 1
            continue
        j = i
        while j + 1 < n and cont[j + 1] == 1:
            j += 1
        if i > 0 and j < n - 1 and (j - i + 1) * tick >= p.sp_min_pct * preco:
            zonas.append((base + i * tick, base + (j + 1) * tick))
        i = j + 1
    return zonas


def escolher_zona(zonas: Sequence[Tuple[float, float]], preco: float, lado_impulso: int) -> Optional[Tuple[float, float]]:
    """O vácuo mais perto ATRÁS do preço: embaixo num impulso de alta, em cima num de baixa."""
    if lado_impulso == 1:
        atras = [z for z in zonas if z[1] < preco]
        return max(atras, key=lambda z: z[1]) if atras else None
    atras = [z for z in zonas if z[0] > preco]
    return min(atras, key=lambda z: z[0]) if atras else None


# ------------------------------------------------------------------ uma jogada
def simular(i: int, ts: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, fds: np.ndarray,
            zona: Tuple[float, float], lado_impulso: int, jogada: str,
            p: ParametrosScalpVol = ParametrosScalpVol(), barra_ms: int = BARRA_MS) -> Optional[Dict]:
    """
    Detecção no candle `i` (fechado). Devolve o trade, ou None se a ordem não executou.
    `barra_ms` permite executar em candles de 1 min (janela e tempo em `p` passam a contar minutos).
    """
    lo, hi = zona
    n = len(c)
    if jogada == "A":
        s = lado_impulso
        entrada = hi if lado_impulso == 1 else lo
        stop = lo * (1 - p.folga_stop_pct) if s == 1 else hi * (1 + p.folga_stop_pct)
        risco = abs(entrada - stop)
        alvo = entrada + s * p.alvo_r * risco
        um_r: Optional[float] = entrada + s * risco
    else:
        s = -lado_impulso
        entrada = hi if lado_impulso == 1 else lo
        alvo = lo if lado_impulso == 1 else hi
        risco = abs(entrada - alvo)
        stop = entrada - s * risco
        um_r = None
    if risco <= 0:
        return None

    j = None
    for k in range(i + 1, min(i + 1 + p.janela_barras, n)):
        if ts[k] - ts[i] != (k - i) * barra_ms or fds[k]:
            return None                                    # buraco nos dados ou fim de semana: não opera
        if (l[k] <= entrada) if lado_impulso == 1 else (h[k] >= entrada):
            j = k
            break
    if j is None:
        return None

    q = 1.0 / risco
    estado = {"realizado": 0.0, "custo": entrada * p.maker * q, "frac": 1.0}

    def fechar(preco_saida: float, taxa: float, motivo: str, k_saida: int) -> Dict:
        bruto = estado["realizado"] + (preco_saida - entrada) * s * q * estado["frac"]
        custo = estado["custo"] + preco_saida * taxa * q * estado["frac"]
        return {"ts": int(ts[i]), "ts_entrada": int(ts[j]), "i_entrada": j, "i_saida": k_saida, "lado": s,
                "jogada": jogada, "entrada": entrada, "stop": stop, "alvo": alvo, "bruto_r": bruto, "custo_r": custo,
                "liquido_r": bruto - custo, "motivo": motivo}

    # no candle da entrada não se sabe a ordem dos preços: só o stop vale
    if (l[j] <= stop) if s == 1 else (h[j] >= stop):
        return fechar(stop * (1 - s * p.slip_stop), p.taker, "stop", j)

    stop_atual, parcial = stop, False
    fim = min(j + 1 + p.tempo_barras, n)
    for k in range(j + 1, fim):
        if ts[k] - ts[j] != (k - j) * barra_ms:
            return fechar(c[k - 1] * (1 - s * p.slip_tempo), p.taker, "buraco", k - 1)
        if (l[k] <= stop_atual) if s == 1 else (h[k] >= stop_atual):
            return fechar(stop_atual * (1 - s * p.slip_stop), p.taker, "zero_a_zero" if parcial else "stop", k)
        if um_r is not None and not parcial and ((h[k] >= um_r) if s == 1 else (l[k] <= um_r)):
            estado["realizado"] += (um_r - entrada) * s * q * p.realizar
            estado["custo"] += um_r * p.maker * q * p.realizar
            estado["frac"] = 1.0 - p.realizar
            stop_atual, parcial = entrada, True
        if (h[k] >= alvo) if s == 1 else (l[k] <= alvo):
            return fechar(alvo, p.maker, "alvo", k)
    k = fim - 1
    return fechar(c[k] * (1 - s * p.slip_tempo), p.taker, "tempo", k)


# ------------------------------------------------------------------ estudo
class EstudoScalpVol:
    def __init__(self, df: pd.DataFrame, p: ParametrosScalpVol = ParametrosScalpVol()):
        self.p = p
        self.ts = df["timestamp"].to_numpy(np.int64)
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.v = df["volume"].to_numpy(float)
        self.fds = pd.to_datetime(self.ts, unit="ms").dayofweek.to_numpy() >= 5
        self.vol_rel, self.volume_rel = medidas(self.h, self.l, self.c, self.v, p)

    def candidatos(self, regra: str = "volatil", limiar: Optional[float] = None) -> np.ndarray:
        p = self.p
        with np.errstate(invalid="ignore"):
            if regra == "volatil":
                cond = (self.vol_rel >= (limiar or p.vol_min)) & (self.volume_rel >= (limiar or p.volume_min))
            elif regra == "calmo":
                # controle: mercado parado, amostrado a cada 30 min
                cond = (self.vol_rel < 1.5) & (self.volume_rel < 1.5) & (np.arange(len(self.c)) % p.impulso_barras == 0)
            else:
                raise ValueError(regra)
        if not p.fim_de_semana:
            cond &= ~self.fds
        return np.flatnonzero(cond)

    def eventos(self, regra: str = "volatil", limiar: Optional[float] = None) -> List[int]:
        """Um evento por janela: detecções dentro dos 120 min seguintes são o mesmo evento."""
        out, livre = [], 0
        for i in self.candidatos(regra, limiar):
            if i >= livre:
                out.append(int(i))
                livre = i + self.p.janela_barras
        return out

    def trades(self, regra: str = "volatil", jogada: str = "A", limiar: Optional[float] = None) -> List[Dict]:
        p = self.p
        out: List[Dict] = []
        livre = 0
        for i in self.candidatos(regra, limiar):
            if i < livre or i < p.impulso_barras:
                continue
            a = i - p.impulso_barras + 1
            if self.ts[i] - self.ts[a] != (i - a) * BARRA_MS:
                continue
            lado = 1 if self.c[i] > self.o[a] else -1 if self.c[i] < self.o[a] else 0
            if lado == 0:
                continue
            zona = escolher_zona(zonas_single_print(self.h[a:i + 1], self.l[a:i + 1], self.c[i], p), self.c[i], lado)
            if zona is None:
                continue                                   # sem vácuo atrás do preço: o evento segue, sem jogada ainda
            r = simular(i, self.ts, self.h, self.l, self.c, self.fds, zona, lado, jogada, p)
            livre = i + p.janela_barras
            if r is not None:
                livre = max(livre, r["i_saida"] + 1)
                r.update(vol_rel=float(self.vol_rel[i]), volume_rel=float(self.volume_rel[i]),
                         zona_lo=zona[0], zona_hi=zona[1], lado_impulso=lado)
                out.append(r)
        return out


def resumo(trades: Sequence[Dict]) -> Dict:
    if not trades:
        return {"trades": 0}
    t = np.array([x["liquido_r"] for x in trades])
    b = np.array([x["bruto_r"] for x in trades])
    ganhos, perdas = t[t > 0].sum(), -t[t < 0].sum()
    desvio = t.std(ddof=1) if len(t) > 1 else 0.0
    return {"trades": len(t), "acerto": float((t > 0).mean()), "medio_r": float(t.mean()), "bruto_r": float(b.mean()),
            "soma_r": float(t.sum()), "fl": round(float(ganhos / perdas), 2) if perdas > 0 else None,
            "t": float(t.mean() / desvio * math.sqrt(len(t))) if desvio > 0 else None,
            "saidas": Counter(x["motivo"] for x in trades)}
