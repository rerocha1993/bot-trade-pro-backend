# core/range_tradeiros.py
"""
O JOGO DO RANGE, do jeito do Tradeiros (resumo das lives em .claude/agents/perito-btc.md):

    - o range é o MERGE dos últimos `n_dias` dias (perfil composto): VAL, POC, VAH, fundo e topo
    - o range só vale se o mercado está em equilíbrio: a maioria dos POCs diários caiu dentro do valor composto
    - compra no VAL (fundo do valor), vende no VAH (topo do valor); NO MEIO NÃO SE OPERA
    - cada toque enfraquece a borda: só o 1º e o 2º toque são operados (o 3º/4º costuma romper)
    - DESVIO: sai do valor e volta — é a entrada mais clara (a maioria dos rompimentos é falsa)
    - ACEITAÇÃO: o dia constrói valor do lado de fora (blocos fechando fora e o POC do dia lá fora) — a borda
      daquele lado não é mais operada contra; opera-se o RETESTE da borda rompida a favor
    - entradas em fatias (ordens limitadas em escada), stop abaixo do fundo (acima do topo), alvo no POC e depois
      na borda oposta; tirar o risco no POC ou no 1:1 realizando metade e levando o stop para o zero a zero

Três jogadas, testadas separadamente:
    'borda'   compra/venda na borda do valor (fade), 1º e 2º toque
    'desvio'  só depois de um bloco fechar fora do valor e outro fechar de volta dentro
    'reteste' depois da aceitação fora do valor, no reteste da borda rompida

Tudo com blocos de 30 min fechados; o contexto de cada dia usa só os dias ANTERIORES completos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.tpo_sessao import BLOCO_MS, DIA_MS, Perfil, merge

SLIPPAGE = 0.0002


@dataclass(frozen=True)
class ParametrosRange:
    n_dias: int = 10                 # merge ~10 dias, como nas lives (janela fixa, se range_adaptativo=False)
    range_adaptativo: bool = True    # o range é o período LATERAL: volta dia a dia enquanto o valor se sobrepõe
    min_dias: int = 3
    max_dias: int = 20
    balanco_min: float = 0.6         # fração dos POCs diários dentro do valor composto
    zona_dentro: float = 0.15        # a zona da borda vai até 15% da largura do valor para dentro
    zona_fora: float = 0.10          # ... e 10% para fora
    toques_max: int = 2
    afastamento_toque: float = 0.40  # para contar um toque novo, o preço tem que ter se afastado 40% da largura
    aceitacao_blocos: int = 8        # 4 h de blocos fechando fora do valor
    rr_min: float = 2.0              # até a borda oposta, com todas as fatias executadas
    espera_armado: int = 8           # a escada fica no livro até 4 h
    tempo_max: int = 144             # 3 dias em blocos de 30 min
    n_fatias: int = 5
    realizar: float = 0.5            # metade no POC ou no 1:1, stop no zero a zero
    folga_stop_pct: float = 0.001


# ------------------------------------------------------------------ contexto do dia
@dataclass
class Contexto:
    val: float
    vah: float
    poc: float
    minima: float
    maxima: float
    valido: bool
    pocs_diarios: List[float]
    dias: int = 0

    @property
    def largura(self) -> float:
        return self.vah - self.val

    def zona(self, lado: int, p: ParametrosRange) -> Tuple[float, float]:
        """(de, até) da zona da borda: lado +1 = compra no VAL, −1 = venda no VAH."""
        w = self.largura
        if lado == 1:
            return self.val - p.zona_fora * w, self.val + p.zona_dentro * w
        return self.vah - p.zona_dentro * w, self.vah + p.zona_fora * w


def contexto(perfis_anteriores: Sequence[Perfil], p: ParametrosRange = ParametrosRange()) -> Optional[Contexto]:
    """
    O range dos últimos `n_dias` dias. É range (equilíbrio) quando o valor anda de lado:
        - as áreas de valor de dias seguidos se SOBREPÕEM (pelo menos metade da menor) em `balanco_min` dos pares
        - o POC não migrou mais que meia largura de valor composto do primeiro para o último dia
    Numa tendência o valor migra: as áreas de valor se descolam e o POC anda.
    """
    if p.range_adaptativo:
        return contexto_adaptativo(perfis_anteriores, p)
    if len(perfis_anteriores) < p.n_dias:
        return None
    janela = list(perfis_anteriores[-p.n_dias:])
    comp = merge(janela)
    val, vah = comp.area_valor()
    pocs = [d.poc() for d in janela]
    vas = [d.area_valor() for d in janela]
    sobrepoe = 0
    for (a0, a1), (b0, b1) in zip(vas, vas[1:]):
        inter = min(a1, b1) - max(a0, b0)
        menor = min(a1 - a0, b1 - b0) or 1e-9
        sobrepoe += inter >= 0.5 * menor
    lateral = sobrepoe / max(len(vas) - 1, 1) >= p.balanco_min
    migrou = abs(pocs[-1] - pocs[0]) > 0.5 * (vah - val)
    return Contexto(val, vah, comp.poc(), comp.minima, comp.maxima, lateral and not migrou and vah > val, pocs, len(janela))


def _sobrepoe(a: Tuple[float, float], b: Tuple[float, float], fracao: float = 0.5) -> bool:
    inter = min(a[1], b[1]) - max(a[0], b[0])
    return inter >= fracao * (min(a[1] - a[0], b[1] - b[0]) or 1e-9)


def contexto_adaptativo(perfis_anteriores: Sequence[Perfil], p: ParametrosRange = ParametrosRange()) -> Optional[Contexto]:
    """
    O range como um trader desenha ("merge dos dias do range"): parte de ontem e volta dia a dia enquanto a área
    de valor do dia se sobrepõe (pelo menos metade) à área de valor do range montado até ali. Para no primeiro dia
    que não se sobrepõe — ali o valor estava em outro lugar (tendência). Range de verdade tem `min_dias` ou mais.
    """
    if not perfis_anteriores:
        return None
    dias = [perfis_anteriores[-1]]
    for d in reversed(perfis_anteriores[-p.max_dias:-1]):
        va_range = merge(dias).area_valor()
        if not _sobrepoe(d.area_valor(), va_range):
            break
        dias.insert(0, d)
    comp = merge(dias)
    val, vah = comp.area_valor()
    return Contexto(val, vah, comp.poc(), comp.minima, comp.maxima, len(dias) >= p.min_dias and vah > val,
                    [d.poc() for d in dias], len(dias))


def aceitacao(blocos_do_dia: Sequence[Tuple], ctx: Contexto, p: ParametrosRange = ParametrosRange()) -> int:
    """+1 aceitou ACIMA do valor, −1 ABAIXO, 0 não. Blocos fechando fora e o POC do dia (até agora) lá fora."""
    if len(blocos_do_dia) < p.aceitacao_blocos:
        return 0
    acima = sum(1 for b in blocos_do_dia if b[4] > ctx.vah)
    abaixo = sum(1 for b in blocos_do_dia if b[4] < ctx.val)
    poc_dia = Perfil(list(blocos_do_dia), tick=None).poc()
    if acima >= p.aceitacao_blocos and poc_dia > ctx.vah:
        return 1
    if abaixo >= p.aceitacao_blocos and poc_dia < ctx.val:
        return -1
    return 0


# ------------------------------------------------------------------ plano da entrada
@dataclass
class Plano:
    lado: int
    niveis: List[float]
    stop: float
    alvo1: float
    alvo2: float
    jogada: str
    motivo: str

    @property
    def medio_todas(self) -> float:
        return sum(self.niveis) / len(self.niveis)

    @property
    def rr(self) -> float:
        risco = abs(self.medio_todas - self.stop)
        return abs(self.alvo2 - self.medio_todas) / risco if risco > 0 else 0.0


def plano_borda(ctx: Contexto, lado: int, jogada: str, p: ParametrosRange, fundo_extra: Optional[float] = None,
                preco_ref: Optional[float] = None) -> Optional[Plano]:
    """Escada de fatias na zona da borda, stop além do fundo/topo do range, alvo no POC e na borda oposta."""
    de, ate = ctx.zona(lado, p)
    alto, baixo = max(de, ate), min(de, ate)
    niveis = list(np.linspace(alto, baixo, p.n_fatias)) if lado == 1 else list(np.linspace(baixo, alto, p.n_fatias))
    folga = (preco_ref or ctx.poc) * p.folga_stop_pct
    if lado == 1:
        extremo = min(ctx.minima, ctx.val - 0.25 * ctx.largura, fundo_extra if fundo_extra is not None else ctx.minima)
        stop, alvo1, alvo2 = extremo - folga, ctx.poc, ctx.vah
    else:
        extremo = max(ctx.maxima, ctx.vah + 0.25 * ctx.largura, fundo_extra if fundo_extra is not None else ctx.maxima)
        stop, alvo1, alvo2 = extremo + folga, ctx.poc, ctx.val
    pl = Plano(lado, niveis, stop, alvo1, alvo2, jogada,
               f"{jogada}: {'compra no VAL' if lado == 1 else 'venda no VAH'} do merge de {ctx.dias or p.n_dias} dias "
               f"(VAL {ctx.val:,.0f} POC {ctx.poc:,.0f} VAH {ctx.vah:,.0f}), stop {stop:,.0f}")
    return pl if pl.rr >= p.rr_min else None


def plano_reteste(ctx: Contexto, lado: int, p: ParametrosRange, preco_ref: float) -> Optional[Plano]:
    """Aceitou fora do valor: compra o reteste do VAH rompido (vende o reteste do VAL rompido)."""
    w = ctx.largura
    borda = ctx.vah if lado == 1 else ctx.val
    niveis = list(np.linspace(borda + lado * 0.10 * w, borda - lado * 0.10 * w, p.n_fatias))
    stop = borda - lado * 0.35 * w - lado * preco_ref * p.folga_stop_pct
    medio = sum(niveis) / len(niveis)
    alvo1 = medio + lado * abs(medio - stop)            # 1:1
    alvo2 = borda + lado * w                            # projeção de uma largura de valor
    pl = Plano(lado, niveis, stop, alvo1, alvo2, "reteste",
               f"reteste: aceitou {'acima do VAH' if lado == 1 else 'abaixo do VAL'} {borda:,.0f}, "
               f"{'compra' if lado == 1 else 'venda'} no reteste, stop de volta dentro do valor {stop:,.0f}")
    return pl if pl.rr >= p.rr_min else None


# ------------------------------------------------------------------ execução de um trade (fatias + tirar o risco)
@dataclass
class Posicao:
    plano: Plano
    q: float                                   # quantidade de CADA fatia (em unidades de R por preço)
    exec_: List[Tuple[float, float]] = field(default_factory=list)
    pendentes: List[float] = field(default_factory=list)
    stop: float = 0.0
    realizado: float = 0.0
    custo: float = 0.0
    parcial_feita: bool = False
    blocos: int = 0
    i_primeira: Optional[int] = None

    @property
    def qtd(self) -> float:
        return sum(x for _, x in self.exec_)

    @property
    def medio(self) -> float:
        return sum(pr * x for pr, x in self.exec_) / self.qtd if self.exec_ else 0.0


def abrir(pl: Plano) -> Posicao:
    """Tamanho: se TODAS as fatias executarem e o stop bater, a perda é 1 R."""
    q = 1.0 / abs(pl.medio_todas - pl.stop) / len(pl.niveis)
    return Posicao(pl, q, [], list(pl.niveis), pl.stop)


def passo_posicao(pos: Posicao, bloco: Tuple, gestao: str, p: ParametrosRange) -> Optional[Dict]:
    """
    Um bloco fechado sobre a posição. Ordem (pior caso): stop, realização/alvos, fatias novas, tempo.
    Devolve o resultado quando o trade termina; None enquanto segue.
    """
    _, _, h, l, c, _ = bloco
    s = pos.plano.lado
    if pos.exec_:
        pos.blocos += 1
        if (l <= pos.stop) if s == 1 else (h >= pos.stop):
            saida = pos.stop * (1 - s * SLIPPAGE)
            return _fechar(pos, saida, TAXA_TAKER, "zero_a_zero" if pos.parcial_feita else "stop")
        if gestao == "tradeiros" and not pos.parcial_feita:
            um_r = pos.medio + s * abs(pos.medio - pos.plano.stop)
            gatilho = min(pos.plano.alvo1, um_r) if s == 1 else max(pos.plano.alvo1, um_r)
            if (h >= gatilho) if s == 1 else (l <= gatilho):
                q_real = pos.qtd * p.realizar
                pos.realizado += (gatilho - pos.medio) * q_real * s
                pos.custo += gatilho * q_real * TAXA_MAKER
                medio = pos.medio
                # tira a metade de CADA fatia (o preço médio do resto não muda)
                pos.exec_ = [(pr, x * (1 - p.realizar)) for pr, x in pos.exec_]
                pos.stop = medio
                pos.parcial_feita = True
                pos.pendentes = []
        if (h >= pos.plano.alvo2) if s == 1 else (l <= pos.plano.alvo2):
            return _fechar(pos, pos.plano.alvo2, TAXA_MAKER, "alvo")
        if pos.blocos >= p.tempo_max:
            return _fechar(pos, c, TAXA_TAKER, "tempo")
    for nivel in list(pos.pendentes):
        if (l <= nivel) if s == 1 else (h >= nivel):
            pos.exec_.append((nivel, pos.q))
            pos.custo += nivel * pos.q * TAXA_MAKER
            pos.pendentes.remove(nivel)
    return None


def _fechar(pos: Posicao, saida: float, taxa: float, motivo: str) -> Dict:
    s = pos.plano.lado
    bruto = pos.realizado + (saida - pos.medio) * pos.qtd * s
    custo = pos.custo + saida * pos.qtd * taxa
    return {"lado": s, "jogada": pos.plano.jogada, "bruto_r": bruto, "custo_r": custo, "liquido_r": bruto - custo,
            "motivo": motivo, "fatias": sum(1 for _ in pos.exec_), "rr_planejado": pos.plano.rr}


# ------------------------------------------------------------------ backtest
class BacktestRange:
    def __init__(self, blocos: Sequence[Tuple], jogada: str = "borda", gestao: str = "tradeiros",
                 p: ParametrosRange = ParametrosRange()):
        self.blocos = list(blocos)
        self.jogada = jogada
        self.gestao = gestao
        self.p = p

    def executar(self, inicio_ms: int = 0, fim_ms: Optional[int] = None) -> Dict:
        p = self.p
        por_dia: Dict[int, list] = {}
        for b in self.blocos:
            por_dia.setdefault(b[0] // DIA_MS, []).append(b)
        dias_ord = sorted(por_dia)
        perfis = {d: Perfil(por_dia[d]) for d in dias_ord}
        trades: List[Dict] = []
        pos: Optional[Posicao] = None
        armado: Optional[Tuple[Plano, int]] = None
        for k, d in enumerate(dias_ord):
            if d * DIA_MS < inicio_ms - DIA_MS or (fim_ms is not None and d * DIA_MS >= fim_ms):
                continue
            olhar = p.max_dias if p.range_adaptativo else p.n_dias
            ctx = contexto([perfis[x] for x in dias_ord[max(0, k - olhar):k]], p) if k >= p.min_dias else None
            hoje: List[Tuple] = []
            toques = {1: self._toques_anteriores(dias_ord, por_dia, k, ctx, 1),
                      -1: self._toques_anteriores(dias_ord, por_dia, k, ctx, -1)}
            longe = {1: True, -1: True}
            desvio = {1: None, -1: None}
            for b in por_dia[d]:
                ts, _, h, l, c, _ = b
                if ts < inicio_ms or (fim_ms is not None and ts >= fim_ms):
                    continue
                hoje.append(b)
                # 1) leitura do bloco (sempre, com ou sem posição): toques na borda, desvio, aceitação
                ac = 0
                if ctx is not None:
                    w = ctx.largura
                    for lado in (1, -1):
                        de, ate = ctx.zona(lado, p)
                        na_zona = (l <= ate) if lado == 1 else (h >= de)
                        afastado = (c >= ctx.val + p.afastamento_toque * w) if lado == 1 else (c <= ctx.vah - p.afastamento_toque * w)
                        rodou = (c >= ctx.poc) if lado == 1 else (c <= ctx.poc)   # rotação: foi até o POC
                        if rodou:
                            toques[lado], longe[lado] = 0, True
                        elif na_zona and longe[lado]:
                            toques[lado] += 1
                            longe[lado] = False
                        elif afastado:
                            longe[lado] = True
                        if (c < ctx.val) if lado == 1 else (c > ctx.vah):          # fechou fora do valor
                            desvio[lado] = (l if lado == 1 else h) if desvio[lado] is None else \
                                (min(desvio[lado], l) if lado == 1 else max(desvio[lado], h))
                    ac = aceitacao(hoje, ctx, p)
                # 2) posição aberta (ou escada esperando execução)
                if pos is not None:
                    r = passo_posicao(pos, b, self.gestao, p)
                    if r is not None:
                        r["ts"] = ts
                        trades.append(r)
                        pos, armado = None, None
                    elif not pos.exec_ and armado is not None:
                        armado = (armado[0], armado[1] + 1)
                        alvo1 = pos.plano.alvo1
                        andou = (h >= alvo1) if pos.plano.lado == 1 else (l <= alvo1)
                        if armado[1] >= p.espera_armado or andou:
                            pos, armado = None, None          # a escada não executou: cancela
                # 3) sinal, só sem posição
                if pos is None and ctx is not None:
                    pl = self._sinal(ctx, b, ac, toques, desvio)
                    if pl is not None:
                        pos = abrir(pl)
                        armado = (pl, 0)
                # o desvio vale até o preço fechar de volta dentro do valor (usado ou não)
                if ctx is not None:
                    for lado in (1, -1):
                        if desvio[lado] is not None and ((c > ctx.val) if lado == 1 else (c < ctx.vah)):
                            desvio[lado] = None
        return resumo(trades)

    def _toques_anteriores(self, dias_ord, por_dia, k, ctx, lado) -> int:
        """
        Retestes da borda SEM rotação ("a bola quicando"): cada vez que o preço volta à zona sem ter ido até o POC
        conta um toque; chegar no POC zera. O 3º/4º toque seguido costuma romper.
        """
        if ctx is None:
            return 0
        p = self.p
        de, ate = ctx.zona(lado, p)
        w = ctx.largura
        n, longe = 0, True
        for d in dias_ord[max(0, k - (ctx.dias or p.n_dias)):k]:
            for _, _, h, l, c, _ in por_dia[d]:
                if (c >= ctx.poc) if lado == 1 else (c <= ctx.poc):
                    n, longe = 0, True
                elif ((l <= ate) if lado == 1 else (h >= de)) and longe:
                    n += 1
                    longe = False
                elif (c >= ctx.val + p.afastamento_toque * w) if lado == 1 else (c <= ctx.vah - p.afastamento_toque * w):
                    longe = True
        return n

    def _sinal(self, ctx: Contexto, b, ac: int, toques, desvio) -> Optional[Plano]:
        p = self.p
        _, _, h, l, c, _ = b
        w = ctx.largura
        if self.jogada == "reteste":
            if ac == 0:
                return None
            borda = ctx.vah if ac == 1 else ctx.val
            perto = abs(c - borda) <= 0.30 * w
            return plano_reteste(ctx, ac, p, c) if perto else None
        if not ctx.valido:
            return None
        for lado in (1, -1):
            if ac == -lado:                       # aceitou do lado de fora desta borda: não se opera contra
                continue
            if toques[lado] > p.toques_max:
                continue
            if self.jogada == "borda":
                # arma quando o preço se aproxima da borda (nunca no meio)
                perto = (ctx.val - p.zona_fora * w <= c <= ctx.val + 0.45 * w) if lado == 1 else \
                        (ctx.vah - 0.45 * w <= c <= ctx.vah + p.zona_fora * w)
                if perto:
                    pl = plano_borda(ctx, lado, "borda", p, preco_ref=c)
                    if pl is not None:
                        return pl
            elif self.jogada == "desvio":
                voltou = desvio[lado] is not None and ((c > ctx.val) if lado == 1 else (c < ctx.vah))
                if voltou:
                    pl = plano_borda(ctx, lado, "desvio", p, fundo_extra=desvio[lado], preco_ref=c)
                    if pl is not None:
                        return pl
        return None


def resumo(trades: List[Dict]) -> Dict:
    if not trades:
        return {"trades": 0, "soma_r": 0.0, "medio_r": 0.0, "acerto": None, "fator_lucro": None,
                "compra_r": 0.0, "venda_r": 0.0, "n_compra": 0, "n_venda": 0, "saidas": {}, "lista": []}
    t = np.array([x["liquido_r"] for x in trades])
    ld = np.array([x["lado"] for x in trades])
    ganhos, perdas = t[t > 0].sum(), -t[t <= 0].sum()
    saidas: Dict[str, int] = {}
    for x in trades:
        saidas[x["motivo"]] = saidas.get(x["motivo"], 0) + 1
    return {"trades": len(t), "soma_r": round(float(t.sum()), 2), "medio_r": round(float(t.mean()), 4),
            "acerto": round(float((t > 0).mean()), 3), "fator_lucro": round(float(ganhos / perdas), 2) if perdas > 0 else None,
            "compra_r": round(float(t[ld == 1].sum()), 2), "venda_r": round(float(t[ld == -1].sum()), 2),
            "n_compra": int((ld == 1).sum()), "n_venda": int((ld == -1).sum()), "saidas": saidas, "lista": trades}
