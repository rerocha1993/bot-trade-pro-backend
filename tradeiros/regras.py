# tradeiros/regras.py
"""
REGRAS R1–R38 e os dois PERFIS (Shaka × Maroja): da leitura do dia + mapa de Elliott sai o PLANO do operador —
% de hedge e as ordens do dia nas DUAS bordas (zona, fatias, stop, alvo, risco) — cada decisão com as regras que a
geraram. Como nas lives, o plano é feito antes: limitadas na VAL (compra, realização do hedge) e na VAH (escada do
hedge, venda do Shaka) esperando o preço; no meio, nada a mercado (R1).

Os dois olham para as MESMAS coisas (docs/tradeiros/perfil_por_regime.md, docs/tradeiros/gabarito.json); mudam os pesos:

    Shaka   agressivo: risco até ~2% nos extremos, entra pequeno sem esperar reação (R38), mais peso ao fluxo,
            Elliott "bem depois", faz venda direcional na resistência, hedge 20–65% (extremo de bear 90%),
            realiza metade em 1:1
    Maroja  conservador: risco ≤ 1%, Elliott é o mapa principal (veto de onda 4, invalidação da contagem), espera
            reação fora do valor (R6, R9, R10), vende pelo hedge, protege mais no mesmo dia (hedge 24–60%),
            realiza 25% em 1:1

O stop fica na INVALIDAÇÃO (fundo/topo do range ou da contagem) com a folga deles — largo, e o tamanho se ajusta
(R18, R21). O filtro de 3 R vale para os dois (R19): replica também os trades que eles deixam passar e os que erram.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Dict, List, Optional, Tuple

from tradeiros.leitura import Leitura, posicao_no_range, zona_do_range


# ------------------------------------------------------------------ perfis
@dataclass(frozen=True)
class Perfil:
    nome: str
    risco_extremo: float            # risco por trade no fundo/topo do range (fração da carteira)
    risco_meio: float               # mão pequena (R3)
    risco_teto: float               # com quebra de estrutura a favor a mão cresce até aqui (R11)
    exige_reacao_fora_do_valor: bool  # R6/R9/R10 (Maroja) × R38 entra pequeno com stop barato (Shaka)
    peso_elliott: float             # quanto a inclinação e o veto de onda 4 mexem no plano
    peso_fluxo: float               # quanto reset de OI, funding e presos mexem no hedge
    hedge_min: float
    hedge_max: float
    hedge_extra: float              # no mesmo dia o Maroja protege mais (ETF: 55–60% × 20–25%; gabarito)
    venda_direcional: bool          # além do hedge, abre short direcional na resistência
    fatias: int                     # limitadas escalonadas (R20)
    folga_stop: float               # além da invalidação (fração do preço)
    rr_minimo: float = 3.0          # R19
    realizar_em_1r: float = 0.25    # R22: fração realizada em 1:1, stop vai ao preço médio
    preenchimento_minimo: float = 0.4  # R24: abaixo disso e o preço saiu da zona → fecha o que preencheu


SHAKA = Perfil(nome="shaka", risco_extremo=0.02, risco_meio=0.01, risco_teto=0.03, exige_reacao_fora_do_valor=False,
               peso_elliott=0.3, peso_fluxo=1.0, hedge_min=0.20, hedge_max=0.65, hedge_extra=0.0,
               venda_direcional=True, fatias=5, folga_stop=0.003, realizar_em_1r=0.5)
MAROJA = Perfil(nome="maroja", risco_extremo=0.01, risco_meio=0.006, risco_teto=0.01, exige_reacao_fora_do_valor=True,
                peso_elliott=1.0, peso_fluxo=0.5, hedge_min=0.24, hedge_max=0.60, hedge_extra=0.10,
                venda_direcional=False, fatias=9, folga_stop=0.006, realizar_em_1r=0.25)
PERFIS = {"shaka": SHAKA, "maroja": MAROJA}

HEDGE_BEAR = 0.90                   # bear declarado de 2022 (I_zjWuQqn_s): 90–100%
PASSO_HEDGE = 0.05                  # mudança mínima de hedge que vira ordem


# ------------------------------------------------------------------ decisões e plano
@dataclass
class Decisao:
    tipo: str                       # compra | venda_direcional | hedge_aumentar | hedge_realizar | ficar_fora
    regras: List[str]
    motivo: str
    zona: Optional[Tuple[float, float]] = None
    pesos_fatias: List[float] = field(default_factory=list)   # soma 1; a fatia mais longe do preço é a maior
    stop: Optional[float] = None
    alvo: Optional[float] = None
    risco: float = 0.0              # fração da carteira arriscada até o stop
    fracao_hedge: float = 0.0       # hedge_aumentar / hedge_realizar: quanto da carteira muda
    exige_reacao: bool = False

    @property
    def rr(self) -> Optional[float]:
        if not self.zona or self.stop is None or self.alvo is None:
            return None
        medio = medio_das_fatias(self.zona, self.pesos_fatias, self.tipo)
        risco = abs(medio - self.stop)
        return abs(self.alvo - medio) / risco if risco > 0 else None


@dataclass
class Plano:
    operador: str
    ts: int
    preco: float
    hedge_alvo: float               # hedge para o preço de agora
    hedge_regras: List[str]
    fluxo: Dict
    decisoes: List[Decisao]

    def as_dict(self) -> Dict:
        d = asdict(self)
        for dd, dec in zip(d["decisoes"], self.decisoes):
            dd["rr"] = None if dec.rr is None else round(dec.rr, 2)
        return d


def pesos_crescentes(n: int) -> List[float]:
    """Camadas maiores mais longe (5% → 10% → 20%, 10/20/20/30%): pesos 1, 2, …, n normalizados."""
    total = n * (n + 1) / 2
    return [(i + 1) / total for i in range(n)]


def precos_das_fatias(zona: Tuple[float, float], n: int, tipo: str) -> List[float]:
    """Da borda mais perto do preço para a mais longe: compra desce, venda sobe."""
    lo, hi = zona
    if n == 1:
        return [(lo + hi) / 2]
    passos = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    return list(reversed(passos)) if tipo in ("compra", "hedge_realizar") else passos


def medio_das_fatias(zona: Tuple[float, float], pesos: List[float], tipo: str) -> float:
    pesos = pesos or [1.0]
    precos = precos_das_fatias(zona, len(pesos), tipo)
    return sum(p * w for p, w in zip(precos, pesos)) / sum(pesos)


# ------------------------------------------------------------------ fluxo como contexto (P11, P13, P14)
def contexto_fluxo(lt: Leitura) -> Dict:
    dv = lt.derivativos or {}
    oi = dv.get("oi_vs_max_30d")
    fund, fund30 = dv.get("funding"), dv.get("funding_media_30d")
    lsr, lsr_med = dv.get("long_short"), dv.get("long_short_mediana_30d")
    fg = lt.sentimento
    return {
        "oi_reset": oi is not None and oi <= -0.30,                          # limpeza de 30–50% (D1fyBUuDCX0)
        "funding_negativo": fund30 is not None and fund30 < 0,               # negativo prolongado = fundo (P13)
        "funding_caro": fund is not None and fund30 is not None and fund > 0 and fund > 3 * max(fund30, 1e-5),
        "longs_presos": lsr is not None and lsr_med is not None and lsr > lsr_med * 1.15,
        "shorts_presos": lsr is not None and lsr_med is not None and lsr < lsr_med * 0.85,
        "medo_extremo": fg is not None and fg <= 20,
        "euforia": fg is not None and fg >= 80,
    }


# ------------------------------------------------------------------ hedge alvo (R12, R27–R34, P11, P12)
def hedge_alvo(lt: Leitura, mapa: Dict, fluxo: Dict, perfil: Perfil) -> Tuple[float, List[str]]:
    regras: List[str] = []
    estado = (lt.ciclo or {}).get("estado")
    do_topo = (lt.ciclo or {}).get("do_topo") or 0.0
    est = lt.estrutura or {}
    inclinacao = float(mapa.get("inclinacao") or 0.0)

    # bear declarado: perdeu o valor, estrutura de baixa e o mapa de baixa (2022)
    if (lt.zona == "abaixo_do_valor" and est.get("tendencia") == "baixa" and do_topo <= -0.20
            and inclinacao * perfil.peso_elliott <= -0.15):
        return HEDGE_BEAR, ["R31", "bear"]

    h = {"esticado": 0.50, "intermediario": 0.35, "descontado": 0.25}.get(estado, 0.35) + perfil.hedge_extra
    regras.append("R31")
    if lt.zona in ("topo", "acima_do_valor"):
        h += 0.10
        regras.append("R28")
    elif lt.zona in ("fundo", "abaixo_do_valor"):
        h -= 0.10
        regras.append("R28")
    if fluxo["medo_extremo"] and do_topo <= -0.25:
        h = min(h, 0.25)                                          # correção de ~30% com medo extremo: exposição alta
        regras.append("R31")
    if fluxo["oi_reset"] or fluxo["funding_negativo"]:
        h -= 0.05 * perfil.peso_fluxo
        regras.append("P11")
    if fluxo["euforia"] or fluxo["funding_caro"]:
        h += 0.05 * perfil.peso_fluxo
        regras.append("P13")
    if est.get("quebra") == "alta" and lt.zona == "acima_do_valor":
        h -= 0.10
        regras.append("R12")
    h -= 0.10 * inclinacao * perfil.peso_elliott                  # contagens mudam a % de exposição, não o lado (R15)
    if perfil.peso_elliott and inclinacao:
        regras.append("R15")
    h = min(perfil.hedge_max, max(perfil.hedge_min, h))
    # R30: pouca proteção com queda profunda PROVÁVEL (em xybIvLoZ13s, com o cenário baixista menos provável, ficou 24%)
    if h < 0.40 and float(mapa.get("prob_bear") or 0) >= 0.5:
        h = 0.40
        regras.append("R30")
    return round(h, 3), regras


# ------------------------------------------------------------------ o plano do dia
def na_borda(lt: Leitura, preco: float) -> Leitura:
    """A mesma leitura com o preço levado a um nível: é assim que a ordem limitada é pensada antes do toque."""
    r = lt.range
    p = posicao_no_range(preco, r["val"], r["vah"])
    return replace(lt, preco=preco, p=p, zona=zona_do_range(p))


def _invalidacao_compra(lt: Leitura, mapa: Dict, perfil: Perfil, zona_baixa: float) -> Tuple[float, str]:
    base, fonte = min(lt.range["minima"], zona_baixa), "fundo do range"
    inval = mapa.get("invalidacao_compra")
    # Maroja: a invalidação da contagem manda quando fica abaixo da zona e a até 10% dela
    if perfil.peso_elliott >= 1.0 and inval and zona_baixa * 0.90 <= inval < zona_baixa:
        base, fonte = float(inval), "invalidação da contagem"
    return base * (1 - perfil.folga_stop), fonte


def _invalidacao_venda(lt: Leitura, mapa: Dict, perfil: Perfil, zona_alta: float) -> Tuple[float, str]:
    base, fonte = max(lt.range["maxima"], zona_alta), "topo do range"
    inval = mapa.get("invalidacao_venda")
    if perfil.peso_elliott >= 1.0 and inval and zona_alta < inval <= zona_alta * 1.10:
        base, fonte = float(inval), "invalidação da contagem"
    return base * (1 + perfil.folga_stop), fonte


def _filtro_rr(d: Decisao, perfil: Perfil) -> Decisao:
    rr = d.rr
    if rr is None or rr >= perfil.rr_minimo:
        return d
    return Decisao("ficar_fora", d.regras + ["R19"], f"{d.tipo} recusada: {rr:.1f} R até o alvo (mínimo {perfil.rr_minimo:g})",
                   zona=d.zona, stop=d.stop, alvo=d.alvo)


def _compra(lt, mapa, fluxo, perfil, pesos) -> Optional[Decisao]:
    r, est = lt.range, lt.estrutura or {}
    val, poc, vah = r["val"], r["poc"], r["vah"]
    w = vah - val
    regras, exige = ["R2", "R3"], False
    risco = perfil.risco_extremo
    if lt.zona == "abaixo_do_valor":                                # zona reativa, abaixo do suporte
        regras.append("R10")
        if lt.p < -1.0:
            regras.append("R9")                                     # vazio abaixo do VAL: o preço pode parar em qualquer lugar
            risco *= 0.5
        exige = perfil.exige_reacao_fora_do_valor
        if not exige:
            regras.append("R38")
            risco *= 0.5                                            # entra pequeno, soma se quebrar a estrutura
        lo, hi, alvo = lt.preco * 0.97, lt.preco * 0.995, poc
    else:                                                           # zona passiva: limitadas na VAL esperando o preço
        lo, hi, alvo = val - 0.15 * w, min(val + 0.20 * w, lt.preco * 0.999), vah
    if hi <= lo:
        return None
    setup2 = mapa.get("setup_onda_2") or {}
    if setup2.get("vies") == "bull" and setup2.get("invalidacao") and float(setup2["invalidacao"]) < lo:
        regras.append("R14")
    if est.get("quebra") == "alta":
        risco = min(perfil.risco_teto, risco * 1.5)
        regras.append("R11")
    capitulacao = fluxo["medo_extremo"] or fluxo["oi_reset"]
    if est.get("tendencia") == "baixa" and est.get("quebra") == "baixa":
        if capitulacao:
            regras.append("P12")                                    # pânico: compra em camadas, mão menor
            risco *= 0.5
        else:
            regras.append("R16")                                    # mínima renovada sem limpeza: Shaka pouco, Maroja nada
            risco *= 0.5 if not perfil.exige_reacao_fora_do_valor else 0.0
    if mapa.get("veto_onda_4") and perfil.peso_elliott >= 1.0:
        regras.append("R14")
        risco = 0.0
    if risco <= 0:
        return Decisao("ficar_fora", regras, "compra vetada (onda 4 ou mínima renovada sem limpeza)")
    stop, fonte = _invalidacao_compra(lt, mapa, perfil, lo)
    return _filtro_rr(Decisao("compra", regras + ["R20", "R21", "R23"],
                              f"fatias de {lo:,.0f} a {hi:,.0f}, stop no {fonte}, alvo {alvo:,.0f}",
                              zona=(lo, hi), pesos_fatias=pesos, stop=stop, alvo=alvo, risco=risco, exige_reacao=exige),
                      perfil)


def _zona_de_venda(lt: Leitura) -> Tuple[float, float]:
    r = lt.range
    w = r["vah"] - r["val"]
    if lt.zona == "acima_do_valor":
        lo = lt.preco * 1.001
        return lo, max(lo * 1.02, r["vah"] + 0.25 * w)
    lo = max(r["vah"] - 0.10 * w, lt.preco * 1.001)
    hi = r["vah"] + 0.25 * w
    for nivel in ((lt.pivo_virgem or {}).get("acima"), (lt.aberturas or {}).get("semana")):
        if nivel and hi < nivel <= hi * 1.03:
            hi = nivel                                              # abertura semanal / pivô virgem entram na escada
    return lo, max(hi, lo * 1.005)


def planejar(lt: Leitura, mapa: Dict, perfil: Perfil, hedge_atual: Optional[float] = None,
             evento: bool = False) -> Plano:
    """`hedge_atual` None = a carteira já está no hedge do preço de agora (útil para comparar com as lives)."""
    fluxo = contexto_fluxo(lt)
    h_agora, h_regras = hedge_alvo(lt, mapa, fluxo, perfil)
    plano = Plano(perfil.nome, lt.ts, lt.preco, h_agora, h_regras, fluxo, [])
    dec = plano.decisoes
    r = lt.range
    if r is None or lt.p is None:
        dec.append(Decisao("ficar_fora", ["R1"], "sem range montado"))
        return plano
    hedge_atual = h_agora if hedge_atual is None else hedge_atual
    val, poc, vah = r["val"], r["poc"], r["vah"]
    w = vah - val
    est = lt.estrutura or {}
    pesos = pesos_crescentes(perfil.fatias)

    if lt.zona == "meio":
        dec.append(Decisao("ficar_fora", ["R1"], f"p={lt.p:.2f}: meio do range, nada a mercado; ordens só nas bordas"))
    if evento:
        dec.append(Decisao("ficar_fora", ["R36"], "dado macro agendado: nada aberto pelo dado; ordens já nas bordas"))

    # ---- borda de baixo: compra (passiva na VAL ou reativa abaixo) e realização do hedge (R28, R34)
    compra = _compra(lt, mapa, fluxo, perfil, pesos)
    if compra is not None:
        dec.append(compra)
    if lt.zona == "abaixo_do_valor":
        zr, h_fundo = (lt.preco * 0.97, lt.preco * 0.999), h_agora
    else:
        zr = (val - 0.15 * w, min(val + 0.10 * w, lt.preco * 0.999))
        h_fundo = hedge_alvo(na_borda(lt, val), mapa, fluxo, perfil)[0]
    if hedge_atual - h_fundo >= PASSO_HEDGE and zr[1] > zr[0]:
        dec.append(Decisao("hedge_realizar", ["R28", "R34"], f"realizar short no suporte até {h_fundo:.0%}",
                           zona=zr, pesos_fatias=pesos, fracao_hedge=round(hedge_atual - h_fundo, 3)))

    # ---- borda de cima: escada do hedge (R27, R28, R32) e venda direcional (R2, R5)
    zv = _zona_de_venda(lt)
    h_topo = h_agora if lt.zona == "acima_do_valor" else hedge_alvo(na_borda(lt, vah), mapa, fluxo, perfil)[0]
    if h_topo - hedge_atual >= PASSO_HEDGE:
        stop, _ = _invalidacao_venda(lt, mapa, perfil, zv[1])
        dec.append(Decisao("hedge_aumentar", ["R27", "R28"] + (["R32"] if hedge_atual > 0 else []),
                           f"escada de venda no inverse até {h_topo:.0%} (stop é pedágio acima do topo)",
                           zona=zv, pesos_fatias=pesos, stop=stop, fracao_hedge=round(h_topo - hedge_atual, 3)))
    bear_no_mapa = float(mapa.get("prob_bear") or 0) > float(mapa.get("prob_bull") or 0) + 0.2
    if perfil.venda_direcional or bear_no_mapa:
        if lt.zona == "acima_do_valor" and est.get("quebra") == "alta":
            dec.append(Decisao("ficar_fora", ["R5", "R9"], "rompimento com quebra de estrutura: esperar aceitação ou falha"))
        elif lt.zona not in ("fundo", "abaixo_do_valor"):          # R4: no VAL ou abaixo, sem venda nova
            stop, fonte = _invalidacao_venda(lt, mapa, perfil, zv[1])
            acima = lt.zona == "acima_do_valor"
            dec.append(_filtro_rr(Decisao("venda_direcional", ["R2", "R20", "R21", "R23"] + (["R5"] if acima else []),
                                          f"venda na resistência, stop no {fonte}, alvo no VAL", zona=zv,
                                          pesos_fatias=pesos, stop=stop, alvo=val,
                                          risco=perfil.risco_extremo * (0.5 if acima else 1.0),
                                          exige_reacao=acima and perfil.exige_reacao_fora_do_valor), perfil))
    # R7: perdeu o VAL com estrutura de baixa → vende o reteste do VAL por baixo (voltar ao valor = errado, R8)
    if lt.zona == "abaixo_do_valor" and est.get("quebra") == "baixa" and perfil.venda_direcional:
        lo, hi = max(val - 0.10 * w, lt.preco * 1.001), val + 0.05 * w
        if hi > lo:
            dec.append(_filtro_rr(Decisao("venda_direcional", ["R4", "R7", "R8"], "perdeu o VAL: vende o reteste por baixo",
                                          zona=(lo, hi), pesos_fatias=pesos, stop=poc * (1 + perfil.folga_stop),
                                          alvo=lt.preco - w, risco=perfil.risco_meio, exige_reacao=True), perfil))

    if not any(d.tipo in ("compra", "venda_direcional", "ficar_fora") for d in dec):
        dec.append(Decisao("ficar_fora", ["R2"], f"zona {lt.zona}: sem entrada nova para o perfil {perfil.nome}"))
    return plano
