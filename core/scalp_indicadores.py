# core/scalp_indicadores.py
"""
SCALP POR INDICADORES (5m): o scalp sem Elliott, só com os indicadores que o usuário programou.

Por que sem Elliott, e só no scalp: em 1m a contagem trocava de fase em 45% das leituras — ruído, não
estrutura —, e nas leituras de scalp testadas em 30 dias nenhuma que dependia dela teve vantagem. Nos graus
maiores (daytrade, swing) Elliott continua sendo a lei; os vetos de ciclo do plano valem para todos.

Regra do usuário: NENHUM indicador de mercado novo — nada de EMA, RSI, MACD, Estocástico, Bollinger. Só
VARIAÇÕES dos que já existem no projeto:

    VWAP        -> VWAP da SESSÃO (âncora 00:00 UTC) e bandas de desvio ponderado por volume (core/vwap.py)
    TPO / VP    -> value area da SESSÃO ANTERIOR (VAL, POC, VAH) — referência clássica do Market Profile
                   (core/tpo.py, core/volume_profile_pro.py)
    Order Block -> blocos ativos, não mitigados, das últimas horas (core/order_block.py)
    Fibonacci   -> retração da perna da sessão
    Regime      -> eficiência de Kaufman em 5m: tendência x serrilhado (core/regime.py)
    Order Flow  -> delta de agressão do candle, quando há negócios (confirmação opcional)

O ATR aparece só onde já aparecia no projeto: no piso de ruído do stop.

Cada SETUP combina indicadores com funções diferentes — um diz o lado, outro diz se o mercado anda, outro dá
o gatilho, outro dá o risco. Nenhum decide sozinho, e nenhum repete a pergunta de outro.

Nada aqui olha o futuro: o contexto do candle t usa só candles até t (há teste para isso).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.order_block import OrderBlockDetector
from core.regime import analisar_regime
from core.tpo import TPOProfile
from core.utils_indicadores import atr as calc_atr
from core.volume_profile_pro import VolumeProfilePRO

DIA_MS = 86_400_000
# piso do stop: fora do ruído e bem acima do custo — o mesmo número do motor por candle e do motor de fluxo
RISCO_MINIMO_PCT = 0.0012
# o bot 4 é 'turbo': R:R líquido de custo mínimo de 1,0
RR_MINIMO = 1.0


@dataclass(slots=True)
class Ctx:
    """Tudo que os setups podem ver no fechamento de um candle de 5m — só com o que já aconteceu."""
    i: int
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float
    dia: int
    k: int                        # posição do candle dentro da sessão (0 = primeiro do dia)
    vwap: float                   # VWAP da sessão até este candle
    sigma: float                  # desvio ponderado por volume da sessão
    va_vp: Optional[Dict]         # value area da sessão ANTERIOR pelo Volume Profile
    va_tpo: Optional[Dict]        # value area da sessão ANTERIOR pelo TPO
    abertura_sessao: float
    maxima_sessao: float
    minima_sessao: float
    ts_max_sessao: int
    ts_min_sessao: int
    regime: str
    eficiencia: float
    atr: float
    blocos_bull: List[Dict]
    blocos_bear: List[Dict]
    delta: Optional[float] = None  # agressão líquida do candle, quando há negócios

    @property
    def posicao_no_candle(self) -> float:
        """Onde o candle fechou dentro do próprio range: 0 = na mínima, 1 = na máxima."""
        faixa = self.h - self.l
        return (self.c - self.l) / faixa if faixa > 0 else 0.5


@dataclass(frozen=True)
class Sinal:
    setup: str
    acao: str            # 'buy' | 'sell'
    entrada: float       # preço da ordem limitada
    sl: float
    tp: float
    motivo: str


# ------------------------------------------------------------------ contexto
def _value_areas(sessao: Sequence) -> tuple:
    """Value area de uma sessão inteira pelos dois indicadores do usuário: Volume Profile e TPO."""
    try:
        vp = VolumeProfilePRO(sessao, num_bins=40).poc_va()
        va_vp = {"VAL": float(vp["VAL"]), "POC": float(vp["POC"]), "VAH": float(vp["VAH"])}
    except Exception:
        va_vp = None
    try:
        t = TPOProfile(sessao, bins=30).calculate_poc_val_vah()
        va_tpo = {"VAL": float(t["VAL"]), "POC": float(t["POC"]), "VAH": float(t["VAH"])}
    except Exception:
        va_tpo = None
    return va_vp, va_tpo


def montar_contextos(candles: Sequence, deltas: Optional[Dict[int, float]] = None, janela_regime: int = 40,
                     janela_ob: int = 288, passo_ob: int = 12, minimo_sessao: int = 60) -> List[Ctx]:
    """
    Contexto de cada candle, calculado em sequência e só com o passado.

    - VWAP e desvio da sessão: acumulados desde 00:00 UTC (a mesma conta do core/vwap.py, incremental)
    - value area: da sessão anterior inteira; sessão incompleta (começo da série, buraco nos dados) não vale
    - order blocks: recalculados a cada `passo_ob` candles sobre as últimas `janela_ob`
    """
    dados = [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)] for c in candles]
    deltas = deltas or {}
    out: List[Ctx] = []
    dia_atual = None
    sessao: List[list] = []
    va_vp = va_tpo = None
    s_pv = s_v = s_pv2 = 0.0
    abertura = maxs = mins = 0.0
    ts_max = ts_min = 0
    k = 0
    bull: List[Dict] = []
    bear: List[Dict] = []
    for i, c in enumerate(dados):
        ts, o, h, l, cl, v = c
        dia = ts // DIA_MS
        if dia != dia_atual:
            va_vp, va_tpo = _value_areas(sessao) if len(sessao) >= minimo_sessao else (None, None)
            dia_atual, sessao, k = dia, [], 0
            s_pv = s_v = s_pv2 = 0.0
            abertura, maxs, mins, ts_max, ts_min = o, h, l, ts, ts
        sessao.append(c)
        tp = (h + l + cl) / 3.0
        s_pv += tp * v
        s_v += v
        s_pv2 += tp * tp * v
        if s_v > 0:
            vw = s_pv / s_v
            sig = math.sqrt(max(s_pv2 / s_v - vw * vw, 0.0))
        else:
            vw, sig = tp, 0.0
        if h > maxs:
            maxs, ts_max = h, ts
        if l < mins:
            mins, ts_min = l, ts
        janela = dados[max(0, i - 149):i + 1]
        if len(janela) >= 30:
            r = analisar_regime(janela, janela_regime)
            regime, efic = r["regime"], float(r["eficiencia"])
        else:
            regime, efic = "indefinido", 0.0
        a = calc_atr(dados[max(0, i - 20):i + 1], 14) or 0.0
        if i >= 30 and i % passo_ob == 0:
            try:
                obd = OrderBlockDetector(dados[max(0, i - janela_ob + 1):i + 1])
                bull, bear = obd.identificar_blocks("bullish"), obd.identificar_blocks("bearish")
            except ValueError:
                bull, bear = [], []
        out.append(Ctx(i, ts, o, h, l, cl, v, dia, k, vw, sig, va_vp, va_tpo, abertura, maxs, mins, ts_max, ts_min,
                       regime, efic, a, bull, bear, deltas.get(ts)))
        k += 1
    return out


# ------------------------------------------------------------------ montagem do sinal
def risco_minimo(x: Ctx) -> float:
    """Piso do stop: meio ATR, 0,12% do preço e 1,5x o custo de ida e volta — o que for maior."""
    custo = x.c * (TAXA_MAKER + TAXA_TAKER)
    return max(0.5 * x.atr, x.c * RISCO_MINIMO_PCT, 1.5 * custo)


def montar_sinal(setup: str, acao: str, x: Ctx, sl_estrutural: float, tp: Optional[float] = None,
                 rr_alvo: float = 2.0, rr_minimo: float = RR_MINIMO, motivo: str = "") -> Optional[Sinal]:
    """
    Entrada limitada no fechamento; stop estrutural respeitando o piso; alvo dado ou em múltiplos de R.
    Recusa quando o risco:retorno LÍQUIDO de custo fica abaixo do mínimo — o alvo é servido por ordem limitada
    (maker nos dois lados), o stop sai a mercado (maker na entrada, taker na saída).
    """
    s = 1 if acao == "buy" else -1
    entrada = x.c
    piso = risco_minimo(x)
    if (entrada - sl_estrutural) * s <= 0 or abs(entrada - sl_estrutural) < piso:
        sl = entrada - s * piso
    else:
        sl = sl_estrutural
    risco = abs(entrada - sl)
    if tp is None:
        tp = entrada + s * rr_alvo * risco
    ganho = (tp - entrada) * s
    if ganho <= 0:
        return None
    rr_liquido = (ganho - entrada * 2 * TAXA_MAKER) / (risco + entrada * (TAXA_MAKER + TAXA_TAKER))
    if rr_liquido < rr_minimo:
        return None
    return Sinal(setup, acao, round(entrada, 2), round(sl, 2), round(tp, 2), motivo)


def _mesma_sessao(a: Ctx, b: Ctx) -> bool:
    return a.dia == b.dia


# ------------------------------------------------------------------ setups
def setup_vwap_tendencia(ctxs: Sequence[Ctx], i: int, est: Dict) -> Optional[Sinal]:
    """
    RETOMADA NA VWAP. Lado: VWAP da sessão inclinada e preço do lado dela, do mesmo lado do POC da sessão
    anterior. Regime: tendência. Gatilho: recuo até a VWAP e fechamento de volta, longe do extremo contra.
    """
    x = ctxs[i]
    if i < 6 or x.k < 12 or x.regime not in ("tendencia", "expansao"):
        return None
    ant = ctxs[i - 6]
    if not _mesma_sessao(ant, x):
        return None
    inclinacao = x.vwap - ant.vwap
    zona = 0.25 * x.sigma
    poc = (x.va_vp or {}).get("POC")
    pos = x.posicao_no_candle
    if inclinacao > 0 and x.c > x.vwap and x.l <= x.vwap + zona and pos >= 0.5 and (poc is None or x.c > poc):
        return montar_sinal("vwap_tendencia", "buy", x, x.l - 0.1 * x.atr,
                            motivo=f"retomada na VWAP {x.vwap:,.0f} subindo, regime {x.regime}")
    if inclinacao < 0 and x.c < x.vwap and x.h >= x.vwap - zona and pos <= 0.5 and (poc is None or x.c < poc):
        return montar_sinal("vwap_tendencia", "sell", x, x.h + 0.1 * x.atr,
                            motivo=f"retomada na VWAP {x.vwap:,.0f} descendo, regime {x.regime}")
    return None


def setup_vwap_reversao(ctxs: Sequence[Ctx], i: int, est: Dict) -> Optional[Sinal]:
    """
    REVERSÃO NAS BANDAS. Regime: sem tendência limpa. Gatilho: o candle estica até ±2σ da VWAP da sessão e
    fecha de volta para dentro. Alvo: a própria VWAP.
    """
    x = ctxs[i]
    if x.k < 24 or x.sigma <= 0 or x.regime == "tendencia":
        return None
    inf, sup = x.vwap - 2 * x.sigma, x.vwap + 2 * x.sigma
    pos = x.posicao_no_candle
    if x.l <= inf and x.c > inf and pos >= 0.5:
        return montar_sinal("vwap_reversao", "buy", x, x.l - 0.1 * x.atr, tp=x.vwap,
                            motivo=f"rejeição na banda -2σ {inf:,.0f}, alvo na VWAP {x.vwap:,.0f}")
    if x.h >= sup and x.c < sup and pos <= 0.5:
        return montar_sinal("vwap_reversao", "sell", x, x.h + 0.1 * x.atr, tp=x.vwap,
                            motivo=f"rejeição na banda +2σ {sup:,.0f}, alvo na VWAP {x.vwap:,.0f}")
    return None


def _setup_value_area(nome: str, campo: str) -> Callable:
    """
    REGRA DOS 80% DO VALUE AREA (Market Profile). A sessão abre FORA do valor da sessão anterior e o preço volta
    para dentro, com dois fechamentos seguidos: a tendência é atravessar o valor até o outro lado. Uma vez por
    sessão e por lado. `campo` escolhe o indicador: 'va_vp' (Volume Profile) ou 'va_tpo' (TPO).
    """
    def setup(ctxs: Sequence[Ctx], i: int, est: Dict) -> Optional[Sinal]:
        x = ctxs[i]
        va = getattr(x, campo)
        if not va or i < 1 or x.k < 2:
            return None
        p = ctxs[i - 1]
        if not _mesma_sessao(p, x):
            return None
        val, vah = va["VAL"], va["VAH"]
        if vah <= val:
            return None
        dentro = lambda z: val < z.c < vah
        if x.abertura_sessao < val and dentro(p) and dentro(x) and not est.get((nome, x.dia, "buy")):
            est[(nome, x.dia, "buy")] = True
            return montar_sinal(nome, "buy", x, min(p.l, x.l) - 0.1 * x.atr, tp=vah,
                                motivo=f"abriu abaixo do valor ({val:,.0f}) e voltou: alvo no topo do valor {vah:,.0f}")
        if x.abertura_sessao > vah and dentro(p) and dentro(x) and not est.get((nome, x.dia, "sell")):
            est[(nome, x.dia, "sell")] = True
            return montar_sinal(nome, "sell", x, max(p.h, x.h) + 0.1 * x.atr, tp=val,
                                motivo=f"abriu acima do valor ({vah:,.0f}) e voltou: alvo no fundo do valor {val:,.0f}")
        return None
    setup.__name__ = f"setup_{nome}"
    return setup


def setup_ob_reteste(ctxs: Sequence[Ctx], i: int, est: Dict) -> Optional[Sinal]:
    """
    RETESTE DE ORDER BLOCK. Lado: a VWAP da sessão (acima dela só blocos de compra). Regime: não serrilhado.
    Gatilho: o preço volta ao bloco ativo e fecha de volta além dele. Cada bloco é usado uma vez.
    """
    x = ctxs[i]
    if x.k < 6 or x.regime == "serrilhado":
        return None
    usados = est.setdefault("ob_usados", set())
    pos = x.posicao_no_candle
    if x.c > x.vwap:
        for b in x.blocos_bull:
            lo, hi = b["zona"]
            if b["timestamp"] not in usados and x.l <= hi and x.l >= lo - 0.25 * x.atr and x.c > hi and pos >= 0.5:
                usados.add(b["timestamp"])
                return montar_sinal("ob_reteste", "buy", x, lo - 0.1 * x.atr,
                                    motivo=f"reteste do order block de compra {lo:,.0f}-{hi:,.0f} acima da VWAP")
    if x.c < x.vwap:
        for b in x.blocos_bear:
            lo, hi = b["zona"]
            if b["timestamp"] not in usados and x.h >= lo and x.h <= hi + 0.25 * x.atr and x.c < lo and pos <= 0.5:
                usados.add(b["timestamp"])
                return montar_sinal("ob_reteste", "sell", x, hi + 0.1 * x.atr,
                                    motivo=f"reteste do order block de venda {lo:,.0f}-{hi:,.0f} abaixo da VWAP")
    return None


def setup_fib_sessao(ctxs: Sequence[Ctx], i: int, est: Dict) -> Optional[Sinal]:
    """
    RECUO DE FIBONACCI DA SESSÃO. A perna do dia (da mínima à máxima, na ordem em que aconteceram) recua até a
    zona 50%–78,6% e o candle fecha de volta acima dos 50%, do lado da VWAP. Alvo: a extremidade da perna.
    Uma vez por sessão e por lado.
    """
    x = ctxs[i]
    if x.k < 24 or x.regime == "serrilhado":
        return None
    rng = x.maxima_sessao - x.minima_sessao
    if rng <= 0 or rng < 3 * x.atr:
        return None
    pos = x.posicao_no_candle
    if x.ts_min_sessao < x.ts_max_sessao < x.ts and x.c > x.vwap and not est.get(("fib", x.dia, "buy")):
        f50, f786 = x.maxima_sessao - 0.5 * rng, x.maxima_sessao - 0.786 * rng
        if f786 <= x.l <= f50 and x.c > f50 and pos >= 0.5:
            est[("fib", x.dia, "buy")] = True
            return montar_sinal("fib_sessao", "buy", x, f786 - 0.1 * x.atr, tp=x.maxima_sessao,
                                motivo=f"recuo de Fibonacci até {x.l:,.0f} na perna de alta do dia, alvo na máxima {x.maxima_sessao:,.0f}")
    if x.ts_max_sessao < x.ts_min_sessao < x.ts and x.c < x.vwap and not est.get(("fib", x.dia, "sell")):
        f50, f786 = x.minima_sessao + 0.5 * rng, x.minima_sessao + 0.786 * rng
        if f50 <= x.h <= f786 and x.c < f50 and pos <= 0.5:
            est[("fib", x.dia, "sell")] = True
            return montar_sinal("fib_sessao", "sell", x, f786 + 0.1 * x.atr, tp=x.minima_sessao,
                                motivo=f"recuo de Fibonacci até {x.h:,.0f} na perna de baixa do dia, alvo na mínima {x.minima_sessao:,.0f}")
    return None


def com_fluxo(setup: Callable) -> Callable:
    """Variação com ORDER FLOW: o sinal só vale se a agressão do candle do gatilho estiver a favor."""
    def filtrado(ctxs: Sequence[Ctx], i: int, est: Dict) -> Optional[Sinal]:
        x = ctxs[i]
        if x.delta is None:
            return None
        sig = setup(ctxs, i, est)
        if sig is None:
            return None
        return sig if (x.delta > 0) == (sig.acao == "buy") and x.delta != 0 else None
    filtrado.__name__ = f"{getattr(setup, '__name__', 'setup')}_com_fluxo"
    return filtrado


SETUPS: Dict[str, Callable] = {
    "vwap_tendencia": setup_vwap_tendencia,
    "vwap_reversao": setup_vwap_reversao,
    "va_vp": _setup_value_area("va_vp", "va_vp"),
    "va_tpo": _setup_value_area("va_tpo", "va_tpo"),
    "ob_reteste": setup_ob_reteste,
    "fib_sessao": setup_fib_sessao,
}
