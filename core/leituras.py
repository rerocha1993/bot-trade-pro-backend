# core/leituras.py
"""
LEITURA padronizada: a saída única de todo indicador independente.

Cada indicador continua sendo um módulo puro (core/tpo.py, core/vwap.py, ...), sem saber dos outros. Aqui ficam os
adaptadores que transformam a saída de cada um em uma `Leitura`:

    Leitura(fonte, vies, forca, acao, niveis[Nivel], motivo, dados, ts, validade_s)

O orquestrador (core/orquestrador/plano.py) e o motor tático (core/strategy_engine.py) só consomem Leituras.
Nenhum adaptador levanta exceção: em erro devolve uma leitura neutra com o motivo.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

from core.order_block import OrderBlockDetector
from core.order_flow import OrderFlowAnalyzerPro
from core.regime import analisar_regime
from core.tpo import TPOProfile
from core.volume_profile_pro import VolumeProfilePRO
from core.vwap import VWAPCalculator

VIES = ("bull", "bear", "neutro")


@dataclass
class Nivel:
    preco: float
    tipo: str            # 'resistencia' | 'suporte' | 'referencia'
    fonte: str           # 'tpo_poc', 'vwap_+2σ', 'ob_bearish', 'elliott_alvo', ...
    peso: float = 1.0
    rotulo: str = ""


@dataclass
class Leitura:
    fonte: str
    vies: str = "neutro"          # próximo movimento esperado
    forca: float = 0.0            # 0..1
    acao: str = "hold"            # sugestão bruta: buy | sell | hold
    niveis: List[Nivel] = field(default_factory=list)
    motivo: str = ""
    dados: Dict = field(default_factory=dict)
    ts: int = 0
    validade_s: int = 900
    erro: Optional[str] = None

    def __post_init__(self):
        if not self.ts:
            self.ts = int(time.time())
        if self.vies not in VIES:
            self.vies = "neutro"
        self.forca = max(0.0, min(1.0, float(self.forca or 0.0)))

    @property
    def valida(self) -> bool:
        return self.erro is None and time.time() - self.ts <= self.validade_s

    def dict(self) -> Dict:
        d = asdict(self)
        d["valida"] = self.valida
        return d


def _vies_de_acao(acao: Optional[str]) -> str:
    return "bull" if acao == "buy" else "bear" if acao == "sell" else "neutro"


def _lado(preco_nivel: float, preco: float) -> str:
    return "resistencia" if preco_nivel > preco else "suporte" if preco_nivel < preco else "referencia"


def _neutra(fonte: str, erro: str) -> Leitura:
    return Leitura(fonte=fonte, motivo=f"{fonte} indisponível: {erro}"[:200], erro=str(erro)[:200])


# ------------------------------------------------------------------ adaptadores
def leitura_tpo(ohlcv: Sequence, preco: float, bins: int = 30) -> Leitura:
    try:
        tp = TPOProfile(ohlcv, bins=bins)
        res = tp.analisar()
        s = tp.sinal_estrategico(preco)
        niveis = [Nivel(res["POC"], _lado(res["POC"], preco), "tpo_poc", 1.0, "POC"),
                  Nivel(res["VAH"], _lado(res["VAH"], preco), "tpo_vah", 1.5, "VAH"),
                  Nivel(res["VAL"], _lado(res["VAL"], preco), "tpo_val", 1.5, "VAL")]
        for h in (res.get("HVN") or [])[:2]:
            niveis.append(Nivel(float(h), _lado(h, preco), "tpo_hvn", 0.8, "HVN"))
        dados = {k: res.get(k) for k in ("POC", "VAH", "VAL", "shape", "HVN", "LVN")}
        return Leitura("tpo", _vies_de_acao(s.get("acao")), s.get("forca", 0.0), s.get("acao", "hold"), niveis, s.get("motivo", ""), dados)
    except Exception as e:
        return _neutra("tpo", str(e))


def leitura_volume_profile(ohlcv: Sequence, preco: float, bins: int = 40) -> Leitura:
    try:
        vp = VolumeProfilePRO(ohlcv, num_bins=bins)
        res = vp.analisar()
        s = vp.price_signal(preco)
        niveis = []
        for k, peso in (("POC", 1.0), ("VAH", 1.2), ("VAL", 1.2)):
            if res.get(k):
                niveis.append(Nivel(float(res[k]), _lado(res[k], preco), f"vp_{k.lower()}", peso, k))
        return Leitura("volume_profile", _vies_de_acao(s.get("acao")), s.get("forca", 0.0), s.get("acao", "hold"), niveis, s.get("motivo", ""),
                       {k: res.get(k) for k in ("POC", "VAH", "VAL")})
    except Exception as e:
        return _neutra("volume_profile", str(e))


def leitura_vwap(ohlcv: Sequence, preco: float) -> Leitura:
    try:
        v = VWAPCalculator(ohlcv)
        s = v.sinal(preco)
        bandas = s.get("bandas") or (v.vwap_bandas() or {}).get("bandas") or {}
        vwap = s.get("vwap")
        niveis = []
        if vwap:
            niveis.append(Nivel(float(vwap), _lado(vwap, preco), "vwap", 1.0, "VWAP"))
        for nome, val in bandas.items():
            if val and nome in ("+1σ", "-1σ", "+2σ", "-2σ"):
                niveis.append(Nivel(float(val), _lado(val, preco), f"vwap_{nome}", 0.8 if "1" in nome else 1.0, nome))
        return Leitura("vwap", _vies_de_acao(s.get("acao")), s.get("forca", 0.0), s.get("acao", "hold"), niveis, s.get("motivo", ""),
                       {"vwap": vwap, "z": s.get("z"), "bandas": bandas})
    except Exception as e:
        return _neutra("vwap", str(e))


def leitura_order_flow(order_book: Dict, trades: List[Dict], ohlcv: Sequence, timeframe: str = "15m") -> Leitura:
    try:
        s = OrderFlowAnalyzerPro(order_book or {"bids": [], "asks": []}, trades or [], ohlcv, timeframe=timeframe).analisar()
        return Leitura("order_flow", _vies_de_acao(s.get("acao")), s.get("forca", 0.0), s.get("acao", "hold"), [], s.get("motivo", ""),
                       {k: s.get(k) for k in ("delta", "razao_delta", "imbalance", "cvd", "absorcao")}, validade_s=120)
    except Exception as e:
        return _neutra("order_flow", str(e))


def leitura_order_block(ohlcv: Sequence, preco: float, raio: float = 0.05) -> Leitura:
    try:
        obd = OrderBlockDetector(ohlcv)
        s = obd.sinal(preco)
        niveis = []
        for b in obd.blocos_proximos(preco, "bearish", raio):
            lo, hi = b["zona"]
            niveis.append(Nivel(float(lo), "resistencia", "ob_bearish", 1.5, "OB oferta"))
        for b in obd.blocos_proximos(preco, "bullish", raio):
            lo, hi = b["zona"]
            niveis.append(Nivel(float(hi), "suporte", "ob_bullish", 1.5, "OB demanda"))
        return Leitura("order_block", _vies_de_acao(s.get("acao")), s.get("forca", 0.0), s.get("acao", "hold"), niveis, s.get("motivo", ""),
                       {"n_bullish": len(obd.identificar_blocks("bullish")), "n_bearish": len(obd.identificar_blocks("bearish"))})
    except Exception as e:
        return _neutra("order_block", str(e))


def leitura_fibonacci(ohlcv: Sequence, fase: str, direcao: str, janela: int = 200) -> Leitura:
    try:
        from core.fibonacci_strategies import FibonacciStrategies
        fib = FibonacciStrategies(ohlcv, janela=janela).para_fase(fase, direcao)
        preco = float(ohlcv[-1][4])
        niveis = []
        if fib.get("tp"):
            niveis.append(Nivel(float(fib["tp"]), _lado(fib["tp"], preco), "fib_alvo", 1.0, "alvo Fibonacci"))
        if fib.get("sl") and not fib.get("sl_fallback"):
            niveis.append(Nivel(float(fib["sl"]), _lado(fib["sl"], preco), "fib_protecao", 1.0, "proteção Fibonacci"))
        return Leitura("fibonacci", _vies_de_acao(direcao), 0.5 if fib.get("tp") else 0.0, "hold", niveis, fib.get("motivo", ""), fib)
    except Exception as e:
        return _neutra("fibonacci", str(e))


def leitura_regime(ohlcv: Sequence) -> Leitura:
    try:
        r = analisar_regime(ohlcv)
        permite = bool(r.get("permite_entrada", True))
        return Leitura("regime", "neutro", 0.0 if permite else 1.0, "hold", [], r.get("motivo", ""), r)
    except Exception as e:
        return _neutra("regime", str(e))


def leitura_sentimento(score: Optional[Dict]) -> Leitura:
    """Sentimento é filtro CONTRÁRIO: euforia = viés de baixa, medo = viés de alta."""
    if not score:
        return _neutra("sentimento", "sem dados")
    v = float(score.get("score") or 0.0)
    vies = "bear" if v >= 0.6 else "bull" if v <= -0.6 else "neutro"
    return Leitura("sentimento", vies, min(1.0, abs(v)), "hold", [], f"score {v:+.2f} · {score.get('zona')}",
                   {k: score.get(k) for k in ("score", "zona", "bloqueia_compra", "bloqueia_venda", "componentes")}, validade_s=600)


def leitura_elliott(grau: Optional[Dict], preco: float, nome: str = "elliott") -> Leitura:
    """Converte a análise de um grau (ScenarioEngine/analisar_serie) em Leitura com invalidação e alvos do primário."""
    if not grau or grau.get("erro"):
        return _neutra(nome, (grau or {}).get("erro") or "sem análise")
    prim = grau.get("primario") or {}
    pb, pr = float(grau.get("prob_bull") or 0), float(grau.get("prob_bear") or 0)
    vies = "bull" if pb >= 0.6 else "bear" if pr >= 0.6 else "neutro"
    niveis = []
    if prim.get("invalidacao"):
        niveis.append(Nivel(float(prim["invalidacao"]), _lado(prim["invalidacao"], preco), f"{nome}_invalidacao", 2.0, "invalidação"))
    for i, a in enumerate((prim.get("alvos") or [])[:3]):
        niveis.append(Nivel(float(a), _lado(a, preco), f"{nome}_alvo", 2.0 if i == 0 else 1.2, f"alvo {i + 1}"))
    for c in (grau.get("alternativos") or [])[:2]:
        for a in (c.get("alvos") or [])[:1]:
            niveis.append(Nivel(float(a), _lado(a, preco), f"{nome}_alt", 0.8, "alvo alternativo"))
    return Leitura(nome, vies, max(pb, pr), grau.get("direcao", "hold"), niveis,
                   f"{grau.get('fase')} · {prim.get('nome', '')} · bull {pb:.0%} / bear {pr:.0%}",
                   {"fase": grau.get("fase"), "prob_bull": pb, "prob_bear": pr, "primario": prim.get("nome"), "prob_sucesso": prim.get("prob_sucesso")})


def niveis_de(leituras: Sequence[Leitura]) -> List[Dict]:
    """Todos os níveis das leituras válidas no formato do agrupador de barreiras ({preco, fonte, peso})."""
    out = []
    for l in leituras:
        if l.erro:
            continue
        for n in l.niveis:
            out.append({"preco": n.preco, "fonte": n.fonte, "peso": n.peso, "tipo": n.tipo, "rotulo": n.rotulo})
    return out
