# tradeiros/leitura.py
"""
LEITURA DIÁRIA do Tradeiros, feita como eles abrem a live — e sempre COMO SE FOSSE NAQUELE MOMENTO: só entra o que
já tinha fechado até `ts`, para o imitador e o backtest nunca enxergarem o futuro.

    range        merge adaptativo dos dias anteriores (~10–12 dias quando lateral): VAL, POC, VAH, fundo e topo
    posição      p = (preço − VAL) / (VAH − VAL): 0 = VAL, 1 = VAH; zona fundo / meio / topo (regras R1 e R3)
    níveis       naked POCs diários; abertura do dia, da semana e do mês; pivô diário virgem acima e abaixo
    estrutura    topos e fundos confirmados no 4h (ZigZag em ATR): tendência e quebra de estrutura (R11, R12)
    Fibonacci    retrações 0,382 / 0,5 / 0,618 / 0,666 / 0,786 do último movimento confirmado no 4h
    ciclo        distância do topo histórico: esticado (perto do ATH) × descontado (R31)
    sentimento   Fear & Greed do dia
    derivativos  funding (último e média de 30 dias), open interest contra a máxima de 30 dias (reset), long/short
                 de contas contra a mediana de 30 dias
"""
from __future__ import annotations

import bisect
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from core.elliott_pro.pivots import Pivot, zigzag_atr
from core.fibonacci import Fibonacci
from core.range_tradeiros import ParametrosRange, contexto_adaptativo
from core.tpo_sessao import BLOCO_MS, DIA_MS, Perfil, blocos_30m, naked_pocs

H4_MS = 4 * 3_600_000
RETRACOES = (0.382, 0.5, 0.618, 0.666, 0.786)


@dataclass(frozen=True)
class ParametrosLeitura:
    dias_merge_min: int = 3
    dias_merge_max: int = 20
    meio_largura: float = 0.15          # |p − 0,5| < 0,15 → meio do range: não abrir posição (R1)
    quartil: float = 0.25               # p ≤ 0,25 → fundo; p ≥ 0,75 → topo (R3)
    fator_zigzag_4h: float = 2.5
    quebra_barras: int = 6              # quebra de estrutura nos últimos 6 candles de 4h (24 h)
    esticado_do_topo: float = -0.10     # até 10% abaixo do ATH = esticado
    descontado_do_topo: float = -0.30   # mais de 30% abaixo do ATH = descontado
    janela_virgem_dias: int = 30


@dataclass
class Leitura:
    ts: int
    preco: float
    range: Optional[Dict] = None
    p: Optional[float] = None
    zona: str = "sem_range"
    naked_pocs: List[float] = field(default_factory=list)
    aberturas: Dict[str, Optional[float]] = field(default_factory=dict)
    pivo_virgem: Dict[str, Optional[float]] = field(default_factory=dict)
    estrutura: Dict = field(default_factory=dict)
    fib: Dict = field(default_factory=dict)
    ciclo: Dict = field(default_factory=dict)
    sentimento: Optional[int] = None
    derivativos: Dict = field(default_factory=dict)

    def as_dict(self) -> Dict:
        return asdict(self)


# ------------------------------------------------------------------ peças puras (testáveis sozinhas)
def posicao_no_range(preco: float, val: float, vah: float) -> Optional[float]:
    largura = vah - val
    return None if largura <= 0 else (preco - val) / largura


def zona_do_range(p: Optional[float], prm: ParametrosLeitura = ParametrosLeitura()) -> str:
    if p is None:
        return "sem_range"
    if p < 0:
        return "abaixo_do_valor"
    if p > 1:
        return "acima_do_valor"
    if abs(p - 0.5) < prm.meio_largura:
        return "meio"
    if p <= prm.quartil:
        return "fundo"
    if p >= 1 - prm.quartil:
        return "topo"
    return "entre_fundo_e_meio" if p < 0.5 else "entre_meio_e_topo"


def estrutura_dos_pivos(pivos: Sequence[Pivot], closes_recentes: Sequence[float]) -> Dict:
    """Tendência pelos dois últimos topos e fundos confirmados; quebra = fechamento recente além do último."""
    conf = [x for x in pivos if x.confirmado]
    topos = [x.preco for x in conf if x.tipo == "H"][-2:]
    fundos = [x.preco for x in conf if x.tipo == "L"][-2:]
    tendencia = "indefinida"
    if len(topos) == 2 and len(fundos) == 2:
        if topos[1] > topos[0] and fundos[1] > fundos[0]:
            tendencia = "alta"
        elif topos[1] < topos[0] and fundos[1] < fundos[0]:
            tendencia = "baixa"
        else:
            tendencia = "lateral"
    ultimo_topo = topos[-1] if topos else None
    ultimo_fundo = fundos[-1] if fundos else None
    quebra = None
    if ultimo_topo is not None and any(c > ultimo_topo for c in closes_recentes):
        quebra = "alta"
    if ultimo_fundo is not None and any(c < ultimo_fundo for c in closes_recentes):
        quebra = "baixa" if quebra is None else "ambas"
    return {"tendencia": tendencia, "ultimo_topo": ultimo_topo, "ultimo_fundo": ultimo_fundo, "quebra": quebra}


