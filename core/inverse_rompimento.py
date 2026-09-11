# core/inverse_rompimento.py
"""
ROMPIMENTO DO RANGE no modo inverse: o que fazer quando o preço sai da faixa.

As regras são do usuário. Num range de 57k a 82k, por exemplo:

    - SUBINDO dentro do range: a grade aumenta o short a cada nível, até 100% no topo (core/inverse_grade.py)
    - rompeu o TOPO de verdade  -> fecha todo o short e deixa subir; um range novo vai se formar
    - rompeu o topo em FALSO    -> não fecha nada; deixa voltar para dentro do range
    - rompeu o FUNDO de verdade -> espera o respiro para cima e, no RETESTE do fundo rompido, vende quase 100%
    - rompeu o fundo em FALSO   -> não vende nada; deixa subir

"De verdade" precisa ser uma regra de preço, senão vira palpite:

    - CONFIRMADO: dois fechamentos seguidos além da borda com folga (padrão 1%), ou um único fechamento além de
      três vezes a folga — um rompimento que não deixa dúvida
    - FALSO: o fechamento volta para dentro do range antes de confirmar

A confirmação é só de preço, de propósito. A regra anterior fechava tudo no PRIMEIRO fechamento acima do topo se
a contagem de Elliott estivesse de alta naquele momento — e a contagem estar de alta num pavio acima do topo não
diz que o rompimento é real. Era exatamente o caso em que o usuário não queria fechar.

O short de reteste é o único lugar do modo inverse que vende grande de uma vez, então ele tem regra de saída
explícita: stop se o preço fechar de volta acima do fundo rompido (o rompimento falhou), alvo no alvo de Elliott
abaixo do fundo — ou, sem contagem de baixa, na projeção de 61,8% da altura do range, que é a medida clássica de
um rompimento de faixa.

Nada aqui fala com a corretora: recebe o candle fechado e devolve as execuções. O executor ao vivo e os testes
usam exatamente a mesma máquina.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from core.inverse_grade import PESOS_PADRAO

RANGE = "range"
ROMPENDO_TOPO = "rompendo_topo"
ROMPENDO_FUNDO = "rompendo_fundo"
AGUARDANDO_RETESTE = "aguardando_reteste"
SHORT_RETESTE = "short_reteste"
ENCERRADO = "encerrado"          # topo rompido de verdade: range acabou, sem short
CONCLUIDO = "concluido"          # fundo: o movimento terminou (alvo, ou o reteste não veio)

DESCRICAO = {
    RANGE: "dentro do range: a grade vende subindo e recompra descendo",
    ROMPENDO_TOPO: "acima do topo, ainda sem confirmar: o short fica, nada novo é vendido",
    ROMPENDO_FUNDO: "abaixo do fundo, ainda sem confirmar: nada novo é vendido",
    AGUARDANDO_RETESTE: "fundo rompido de verdade: esperando o respiro para vender no reteste",
    SHORT_RETESTE: "vendido no reteste do fundo rompido",
    ENCERRADO: "topo rompido de verdade: short fechado, esperando um range novo",
    CONCLUIDO: "movimento de baixa concluído, esperando um range novo",
}


def pesos_inverse() -> Dict[float, float]:
    """
    Os níveis DENTRO do range, renormalizados para somar 100% no topo.

    A grade padrão deixava 20% da carteira para vender acima do topo (extensões de 127,2% e 161,8%). Isso é o
    contrário da regra: acima do topo, ou o rompimento é real e o short tem que sair, ou é falso e o short que
    já existe basta. O hedge dial já montava a grade dele assim; o inverse ficou para trás.
    """
    base = {k: v for k, v in PESOS_PADRAO.items() if k <= 1.0}
    total = sum(base.values())
    return {k: v / total for k, v in base.items()}


@dataclass(frozen=True)
class ParametrosRompimento:
    folga: float = 0.01                    # quanto além da borda o fechamento precisa estar para contar
    fechamentos_confirmacao: int = 2       # fechamentos seguidos além da folga que confirmam
    multiplo_rompimento_claro: float = 3.0  # além de 3x a folga, um fechamento só já confirma
    tolerancia_reteste: float = 0.005      # o respiro que chega até 0,5% do fundo rompido já é reteste
    fracao_reteste: float = 0.9            # "quase 100%": o short total depois do reteste
    espera_max_reteste: int = 42           # 42 candles de 4h = 7 dias esperando o reteste
    alvo_fracao_range: float = 0.618       # sem alvo de Elliott, projeta 61,8% da altura do range abaixo do fundo

    def __post_init__(self):
        if not 0 < self.folga < 0.1:
            raise ValueError("a folga do rompimento é uma fração pequena do preço (ex.: 0.01 = 1%)")
        if self.fechamentos_confirmacao < 1:
            raise ValueError("é preciso ao menos um fechamento para confirmar um rompimento")
        if self.multiplo_rompimento_claro <= 1:
            raise ValueError("o rompimento claro tem que ficar além da folga normal")
        if not 0 < self.fracao_reteste <= 1:
            raise ValueError("o short de reteste é uma fração da carteira, entre 0 e 1")
        if self.espera_max_reteste < 1:
            raise ValueError("a espera pelo reteste precisa de ao menos um candle")


@dataclass
class MaquinaRompimento:
    p: ParametrosRompimento = field(default_factory=ParametrosRompimento)
    estado: str = RANGE
    contagem: int = 0
    nivel_rompido: Optional[float] = None
    alvo: Optional[float] = None
    fonte_alvo: Optional[str] = None
    stop: Optional[float] = None
    candles_espera: int = 0
    reteste: Optional[Dict] = None         # {'contratos', 'preco_entrada', 'ts', 'fracao'}
    ultimo_evento: Optional[str] = None

    # ------------------------------------------------------------------ leitura
    @property
    def no_range(self) -> bool:
        """Só dentro do range a grade pode vender. Fora dele o range acabou ou está em xeque."""
        return self.estado == RANGE

    def pnl_nao_realizado(self, preco: float) -> float:
        if not self.reteste or not preco:
            return 0.0
        return self.reteste["contratos"] * (1 / preco - 1 / self.reteste["preco_entrada"])

    # ------------------------------------------------------------------ transições
    def _r(self, execs: Optional[List[Dict]] = None, fechar_grade: bool = False, concluido: bool = False,
           motivo: str = "", evento: Optional[str] = None) -> Dict:
        if evento:
            self.ultimo_evento = evento
        return {"estado": self.estado, "execs": execs or [], "fechar_grade": fechar_grade, "concluido": concluido,
                "motivo": motivo, "evento": evento}

    def _voltar_ao_range(self):
        self.estado, self.contagem, self.candles_espera = RANGE, 0, 0
        self.nivel_rompido = self.alvo = self.fonte_alvo = self.stop = None

    def _alvo(self, low: float, high: float, alvos_elliott: Optional[Sequence[float]]) -> Tuple[float, str]:
        abaixo = [float(a) for a in (alvos_elliott or []) if a and float(a) < low * (1 - self.p.folga)]
        if abaixo:
            return max(abaixo), "Elliott"          # o mais próximo abaixo do fundo
        return low - self.p.alvo_fracao_range * (high - low), "projeção de 61,8% do range"

    def _topo_confirmado(self, high: float, porque: str) -> Dict:
        self.estado, self.contagem = ENCERRADO, 0
        return self._r(fechar_grade=True, evento="topo_confirmado",
                       motivo=f"rompimento do topo {high:,.0f} CONFIRMADO ({porque}): fecha todo o short e deixa subir; "
                              f"um range novo vai se formar")

    def _fundo_confirmado(self, low: float, high: float, alvos_elliott, porque: str) -> Dict:
        self.estado, self.contagem, self.candles_espera = AGUARDANDO_RETESTE, 0, 0
        self.nivel_rompido = low
        self.alvo, self.fonte_alvo = self._alvo(low, high, alvos_elliott)
        return self._r(evento="fundo_confirmado",
                       motivo=f"rompimento do fundo {low:,.0f} CONFIRMADO ({porque}): esperando o respiro para vender no "
                              f"reteste; alvo {self.alvo:,.0f} ({self.fonte_alvo})")

    def _abrir_reteste(self, ts: int, close: float, equity_btc: float, fracao_ja_vendida: float) -> Dict:
        # "quase 100%" é o short TOTAL: fatias de base que ainda estejam abertas contam dentro dele
        fracao = max(0.0, self.p.fracao_reteste - max(float(fracao_ja_vendida or 0.0), 0.0))
        contratos = fracao * max(float(equity_btc or 0.0), 0.0) * close
        if contratos <= 0:
            return self._r(motivo=f"o reteste do fundo {self.nivel_rompido:,.0f} veio, mas não há espaço para vender mais")
        self.reteste = {"contratos": contratos, "preco_entrada": close, "ts": ts, "fracao": round(fracao, 4)}
        self.stop = self.nivel_rompido * (1 + self.p.folga)
        self.estado = SHORT_RETESTE
        ex = {"ts": ts, "tipo": "venda", "nivel": "reteste", "preco": close, "contratos": contratos}
        return self._r([ex], evento="reteste_vendido",
                       motivo=f"reteste do fundo rompido {self.nivel_rompido:,.0f} rejeitado: vendendo {fracao:.0%} da "
                              f"carteira a {close:,.0f}; alvo {self.alvo:,.0f} ({self.fonte_alvo}), stop acima de {self.stop:,.0f}")

    def _fechar_reteste(self, ts: int, preco: float, novo_estado: str, motivo: str, evento: str) -> Dict:
        c, e = self.reteste["contratos"], self.reteste["preco_entrada"]
        pnl = c * (1 / preco - 1 / e)
        ex = {"ts": ts, "tipo": "recompra", "nivel": "reteste", "preco": preco, "contratos": c, "pnl_btc": pnl}
        self.reteste = None
        if novo_estado == RANGE:
            self._voltar_ao_range()
        else:
            self.estado = novo_estado
        return self._r([ex], concluido=novo_estado == CONCLUIDO, evento=evento,
                       motivo=f"{motivo}: recompra a {preco:,.0f}, {pnl:+.6f} BTC")

    # ------------------------------------------------------------------ decisão
    def avaliar(self, ts: int, high: float, low: float, close: float, equity_btc: float,
                range_low: float, range_high: float, alvos_elliott: Optional[Sequence[float]] = None,
                fracao_ja_vendida: float = 0.0) -> Dict:
        """
        Lê um candle FECHADO e devolve {'estado', 'execs', 'fechar_grade', 'concluido', 'motivo', 'evento'}.

        `fechar_grade` pede ao executor que feche as fatias da grade (ela não é vista daqui). `execs` são só as do
        short de reteste, no mesmo formato das execuções da grade.
        """
        p, lo_r, hi_r = self.p, float(range_low), float(range_high)
        acima, acima_claro = hi_r * (1 + p.folga), hi_r * (1 + p.multiplo_rompimento_claro * p.folga)
        abaixo, abaixo_claro = lo_r * (1 - p.folga), lo_r * (1 - p.multiplo_rompimento_claro * p.folga)

        if self.estado in (ENCERRADO, CONCLUIDO):
            return self._r(motivo=f"{DESCRICAO[self.estado]}")

        if self.estado == RANGE:
            if close > acima_claro:
                return self._topo_confirmado(hi_r, f"fechamento a {close:,.0f}, muito além do topo")
            if close > acima:
                self.estado, self.contagem = ROMPENDO_TOPO, 1
                return self._r(evento="rompendo_topo", motivo=f"fechou acima do topo {hi_r:,.0f}: 1/{p.fechamentos_confirmacao} "
                                                              f"para confirmar. O short fica e nada novo é vendido")
            if close < abaixo_claro:
                return self._fundo_confirmado(lo_r, hi_r, alvos_elliott, f"fechamento a {close:,.0f}, muito abaixo do fundo")
            if close < abaixo:
                self.estado, self.contagem = ROMPENDO_FUNDO, 1
                return self._r(evento="rompendo_fundo", motivo=f"fechou abaixo do fundo {lo_r:,.0f}: 1/"
                                                               f"{p.fechamentos_confirmacao} para confirmar")
            return self._r(motivo=DESCRICAO[RANGE])

        if self.estado == ROMPENDO_TOPO:
            if close > acima_claro:
                return self._topo_confirmado(hi_r, f"fechamento a {close:,.0f}, muito além do topo")
            if close > acima:
                self.contagem += 1
                if self.contagem >= p.fechamentos_confirmacao:
                    return self._topo_confirmado(hi_r, f"{self.contagem} fechamentos seguidos acima do topo")
                return self._r(motivo=f"rompendo o topo: {self.contagem}/{p.fechamentos_confirmacao} fechamentos")
            if close <= hi_r:
                self._voltar_ao_range()
                return self._r(evento="topo_falso", motivo=f"rompimento FALSO do topo: fechou de volta a {close:,.0f}, "
                                                           f"dentro do range. O short fica")
            self.contagem = 0              # colado na borda, sem folga: não confirma nem desmente
            return self._r(motivo=f"colado no topo {hi_r:,.0f}, sem folga para confirmar: esperando")

        if self.estado == ROMPENDO_FUNDO:
            if close < abaixo_claro:
                return self._fundo_confirmado(lo_r, hi_r, alvos_elliott, f"fechamento a {close:,.0f}, muito abaixo do fundo")
            if close < abaixo:
                self.contagem += 1
                if self.contagem >= p.fechamentos_confirmacao:
                    return self._fundo_confirmado(lo_r, hi_r, alvos_elliott,
                                                  f"{self.contagem} fechamentos seguidos abaixo do fundo")
                return self._r(motivo=f"rompendo o fundo: {self.contagem}/{p.fechamentos_confirmacao} fechamentos")
            if close >= lo_r:
                self._voltar_ao_range()
                return self._r(evento="fundo_falso", motivo=f"rompimento FALSO do fundo: fechou de volta a {close:,.0f}. "
                                                            f"Não vende nada, deixa subir")
            self.contagem = 0
            return self._r(motivo=f"colado no fundo {lo_r:,.0f}, sem folga para confirmar: esperando")

        if self.estado == AGUARDANDO_RETESTE:
            self.candles_espera += 1
            nivel = self.nivel_rompido
            if close > nivel * (1 + p.folga):
                self._voltar_ao_range()
                return self._r(evento="fundo_retomado", motivo=f"o fundo {nivel:,.0f} foi retomado: o rompimento falhou. "
                                                               f"Volta ao range sem vender")
            if high >= nivel * (1 - p.tolerancia_reteste) and close < nivel:
                return self._abrir_reteste(ts, close, equity_btc, fracao_ja_vendida)
            if close <= self.alvo:
                self.estado = CONCLUIDO
                return self._r(concluido=True, evento="alvo_sem_reteste",
                               motivo=f"chegou ao alvo {self.alvo:,.0f} sem reteste: o movimento aconteceu sem nós")
            if self.candles_espera >= p.espera_max_reteste:
                self.estado = CONCLUIDO
                return self._r(concluido=True, evento="reteste_expirou",
                               motivo=f"o reteste não veio em {self.candles_espera} candles: desiste e espera um range novo")
            return self._r(motivo=f"esperando o reteste do fundo rompido {nivel:,.0f} "
                                  f"({self.candles_espera}/{p.espera_max_reteste} candles)")

        if self.estado == SHORT_RETESTE:
            # o alvo é uma ordem limitada: se o candle tocou, ela executou dentro dele, antes do fechamento
            if low <= self.alvo:
                return self._fechar_reteste(ts, self.alvo, CONCLUIDO, "alvo do short de reteste atingido", "alvo_reteste")
            if close > self.stop:
                return self._fechar_reteste(ts, close, RANGE, "stop do short de reteste: o preço voltou para dentro do "
                                                              "range, o rompimento falhou", "stop_reteste")
            return self._r(motivo=f"vendido no reteste a {self.reteste['preco_entrada']:,.0f}: alvo {self.alvo:,.0f}, "
                                  f"stop acima de {self.stop:,.0f}")

        return self._r(motivo=f"estado desconhecido {self.estado!r}")

    # ------------------------------------------------------------------ persistência
    def as_dict(self) -> Dict:
        return {"estado": self.estado, "contagem": self.contagem, "nivel_rompido": self.nivel_rompido,
                "alvo": self.alvo, "fonte_alvo": self.fonte_alvo, "stop": self.stop,
                "candles_espera": self.candles_espera, "reteste": self.reteste, "ultimo_evento": self.ultimo_evento}

    @classmethod
    def from_dict(cls, d: Optional[Dict], p: Optional[ParametrosRompimento] = None) -> "MaquinaRompimento":
        m = cls(p or ParametrosRompimento())
        if not isinstance(d, dict):
            return m
        m.estado = d.get("estado") if d.get("estado") in DESCRICAO else RANGE
        m.contagem = int(d.get("contagem") or 0)
        m.nivel_rompido, m.alvo, m.stop = d.get("nivel_rompido"), d.get("alvo"), d.get("stop")
        m.fonte_alvo, m.ultimo_evento = d.get("fonte_alvo"), d.get("ultimo_evento")
        m.candles_espera = int(d.get("candles_espera") or 0)
        m.reteste = d.get("reteste") if isinstance(d.get("reteste"), dict) else None
        return m

    def resumo(self, preco: Optional[float] = None) -> Dict:
        out = self.as_dict()
        out["descricao"] = DESCRICAO.get(self.estado, self.estado)
        out["pnl_reteste_btc"] = round(self.pnl_nao_realizado(preco), 6) if preco else None
        return out


# ---------------------------------------------------------------- aprovação do range
def validar_aprovacao(low: Optional[float], high: Optional[float], preco: Optional[float],
                      status_atual: Optional[str], contratos_abertos: float) -> Tuple[List[str], List[str]]:
    """
    O que impede aprovar um range. Devolve (bloqueios, avisos).

    BLOQUEIO não passa nem forçando: range impossível, ou uma grade ainda com short aberto — trocar a grade por
    baixo dela deixaria essa posição na corretora sem ninguém cuidando.
    AVISO passa se o usuário forçar, sabendo o que está fazendo. A rota antiga aceitava tudo calada, inclusive a
    proposta que o próprio robô marcava como inválida.
    """
    bloqueios: List[str] = []
    avisos: List[str] = []
    if not low or not high or high <= low:
        bloqueios.append("informe o fundo (low) e o topo (high) do range, com o topo acima do fundo")
    if contratos_abertos > 0:
        bloqueios.append(f"a grade atual ainda tem short aberto ({contratos_abertos:,.0f} contratos): trocar a grade agora "
                         f"deixaria essa posição na corretora sem gestão. Espere ela zerar")
    if preco is None:
        avisos.append("não consegui conferir o preço atual na corretora")
    elif low and high and high > low and not (low < preco < high):
        avisos.append(f"o preço atual ({preco:,.0f}) está fora do range {low:,.0f}–{high:,.0f}")
    if status_atual != "proposto":
        avisos.append("o robô não tem proposta válida agora: a contagem de Elliott no diário não está corretiva, e o "
                      "modo inverse só vende. Aprovar é vender contra o cenário principal")
    return bloqueios, avisos
