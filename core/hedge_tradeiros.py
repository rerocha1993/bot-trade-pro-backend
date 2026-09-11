# core/hedge_tradeiros.py
"""
HEDGE DE CARTEIRA do jeito do Tradeiros, no contrato inverse (margem em BTC):

    "Shortar 20–40% da carteira em BTC contra a resistência, sem vender o BTC, e receber funding: 70% sobe junto e
     30% fica para comprar nas quedas." O short é realização parcial, não aposta de queda.

Regras (fixadas antes do teste):
    - só com range válido (merge adaptativo, core/range_tradeiros.py)
    - escada de 4 vendas na resistência: VAH − 15% da largura, VAH, meio caminho até o topo, topo do range;
      cada uma com `fatia` da carteira (35% no total)
    - recompra metade do short no POC e o resto no VAL (realiza cada lado no extremo oposto)
    - rompeu de verdade (aceitação acima do valor, ou fechamento além do topo com folga): fecha o short
      (variantes para teste: só o fechamento além do topo, ou nenhum stop)
    - funding a cada 8 h sobre o valor vendido (positivo = o vendido recebe)
Resultado em BTC: quanto a carteira termina a mais (ou a menos) do que só segurar o BTC.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.range_tradeiros import ParametrosRange, aceitacao, contexto
from core.tpo_sessao import DIA_MS, Perfil

SLIPPAGE = 0.0002


@dataclass(frozen=True)
class ParametrosHedge:
    fatia: float = 0.0875          # 4 x 8,75% = 35% da carteira no máximo
    folga_rompimento: float = 0.005
    funding: bool = True
    stop: str = "aceitacao_ou_preco"   # "aceitacao_ou_preco" | "preco" (só fechamento além do topo) | "nenhum"


class BacktestHedgeTradeiros:
    def __init__(self, blocos: Sequence[Tuple], funding: Optional[Dict[int, float]] = None,
                 p: ParametrosHedge = ParametrosHedge(), pr: ParametrosRange = ParametrosRange()):
        self.blocos = list(blocos)
        self.funding = funding or {}
        self.p = p
        self.pr = pr

    def executar(self, inicio_ms: int = 0, fim_ms: Optional[int] = None, btc_inicial: float = 1.0) -> Dict:
        p, pr = self.p, self.pr
        por: Dict[int, list] = {}
        for b in self.blocos:
            por.setdefault(b[0] // DIA_MS, []).append(b)
        dias = sorted(por)
        perfis = {d: Perfil(por[d]) for d in dias}
        btc = btc_inicial
        shorts: List[Tuple[float, float]] = []          # (preço de entrada, contratos em USD)
        pendentes: List[float] = []
        realizado = funding_btc = taxas = 0.0
        eventos = {"vendas": 0, "recompras": 0, "stops": 0, "stops_aceitacao": 0}
        ganho_recompras = perda_stops = 0.0
        curva: List[Tuple[int, float, float]] = []
        ctx_ativo = None
        recomprou_poc = False
        for k, d in enumerate(dias):
            if d * DIA_MS < inicio_ms or (fim_ms is not None and d * DIA_MS >= fim_ms):
                continue
            ctx = contexto([perfis[x] for x in dias[max(0, k - pr.max_dias):k]], pr) if k >= pr.min_dias else None
            hoje = []
            if ctx is not None and ctx.valido and not shorts:
                ctx_ativo = ctx
                w = ctx.largura
                topo = max(ctx.maxima, ctx.vah + 0.1 * w)
                pendentes = [ctx.vah - 0.15 * w, ctx.vah, (ctx.vah + topo) / 2, topo]
            elif not shorts and (ctx is None or not ctx.valido):
                ctx_ativo, pendentes = None, []
            for b in por[d]:
                ts, _, h, l, c, _ = b
                hoje.append(b)
                cx = ctx_ativo
                if shorts and cx is not None:
                    total = sum(x for _, x in shorts)
                    # rompeu de verdade: fecha tudo
                    por_preco = c > max(cx.maxima, cx.vah) * (1 + p.folga_rompimento)
                    por_aceitacao = p.stop == "aceitacao_ou_preco" and aceitacao(hoje, cx, pr) == 1
                    rompeu = p.stop != "nenhum" and (por_preco or por_aceitacao)
                    if rompeu:
                        saida = c * (1 + SLIPPAGE)
                        for e, x in shorts:
                            realizado += x * (1 / saida - 1 / e)
                            perda_stops += x * (1 / saida - 1 / e)
                        taxas += total / saida * TAXA_TAKER
                        shorts, pendentes, ctx_ativo, recomprou_poc = [], [], None, False
                        eventos["stops"] += 1
                        eventos["stops_aceitacao"] += 0 if por_preco else 1
                    else:
                        # recompra metade no POC (uma vez por ciclo) e o resto no VAL
                        for alvo, fracao in ((cx.poc, 0.5), (cx.val, 1.0)):
                            if fracao < 1 and recomprou_poc:
                                continue
                            if shorts and l <= alvo:
                                q_total = sum(x for _, x in shorts)
                                q_rec = q_total * fracao
                                recomprou_poc = recomprou_poc or fracao < 1
                                restante = []
                                for e, x in shorts:        # proporcional em todas as entradas
                                    parte = x * (q_rec / q_total)
                                    realizado += parte * (1 / alvo - 1 / e)
                                    ganho_recompras += parte * (1 / alvo - 1 / e)
                                    restante.append((e, x - parte))
                                taxas += q_rec / alvo * TAXA_MAKER
                                shorts = [(e, x) for e, x in restante if x > 1e-9]
                                eventos["recompras"] += 1
                                if not shorts:
                                    pendentes, ctx_ativo, recomprou_poc = [], None, False
                # vendas da escada DEPOIS da gestão do short que já existia (o candle não diz a ordem dos preços)
                if ctx_ativo is not None:
                    for nivel in list(pendentes):
                        if h >= nivel:
                            contratos = p.fatia * btc * nivel
                            shorts.append((nivel, contratos))
                            taxas += contratos / nivel * TAXA_MAKER
                            pendentes.remove(nivel)
                            eventos["vendas"] += 1
                # funding a cada 8 h sobre o short aberto
                if p.funding and shorts:
                    taxa_f = self.funding.get(ts + 30 * 60 * 1000)
                    if taxa_f:
                        f = sum(x for _, x in shorts) * taxa_f / c
                        funding_btc += f
                aberto = sum(x * (1 / c - 1 / e) for e, x in shorts)
                curva.append((ts, btc + realizado + funding_btc - taxas + aberto, c))
        btc_fim = btc + realizado + funding_btc - taxas
        if shorts:
            c = curva[-1][2]
            btc_fim += sum(x * (1 / c - 1 / e) for e, x in shorts)
        return {"btc_final": round(float(btc_fim), 6), "ganho_btc_pct": round(float(btc_fim / btc_inicial - 1) * 100, 2),
                "realizado_btc": round(float(realizado), 6), "funding_btc": round(float(funding_btc), 6),
                "taxas_btc": round(float(taxas), 6), "ganho_recompras_btc": round(float(ganho_recompras), 6),
                "perda_stops_btc": round(float(perda_stops), 6),
                **eventos, "curva": curva}
