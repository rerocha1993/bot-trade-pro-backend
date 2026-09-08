# core/inverse_grade.py
"""
GRADE inversa de acumulação de BTC (short-only, sem stop, entradas e saídas escalonadas).

Princípios (do usuário):
    - o range é um trilho de níveis de Fibonacci (0 .. 100% e extensões 127,2% / 161,8%);
    - cada nível recebe uma fatia da carteira, dividida em sub-fatias com preços progressivos dentro do degrau
      (entrada escalonada, ordens limitadas esperando o preço, nunca valor fechado a mercado);
    - uma fatia vendida no preço P só é recomprada em um nível ABAIXO de P: toda recompra é lucro em BTC
      (contratos x (1/recompra - 1/venda) > 0). Nunca se recompra com prejuízo e nunca há stop;
    - se o preço rompe o topo, as fatias restantes vão sendo vendidas nas extensões até 100% da carteira
      (= totalmente em dólar); depois o bot só espera o preço voltar;
    - short de base guiado por Elliott: se a contagem mestre aponta queda abaixo do fundo, as fatias mais
      baixas ficam abertas até o alvo de Elliott em vez de recomprar no fundo.

Medidas: BTC realizado (só cresce) e BTC marcado a mercado (pode cair enquanto o preço está acima das vendas).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

NIVEIS_RANGE = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
EXTENSOES = [1.272, 1.618]
# fração da carteira vendida ao completar cada nível (acumulado chega a 1.0 na última extensão)
PESOS_PADRAO = {0.236: 0.08, 0.382: 0.12, 0.5: 0.15, 0.618: 0.15, 0.786: 0.15, 1.0: 0.15, 1.272: 0.10, 1.618: 0.10}


@dataclass
class Fatia:
    nivel: float                 # nível de Fibonacci de origem
    preco_venda: float           # preço-limite de venda
    preco_recompra: float        # preço-limite de recompra (um degrau abaixo)
    fracao: float                # fração da carteira
    contratos: float = 0.0
    vendida_em: Optional[int] = None
    recomprada_em: Optional[int] = None
    ciclos: int = 0              # quantas vezes a fatia já vendeu/recomprou
    base: bool = False           # fatia de base (Elliott): recompra só no alvo
    ativa: bool = True           # False = nível abaixo do preço atual; só volta a valer quando o preço cair abaixo dele


@dataclass
class GradeInversa:
    low: float
    high: float
    pesos: Dict[float, float] = field(default_factory=lambda: dict(PESOS_PADRAO))
    subfatias: int = 3           # sub-fatias por degrau (entrada escalonada)
    taxa: float = 0.0002
    fatias: List[Fatia] = field(default_factory=list)
    btc_realizado: float = 0.0
    taxas_btc: float = 0.0
    alvo_base: Optional[float] = None    # alvo de Elliott para as fatias de base
    fracao_base: float = 0.0

    def __post_init__(self):
        if not self.fatias:
            self.fatias = self._montar()

    # ------------------------------------------------------------ montagem
    def preco_nivel(self, n: float) -> float:
        return self.low + n * (self.high - self.low)

    def _montar(self) -> List[Fatia]:
        niveis = sorted(self.pesos)
        fatias: List[Fatia] = []
        for i, n in enumerate(niveis):
            inicio = self.preco_nivel(niveis[i - 1]) if i > 0 else self.low
            fim = self.preco_nivel(n)
            recompra = inicio          # recompra no nível de baixo (degrau anterior)
            peso = self.pesos[n] / self.subfatias
            for k in range(self.subfatias):
                # sub-fatias progressivas dentro do degrau: 1/3, 2/3, 3/3 do caminho até o nível
                pv = inicio + (fim - inicio) * (k + 1) / self.subfatias
                fatias.append(Fatia(nivel=n, preco_venda=round(pv, 2), preco_recompra=round(recompra, 2), fracao=peso))
        return fatias

    # ------------------------------------------------------------ simulação
    def desativar_abaixo(self, preco: float):
        """Ao montar a grade: níveis abaixo do preço atual só entram depois que o preço cair abaixo deles."""
        for f in self.fatias:
            if f.contratos <= 0 and f.preco_venda <= preco:
                f.ativa = False

    def processar_candle(self, ts: int, high: float, low: float, close: float, equity_btc: float,
                         mestre: Optional[Dict] = None, vender: bool = True) -> List[Dict]:
        """
        Executa as ordens limitadas tocadas pelo candle. Vendas na subida (high >= preco_venda) só para fatias
        ativas e se `vender`; recompras na descida (low <= preco_recompra). Devolve a lista de execuções.
        """
        execs = []
        # reativa níveis que o preço voltou a ficar abaixo (vão vender na próxima subida)
        for f in self.fatias:
            if not f.ativa and low < f.preco_venda * 0.995:
                f.ativa = True
        # short de base: fatias mais baixas passam a recomprar só no alvo de Elliott
        if mestre and mestre.get("status", "ativa") == "ativa" and mestre.get("vies") == "bear":
            alvos = [a for a in (mestre.get("alvos") or []) if a and a < self.low]
            if alvos:
                self.alvo_base = max(alvos)          # alvo mais próximo abaixo do fundo
                prob = float(mestre.get("prob_sucesso") or mestre.get("probabilidade") or 0.5)
                self.fracao_base = round(0.5 * prob, 3)
            else:
                self.alvo_base, self.fracao_base = None, 0.0
        else:
            self.alvo_base, self.fracao_base = None, 0.0
        acumulado = 0.0
        for f in sorted(self.fatias, key=lambda x: x.preco_venda):
            f.base = self.alvo_base is not None and acumulado < self.fracao_base
            acumulado += f.fracao
        # vendas (ordens limitadas de venda tocadas pela máxima)
        for f in self.fatias:
            if vender and f.ativa and f.contratos <= 0 and high >= f.preco_venda:
                contratos = f.fracao * equity_btc * f.preco_venda
                f.contratos, f.vendida_em = contratos, ts
                self.taxas_btc += contratos / f.preco_venda * self.taxa
                execs.append({"ts": ts, "tipo": "venda", "nivel": f.nivel, "preco": f.preco_venda, "contratos": round(contratos)})
        # recompras (ordens limitadas de compra tocadas pela mínima), sempre abaixo da venda
        for f in self.fatias:
            if f.contratos > 0 and f.vendida_em != ts:
                alvo = self.alvo_base if (f.base and self.alvo_base) else f.preco_recompra
                if low <= alvo:
                    pnl = f.contratos * (1 / alvo - 1 / f.preco_venda)
                    self.btc_realizado += pnl
                    self.taxas_btc += f.contratos / alvo * self.taxa
                    execs.append({"ts": ts, "tipo": "recompra", "nivel": f.nivel, "preco": alvo, "contratos": round(f.contratos), "pnl_btc": round(pnl, 6)})
                    f.contratos, f.recomprada_em, f.ciclos = 0.0, ts, f.ciclos + 1
        return execs

    # ------------------------------------------------------------ estado
    def contratos_abertos(self) -> float:
        return sum(f.contratos for f in self.fatias)

    def fracao_aberta(self) -> float:
        return sum(f.fracao for f in self.fatias if f.contratos > 0)

    def pnl_nao_realizado(self, preco: float) -> float:
        return sum(f.contratos * (1 / preco - 1 / f.preco_venda) for f in self.fatias if f.contratos > 0)

    def resumo(self, preco: float) -> Dict:
        return {"low": self.low, "high": self.high, "fracao_aberta": round(self.fracao_aberta(), 3),
                "contratos": round(self.contratos_abertos()), "btc_realizado": round(self.btc_realizado, 6),
                "pnl_aberto_btc": round(self.pnl_nao_realizado(preco), 6), "ciclos": sum(f.ciclos for f in self.fatias),
                "alvo_base": self.alvo_base, "fracao_base": self.fracao_base,
                "niveis": [{"nivel": f.nivel, "venda": f.preco_venda, "recompra": f.preco_recompra, "aberta": f.contratos > 0, "ciclos": f.ciclos}
                           for f in self.fatias]}

    def ordens_pendentes(self) -> List[Dict]:
        """Ordens limitadas que deveriam estar no livro agora (para o executor real)."""
        out = []
        for f in self.fatias:
            if f.contratos <= 0:
                out.append({"lado": "sell", "preco": f.preco_venda, "fracao": f.fracao, "nivel": f.nivel})
            else:
                alvo = self.alvo_base if (f.base and self.alvo_base) else f.preco_recompra
                out.append({"lado": "buy", "preco": alvo, "contratos": f.contratos, "nivel": f.nivel, "reduce_only": True})
        return out
