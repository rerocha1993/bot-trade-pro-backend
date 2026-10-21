# conselho/robos.py
"""
Os 4 robôs do conselho, EM SIMULAÇÃO (paper trading): acompanham o mercado ao vivo e registram entradas, stops e alvos
como se fossem ordens, com taxa, mas não mandam nada para corretora. Decisão de 20/10/2026: nenhuma das quatro
combinações passou na régua dos estudos; rodar ao vivo em simulação é o teste que falta. Passar para conta demo ou
real é decisão do usuário depois dos números.

Gestão (a do Tradeiros, igual ao motor dos estudos em conselho/regua.py, só que vela a vela):
  - entrada em fatias limitadas (post-only): uma fatia só preenche se o candle ATRAVESSOU o preço;
  - no candle em que alguma fatia preenche, só o stop conta; favor e contra no mesmo candle = contra;
  - 1R sobre o preço médio: realiza 50% (limitada) e o stop do resto vai ao médio; fatias pendentes canceladas;
  - alvo limitado; teto de tempo desde o 1º preenchimento, saída a mercado no fechamento;
  - custo: maker 0,02% nas limitadas, taker 0,055% + 0,02% de slippage nas saídas a mercado (stop, tempo);
  - banca virtual de 1.000 USDT por robô, risco de 0,5% da banca por trade (o tamanho sai do stop).

Estratégias (docs/especialistas/RECOMENDACAO.md):
  1. absorcao_borda   — absorção (conselho/fluxo.absorcao) na VAH (venda) ou na VAL (compra) do composto de 10 dias;
                        stop além da parede, alvo no POC do composto (>= 1,5R).
  2. cauda_borda      — TPO E2 (scripts/estudo_tpo_e2_e3.py): cauda no bloco de 30 min na borda, regra idêntica.
  3. cauda_calco      — a mesma cauda, só quando há parede no livro (>= 4x o normal) entre o pavio e o nível.
  4. esticado_absorcao— absorção com o mercado esticado: venda com funding no p90 dos últimos ~66 dias e OI de 24 h
                        subindo >= 2%; compra com funding no p10 e OI subindo (vendidos entrando). Alvo a 2R.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

MAKER = 0.0002
TAKER = 0.00055 + 0.0002
BANCA_INICIAL = 1000.0
RISCO_PCT = 0.005

ROBOS = {
    "absorcao_borda": "Absorção na borda",
    "cauda_borda": "Cauda na borda",
    "cauda_calco": "Cauda + calço no livro",
    "esticado_absorcao": "Esticado + absorção",
}


# ================================================================== motor vela a vela
@dataclass
class Plano:
    robo: str
    lado: int                          # +1 compra, −1 venda
    fatias: List[Tuple[float, float]]  # [(preço, peso)], pesos somando 1
    stop: float
    alvo: Optional[float]
    criado_s: int
    valido_ate_s: int                  # limitadas canceladas depois disso
    teto_s: int                        # duração máxima desde o 1º preenchimento
    motivo: str
    contexto: Dict = field(default_factory=dict)


@dataclass
class Posicao:
    plano: Plano
    status: str = "pendente"           # pendente | aberta | fechada | expirada
    cheias: List[Tuple[float, float]] = field(default_factory=list)
    pend: List[Tuple[float, float]] = field(default_factory=list)
    stop_cur: float = 0.0
    tomou_1r: bool = False
    vendido: float = 0.0
    saidas: List[Tuple[float, float, str]] = field(default_factory=list)
    t1_s: Optional[int] = None
    fim_s: Optional[int] = None
    tipo_saida: Optional[str] = None
    resultado_r: Optional[float] = None
    ultimo_ts: int = 0

    def __post_init__(self):
        if not self.pend and not self.cheias:
            self.pend = list(self.plano.fatias)
        if not self.stop_cur:
            self.stop_cur = self.plano.stop

    @property
    def medio(self) -> Optional[float]:
        w = sum(p for _, p in self.cheias)
        return sum(x * p for x, p in self.cheias) / w if w else None

    def as_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def de_dict(d: Dict) -> "Posicao":
        pl = Plano(**{**d["plano"], "fatias": [tuple(x) for x in d["plano"]["fatias"]]})
        campos = {k: v for k, v in d.items() if k != "plano"}
        for k in ("cheias", "pend"):
            campos[k] = [tuple(x) for x in campos.get(k, [])]
        campos["saidas"] = [tuple(x) for x in campos.get("saidas", [])]
        return Posicao(plano=pl, **campos)


def passo(pos: Posicao, ts_s: int, o: float, h: float, l: float, c: float) -> List[str]:
    """Avança a posição com um candle (início em ts_s). Devolve os eventos: 'preencheu', '1r', 'stop', 'medio',
    'alvo', 'tempo', 'expirou'. Candles repetidos ou antigos são ignorados."""
    if pos.status in ("fechada", "expirada") or ts_s <= pos.ultimo_ts:
        return []
    pos.ultimo_ts = ts_s
    pl, d = pos.plano, pos.plano.lado
    eventos: List[str] = []
    preencheu_agora = False
    if pos.pend and ts_s < pl.valido_ate_s and not pos.tomou_1r:
        novas = [x for x in pos.pend if (l < x[0] if d == 1 else h > x[0])]
        if novas:
            pos.cheias += novas
            pos.pend = [x for x in pos.pend if x not in novas]
            preencheu_agora = True
            if pos.t1_s is None:
                pos.t1_s = ts_s
            pos.status = "aberta"
            eventos.append("preencheu")
    if not pos.cheias:
        if ts_s >= pl.valido_ate_s:
            pos.status, pos.fim_s, pos.pend = "expirada", ts_s, []
            eventos.append("expirou")
        return eventos
    wf = sum(w for _, w in pos.cheias)
    medio = pos.medio
    r_abs = abs(pl.stop - medio)
    aberto = wf - pos.vendido
    if (d == 1 and l <= pos.stop_cur) or (d == -1 and h >= pos.stop_cur):
        return eventos + _fechar(pos, aberto, pos.stop_cur, "mkt", "medio" if pos.tomou_1r else "stop", ts_s)
    if not preencheu_agora:
        if not pos.tomou_1r:
            n1 = medio + d * r_abs
            if (d == 1 and h > n1) or (d == -1 and l < n1):
                q = min(0.5 * wf, aberto)
                pos.saidas.append((q, n1, "lim"))
                pos.vendido += q
                aberto -= q
                pos.tomou_1r, pos.pend, pos.stop_cur = True, [], medio
                eventos.append("1r")
                if (d == 1 and l <= medio) or (d == -1 and h >= medio):
                    return eventos + _fechar(pos, aberto, medio, "mkt", "medio", ts_s)
        if pl.alvo is not None and ((d == 1 and h > pl.alvo) or (d == -1 and l < pl.alvo)):
            return eventos + _fechar(pos, aberto, pl.alvo, "lim", "alvo", ts_s)
    if pos.t1_s is not None and ts_s + 60 - pos.t1_s >= pl.teto_s:
        return eventos + _fechar(pos, aberto, c, "mkt", "tempo", ts_s)
    if pos.pend and ts_s >= pl.valido_ate_s:
        pos.pend = []
    return eventos


def _fechar(pos: Posicao, quantidade: float, preco: float, tipo: str, motivo: str, ts_s: int) -> List[str]:
    pos.saidas.append((quantidade, preco, tipo))
    pos.vendido += quantidade
    pos.status, pos.tipo_saida, pos.fim_s, pos.pend = "fechada", motivo, ts_s, []
    pos.resultado_r = resultado_r(pos)
    return [motivo]


def resultado_r(pos: Posicao) -> float:
    """Resultado em R (custos incluídos), por unidade preenchida; R = |stop original − médio| / médio."""
    d = pos.plano.lado
    wf = sum(w for _, w in pos.cheias)
    medio = pos.medio
    r_pct = abs(pos.plano.stop - medio) / medio
    pnl = -MAKER * wf
    for w, p, tp in pos.saidas:
        pnl += w * (d * (p / medio - 1) - (MAKER if tp == "lim" else TAKER))
    return (pnl / wf) / r_pct


def risco_usdt(banca: float) -> float:
    return banca * RISCO_PCT


# ================================================================== contexto e estratégias
@dataclass
class Contexto:
    agora_s: int
    velas5: List[list]                 # [[ts_ms, o, h, l, c, v]] fechadas, 5 min, >= 11 dias
    mapa: object                       # conselho.mapa_do_dia.Mapa montado à 00:00 de hoje
    absorcoes: List[Dict] = field(default_factory=list)   # conselho/fluxo.absorcao da última vela de 5 min fechada
    calor_ultimo: Optional[Dict] = None                    # última coluna de livro_historico.mapa_calor
    funding_pct: Optional[float] = None                    # percentil do funding atual nos ~66 dias
    oi_24h_pct: Optional[float] = None                     # variação do open interest em 24 h


def _niveis_composto(mapa) -> Optional[Dict[str, float]]:
    c = getattr(mapa, "composto", None)
    return c if c and all(k in c for k in ("val", "poc", "vah")) else None


def absorcao_borda(ctx: Contexto, distancia: float = 0.003, rr_min: float = 1.5) -> Optional[Plano]:
    comp = _niveis_composto(ctx.mapa)
    if not comp:
        return None
    for e in ctx.absorcoes:
        venda = e["tipo"] == "venda"
        borda = comp["vah"] if venda else comp["val"]
        if venda and e["fechamento"] < borda * (1 - distancia):
            continue
        if not venda and e["fechamento"] > borda * (1 + distancia):
            continue
        p = _plano_absorcao(ctx, e, "absorcao_borda", alvo=comp["poc"], rr_min=rr_min,
                            motivo=f"absorção {'de venda na VAH' if venda else 'de compra na VAL'} do composto "
                                   f"({borda:,.0f}); parede {e['intensidade']:.0f}x, delta {e['delta_btc']:+.0f} BTC, "
                                   f"OI {e['oi_var_pct']:+.2f}%")
        if p:
            return p
    return None


def esticado_absorcao(ctx: Contexto, p_alto: float = 0.90, p_baixo: float = 0.10, oi_min: float = 2.0) -> Optional[Plano]:
    if ctx.funding_pct is None or ctx.oi_24h_pct is None or ctx.oi_24h_pct < oi_min:
        return None
    for e in ctx.absorcoes:
        venda = e["tipo"] == "venda"
        if venda and ctx.funding_pct < p_alto:
            continue
        if not venda and ctx.funding_pct > p_baixo:
            continue
        return _plano_absorcao(ctx, e, "esticado_absorcao", alvo=None, rr_min=2.0,
                               motivo=f"mercado esticado (funding no p{ctx.funding_pct * 100:.0f}, OI 24 h "
                                      f"{ctx.oi_24h_pct:+.1f}%) e absorção {'de venda' if venda else 'de compra'}; "
                                      f"parede {e['intensidade']:.0f}x")
    return None


def _plano_absorcao(ctx: Contexto, e: Dict, robo: str, alvo: Optional[float], rr_min: float, motivo: str) -> Optional[Plano]:
    venda = e["tipo"] == "venda"
    lado = -1 if venda else 1
    fe = float(e["fechamento"])
    # duas limitadas: no fechamento e no meio do caminho até a parede (o preço costuma voltar a testá-la)
    borda_parede = float(e["baixo"]) if venda else float(e["alto"])
    fatias = [(fe, 0.5), ((fe + borda_parede) / 2, 0.5)]
    stop = float(e["alto"]) * 1.001 if venda else float(e["baixo"]) * 0.999
    medio = sum(p * w for p, w in fatias)
    r = abs(stop - medio)
    if r / medio < 0.002:
        return None
    if alvo is None:
        alvo = medio + lado * 2 * r                # venda: 2R abaixo; compra: 2R acima
    if lado * (alvo - medio) < rr_min * r:
        return None
    ts = ctx.agora_s
    return Plano(robo, lado, fatias, round(stop, 2), round(alvo, 2), ts, ts + 30 * 60, 8 * 3600, motivo,
                 {"evento": e})


# ---------------------------------------------------------------- cauda no bloco de 30 min (TPO E2)
CAUDA_MIN = 0.003
CAUDA_FRAC = 0.60
LONGE = 0.005
FOLGA = 0.001
STOP_MIN = 0.004
RR_MIN = 2.0


def _bloco_30m(velas5: Sequence[Sequence[float]], fim_ms: int) -> Optional[Tuple[float, float, float, float, int]]:
    """O bloco de 30 min que acabou em fim_ms (6 candles de 5 min): (abertura, máxima, mínima, fechamento, início_ms)."""
    ini = fim_ms - 1_800_000
    vs = [v for v in velas5 if ini <= v[0] < fim_ms]
    if len(vs) != 6:
        return None
    return float(vs[0][1]), max(float(v[2]) for v in vs), min(float(v[3]) for v in vs), float(vs[-1][4]), ini


def cauda(ctx: Contexto, exigir_calco: bool = False) -> Optional[Plano]:
    agora_ms = ctx.agora_s * 1000
    fim_ms = agora_ms - agora_ms % 1_800_000
    b = _bloco_30m(ctx.velas5, fim_ms)
    if not b:
        return None
    ab, mx, mn, fe, ini = b
    hora = (ini % 86_400_000) / 3_600_000
    dia_semana = ((ini // 86_400_000) + 3) % 7          # 0 = segunda (01/01/1970 foi quinta)
    if dia_semana >= 5 or not (8.0 <= hora <= 19.5):
        return None
    comp = _niveis_composto(ctx.mapa)
    if not comp or comp["vah"] <= comp["val"]:
        return None
    amp = mx - mn
    if amp <= 0:
        return None
    ontem = getattr(ctx.mapa, "ontem", None) or {}
    nakeds = [n["preco"] for n in getattr(ctx.mapa, "naked_pocs", [])]
    antes = [v for v in ctx.velas5 if ini - 4 * 3_600_000 <= v[0] < ini]
    p_de = lambda x: (x - comp["val"]) / (comp["vah"] - comp["val"])
    for lado in (1, -1):
        if lado == 1:
            cauda_tam = min(ab, fe) - mn
            ok_forma = fe >= mn + 2 * amp / 3
            niveis = [("composto VAL", comp["val"]), ("VAL de ontem", ontem.get("val"))] + [("naked POC", x) for x in nakeds]
            niveis = [(n, x) for n, x in niveis if x and mn < x < fe and p_de(x) < 0.25
                      and any(float(v[4]) >= x * (1 + LONGE) for v in antes)]
        else:
            cauda_tam = mx - max(ab, fe)
            ok_forma = fe <= mx - 2 * amp / 3
            niveis = [("composto VAH", comp["vah"]), ("VAH de ontem", ontem.get("vah"))] + [("naked POC", x) for x in nakeds]
            niveis = [(n, x) for n, x in niveis if x and fe < x < mx and p_de(x) > 0.75
                      and any(float(v[4]) <= x * (1 - LONGE) for v in antes)]
        if not niveis or not ok_forma or cauda_tam < CAUDA_MIN * fe or cauda_tam < CAUDA_FRAC * amp:
            continue
        nome, nivel = niveis[0]
        fatias = [(fe, 0.2), (fe - lado * 0.25 * cauda_tam, 0.3), (fe - lado * 0.5 * cauda_tam, 0.5)]
        stop = mn * (1 - FOLGA) if lado == 1 else mx * (1 + FOLGA)
        medio = sum(p * w for p, w in fatias)
        r = abs(stop - medio)
        if r / medio < STOP_MIN:
            continue
        candidatos = [x for x in ([comp["poc"], ontem.get("poc")] + nakeds) if x]
        alvos = sorted((x for x in candidatos if lado * (x - medio) >= RR_MIN * r), key=lambda x: lado * (x - medio))
        if not alvos:
            continue
        calco = None
        if exigir_calco:
            calco = _parede_atras(ctx.calor_ultimo, lado, mn if lado == 1 else mx, nivel)
            if calco is None:
                continue
        robo = "cauda_calco" if exigir_calco else "cauda_borda"
        teto_fim_dia = (ini - ini % 86_400_000 + 20 * 3_600_000) // 1000 - ctx.agora_s
        motivo = (f"cauda {'compradora' if lado == 1 else 'vendedora'} de {cauda_tam / fe * 100:.2f}% no bloco das "
                  f"{int(hora):02d}:{int(hora % 1 * 60):02d} UTC sobre {nome} ({nivel:,.0f})"
                  + (f"; calço no livro: parede {calco[4]:.0f}x em {calco[0]:,.0f}" if calco else ""))
        return Plano(robo, lado, [(round(p, 2), w) for p, w in fatias], round(stop, 2), round(alvos[0], 2), ctx.agora_s,
                     ctx.agora_s + 2 * 3600, max(3600, min(8 * 3600, teto_fim_dia)), motivo,
                     {"nivel": nivel, "bloco_ini_ms": ini})
    return None


def _parede_atras(coluna: Optional[Dict], lado: int, pavio: float, nivel: float, fator: float = 4.0):
    """Parede do mesmo lado (compra para compra) entre o pavio (com 0,3% de folga) e o nível."""
    if not coluna:
        return None
    lo, hi = (pavio * 0.997, nivel) if lado == 1 else (nivel, pavio * 1.003)
    lado_cel = 0 if lado == 1 else 1
    boas = [c for c in coluna.get("celulas", []) if c[2] == lado_cel and c[4] >= fator and c[1] >= lo and c[0] <= hi]
    return max(boas, key=lambda c: c[4]) if boas else None


def cauda_borda(ctx: Contexto) -> Optional[Plano]:
    return cauda(ctx, exigir_calco=False)


def cauda_calco(ctx: Contexto) -> Optional[Plano]:
    return cauda(ctx, exigir_calco=True)


ESTRATEGIAS = {
    "absorcao_borda": absorcao_borda,
    "cauda_borda": cauda_borda,
    "cauda_calco": cauda_calco,
    "esticado_absorcao": esticado_absorcao,
}


def percentil(valor: float, historico: Sequence[float]) -> Optional[float]:
    """Fração do histórico ESTRITAMENTE abaixo do valor. O funding da Bybit fica parado no neutro (0,01%/8 h) a maior
    parte do tempo; com <= o neutro viraria "percentil 100" e o robô acharia o mercado sempre esticado."""
    h = np.asarray([x for x in historico if x is not None], dtype=float)
    return float((h < valor).mean()) if len(h) else None
