# conselho/mapa_do_dia.py
"""
MAPA DO DIA: os níveis de TPO que o humano olharia ao abrir a tela, calculados COMO SE FOSSE NAQUELE MOMENTO
(`agora_ms`): só entra candle já fechado, e o composto e o "dia anterior" usam dias completos.

    composto     merge fixo dos 10 dias completos anteriores: VAL, POC, VAH (fundo e topo informados à parte)
    ontem        último dia completo: POC, VAH, VAL, máxima e mínima
    sessões      Ásia (00–08 UTC), Europa (08–13:30) e América (13:30–20) de ontem, e as de hoje já fechadas:
                 máxima, mínima e POC
    naked POCs   POCs de dias anteriores que o preço ainda não voltou a tocar (os 5 mais próximos do preço)
    naked de prazo longo  quando o serviço passa `longos` (naked_longos com ~400 dias): POCs de tempo (TPO) e de
                 volume do dia, da semana e do mês que o preço não voltou a tocar, até 25% do preço, os 6 mais
                 perto acima e abaixo; níveis a até 0,2% um do outro viram um só, com todas as origens no rótulo.
                 Com eles, os naked da linha de cima saem da lista de níveis (continuam em `naked_pocs` para os robôs)
    aberturas    abertura do dia, da semana (segunda UTC) e do mês
    pivô virgem  abertura diária que nenhum dia seguinte tocou: a mais perto acima e abaixo (janela de 30 dias)
    posição      onde o preço está no composto: fundo / meio / topo / fora_abaixo / fora_acima

Cada nível sai com rótulo em português e distância % ao preço. É INFORMAÇÃO, não gatilho: os estudos de
20/10/2026 (data/estudo_niveis_tpo_resumo.md e _2_resumo.md) mostraram que nenhum desses níveis faz o preço
reagir acima de um preço sorteado. Por isso aqui não há probabilidade, stop nem alvo.

Função pura: `mapa(candles_5m, agora_ms) -> Mapa`. O mesmo código roda ao vivo (services/avisos_service.py) e
em cima do histórico.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from conselho.tpo import DIA_MS, SESSOES, Perfil, dias as perfis_por_dia, merge, naked_pocs, sessoes, tick_para
from conselho.niveis import pivo_virgem, posicao_no_range

CANDLE_MS = 5 * 60 * 1000
DIAS_COMPOSTO = 10
MIN_DIAS_COMPOSTO = 3
N_NAKED = 5
N_NAKED_LONGO_LADO = 6
FAIXA_NAKED_LONGO = 0.25
JUNTAR_NAKED_PCT = 0.2
ORDEM_PERIODO = {"mes": 0, "semana": 1, "dia": 2}
JANELA_VIRGEM_DIAS = 30
NOME_SESSAO = {"asia": "Ásia", "europa": "Europa", "america": "América"}
QUARTIL = 0.25


@dataclass(frozen=True)
class Nivel:
    chave: str                  # identidade estável do nível no dia (ex.: "composto.val", "naked.1760000000000")
    grupo: str                  # composto | ontem | sessao | naked | abertura | pivo
    rotulo: str                 # em português, para o humano
    preco: float
    distancia_pct: float        # (nível / preço − 1) × 100: positivo = acima do preço
    dia_ms: Optional[int] = None


@dataclass
class Mapa:
    ts: int
    preco: float
    posicao: str = "sem_composto"
    p: Optional[float] = None
    dias_no_composto: int = 0
    composto: Optional[Dict[str, float]] = None
    ontem: Optional[Dict[str, float]] = None
    sessoes_ontem: Dict[str, Dict[str, float]] = field(default_factory=dict)
    sessoes_hoje: Dict[str, Dict[str, float]] = field(default_factory=dict)
    aberturas: Dict[str, Optional[float]] = field(default_factory=dict)
    pivo_virgem: Dict[str, Optional[float]] = field(default_factory=dict)
    naked_pocs: List[Dict] = field(default_factory=list)
    naked_longos: List[Dict] = field(default_factory=list)
    niveis: List[Nivel] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return asdict(self)

    def nivel(self, chave: str) -> Optional[Nivel]:
        return next((n for n in self.niveis if n.chave == chave), None)


# ------------------------------------------------------------------ peças
def distancia_pct(nivel: float, preco: float) -> float:
    return round((float(nivel) / float(preco) - 1.0) * 100.0, 3) if preco else 0.0


def posicao_no_composto(p: Optional[float]) -> str:
    if p is None:
        return "sem_composto"
    if p < 0:
        return "fora_abaixo"
    if p > 1:
        return "fora_acima"
    if p <= QUARTIL:
        return "fundo"
    if p >= 1 - QUARTIL:
        return "topo"
    return "meio"


def _duracao(candles: Sequence[Sequence[float]]) -> int:
    if len(candles) < 2:
        return CANDLE_MS
    return max(1, min(int(candles[i + 1][0]) - int(candles[i][0]) for i in range(min(len(candles) - 1, 50))))


def diarios_de(candles: Sequence[Sequence[float]]) -> List[list]:
    """Candles diários (UTC) a partir dos intradiários: [dia_ms, open, high, low, close, volume]."""
    por_dia: Dict[int, list] = {}
    for c in candles:
        d = int(c[0]) // DIA_MS
        x = por_dia.get(d)
        if x is None:
            por_dia[d] = [d * DIA_MS, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)]
        else:
            x[2] = max(x[2], float(c[2]))
            x[3] = min(x[3], float(c[3]))
            x[4] = float(c[4])
            x[5] += float(c[5] or 0)
    return [por_dia[d] for d in sorted(por_dia)]


def _niveis_perfil(p: Perfil) -> Dict[str, float]:
    val, vah = p.area_valor()
    return {"poc": float(p.poc()), "val": float(val), "vah": float(vah), "maxima": float(p.maxima), "minima": float(p.minima),
            "inicio": int(p.inicio)}


def _data(dia_ms: int) -> str:
    return datetime.fromtimestamp(dia_ms / 1000, tz=timezone.utc).strftime("%d/%m")


# ------------------------------------------------------------------ naked de prazo longo
def _poc_volume(candles: Sequence[Sequence[float]], tick: float) -> Optional[float]:
    """Faixa com mais volume, cada candle pesando no seu preço típico (máxima + mínima + fechamento) / 3."""
    h: Dict[int, float] = {}
    for c in candles:
        k = int(((float(c[2]) + float(c[3]) + float(c[4])) / 3) // tick)
        h[k] = h.get(k, 0.0) + float(c[5] or 0)
    if not h or max(h.values()) <= 0:
        return None
    return round((max(h, key=h.get) + 0.5) * tick, 2)


def naked_longos(candles_5m: Sequence[Sequence[float]], ate_ms: int) -> List[Dict]:
    """
    POCs de tempo (TPO de 30 min) e de volume de cada dia, semana (segunda UTC) e mês COMPLETOS antes do dia de
    `ate_ms` que nenhum dia seguinte, até ontem, voltou a tocar. O mapa ainda tira os que o preço tocar hoje.
    Cada item: {"periodo": dia|semana|mes, "tipo": tempo|volume, "preco", "inicio_ms", "fim_ms"}.
    """
    ate_dia = int(ate_ms) // DIA_MS
    velas = sorted((c for c in candles_5m if int(c[0]) // DIA_MS < ate_dia), key=lambda c: int(c[0]))
    if not velas:
        return []
    tick = tick_para(float(velas[-1][4]))
    perfis = {p.inicio // DIA_MS: p for p in perfis_por_dia(velas)}
    velas_dia: Dict[int, list] = {}
    for c in velas:
        velas_dia.setdefault(int(c[0]) // DIA_MS, []).append(c)
    faixa_dia = {int(x[0]) // DIA_MS: (float(x[3]), float(x[2])) for x in diarios_de(velas)}
    primeiro = min(faixa_dia)

    grupos: Dict[tuple, List[int]] = {}
    for d in sorted(perfis):
        dt = datetime.fromtimestamp(d * DIA_MS / 1000, tz=timezone.utc)
        mes0 = int(dt.replace(day=1).timestamp() * 1000) // DIA_MS
        prox = dt.replace(day=1, month=dt.month % 12 + 1, year=dt.year + (dt.month == 12))
        for chave, ini, fim in (("dia", d, d + 1), ("semana", d - ((d + 3) % 7), d - ((d + 3) % 7) + 7),
                                ("mes", mes0, int(prox.timestamp() * 1000) // DIA_MS)):
            if ini >= primeiro and fim <= ate_dia:          # só período inteiro dentro dos dados
                grupos.setdefault((chave, ini, fim), []).append(d)

    out: List[Dict] = []
    for (periodo, ini, fim), ds in grupos.items():
        ps = [perfis[d] for d in ds]
        tempo = float(ps[0].poc() if len(ps) == 1 else merge(ps).poc())
        volume = _poc_volume([c for d in ds for c in velas_dia.get(d, [])], tick)
        depois = [faixa_dia[d] for d in range(fim, ate_dia) if d in faixa_dia]
        for tipo, poc in (("tempo", tempo), ("volume", volume)):
            if poc is None or any(lo <= poc <= hi for lo, hi in depois):
                continue
            out.append({"periodo": periodo, "tipo": tipo, "preco": poc, "inicio_ms": ini * DIA_MS, "fim_ms": fim * DIA_MS})
    return sorted(out, key=lambda x: x["preco"])


def _origem(x: Dict) -> str:
    dt = datetime.fromtimestamp(x["inicio_ms"] / 1000, tz=timezone.utc)
    if x["periodo"] == "mes":
        return dt.strftime("mês %m/%Y")
    return ("semana de " if x["periodo"] == "semana" else "dia ") + dt.strftime("%d/%m")


def _juntar_naked(itens: List[Dict], preco: float) -> List[Dict]:
    """Níveis a até 0,2% um do outro viram um: o preço é o do período maior; o rótulo lista todas as origens."""
    grupos: List[List[Dict]] = []
    for x in sorted(itens, key=lambda x: x["preco"]):
        if grupos and abs(x["preco"] / grupos[-1][0]["preco"] - 1) * 100 <= JUNTAR_NAKED_PCT:
            grupos[-1].append(x)
        else:
            grupos.append([x])
    out = []
    for g in grupos:
        g = sorted(g, key=lambda x: (ORDEM_PERIODO[x["periodo"]], x["tipo"] != "tempo", -x["inicio_ms"]))
        origens: Dict[str, List[str]] = {}
        for x in g:
            origens.setdefault(_origem(x), []).append(x["tipo"])
        rotulo = "Naked POC " + ", ".join(f"{o} ({' e '.join(t)})" for o, t in origens.items())
        out.append({"preco": float(g[0]["preco"]), "periodo": g[0]["periodo"], "tipo": g[0]["tipo"],
                    "inicio_ms": int(g[0]["inicio_ms"]), "rotulo": rotulo, "origens": len(g),
                    "distancia_pct": distancia_pct(g[0]["preco"], preco)})
    return out


# ------------------------------------------------------------------ o mapa
def mapa(candles_5m: Sequence[Sequence[float]], agora_ms: int, longos: Optional[Sequence[Dict]] = None) -> Mapa:
    agora_ms = int(agora_ms)
    dur = _duracao(candles_5m)
    fechados = sorted((c for c in candles_5m if int(c[0]) + dur <= agora_ms), key=lambda c: int(c[0]))
    if not fechados:
        return Mapa(ts=agora_ms, preco=0.0)
    preco = float(fechados[-1][4])
    m = Mapa(ts=agora_ms, preco=preco)
    hoje = agora_ms // DIA_MS
    niveis: List[Nivel] = []

    def add(chave, grupo, rotulo, valor, dia_ms=None):
        if valor is None:
            return
        niveis.append(Nivel(chave, grupo, rotulo, float(valor), distancia_pct(valor, preco), dia_ms))

    perfis = perfis_por_dia(fechados)
    completos = [p for p in perfis if p.inicio // DIA_MS < hoje]
    perfil_hoje = next((p for p in perfis if p.inicio // DIA_MS == hoje), None)

    # composto de 10 dias completos
    janela = completos[-DIAS_COMPOSTO:]
    if len(janela) >= MIN_DIAS_COMPOSTO:
        comp = merge(janela)
        m.composto = _niveis_perfil(comp)
        m.dias_no_composto = len(janela)
        m.p = posicao_no_range(preco, m.composto["val"], m.composto["vah"])
        if m.p is not None:
            m.p = round(float(m.p), 3)
        m.posicao = posicao_no_composto(m.p)
        add("composto.vah", "composto", f"VAH do composto ({len(janela)}d)", m.composto["vah"])
        add("composto.poc", "composto", f"POC do composto ({len(janela)}d)", m.composto["poc"])
        add("composto.val", "composto", f"VAL do composto ({len(janela)}d)", m.composto["val"])

    # dia anterior (último dia completo) e as sessões dele
    if completos:
        ontem = completos[-1]
        m.ontem = _niveis_perfil(ontem)
        d = _data(ontem.inicio)
        add("ontem.maxima", "ontem", f"Máxima de ontem ({d})", m.ontem["maxima"], ontem.inicio)
        add("ontem.vah", "ontem", f"VAH de ontem ({d})", m.ontem["vah"], ontem.inicio)
        add("ontem.poc", "ontem", f"POC de ontem ({d})", m.ontem["poc"], ontem.inicio)
        add("ontem.val", "ontem", f"VAL de ontem ({d})", m.ontem["val"], ontem.inicio)
        add("ontem.minima", "ontem", f"Mínima de ontem ({d})", m.ontem["minima"], ontem.inicio)
        for nome, s in sessoes(ontem).items():
            m.sessoes_ontem[nome] = _niveis_perfil(s)
            for k, rot in (("maxima", "máx"), ("poc", "POC"), ("minima", "mín")):
                add(f"sessao.ontem.{nome}.{k}", "sessao", f"{NOME_SESSAO[nome]} de ontem {rot}", m.sessoes_ontem[nome][k], s.inicio)

    # sessões de hoje já fechadas
    if perfil_hoje is not None:
        de_hoje = sessoes(perfil_hoje)
        for nome, (_, fim) in SESSOES.items():
            if nome in de_hoje and agora_ms >= hoje * DIA_MS + fim * 60_000:
                s = de_hoje[nome]
                m.sessoes_hoje[nome] = _niveis_perfil(s)
                for k, rot in (("maxima", "máx"), ("poc", "POC"), ("minima", "mín")):
                    add(f"sessao.hoje.{nome}.{k}", "sessao", f"{NOME_SESSAO[nome]} de hoje {rot}", m.sessoes_hoje[nome][k], s.inicio)

    # naked POCs: dias anteriores, descontando o que o preço já tocou (inclusive hoje); os 5 mais próximos
    if len(perfis) >= 2:
        nk = sorted(naked_pocs(perfis), key=lambda x: abs(float(x["preco"]) - preco))[:N_NAKED]
        m.naked_pocs = [{"preco": float(x["preco"]), "dia_ms": int(x["dia_ms"])} for x in nk]
        if longos is None:
            for x in m.naked_pocs:
                add(f"naked.{x['dia_ms']}", "naked", f"Naked POC de {_data(x['dia_ms'])}", x["preco"], x["dia_ms"])

    # naked de prazo longo: tira os que o preço tocou depois do fim do período (inclusive hoje)
    if longos is not None:
        vivos = [x for x in longos if abs(float(x["preco"]) / preco - 1) <= FAIXA_NAKED_LONGO
                 and not any(float(c[3]) <= float(x["preco"]) <= float(c[2]) for c in fechados if int(c[0]) >= int(x["fim_ms"]))]
        juntos = _juntar_naked(vivos, preco)
        acima = [x for x in juntos if x["preco"] > preco][:N_NAKED_LONGO_LADO]
        abaixo = [x for x in juntos if x["preco"] < preco][-N_NAKED_LONGO_LADO:]
        m.naked_longos = abaixo + acima
        for x in m.naked_longos:
            add(f"naked.{x['periodo']}.{x['tipo']}.{x['inicio_ms']}", "naked", x["rotulo"], x["preco"], x["inicio_ms"])

    # aberturas do dia, da semana (segunda UTC) e do mês
    diarios = diarios_de(fechados)
    por_dia = {int(x[0]) // DIA_MS: x for x in diarios}
    segunda = hoje - ((hoje + 3) % 7)                      # dia 0 (01/01/1970) foi quinta: segunda = 0
    dt = datetime.fromtimestamp(agora_ms / 1000, tz=timezone.utc)
    primeiro_do_mes = int(dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000) // DIA_MS

    def abertura_de(dia):
        x = por_dia.get(dia)
        return float(x[1]) if x else None

    m.aberturas = {"dia": abertura_de(hoje), "semana": abertura_de(segunda), "mes": abertura_de(primeiro_do_mes)}
    add("abertura.dia", "abertura", "Abertura do dia", m.aberturas["dia"], hoje * DIA_MS)
    add("abertura.semana", "abertura", "Abertura da semana", m.aberturas["semana"], segunda * DIA_MS)
    add("abertura.mes", "abertura", "Abertura do mês", m.aberturas["mes"], primeiro_do_mes * DIA_MS)

    # pivô virgem: abertura diária que nenhum dia seguinte (nem o de hoje, até agora) tocou
    if len(diarios) >= 2:
        m.pivo_virgem = pivo_virgem(diarios, preco, JANELA_VIRGEM_DIAS)
        add("pivo.acima", "pivo", "Pivô virgem acima", m.pivo_virgem.get("acima"))
        add("pivo.abaixo", "pivo", "Pivô virgem abaixo", m.pivo_virgem.get("abaixo"))

    m.niveis = sorted(niveis, key=lambda n: -n.preco)
    return m
