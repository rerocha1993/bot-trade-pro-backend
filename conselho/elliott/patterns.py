# core/elliott_pro/patterns.py
"""
Catálogo de padrões de Elliott com regras obrigatórias e diretrizes (guidelines).

Um padrão é ajustado sobre uma sequência de PERNAS (legs) consecutivas e alternadas.
Cada ajuste devolve um PatternFit com:
    padrao      nome do padrão
    classe      'motriz' (impulso, diagonais) | 'corretivo' (zigzag, flats, triângulos, combinações)
    direcao     'up' | 'down' -> sentido líquido do padrão (do início da 1ª perna ao fim da última)
    rotulos     ['1','2','3','4','5'] | ['A','B','C'] | ['a','b','c','d','e'] | ['W','X','Y'] | ['W','X','Y','X','Z']
    score       0..1  (regras obrigatórias todas ok; diretrizes ponderam)
    regras      lista de {regra, ok, obrigatoria, detalhe}
    extras      ex.: {'extensao': '3', 'truncada': True, 'alternancia': True}

Regras implementadas (Frost & Prechter, "Elliott Wave Principle"):
  Impulso: onda 2 nunca retrai mais de 100% da 1; onda 3 nunca é a mais curta entre 1,3,5;
           onda 4 não entra no território de preço da onda 1; uma das ondas 1/3/5 costuma se estender;
           alternância entre 2 e 4 (profunda x rasa); onda 5 ~ onda 1 ou 0,618*(1+3).
  Diagonal (leading/ending): 5 pernas em cunha; onda 4 SOBREPÕE a 1; 3 < 1 e 5 < 3 (contração),
           2 e 4 contraem; onda 3 nunca a mais curta.
  Zigzag (5-3-5): B retrai 38,2%-88,6% de A (nunca >100%); C ≥ 61,8% de A e termina além do fim de A.
  Flat regular (3-3-5): B retrai 90%-105% de A; C ≈ A (90-110%) e termina levemente além de A.
  Flat expandido: B 105%-138,2% de A (ultrapassa o início de A); C 100%-161,8% de A além do fim de A.
  Flat running: B >105% de A; C termina ANTES do fim de A (<100%).
  Triângulo contrátil: 5 pernas (a-b-c-d-e) cada uma 50%-90% da anterior, e termina dentro de d.
  Triângulo expansivo: cada perna 110%-170% da anterior.
  Triângulo barreira: contrátil com b e d no mesmo nível (±1%).
  Duplo zigzag / duplo três (W-X-Y): X retrai 38,2%-88,6% de W; Y 61,8%-161,8% de W.
  Triplo três (W-X-Y-X-Z): idem com Z 61,8%-161,8% de W.
  Onda 5 truncada: impulso em que a 5 não ultrapassa o fim da 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Sequence

from .pivots import Pivot


@dataclass
class Leg:
    inicio: float
    fim: float
    ts_inicio: int = 0
    ts_fim: int = 0
    idx_inicio: int = 0
    idx_fim: int = 0
    confirmado: bool = True

    @property
    def tamanho(self) -> float:
        return abs(self.fim - self.inicio)

    @property
    def sobe(self) -> bool:
        return self.fim >= self.inicio

    def dict(self):
        d = asdict(self)
        d["tamanho"] = self.tamanho
        return d


def legs_de_pivots(pivots: Sequence[Pivot]) -> List[Leg]:
    legs = []
    for i in range(1, len(pivots)):
        a, b = pivots[i - 1], pivots[i]
        legs.append(Leg(a.preco, b.preco, a.ts, b.ts, a.idx, b.idx, confirmado=b.confirmado))
    return legs


@dataclass
class PatternFit:
    padrao: str
    classe: str
    direcao: str
    legs: List[Leg]
    rotulos: List[str]
    score: float
    regras: List[Dict] = field(default_factory=list)
    extras: Dict = field(default_factory=dict)
    completo: bool = True

    @property
    def inicio(self) -> float:
        return self.legs[0].inicio

    @property
    def fim(self) -> float:
        return self.legs[-1].fim

    def dict(self):
        return {
            "padrao": self.padrao, "classe": self.classe, "direcao": self.direcao,
            "rotulos": self.rotulos, "score": self.score, "completo": self.completo,
            "regras": self.regras, "extras": self.extras,
            "ondas": [{"rotulo": r, **l.dict()} for r, l in zip(self.rotulos, self.legs)],
        }


# ------------------------------------------------------------------ utilidades
def _r(nome, ok, obrigatoria, detalhe, peso=1.0) -> Dict:
    return {"regra": nome, "ok": bool(ok), "obrigatoria": bool(obrigatoria), "detalhe": detalhe, "peso": peso}


def _score(regras: List[Dict]) -> Optional[float]:
    """None se alguma obrigatória falhou; senão 0.55 + 0.45 * (diretrizes ok ponderadas)."""
    if any(r["obrigatoria"] and not r["ok"] for r in regras):
        return None
    diretrizes = [r for r in regras if not r["obrigatoria"]]
    if not diretrizes:
        return 0.75
    total = sum(r["peso"] for r in diretrizes)
    ok = sum(r["peso"] for r in diretrizes if r["ok"])
    return round(0.55 + 0.45 * ok / total, 3)


def _alternadas(legs: List[Leg]) -> bool:
    return all(legs[i].sobe != legs[i - 1].sobe for i in range(1, len(legs)))


def _alem(a: float, b: float, up: bool) -> bool:
    """a está além de b na direção `up`?"""
    return a > b if up else a < b


def _ratio(a: float, b: float) -> Optional[float]:
    return (b / a) if a else None


def _faixa(x: Optional[float], lo: float, hi: float) -> bool:
    return x is not None and lo - 1e-6 <= x <= hi + 1e-6


# ------------------------------------------------------------------ IMPULSO
def ajustar_impulso(legs: List[Leg], permitir_diagonal: bool = False) -> Optional[PatternFit]:
    if len(legs) != 5 or not _alternadas(legs):
        return None
    up = legs[0].sobe
    w = legs
    t = [l.tamanho for l in w]
    if min(t) <= 0:
        return None
    regras = []
    # obrigatórias
    regras.append(_r("onda2_nao_ultrapassa_inicio_1", not _alem(w[1].fim, w[0].inicio, not up) and w[1].fim != w[0].inicio, True,
                     f"retração da 2 = {t[1] / t[0]:.1%}"))
    regras.append(_r("onda3_nao_e_a_mais_curta", not (t[2] < t[0] and t[2] < t[4]), True, f"1={t[0]:.2f} 3={t[2]:.2f} 5={t[4]:.2f}"))
    regras.append(_r("onda3_rompe_fim_da_1", _alem(w[2].fim, w[0].fim, up), True, ""))
    sobreposicao = _alem(w[3].fim, w[0].fim, not up)  # onda 4 entra no território da 1
    regras.append(_r("onda4_nao_sobrepoe_onda1", not sobreposicao, not permitir_diagonal, "sobrepõe" if sobreposicao else "sem sobreposição"))
    # diretrizes
    r2 = t[1] / t[0]
    r4 = t[3] / t[2]
    r3 = t[2] / t[0]
    r5 = t[4] / t[0]
    regras.append(_r("onda2_retracao_fibonacci", _faixa(r2, 0.382, 0.786), False, f"{r2:.1%} (ideal 50-61,8%)", 1.0))
    regras.append(_r("onda3_extensao", r3 >= 1.618, False, f"onda 3 = {r3:.2f}x onda 1 (ideal ≥ 1,618)", 1.2))
    regras.append(_r("onda4_retracao_fibonacci", _faixa(r4, 0.236, 0.5), False, f"{r4:.1%} (ideal 23,6-38,2%)", 1.0))
    regras.append(_r("onda5_proporcao", _faixa(r5, 0.618, 1.618) or _faixa(t[4] / (t[0] + t[2]), 0.5, 0.8), False, f"onda 5 = {r5:.2f}x onda 1", 0.8))
    regras.append(_r("alternancia_2_4", abs(r2 - r4) >= 0.15, False, f"2={r2:.1%} 4={r4:.1%}", 0.6))
    ext = max(range(0, 5, 2), key=lambda i: t[i])
    regras.append(_r("uma_onda_estendida", t[ext] >= 1.618 * min(t[0], t[2], t[4]), False, f"onda {ext + 1} estendida", 0.5))
    truncada = not _alem(w[4].fim, w[2].fim, up)
    regras.append(_r("onda5_nao_truncada", not truncada, False, "truncada" if truncada else "ok", 0.4))
    score = _score(regras)
    if score is None:
        return None
    extras = {"extensao": str(ext + 1), "truncada": truncada, "retracao_2": round(r2, 3), "retracao_4": round(r4, 3)}
    return PatternFit("impulso", "motriz", "up" if up else "down", legs, ["1", "2", "3", "4", "5"], score, regras, extras)


def ajustar_diagonal(legs: List[Leg], tipo: str = "ending") -> Optional[PatternFit]:
    """Diagonal contrátil (cunha). 'leading' inicia impulsos/zigzags (onda 1/A); 'ending' termina (onda 5/C)."""
    if len(legs) != 5 or not _alternadas(legs):
        return None
    up = legs[0].sobe
    w = legs
    t = [l.tamanho for l in w]
    if min(t) <= 0:
        return None
    regras = []
    regras.append(_r("onda2_nao_ultrapassa_inicio_1", not _alem(w[1].fim, w[0].inicio, not up), True, ""))
    regras.append(_r("onda3_nao_e_a_mais_curta", not (t[2] < t[0] and t[2] < t[4]), True, ""))
    regras.append(_r("onda4_sobrepoe_onda1", _alem(w[3].fim, w[0].fim, not up), True, "diagonal exige sobreposição 4-1"))
    regras.append(_r("onda4_nao_ultrapassa_fim_2", _alem(w[3].fim, w[1].fim, up), True, ""))
    regras.append(_r("contracao_3_menor_que_1", t[2] < t[0], False, f"3/1={t[2] / t[0]:.2f}", 1.0))
    regras.append(_r("contracao_5_menor_que_3", t[4] < t[2], False, f"5/3={t[4] / t[2]:.2f}", 1.0))
    regras.append(_r("contracao_4_menor_que_2", t[3] < t[1], False, f"4/2={t[3] / t[1]:.2f}", 0.8))
    regras.append(_r("onda5_rompe_fim_3", _alem(w[4].fim, w[2].fim, up), False, "", 0.5))
    score = _score(regras)
    if score is None:
        return None
    return PatternFit(f"diagonal_{tipo}", "motriz", "up" if up else "down", legs, ["1", "2", "3", "4", "5"], score, regras)


# ------------------------------------------------------------------ CORRETIVOS ABC
def ajustar_zigzag(legs: List[Leg]) -> Optional[PatternFit]:
    if len(legs) != 3 or not _alternadas(legs):
        return None
    a, b, c = legs
    up = a.sobe
    if a.tamanho <= 0:
        return None
    rb, rc = b.tamanho / a.tamanho, c.tamanho / a.tamanho
    regras = [
        _r("B_retrai_menos_de_100pct_de_A", rb < 1.0, True, f"B={rb:.1%} de A"),
        _r("C_termina_alem_do_fim_de_A", _alem(c.fim, a.fim, up), True, ""),
        _r("B_retracao_fibonacci", _faixa(rb, 0.382, 0.886), False, f"B={rb:.1%} (ideal 50-78,6%)", 1.0),
        _r("C_proporcao_de_A", _faixa(rc, 0.618, 1.618) or _faixa(rc, 1.618, 2.618), False, f"C={rc:.2f}x A (ideal 1,0 ou 1,618)", 1.0),
        _r("C_igual_A", 0.9 <= rc <= 1.1 or 1.5 <= rc <= 1.7, False, "", 0.5),
    ]
    score = _score(regras)
    if score is None:
        return None
    return PatternFit("zigzag", "corretivo", "up" if up else "down", legs, ["A", "B", "C"], score, regras, {"rb": round(rb, 3), "rc": round(rc, 3)})


def ajustar_flat(legs: List[Leg]) -> Optional[PatternFit]:
    """Detecta flat regular, expandido ou running (B retrai ≥ 90% de A)."""
    if len(legs) != 3 or not _alternadas(legs):
        return None
    a, b, c = legs
    up = a.sobe
    if a.tamanho <= 0:
        return None
    rb, rc = b.tamanho / a.tamanho, c.tamanho / a.tamanho
    if rb < 0.9:
        return None
    c_alem = _alem(c.fim, a.fim, up)
    if rb <= 1.05:
        nome = "flat_regular"
        regras = [
            _r("B_retrai_90_105pct", True, True, f"B={rb:.1%}"),
            _r("C_termina_alem_de_A", c_alem, False, "", 1.0),
            _r("C_aprox_A", _faixa(rc, 0.9, 1.15), False, f"C={rc:.2f}x A", 1.0),
        ]
    elif rb <= 1.382:
        if c_alem:
            nome = "flat_expandido"
            regras = [
                _r("B_ultrapassa_inicio_de_A", True, True, f"B={rb:.1%}"),
                _r("C_alem_de_A", c_alem, True, ""),
                _r("C_100_161pct", _faixa(rc, 1.0, 1.618), False, f"C={rc:.2f}x A (ideal 1,236-1,618)", 1.0),
            ]
        else:
            nome = "flat_running"
            regras = [
                _r("B_ultrapassa_inicio_de_A", True, True, f"B={rb:.1%}"),
                _r("C_nao_atinge_fim_de_A", not c_alem, True, ""),
                _r("C_menor_que_A", rc < 1.0, False, f"C={rc:.2f}x A", 1.0),
            ]
    else:
        return None
    score = _score(regras)
    if score is None:
        return None
    return PatternFit(nome, "corretivo", "up" if up else "down", legs, ["A", "B", "C"], score, regras, {"rb": round(rb, 3), "rc": round(rc, 3)})


# ------------------------------------------------------------------ TRIÂNGULOS
def ajustar_triangulo(legs: List[Leg]) -> Optional[PatternFit]:
    if len(legs) != 5 or not _alternadas(legs):
        return None
    t = [l.tamanho for l in legs]
    if min(t) <= 0:
        return None
    props = [t[i] / t[i - 1] for i in range(1, 5)]
    contratil = all(0.45 <= p <= 0.95 for p in props)
    expansivo = all(1.05 <= p <= 1.8 for p in props)
    if not (contratil or expansivo):
        return None
    up = legs[0].sobe  # direção da perna 'a' (o triângulo é lateral; a direção líquida importa pouco)
    a, b, c, d, e = legs
    regras = [_r("pernas_" + ("contraem" if contratil else "expandem"), True, True, " ".join(f"{p:.2f}" for p in props))]
    if contratil:
        regras.append(_r("e_termina_dentro_de_d", not _alem(e.fim, d.inicio, e.sobe), False, "", 1.0))
        barreira = abs(b.fim - d.fim) <= 0.01 * max(abs(b.fim), 1e-9)
        nome = "triangulo_barreira" if barreira else "triangulo_contratil"
        regras.append(_r("c_menor_que_a", t[2] < t[0], False, "", 0.5))
    else:
        nome = "triangulo_expansivo"
    score = _score(regras)
    if score is None:
        return None
    return PatternFit(nome, "corretivo", "up" if up else "down", legs, ["a", "b", "c", "d", "e"], score, regras, {"proporcoes": [round(p, 2) for p in props]})


# ------------------------------------------------------------------ COMBINAÇÕES
def ajustar_wxy(legs: List[Leg]) -> Optional[PatternFit]:
    if len(legs) != 3 or not _alternadas(legs):
        return None
    w, x, y = legs
    up = w.sobe
    if w.tamanho <= 0:
        return None
    rx, ry = x.tamanho / w.tamanho, y.tamanho / w.tamanho
    regras = [
        _r("X_retrai_menos_de_100pct_de_W", rx < 1.0, True, f"X={rx:.1%}"),
        _r("Y_alem_do_fim_de_W", _alem(y.fim, w.fim, up), True, ""),
        _r("X_retracao_fibonacci", _faixa(rx, 0.382, 0.886), False, f"X={rx:.1%}", 0.8),
        _r("Y_proporcao_de_W", _faixa(ry, 0.618, 1.618), False, f"Y={ry:.2f}x W", 1.0),
    ]
    score = _score(regras)
    if score is None:
        return None
    return PatternFit("duplo_tres", "corretivo", "up" if up else "down", legs, ["W", "X", "Y"], score, regras, {"rx": round(rx, 3), "ry": round(ry, 3)})


def ajustar_wxyxz(legs: List[Leg]) -> Optional[PatternFit]:
    if len(legs) != 5 or not _alternadas(legs):
        return None
    w, x, y, x2, z = legs
    up = w.sobe
    if w.tamanho <= 0 or y.tamanho <= 0:
        return None
    regras = [
        _r("X_retrai_menos_de_100pct_de_W", x.tamanho < w.tamanho, True, ""),
        _r("X2_retrai_menos_de_100pct_de_Y", x2.tamanho < y.tamanho, True, ""),
        _r("Z_alem_do_fim_de_Y", _alem(z.fim, y.fim, up), True, ""),
        _r("Z_proporcao_de_W", _faixa(z.tamanho / w.tamanho, 0.618, 1.618), False, "", 1.0),
    ]
    score = _score(regras)
    if score is None:
        return None
    return PatternFit("triplo_tres", "corretivo", "up" if up else "down", legs, ["W", "X", "Y", "X", "Z"], score, regras)


# ------------------------------------------------------------------ registro
PADROES: Dict[str, Dict] = {
    "impulso": {"n_legs": 5, "fn": ajustar_impulso},
    "diagonal_leading": {"n_legs": 5, "fn": lambda l: ajustar_diagonal(l, "leading")},
    "diagonal_ending": {"n_legs": 5, "fn": lambda l: ajustar_diagonal(l, "ending")},
    "zigzag": {"n_legs": 3, "fn": ajustar_zigzag},
    "flat": {"n_legs": 3, "fn": ajustar_flat},
    "triangulo": {"n_legs": 5, "fn": ajustar_triangulo},
    "duplo_tres": {"n_legs": 3, "fn": ajustar_wxy},
    "triplo_tres": {"n_legs": 5, "fn": ajustar_wxyxz},
}


def ajustar_todos(legs: List[Leg]) -> List[PatternFit]:
    """Tenta todos os padrões compatíveis com o número de pernas e devolve os que passaram."""
    saida = []
    for nome, cfg in PADROES.items():
        if cfg["n_legs"] != len(legs):
            continue
        try:
            fit = cfg["fn"](legs)
        except Exception:
            fit = None
        if fit:
            saida.append(fit)
    return saida
