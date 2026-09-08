# core/inverse_range.py
"""
Modo INVERSE de acumulação de BTC: short-only em range, com escada de Fibonacci.

Ideia (do usuário): dentro de um range lateral (ex.: 61k-85k) traça-se o Fibonacci do fundo ao topo.
Subindo, o bot vende (aumenta o short) a cada nível; no topo a carteira está 100% short (= hedge
perfeito, "em dólar"). Descendo, recompra a cada nível até zerar no fundo. Cada perna paga em BTC:
    P&L_BTC(short) = contratos x (1/preco_saida - 1/preco_entrada)   (contratos de 1 USD; lucra quando o preço cai)
    ex.: 80 000 contratos vendidos a 80 000 e recomprados a 62 000 -> 80 000 x (1/62 000 - 1/80 000) = +0,29 BTC
Se o topo romper (fechamento acima de topo x (1 + folga)), zera tudo e espera um range novo.

Short de base guiado por Elliott: se a contagem mestre (travada ou calculada) aponta queda ABAIXO do
fundo do range, uma fatia (até `short_base_max` x probabilidade do cenário) não é zerada no fundo e
segue até o alvo de Elliott; ela é fechada se o cenário for invalidado. Se a contagem mestre é de
ALTA forte, a escada é limitada a `teto_escada_alta` (50%) e o stop fica mais perto.

Timeframes: range e leitura de longo prazo no DIÁRIO (contagem mestre); escada executada no 4h.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Sequence

NIVEIS_FIB = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
ESCADA_PADRAO = {"0.0": 0.0, "0.236": 0.10, "0.382": 0.25, "0.5": 0.40, "0.618": 0.60, "0.786": 0.80, "1.0": 1.0}


@dataclass
class RangeConfig:
    low: float
    high: float
    origem: str = "manual"            # manual | elliott | pivots
    folga_stop: float = 0.01          # fechamento acima de high*(1+folga) = stop
    escada: Dict[str, float] = field(default_factory=lambda: dict(ESCADA_PADRAO))
    short_base_max: float = 0.5       # fatia máxima carregada no fundo quando Elliott aponta mais queda
    teto_escada_alta: float = 0.5     # teto da escada quando a contagem mestre é de alta forte
    histerese: float = 0.003          # fração do range para não oscilar na borda de um nível

    def dict(self):
        return asdict(self)


def nivel_preco(cfg: RangeConfig, nivel: float) -> float:
    return cfg.low + nivel * (cfg.high - cfg.low)


def posicao_no_range(cfg: RangeConfig, preco: float) -> float:
    if cfg.high <= cfg.low:
        return 0.0
    return max(0.0, min(1.0, (preco - cfg.low) / (cfg.high - cfg.low)))


def alocacao_escada(cfg: RangeConfig, preco: float, alocacao_atual: float = 0.0) -> float:
    """
    Alocação-alvo pela escada (fração 0..1 da carteira em short).
    Degrau = maior nível de Fibonacci cujo preço já foi atingido. Histerese: para SUBIR de degrau o preço
    precisa passar o nível por `histerese` do range; para DESCER, ficar abaixo por `histerese`.
    """
    pos = posicao_no_range(cfg, preco)
    h = cfg.histerese
    niveis = sorted(float(k) for k in cfg.escada)
    alvo = 0.0
    for n in niveis:
        limite = (n - h) if n >= 1.0 else (n + h)     # o topo (100%) conta ao ser tocado
        if pos >= limite:
            alvo = cfg.escada[str(n) if str(n) in cfg.escada else f"{n}"]
    # se a escada atual é maior que o alvo, só reduz quando o preço passar abaixo do nível com histerese
    if alocacao_atual > alvo:
        for n in niveis:
            if cfg.escada.get(str(n)) == alocacao_atual and pos >= n - h:
                return alocacao_atual
    return alvo


def decidir_alocacao(cfg: RangeConfig, preco_fechamento: float, alocacao_atual: float, mestre: Optional[Dict] = None,
                     estado: str = "ativo") -> Dict:
    """
    Devolve {'alvo': fração short, 'estado': 'ativo'|'stopado'|'carregando', 'motivo', 'short_base'}.
    mestre: {'vies': 'bull'|'bear', 'alvos': [...], 'invalidacao': float, 'prob_sucesso': float, 'status': 'ativa'|'invalidada'}
    """
    if estado == "stopado":
        return {"alvo": 0.0, "estado": "stopado", "motivo": "aguardando novo range aprovado", "short_base": 0.0}
    # stop: fechamento acima do topo com folga
    if preco_fechamento > cfg.high * (1 + cfg.folga_stop):
        return {"alvo": 0.0, "estado": "stopado", "motivo": f"rompeu o topo {cfg.high:.0f} (+{cfg.folga_stop:.1%}): zera e espera novo range",
                "short_base": 0.0}

    escada = alocacao_escada(cfg, preco_fechamento, alocacao_atual)
    short_base = 0.0
    teto = 1.0
    motivo = f"escada: preço em {posicao_no_range(cfg, preco_fechamento):.0%} do range -> {escada:.0%} short"
    if mestre and mestre.get("status", "ativa") == "ativa":
        prob = float(mestre.get("prob_sucesso") or mestre.get("probabilidade") or 0.5)
        alvos = [a for a in (mestre.get("alvos") or []) if a]
        if mestre.get("vies") == "bear" and alvos and min(alvos) < cfg.low:
            short_base = round(cfg.short_base_max * prob, 3)
            motivo += f" | Elliott bear com alvo {min(alvos):.0f} abaixo do fundo: short de base {short_base:.0%}"
        elif mestre.get("vies") == "bull" and prob >= 0.6:
            teto = cfg.teto_escada_alta
            motivo += f" | Elliott bull forte ({prob:.0%}): escada limitada a {teto:.0%}"
    alvo = min(max(escada, short_base), teto)
    est = "carregando" if (preco_fechamento < cfg.low and short_base > 0) else "ativo"
    if preco_fechamento < cfg.low and short_base == 0:
        motivo += " | abaixo do fundo sem cenário bear: zerado"
        alvo = 0.0
    return {"alvo": round(alvo, 4), "estado": est, "motivo": motivo, "short_base": short_base}


# --------------------------------------------------------------- proposta de range
FASES_CORRETIVAS = ("correcao_a", "correcao_b", "correcao_c", "triangulo", "consolidacao", "onda_2", "onda_4")


def propor_range(pivots_1d: Sequence, preco: float, regime: Optional[Dict] = None, mestre_primario: Optional[Dict] = None,
                 min_pct: float = 0.12, max_pct: float = 0.80, exigir_corretivo: bool = True) -> Optional[Dict]:
    """
    Proposta automática a partir dos pivôs do grau primário no diário (últimos H e L confirmados),
    validada por: preço dentro do range, amplitude entre min_pct e max_pct, regime não-tendência
    forte e (se houver) cenário primário corretivo/lateral.
    pivots_1d: lista de dicts {'preco','tipo','confirmado','data'} (saída de contagem_mestre).
    """
    conf = [p for p in pivots_1d if p.get("confirmado")]
    if len(conf) < 2:
        return None
    a, b = conf[-2], conf[-1]
    low, high = min(a["preco"], b["preco"]), max(a["preco"], b["preco"])
    if high <= low:
        return None
    amp = (high - low) / low
    motivos = []
    if not (min_pct <= amp <= max_pct):
        return {"valido": False, "low": low, "high": high, "motivo": f"amplitude {amp:.0%} fora de {min_pct:.0%}-{max_pct:.0%}"}
    if not (low <= preco <= high):
        return {"valido": False, "low": low, "high": high, "motivo": "preço fora do range dos últimos pivôs"}
    motivos.append(f"pivôs primários {a.get('data')} ({a['preco']:.0f}) e {b.get('data')} ({b['preco']:.0f}), amplitude {amp:.0%}")
    if regime:
        if regime.get("regime") == "tendencia" and regime.get("eficiencia", 0) > 0.5:
            return {"valido": False, "low": low, "high": high, "motivo": f"regime de tendência forte ({regime.get('eficiencia')})"}
        motivos.append(f"regime {regime.get('regime')}")
    if mestre_primario:
        fase = mestre_primario.get("fase", "")
        if fase in FASES_CORRETIVAS:
            motivos.append(f"Elliott primário em {fase} (corretivo)")
        elif exigir_corretivo:
            return {"valido": False, "low": low, "high": high, "motivo": f"Elliott primário em {fase} (não corretivo): sem range"}
        else:
            motivos.append(f"atenção: Elliott primário em {fase} (impulso); rompimento é o cenário provável")
    elif exigir_corretivo:
        return {"valido": False, "low": low, "high": high, "motivo": "sem leitura de Elliott para confirmar correção"}
    if regime and regime.get("regime") == "tendencia" and exigir_corretivo:
        return {"valido": False, "low": low, "high": high, "motivo": "regime de tendência: sem range"}
    return {"valido": True, "low": round(low, 2), "high": round(high, 2), "amplitude": round(amp, 4), "origem": "pivots",
            "motivo": " | ".join(motivos)}


# --------------------------------------------------------------- posição inversa
class PosicaoInversa:
    """Posição short em contrato inverso (contratos de 1 USD). Média de entrada harmônica."""

    def __init__(self):
        self.contratos = 0.0
        self.inv_entrada = 0.0     # soma de contratos/preco (= contratos / entrada_media)
        self.pnl_btc_realizado = 0.0
        self.taxas_btc = 0.0

    @property
    def entrada_media(self) -> Optional[float]:
        return (self.contratos / self.inv_entrada) if self.inv_entrada else None

    def vender(self, contratos: float, preco: float, taxa: float = 0.0002):
        self.contratos += contratos
        self.inv_entrada += contratos / preco
        self.taxas_btc += contratos / preco * taxa

    def recomprar(self, contratos: float, preco: float, taxa: float = 0.0002) -> float:
        contratos = min(contratos, self.contratos)
        if contratos <= 0:
            return 0.0
        fracao = contratos / self.contratos
        inv_saida = self.inv_entrada * fracao
        pnl = contratos / preco - inv_saida          # short inverso: contratos*(1/saida - 1/entrada) > 0 quando o preço cai
        self.contratos -= contratos
        self.inv_entrada -= inv_saida
        self.pnl_btc_realizado += pnl
        self.taxas_btc += contratos / preco * taxa
        return pnl

    def pnl_nao_realizado(self, preco: float) -> float:
        return (self.contratos / preco - self.inv_entrada) if self.contratos else 0.0
