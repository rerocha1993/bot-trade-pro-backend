# tradeiros/elliott_mapa.py
"""
MAPA DE ELLIOTT do Tradeiros: várias contagens vivas, cada uma com probabilidade e invalidação, refeitas UMA VEZ POR
DIA com o que já fechou — como o Maroja atualiza as contagens antes da live.

    graus        ciclo (semanal do histórico longo, desde 2011), primário (diário), intermediário (4h),
                 via core/elliott_pro/mestre.contagem_mestre
    probabilidade de alta × baixa ponderada pelos graus
    fases        onda 2 = setup preferido (R14); onda 4 = não operar (R14)
    invalidação  comum: o nível que derruba a maior parte da probabilidade do lado da posição (R15 — operar a zona e
                 a invalidação comuns e ajustar a % de exposição, não o lado inteiro)

O mapa não decide tamanho: entrega probabilidades, fases e níveis para as regras e os perfis (Shaka × Maroja).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from core.tpo_sessao import DIA_MS

PESOS_GRAU = {"ciclo": 0.2, "primario": 0.5, "intermediario": 0.3}
SEMANA_MS = 7 * DIA_MS
SEGUNDA_EPOCH_MS = 4 * DIA_MS          # 01/01/1970 foi quinta; a primeira segunda-feira é 05/01/1970


def semanais_ate(diarios: Sequence[Sequence[float]], ts: int) -> List[list]:
    """Candles semanais (segunda a domingo UTC) só das semanas JÁ FECHADAS até `ts`."""
    semanas: Dict[int, list] = {}
    for c in diarios:
        t = int(c[0])
        ini = t - ((t - SEGUNDA_EPOCH_MS) % SEMANA_MS)
        if ini + SEMANA_MS > ts:
            continue
        w = semanas.get(ini)
        if w is None:
            semanas[ini] = [ini, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)]
        else:
            w[2] = max(w[2], float(c[2]))
            w[3] = min(w[3], float(c[3]))
            w[4] = float(c[4])
            w[5] += float(c[5] or 0)
    return [semanas[k] for k in sorted(semanas)]


def invalidacao_comum(cenarios: Sequence[Dict], preco: float, lado: int, cobertura: float = 0.6) -> Optional[float]:
    """
    Para uma compra (lado=+1): entre as contagens de alta com invalidação abaixo do preço, o nível mais alto em que,
    se perdido, cai pelo menos `cobertura` da probabilidade de alta. Venda é o espelho.
    """
    vies = "bull" if lado == 1 else "bear"
    validos = [c for c in cenarios if c.get("vies") == vies and c.get("invalidacao") is not None
               and ((c["invalidacao"] < preco) if lado == 1 else (c["invalidacao"] > preco))]
    total = sum(float(c.get("probabilidade") or 0) for c in validos)
    if total <= 0:
        return None
    ordem = sorted(validos, key=lambda c: c["invalidacao"], reverse=(lado == 1))
    acumulado = 0.0
    for c in ordem:
        acumulado += float(c.get("probabilidade") or 0)
        if acumulado >= cobertura * total:
            return float(c["invalidacao"])
    return float(ordem[-1]["invalidacao"])


def resumir(graus: Dict[str, Dict], preco: float, pesos: Dict[str, float] = PESOS_GRAU) -> Dict:
    presentes = {g: r for g, r in graus.items() if r and r.get("cenarios")}
    soma = sum(pesos.get(g, 0) for g in presentes) or 1.0
    prob_bull = sum(pesos.get(g, 0) * float(r.get("prob_bull") or 0) for g, r in presentes.items()) / soma
    prob_bear = sum(pesos.get(g, 0) * float(r.get("prob_bear") or 0) for g, r in presentes.items()) / soma
    operacional_nome = "intermediario" if "intermediario" in presentes else "primario" if "primario" in presentes else None
    op = presentes.get(operacional_nome, {}).get("cenarios", []) if operacional_nome else []
    prob_fase = {}
    for c in op:
        prob_fase[c.get("fase")] = prob_fase.get(c.get("fase"), 0.0) + float(c.get("probabilidade") or 0)
    onda2 = [c for c in op if c.get("fase") == "onda_2"]
    setup_onda_2 = None
    if onda2 and sum(float(c.get("probabilidade") or 0) for c in onda2) >= 0.4:
        melhor = max(onda2, key=lambda c: float(c.get("probabilidade") or 0))
        setup_onda_2 = {"vies": melhor.get("vies"), "invalidacao": melhor.get("invalidacao"), "alvos": melhor.get("alvos")}
    return {
        "preco": preco,
        "prob_bull": round(prob_bull, 3),
        "prob_bear": round(prob_bear, 3),
        "inclinacao": round(prob_bull - prob_bear, 3),                 # −1 (tudo baixa) a +1 (tudo alta)
        "grau_operacional": operacional_nome,
        "prob_por_fase": {k: round(v, 3) for k, v in sorted(prob_fase.items(), key=lambda kv: -kv[1])},
        "veto_onda_4": prob_fase.get("onda_4", 0.0) >= 0.5,
        "setup_onda_2": setup_onda_2,
        "invalidacao_compra": invalidacao_comum(op, preco, 1),
        "invalidacao_venda": invalidacao_comum(op, preco, -1),
        "contagens": [{"grau": g, **{k: c.get(k) for k in ("nome", "vies", "fase", "probabilidade", "invalidacao", "alvos")}}
                      for g, r in presentes.items() for c in r["cenarios"][:6]],
    }


class MapaElliott:
    """Refaz as contagens uma vez por dia (com o que fechou) e guarda o resultado do dia."""

    def __init__(self, dados, pesos: Dict[str, float] = PESOS_GRAU, candles_4h: int = 2000):
        self.dados = dados
        self.pesos = pesos
        self.candles_4h = candles_4h
        self._cache: Dict[int, Dict] = {}

    def ler(self, ts: int) -> Dict:
        from core.elliott_pro.mestre import contagem_mestre
        dia = ts // DIA_MS
        if dia in self._cache:
            return self._cache[dia]
        inicio_do_dia = dia * DIA_MS
        d1 = self.dados.diarios_ate(inicio_do_dia)
        h4 = self.dados.h4_ate(inicio_do_dia)[-self.candles_4h:]
        # o grau de ciclo é contado no semanal do histórico LONGO (desde 2011), como eles contam desde 2009
        w1 = semanais_ate(self.dados.diarios_longos_ate(inicio_do_dia), inicio_do_dia)
        if len(d1) < 60:
            res = {"erro": "histórico curto", "prob_bull": 0.0, "prob_bear": 0.0, "inclinacao": 0.0, "contagens": []}
        else:
            try:
                m = contagem_mestre({"1w": w1, "1d": d1, "4h": h4})
                res = resumir(m["graus"], float(d1[-1][4]), self.pesos)
            except Exception as e:                               # contagem sem estrutura não derruba a leitura
                res = {"erro": str(e)[:200], "prob_bull": 0.0, "prob_bear": 0.0, "inclinacao": 0.0, "contagens": []}
        self._cache[dia] = res
        return res