def fib_do_ultimo_movimento(pivos: Sequence[Pivot]) -> Dict:
    conf = [x for x in pivos if x.confirmado]
    if len(conf) < 2:
        return {}
    a, b = conf[-2], conf[-1]
    f = Fibonacci.de_swing(a.preco, b.preco)
    return {"de": a.preco, "ate": b.preco, "direcao": f.direcao,
            "niveis": {str(r): f.retracao(r) for r in RETRACOES}}


def pivo_virgem(diarios: Sequence[Sequence[float]], preco: float, janela: int = 30) -> Dict[str, Optional[float]]:
    """Abertura de um dia que nenhum dia seguinte voltou a tocar (gente presa ali); o mais perto acima e abaixo."""
    ult = list(diarios)[-janela:]
    virgens = []
    for i, d in enumerate(ult):
        abertura = float(d[1])
        if all(not (float(x[3]) <= abertura <= float(x[2])) for x in ult[i + 1:]) and i < len(ult) - 1:
            virgens.append(abertura)
    acima = [v for v in virgens if v > preco]
    abaixo = [v for v in virgens if v < preco]
    return {"acima": min(acima) if acima else None, "abaixo": max(abaixo) if abaixo else None}


# ------------------------------------------------------------------ dados e leitura no tempo
def _serie_ts(d: Dict) -> Tuple[List[int], List[float]]:
    pares = sorted((int(k), float(v)) for k, v in d.items())
    return [p[0] for p in pares], [p[1] for p in pares]


class Dados:
    """Históricos carregados uma vez; toda consulta é 'até ts'."""

    def __init__(self, d1: pd.DataFrame, h4: pd.DataFrame, m15: Optional[pd.DataFrame] = None,
                 funding: Optional[Dict] = None, oi: Optional[Dict] = None, lsr: Optional[Dict] = None,
                 fear: Optional[pd.DataFrame] = None):
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        self.d1 = d1[cols].sort_values("timestamp").values.tolist()
        self.h4 = h4[cols].sort_values("timestamp").values.tolist()
        self.d1_ts = [int(x[0]) for x in self.d1]
        self.h4_ts = [int(x[0]) for x in self.h4]
        self.blocos = blocos_30m(m15[cols].sort_values("timestamp").values.tolist()) if m15 is not None else []
        self.blocos_ts = [int(b[0]) for b in self.blocos]
        self.funding = _serie_ts(funding) if funding else ([], [])
        self.oi = _serie_ts(oi) if oi else ([], [])
        self.lsr = _serie_ts(lsr) if lsr else ([], [])
        if fear is not None:
            f = fear.sort_values("timestamp")
            self.fear = ([int(t) for t in f["timestamp"]], [int(v) for v in f["valor"]])
        else:
            self.fear = ([], [])
        self._perfis: Dict[int, Perfil] = {}

    @classmethod
    def do_projeto(cls, raiz: str = ".") -> "Dados":
        h = os.path.join(raiz, "data", "historico")

        def csv(nome):
            caminho = os.path.join(h, nome)
            return pd.read_csv(caminho) if os.path.exists(caminho) else None

        def js(nome, chave=None):
            caminho = os.path.join(h, nome)
            if not os.path.exists(caminho):
                return None
            d = json.load(open(caminho, encoding="utf-8"))
            return d.get(chave) if chave else d

        return cls(csv("BTCUSDT_binance_1d.csv"), csv("BTCUSDT_binance_4h.csv"), csv("BTCUSDT_binance_15m.csv"),
                   js("funding_bybit.json", "inverse"), js("oi_bybit_1h.json"), js("lsr_bybit_1h.json"),
                   csv("fear_greed.csv"))

    # --- recortes "até ts" (candle só conta depois de FECHADO)
    def diarios_ate(self, ts: int) -> List[list]:
        return self.d1[:bisect.bisect_right(self.d1_ts, ts - DIA_MS)]

    def h4_ate(self, ts: int) -> List[list]:
        return self.h4[:bisect.bisect_right(self.h4_ts, ts - H4_MS)]

    def blocos_ate(self, ts: int) -> List[tuple]:
        return self.blocos[:bisect.bisect_right(self.blocos_ts, ts - BLOCO_MS)]

    def perfil_do_dia(self, dia: int) -> Optional[Perfil]:
        if dia not in self._perfis:
            ini = bisect.bisect_left(self.blocos_ts, dia * DIA_MS)
            fim = bisect.bisect_left(self.blocos_ts, (dia + 1) * DIA_MS)
            bl = self.blocos[ini:fim]
            self._perfis[dia] = Perfil(bl) if len(bl) >= 40 else None
        return self._perfis[dia]

    @staticmethod
    def ultimo(serie: Tuple[List[int], List[float]], ts: int) -> Optional[float]:
        i = bisect.bisect_right(serie[0], ts) - 1
        return serie[1][i] if i >= 0 else None

    @staticmethod
    def janela(serie: Tuple[List[int], List[float]], ts: int, ms: int) -> List[float]:
        a = bisect.bisect_right(serie[0], ts - ms)
        b = bisect.bisect_right(serie[0], ts)
        return serie[1][a:b]


