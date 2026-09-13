# tradeiros/carteira.py
"""
CARTEIRA do Tradeiros simulada em BTC: é assim que eles medem ("cai 10%, perco 3–4%"; mais BTC no bolso).

    colateral    BTC no inverse (coin-M), sem alavancagem: segurar o colateral = estar comprado
    hedge        tranches vendidas em contratos de 1 USD: P&L_BTC = contratos × (1/entrada − 1/saída). Sobe em escada na
                 VAH (limitadas), realiza na VAL (LIFO); o stop de cada escada é pedágio acima do topo (R27)
    trades       compra/venda direcional das fatias do plano: tamanho = risco × patrimônio ÷ |1/médio − 1/stop|;
                 stop a mercado com slippage (R21); em 1 R realiza a fração do perfil e leva o stop ao médio (R22);
                 alvo na borda oposta (R23); entrada mal preenchida que saiu da zona fecha (R24); "reação" antes de
                 armar as ordens do Maroja fora do valor (candle de 30 min que toca a zona e fecha na metade oposta)
    dia          o plano é refeito à 00:00 UTC com o que fechou; ordens não executadas do dia anterior são canceladas
    custos       maker nas limitadas, taker + slippage no stop e a mercado, funding a cada 8 h (vendido recebe)

Ordem dentro do candle, sempre a PESSIMISTA: fatias do caminho → stop → (só em candle seguinte) 1 R e alvo.
Resultado contra segurar 1 BTC: BTC final, retorno em USD, drawdown em BTC, em USD e do HODL.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.tpo_sessao import DIA_MS
from tradeiros.regras import Decisao, Perfil, Plano, medio_das_fatias, planejar, precos_das_fatias

SLIPPAGE = 0.0002
MEIA_HORA = 30 * 60 * 1000
HEDGE_TETO = 1.0                    # vendido no máximo o patrimônio inteiro: coin-M sem risco de liquidação


def pnl_btc(lado: int, contratos: float, entrada: float, saida: float) -> float:
    """Contratos inverse de 1 USD. lado +1 comprado, −1 vendido."""
    return lado * contratos * (1 / entrada - 1 / saida)


@dataclass
class Fatia:
    preco: float
    contratos: float
    feita: bool = False


@dataclass
class Trade:
    lado: int
    decisao: Decisao
    fatias: List[Fatia]
    stop: float
    alvo: float
    dia: int
    risco_btc: float
    lado_ordem: int = 0             # lado das limitadas (o do plano); `lado` é o do P&L — difere só no sorteio
    armado: bool = True
    stop_original: float = 0.0
    contratos: float = 0.0          # abertos agora
    preenchido: float = 0.0         # que chegaram a entrar
    medio: float = 0.0
    risco_tirado: bool = False
    resultado_btc: float = 0.0
    saida: str = ""

    @property
    def planejado(self) -> float:
        return sum(f.contratos for f in self.fatias)

    @property
    def r(self) -> Optional[float]:
        return self.resultado_btc / self.risco_btc if self.risco_btc > 0 else None


@dataclass
class Escada:
    vende: bool                     # True = sobe o hedge; False = recompra (realiza)
    fatias: List[Fatia]
    stop: Optional[float]
    regras: List[str] = field(default_factory=list)
    acao_vende: Optional[bool] = None   # o que faz ao executar; None = o mesmo lado da borda (difere só no sorteio)


class Carteira:
    def __init__(self, blocos: Sequence[Sequence[float]], planejador: Callable[[int, Optional[float]], Optional[Plano]],
                 perfil: Perfil, funding: Optional[Dict[int, float]] = None, btc_inicial: float = 1.0,
                 guardar_log: bool = False, sortear=None):
        """`sortear` (random.Random): régua de acaso — mesmas ordens e mesmos candles, direção de cada trade e de cada
        escada de hedge sorteada (stop e alvo espelhados no preço médio planejado)."""
        self.sortear = sortear
        self.blocos = blocos
        self.planejador = planejador
        self.perfil = perfil
        self.funding = funding or {}
        self.btc_inicial = btc_inicial
        self.guardar_log = guardar_log

    # ------------------------------------------------------------------ contabilidade
    def _taxa(self, contratos: float, preco: float, taker: bool) -> None:
        t = contratos / preco * (TAXA_TAKER if taker else TAXA_MAKER)
        self.btc -= t
        self.taxas += t

    def patrimonio(self, preco: float) -> float:
        aberto = sum(pnl_btc(-1, tr[0], tr[1], preco) for tr in self.tranches)
        aberto += sum(pnl_btc(t.lado, t.contratos, t.medio, preco) for t in self.abertos if t.contratos > 0)
        return self.btc + aberto

    def hedge_frac(self, preco: float) -> float:
        eq = self.patrimonio(preco)
        return sum(tr[0] for tr in self.tranches) / (eq * preco) if eq > 0 else 0.0

    def _vende_hedge(self, contratos: float, preco: float, stop: Optional[float], taker: bool = False) -> None:
        livre = HEDGE_TETO * self.patrimonio(preco) * preco - sum(tr[0] for tr in self.tranches)
        contratos = min(contratos, max(0.0, livre))
        if contratos <= 0:
            return
        self.tranches.append([contratos, preco, stop])
        self._taxa(contratos, preco, taker)

    def _recompra_hedge(self, contratos: float, preco: float, taker: bool = False) -> None:
        while contratos > 1e-9 and self.tranches:
            tr = self.tranches[-1]                                  # LIFO: realiza primeiro o que vendeu por último
            q = min(contratos, tr[0])
            self.btc += pnl_btc(-1, q, tr[1], preco)
            self._taxa(q, preco, taker)
            tr[0] -= q
            contratos -= q
            if tr[0] <= 1e-9:
                self.tranches.pop()

    def _entra(self, t: Trade, f: Fatia, preco: float, taker: bool = False) -> None:
        c = f.contratos
        # médio de contratos inverse é harmônico
        t.medio = (t.contratos + c) / ((t.contratos / t.medio if t.contratos else 0.0) + c / preco)
        t.contratos += c
        t.preenchido += c
        f.feita = True
        self._taxa(c, preco, taker)
        t.resultado_btc -= c / preco * (TAXA_TAKER if taker else TAXA_MAKER)

    def _sai(self, t: Trade, contratos: float, preco: float, taker: bool = False) -> None:
        contratos = min(contratos, t.contratos)
        pnl = pnl_btc(t.lado, contratos, t.medio, preco)
        self.btc += pnl
        t.resultado_btc += pnl
        self._taxa(contratos, preco, taker)
        t.resultado_btc -= contratos / preco * (TAXA_TAKER if taker else TAXA_MAKER)
        t.contratos -= contratos

    def _fecha(self, t: Trade, motivo: str) -> None:
        t.saida = motivo
        t.fatias = [f for f in t.fatias if f.feita]
        self.abertos.remove(t)
        self.fechados.append(t)

    # ------------------------------------------------------------------ plano do dia
    def _novo_dia(self, ts: int, preco: float, primeiro: bool) -> None:
        for t in list(self.abertos):                                # cancela o que não executou
            t.fatias = [f for f in t.fatias if f.feita]
            if t.contratos <= 0:
                self.abertos.remove(t)
        self.escadas = []
        try:
            plano = self.planejador(ts, None if primeiro else self.hedge_frac(preco))
        except ValueError:
            plano = None
        if plano is None:
            return
        eq = self.patrimonio(preco)
        if primeiro and plano.hedge_alvo > 0:
            self._vende_hedge(plano.hedge_alvo * eq * preco, preco, None, taker=True)
        for d in plano.decisoes:
            if self.guardar_log:
                self.log.append({"ts": ts, "tipo": d.tipo, "regras": d.regras, "motivo": d.motivo, "zona": d.zona,
                                 "stop": d.stop, "alvo": d.alvo, "risco": d.risco, "fracao_hedge": d.fracao_hedge,
                                 "hedge_alvo": plano.hedge_alvo})
            if d.tipo in ("compra", "venda_direcional") and d.zona and d.stop and d.alvo and d.risco > 0:
                lado = 1 if d.tipo == "compra" else -1
                if any((t.lado_ordem or t.lado) == lado for t in self.abertos):   # um trade por lado; nada de salvar outro (R26)
                    continue
                pesos = d.pesos_fatias or [1.0]
                medio = medio_das_fatias(d.zona, pesos, d.tipo)
                dist = abs(1 / medio - 1 / d.stop)
                if dist <= 0:
                    continue
                risco_btc = d.risco * eq
                total = risco_btc / dist
                fatias = [Fatia(p, total * w) for p, w in zip(precos_das_fatias(d.zona, len(pesos), d.tipo), pesos)]
                lado_pnl, stop, alvo = lado, d.stop, d.alvo
                if self.sortear is not None and self.sortear.random() < 0.5:
                    lado_pnl, stop, alvo = -lado, 2 * medio - d.stop, 2 * medio - d.alvo
                self.abertos.append(Trade(lado_pnl, d, fatias, stop, alvo, ts // DIA_MS, risco_btc, lado_ordem=lado,
                                          armado=not d.exige_reacao, stop_original=stop))
            elif d.tipo in ("hedge_aumentar", "hedge_realizar") and d.zona and d.fracao_hedge > 0:
                vende = d.tipo == "hedge_aumentar"
                pesos = d.pesos_fatias or [1.0]
                precos = precos_das_fatias(d.zona, len(pesos), "venda_direcional" if vende else "compra")
                acao = vende if self.sortear is None or self.sortear.random() >= 0.5 else not vende
                stop = (d.stop if vende else max(precos) * (1 + self.perfil.folga_pedagio)) if acao else None
                self.escadas.append(Escada(vende, [Fatia(p, d.fracao_hedge * w * eq * p) for p, w in zip(precos, pesos)],
                                           stop, d.regras, acao_vende=acao))

    # ------------------------------------------------------------------ candle de 30 min
    def _candle_trades(self, o: float, h: float, l: float, c: float) -> None:
        pf = self.perfil
        for t in list(self.abertos):
            lo, hi = t.decisao.zona
            s = t.lado_ordem or t.lado                              # execução segue o plano; stop, 1 R e alvo seguem o P&L
            if not t.armado:
                if s == 1:
                    tocou, reagiu = l <= hi, c >= l + 0.5 * (h - l) and c >= lo and l > t.decisao.stop
                else:
                    tocou, reagiu = h >= lo, c <= h - 0.5 * (h - l) and c <= hi and h < t.decisao.stop
                if tocou and reagiu:
                    t.armado = True
                    for f in t.fatias:                              # fatias que o candle tocou entram a mercado no fechamento
                        if (s == 1 and f.preco >= l) or (s == -1 and f.preco <= h):
                            self._entra(t, f, c, taker=True)
                continue
            novos = 0
            for f in t.fatias:
                if not f.feita and ((s == 1 and l <= f.preco) or (s == -1 and h >= f.preco)):
                    self._entra(t, f, min(f.preco, o) if s == 1 else max(f.preco, o))
                    novos += 1
            if t.contratos <= 0:
                continue
            if (t.lado == 1 and l <= t.stop) or (t.lado == -1 and h >= t.stop):
                px = (min(t.stop, o) * (1 - SLIPPAGE)) if t.lado == 1 else (max(t.stop, o) * (1 + SLIPPAGE))
                self._sai(t, t.contratos, px, taker=True)
                self._fecha(t, "zero_a_zero" if t.risco_tirado else "stop")
                continue
            if novos:
                continue                                            # o que entrou neste candle não realiza nele
            r = abs(t.medio - t.stop_original)
            if not t.risco_tirado and r > 0:
                nivel = t.medio + t.lado * r
                if (t.lado == 1 and h >= nivel) or (t.lado == -1 and l <= nivel):
                    self._sai(t, t.contratos * pf.realizar_em_1r, nivel)
                    t.stop, t.risco_tirado = t.medio, True
                    t.fatias = [f for f in t.fatias if f.feita]
            if (t.lado == 1 and h >= t.alvo) or (t.lado == -1 and l <= t.alvo):
                self._sai(t, t.contratos, t.alvo)
                self._fecha(t, "alvo")
                continue
            largura = hi - lo
            if not t.risco_tirado and t.preenchido < pf.preenchimento_minimo * t.planejado:
                if (s == 1 and c > hi + largura) or (s == -1 and c < lo - largura):
                    self._sai(t, t.contratos, c, taker=True)
                    self._fecha(t, "mal_preenchida")

    def _candle_hedge(self, o: float, h: float, l: float) -> None:
        for e in self.escadas:
            acao = e.vende if e.acao_vende is None else e.acao_vende
            for f in e.fatias:
                if f.feita or not ((e.vende and h >= f.preco) or (not e.vende and l <= f.preco)):
                    continue
                px = max(f.preco, o) if e.vende else min(f.preco, o)
                if acao:
                    self._vende_hedge(f.contratos, px, e.stop)
                else:
                    self._recompra_hedge(f.contratos, px)
                f.feita = True
        for tr in list(self.tranches):                              # pedágio: stopado, a carteira volta a ficar comprada
            if tr[2] is not None and h >= tr[2]:
                px = max(tr[2], o) * (1 + SLIPPAGE)
                self.btc += pnl_btc(-1, tr[0], tr[1], px)
                self._taxa(tr[0], px, True)
                self.tranches.remove(tr)
                self.stops_hedge += 1

    def _pagar_funding(self, taxa: float, preco: float) -> None:
        vendido = sum(tr[0] for tr in self.tranches) + sum(t.contratos for t in self.abertos if t.lado == -1)
        comprado = sum(t.contratos for t in self.abertos if t.lado == 1)
        f = (vendido - comprado) / preco * taxa
        self.btc += f
        self.funding_btc += f

    # ------------------------------------------------------------------ execução
    def executar(self, inicio: int, fim: int) -> Dict:
        bl = [b for b in self.blocos if inicio <= b[0] < fim]
        if not bl:
            return {"erro": "sem candles no período"}
        self.btc, self.tranches, self.escadas, self.abertos, self.fechados = self.btc_inicial, [], [], [], []
        self.taxas = self.funding_btc = 0.0
        self.stops_hedge = 0
        self.log: List[Dict] = []
        p0 = float(bl[0][1])
        dia = None
        pico_btc = pico_usd = pico_hodl = 0.0
        dd_btc = dd_usd = dd_hodl = 0.0
        soma_hedge = 0.0
        for i, b in enumerate(bl):
            ts, o, h, l, c = int(b[0]), float(b[1]), float(b[2]), float(b[3]), float(b[4])
            if ts // DIA_MS != dia:
                dia = ts // DIA_MS
                self._novo_dia(ts, o, primeiro=(i == 0))
            self._candle_trades(o, h, l, c)
            self._candle_hedge(o, h, l)
            taxa_f = self.funding.get(ts + MEIA_HORA)
            if taxa_f:
                self._pagar_funding(taxa_f, c)
            eq = self.patrimonio(c)
            soma_hedge += self.hedge_frac(c)
            pico_btc, pico_usd, pico_hodl = max(pico_btc, eq), max(pico_usd, eq * c), max(pico_hodl, self.btc_inicial * c)
            dd_btc = min(dd_btc, eq / pico_btc - 1)
            dd_usd = min(dd_usd, eq * c / pico_usd - 1)
            dd_hodl = min(dd_hodl, c / (pico_hodl / self.btc_inicial) - 1)
        c = float(bl[-1][4])
        for t in list(self.abertos):
            if t.contratos > 0:
                self._sai(t, t.contratos, c, taker=True)
                self._fecha(t, "fim")
        eq = self.patrimonio(c)
        saidas = Counter(t.saida for t in self.fechados)
        rs = [t.r for t in self.fechados if t.r is not None]
        return {
            "operador": self.perfil.nome, "inicio": inicio, "fim": fim,
            "btc_final": round(eq, 6), "ganho_btc_pct": round((eq / self.btc_inicial - 1) * 100, 2),
            "retorno_usd_pct": round((eq * c / (self.btc_inicial * p0) - 1) * 100, 2),
            "hodl_usd_pct": round((c / p0 - 1) * 100, 2),
            "dd_btc_pct": round(dd_btc * 100, 2), "dd_usd_pct": round(dd_usd * 100, 2), "dd_hodl_pct": round(dd_hodl * 100, 2),
            "hedge_medio_pct": round(soma_hedge / len(bl) * 100, 1), "hedge_final_pct": round(self.hedge_frac(c) * 100, 1),
            "stops_hedge": self.stops_hedge, "funding_btc": round(self.funding_btc, 6), "taxas_btc": round(self.taxas, 6),
            "trades": len(self.fechados), "saidas": dict(saidas),
            "r_total": round(sum(rs), 2), "r_medio": round(sum(rs) / len(rs), 3) if rs else None,
            "log": self.log if self.guardar_log else None,
            "lista_trades": [{"lado": t.lado, "dia": t.dia, "medio": round(t.medio, 2), "stop": t.stop_original,
                              "alvo": t.alvo, "saida": t.saida, "r": None if t.r is None else round(t.r, 2),
                              "regras": t.decisao.regras} for t in self.fechados],
        }


def planejador_tradeiros(dados, perfil: Perfil) -> Callable[[int, Optional[float]], Optional[Plano]]:
    """Liga a leitura do dia e o mapa de Elliott às regras do perfil, sempre com o que fechou até ts."""
    from tradeiros.elliott_mapa import MapaElliott
    from tradeiros.leitura import LeituraDiaria
    leitura, mapa = LeituraDiaria(dados), MapaElliott(dados)
    cache: Dict[int, Tuple] = {}                                    # a leitura do dia não depende da carteira: os sorteios reusam

    def planejador(ts: int, hedge_atual: Optional[float]) -> Optional[Plano]:
        if ts not in cache:
            cache[ts] = (leitura.ler(ts), mapa.ler(ts))
        lt, mp = cache[ts]
        return planejar(lt, mp, perfil, hedge_atual)
    return planejador
