# conselho/avisos.py
"""
AVISOS do conselho: só informação, sem probabilidade, sem stop, sem alvo.

    mapa          às 00:00, 08:00 e 13:30 UTC (abertura de Ásia, Europa e América): os níveis conhecidos naquele
                  momento, para o humano ler antes da sessão. Um por sessão por dia.
    proximidade   preço a até 0,2% de um nível do composto (VAL/POC/VAH), de um naked POC ou da abertura da
                  semana. No máximo UM aviso por nível por dia.

Todo aviso carrega a ressalva fixa (RESSALVA): nos estudos de 20/10/2026 nenhum nível de TPO fez o preço reagir
acima de um preço sorteado. O aviso diz onde o preço está; quem decide é o humano.

Função pura: `avaliar(mapa, preco, estado) -> [Aviso]`. `estado` guarda o que já foi avisado (ids) e é
atualizado pela própria função; o serviço o reconstrói do data/avisos.jsonl ao subir (Estado.de_registros).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set

from conselho.mapa_do_dia import DIA_MS, NOME_SESSAO, Mapa, Nivel, distancia_pct

RESSALVA = "nível de TPO não bate o sorteio nos estudos de 20/10; informação, não gatilho"
PROXIMIDADE_PCT = 0.2
JANELA_MAPA_MIN = 30                       # o aviso de mapa sai até 30 min depois da hora (serviço roda a cada 60 s)
HORAS_MAPA = (("asia", 0, 0), ("europa", 8, 0), ("america", 13, 30))
PREFIXOS_PROXIMIDADE = ("composto.", "naked.", "abertura.semana")
NOME_POSICAO = {"fundo": "fundo do composto", "meio": "meio do composto", "topo": "topo do composto",
                "fora_abaixo": "fora do composto, abaixo", "fora_acima": "fora do composto, acima",
                "sem_composto": "sem composto"}


@dataclass(frozen=True)
class Aviso:
    id: str                     # "<dia>:<tipo>:<chave>": um por nível (ou sessão) por dia
    tipo: str                   # "mapa" | "proximidade" | "absorcao" | "presos"
    ts: int
    chave: str
    titulo: str
    texto: str
    preco: float
    nivel: Optional[Dict] = None
    ressalva: str = RESSALVA

    def as_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Estado:
    enviados: Set[str] = field(default_factory=set)

    @classmethod
    def de_registros(cls, registros: Iterable[Dict]) -> "Estado":
        return cls({str(r["id"]) for r in registros if r.get("id")})


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def _linha(n: Nivel, preco: float) -> str:
    d = distancia_pct(n.preco, preco)
    return f"{n.rotulo}: {_fmt(n.preco)} ({d:+.2f}%)"


def _hora(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%d/%m %H:%M")


def texto_mapa(m: Mapa, preco: float, sessao: str) -> str:
    linhas = [f"Mapa do dia — abre a sessão {NOME_SESSAO[sessao]} ({_hora(m.ts)} UTC)",
              f"Preço {_fmt(preco)} · {NOME_POSICAO.get(m.posicao, m.posicao)}"]
    linhas += [_linha(n, preco) for n in sorted(m.niveis, key=lambda n: -n.preco)]
    linhas.append(RESSALVA)
    return "\n".join(linhas)


def avisos_de_mapa(m: Mapa, preco: float, estado: Estado) -> List[Aviso]:
    dia = m.ts // DIA_MS
    minuto = (m.ts % DIA_MS) // 60_000
    out = []
    for sessao, h, mi in HORAS_MAPA:
        inicio = h * 60 + mi
        if not (inicio <= minuto < inicio + JANELA_MAPA_MIN):
            continue
        id_ = f"{dia}:mapa:{sessao}"
        if id_ in estado.enviados or not m.niveis:
            continue
        estado.enviados.add(id_)
        out.append(Aviso(id_, "mapa", m.ts, f"mapa.{sessao}", f"Mapa do dia · {NOME_SESSAO[sessao]}",
                         texto_mapa(m, preco, sessao), float(preco)))
    return out


def avisos_de_proximidade(m: Mapa, preco: float, estado: Estado) -> List[Aviso]:
    dia = m.ts // DIA_MS
    out = []
    for n in m.niveis:
        if not n.chave.startswith(PREFIXOS_PROXIMIDADE):
            continue
        d = distancia_pct(n.preco, preco)
        if abs(d) > PROXIMIDADE_PCT:
            continue
        id_ = f"{dia}:proximidade:{n.chave}"
        if id_ in estado.enviados:
            continue
        estado.enviados.add(id_)
        lado = "acima" if d > 0 else "abaixo" if d < 0 else "em cima"
        texto = (f"Preço {_fmt(preco)} a {abs(d):.2f}% de {n.rotulo} ({_fmt(n.preco)}), nível {lado} do preço. "
                 f"Posição: {NOME_POSICAO.get(m.posicao, m.posicao)}. {RESSALVA}")
        out.append(Aviso(id_, "proximidade", m.ts, n.chave, f"Perto de {n.rotulo}", texto, float(preco),
                         {**asdict(n), "distancia_pct": d}))
    return out


def avaliar(m: Mapa, preco: float, estado: Estado) -> List[Aviso]:
    """Os avisos novos deste instante; `estado` sai atualizado com os ids emitidos."""
    if not m.niveis or not preco:
        return []
    return avisos_de_mapa(m, preco, estado) + avisos_de_proximidade(m, preco, estado)


# ----------------------------------------------------------------- avisos de fluxo (absorção e presos)
RESSALVA_FLUXO = "leitura de fluxo ainda sem % medido contra sorteio; informação, não gatilho"
JANELA_PRESOS_S = 2 * 3600          # só avisa presos confirmados nas últimas 2 h
JANELA_ABSORCAO_S = 3600            # e absorção da última hora


def _hora_s(ts_s: float) -> str:
    return datetime.fromtimestamp(ts_s, tz=timezone.utc).strftime("%H:%M UTC")


def _dia_s(ts_s: float) -> str:
    return datetime.fromtimestamp(ts_s, tz=timezone.utc).strftime("%Y-%m-%d")


def avisos_de_fluxo(presos: Iterable[Dict], absorcoes: Iterable[Dict], preco: float, estado: Estado,
                    agora_s: float, passo_presos_s: int = 1800) -> List[Aviso]:
    """
    Avisos novos de absorção (conselho/fluxo.absorcao) e de presos CONFIRMADOS no footprint (conselho/fluxo.presos).
    Cada evento sai uma vez só (``estado.enviados``); eventos antigos (fora das janelas) não saem.
    """
    out: List[Aviso] = []
    for e in absorcoes:
        if agora_s - e["ts"] > JANELA_ABSORCAO_S:
            continue
        aid = f"{_dia_s(e['ts'])}:absorcao:{e['ts']}:{e['tipo']}"
        if aid in estado.enviados:
            continue
        topo = e["tipo"] == "venda"
        parede = f"{_fmt(e['baixo'])}–{_fmt(e['alto'])}"
        titulo = (f"Absorção no topo: parede de venda em {parede}" if topo
                  else f"Absorção no fundo: parede de compra em {parede}")
        quem = "Compra" if topo else "Venda"
        texto = (f"{quem} agressiva de {abs(e['delta_btc']):.0f} BTC na vela das {_hora_s(e['ts'])} "
                 f"({abs(e['delta_z']):.1f} desvios acima do normal), com o open interest subindo {e['oi_var_pct']:+.2f}%, "
                 f"bateu numa parede {e['intensidade']:.0f}x maior que o normal ({e['parede_btc']:.0f} BTC) "
                 f"e o preço não passou: fechou em {_fmt(e['fechamento'])}. "
                 + ("Compradores alavancados ficaram presos no topo." if topo else "Vendedores alavancados ficaram presos no fundo.")
                 + f" Preço agora: {_fmt(preco)}.")
        out.append(Aviso(aid, "absorcao", int(agora_s * 1000), f"absorcao:{e['ts']}", titulo, texto, preco,
                         {"baixo": e["baixo"], "alto": e["alto"], "lado": e["tipo"]}, RESSALVA_FLUXO))
        estado.enviados.add(aid)
    for e in presos:
        if e.get("confirmado") is not True or agora_s - e["ts"] > JANELA_PRESOS_S:
            continue
        aid = f"{_dia_s(e['ts'])}:presos:{e['ts']}:{e['lado']}"
        if aid in estado.enviados:
            continue
        compradores = e["lado"] == "compradores"
        dist = distancia_pct(e["preco"], preco)
        titulo = f"{'Compradores' if compradores else 'Vendedores'} presos em {_fmt(e['preco'])} ({passo_presos_s // 60} min)"
        texto = (f"{e['btc']:.0f} BTC {'comprados' if compradores else 'vendidos'} a mercado "
                 f"({e['vezes']:.0f}x a média da vela) {'no topo' if compradores else 'no fundo'} da vela das {_hora_s(e['ts'])}, "
                 f"e as velas seguintes fecharam {'abaixo' if compradores else 'acima'}: quem entrou ali está no prejuízo. "
                 f"No reteste desse preço, o Tradeiros procura {'venda, com stop acima' if compradores else 'compra, com stop abaixo'} "
                 f"da vela. Preço agora: {_fmt(preco)} ({dist:+.2f}% do nível).")
        out.append(Aviso(aid, "presos", int(agora_s * 1000), f"presos:{e['ts']}", titulo, texto, preco,
                         {"preco": e["preco"], "lado": e["lado"]}, RESSALVA_FLUXO))
        estado.enviados.add(aid)
    return out