class LeituraDiaria:
    def __init__(self, dados: Dados, prm: ParametrosLeitura = ParametrosLeitura()):
        self.dados = dados
        self.prm = prm

    def ler(self, ts: int) -> Leitura:
        d, prm = self.dados, self.prm
        h4 = d.h4_ate(ts)
        blocos = d.blocos_ate(ts)
        diarios = d.diarios_ate(ts)
        if blocos:
            preco = float(blocos[-1][4])
        elif h4:
            preco = float(h4[-1][4])
        elif diarios:
            preco = float(diarios[-1][4])
        else:
            raise ValueError("sem dados até esse momento")
        lt = Leitura(ts=ts, preco=preco)

        # range: merge adaptativo dos dias COMPLETOS anteriores
        hoje = ts // DIA_MS
        perfis = [pf for pf in (d.perfil_do_dia(x) for x in range(hoje - prm.dias_merge_max, hoje)) if pf is not None]
        if len(perfis) >= prm.dias_merge_min:
            ctx = contexto_adaptativo(perfis, ParametrosRange(min_dias=prm.dias_merge_min, max_dias=prm.dias_merge_max))
            if ctx is not None:
                lt.range = {"val": float(ctx.val), "poc": float(ctx.poc), "vah": float(ctx.vah),
                            "minima": float(ctx.minima), "maxima": float(ctx.maxima), "dias": int(ctx.dias),
                            "valido": bool(ctx.valido)}
                lt.p = posicao_no_range(preco, lt.range["val"], lt.range["vah"])
                lt.zona = zona_do_range(lt.p, prm)
            lt.naked_pocs = sorted(float(x["preco"]) for x in naked_pocs(perfis))

        # aberturas do dia, da semana (segunda UTC) e do mês
        if diarios:
            ult = diarios[-1]
            dia_atual = pd.Timestamp(ts, unit="ms")
            ini_semana = int((dia_atual.normalize() - pd.Timedelta(days=dia_atual.dayofweek)).timestamp() * 1000)
            ini_mes = int(dia_atual.normalize().replace(day=1).timestamp() * 1000)

            def abertura_desde(t0):
                i = bisect.bisect_left(d.d1_ts, t0)
                return float(d.d1[i][1]) if i < len(d.d1) and d.d1_ts[i] <= ts else None

            lt.aberturas = {"dia": abertura_desde(hoje * DIA_MS), "semana": abertura_desde(ini_semana),
                            "mes": abertura_desde(ini_mes), "fechamento_ontem": float(ult[4])}
            lt.pivo_virgem = pivo_virgem(diarios, preco, prm.janela_virgem_dias)
            ath = max(float(x[2]) for x in diarios)
            do_topo = preco / ath - 1
            estado = "esticado" if do_topo >= prm.esticado_do_topo else "descontado" if do_topo <= prm.descontado_do_topo else "intermediario"
            lt.ciclo = {"ath": ath, "do_topo": round(do_topo, 4), "estado": estado}

        # estrutura e Fibonacci no 4h
        if len(h4) >= 60:
            pivos, _ = zigzag_atr(h4[-600:], fator_atr=prm.fator_zigzag_4h)
            closes = [float(x[4]) for x in h4[-prm.quebra_barras:]]
            lt.estrutura = estrutura_dos_pivos(pivos, closes)
            lt.fib = fib_do_ultimo_movimento(pivos)

        # sentimento e derivativos
        fg = d.ultimo(d.fear, ts)
        lt.sentimento = int(fg) if fg is not None else None
        fund = d.ultimo(d.funding, ts)
        fund30 = d.janela(d.funding, ts, 30 * DIA_MS)
        oi = d.ultimo(d.oi, ts - 3_600_000)
        oi30 = d.janela(d.oi, ts - 3_600_000, 30 * DIA_MS)
        lsr = d.ultimo(d.lsr, ts - 3_600_000)
        lsr30 = sorted(d.janela(d.lsr, ts - 3_600_000, 30 * DIA_MS))
        lt.derivativos = {
            "funding": fund, "funding_media_30d": (sum(fund30) / len(fund30)) if fund30 else None,
            "oi_vs_max_30d": (oi / max(oi30) - 1) if (oi and oi30) else None,
            "long_short": lsr, "long_short_mediana_30d": lsr30[len(lsr30) // 2] if lsr30 else None,
        }
        return lt
