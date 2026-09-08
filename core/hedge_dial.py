# core/hedge_dial.py
"""
DIAL DE HEDGE para quem já está comprado em BTC (colateral em BTC, short no perpétuo inverso).

Premissas (do usuário):
    - o estado natural é COMPRADO em BTC (hedge 0%); o short inverso só converte parte da carteira em dólar;
    - em impulso de alta confirmado (onda 3, ciclo de alta) o hedge é 0%: deixa andar até a próxima BARREIRA;
    - barreira = confluência acima do preço: alvos de Elliott (extensões), VAH/POC do TPO, pontos institucionais,
      order blocks de baixa; suporte = confluência abaixo (VAL, invalidação, OB de alta);
    - chegando na barreira, o hedge sobe POUCO A POUCO (fatias de Fibonacci entre suporte e barreira) e só
      quando há EXAUSTÃO: euforia (Fear & Greed), preço esticado (VWAP z-score), rejeição acima da VAH,
      cenário de baixa ganhando probabilidade, fluxo comprador travando;
    - na barreira, ~100% em dólar. Na descida, desmonta o hedge fatia a fatia (cada recompra com lucro em BTC)
      até o suporte;
    - se a contagem mestre diz que vem onda 2 / C grande (alvo bem abaixo do suporte), segura o hedge até o alvo;
    - se a barreira rompe COM estrutura de alta (onda 3), o hedge sai (custo pequeno) e a barreira seguinte vira
      o novo alvo. Não é stop de preço: é troca de cenário.

Saída: {'hedge_alvo': 0..1, 'barreira': R, 'suporte': S, 'exaustao': 0..1, 'modo': 'deixa_andar'|'montando'|'desmontando'|'segurando'|'rompimento', 'motivo'}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from core.inverse_grade import GradeInversa, PESOS_PADRAO

FASES_IMPULSO_ALTA = ("inicio_onda_3", "meio_onda_3", "onda_1", "onda_5")


def barreiras(preco: float, niveis: List[Dict], min_dist: float = 0.02, max_dist: float = 0.60, raio_cluster: float = 0.015) -> Dict:
    """
    niveis: [{'preco', 'fonte', 'peso'}] de todas as fontes (elliott, tpo, institucional, orderblock, fib).
    Agrupa em clusters de ±raio_cluster e devolve a resistência (acima) e o suporte (abaixo) com maior confluência,
    preferindo o cluster mais próximo quando a confluência empata.
    """
    acima = sorted([n for n in niveis if preco * (1 + min_dist) <= n["preco"] <= preco * (1 + max_dist)], key=lambda n: n["preco"])
    abaixo = sorted([n for n in niveis if preco * (1 - max_dist) <= n["preco"] <= preco * (1 - min_dist)], key=lambda n: -n["preco"])

    def clusters(lista):
        out = []
        for n in lista:
            if out and abs(n["preco"] - out[-1]["preco"]) <= out[-1]["preco"] * raio_cluster:
                c = out[-1]
                c["peso"] += n.get("peso", 1.0)
                c["fontes"].append(n.get("fonte"))
                c["preco"] = (c["preco"] * (len(c["fontes"]) - 1) + n["preco"]) / len(c["fontes"])
            else:
                out.append({"preco": n["preco"], "peso": n.get("peso", 1.0), "fontes": [n.get("fonte")]})
        return out

    def escolher(cl, sentido):
        if not cl:
            return None
        melhor = max(cl, key=lambda c: (c["peso"], -abs(c["preco"] - preco)))
        # se o mais próximo tem confluência >= 2 fontes, prefere ele (barreira imediata)
        proximo = cl[0]
        if len(proximo["fontes"]) >= 2 and proximo is not melhor and abs(proximo["preco"] - preco) < abs(melhor["preco"] - preco):
            melhor = proximo
        return {"preco": round(melhor["preco"], 2), "peso": round(melhor["peso"], 2), "fontes": melhor["fontes"], "sentido": sentido}

    return {"resistencia": escolher(clusters(acima), "acima"), "suporte": escolher(clusters(abaixo), "abaixo")}


def exaustao(sinais: Dict) -> Dict:
    """
    Combina sinais de topo em 0..1:
        fear_greed (0..100)     >= 60 começa a contar, 80+ = 1
        vwap_z                  >= 1 começa, 2.5+ = 1
        acima_vah (bool)        rejeição/aceitação acima da value area
        prob_bear (0..1)        cenários de baixa no grau primário
        delta_of (-1..1)        fluxo: negativo nas máximas conta
        rsi (0..100) opcional   >= 70 começa, 85 = 1
    """
    comp = {}
    fg = sinais.get("fear_greed")
    if fg is not None:
        comp["fear_greed"] = max(0.0, min(1.0, (fg - 60) / 20.0))
    z = sinais.get("vwap_z")
    if z is not None:
        comp["vwap_z"] = max(0.0, min(1.0, (z - 1.0) / 1.5))
    if sinais.get("acima_vah") is not None:
        comp["acima_vah"] = 1.0 if sinais["acima_vah"] else 0.0
    pb = sinais.get("prob_bear")
    if pb is not None:
        comp["prob_bear"] = max(0.0, min(1.0, (pb - 0.3) / 0.4))
    d = sinais.get("delta_of")
    if d is not None:
        comp["fluxo"] = max(0.0, min(1.0, -d / 0.3))
    rsi = sinais.get("rsi")
    if rsi is not None:
        comp["rsi"] = max(0.0, min(1.0, (rsi - 70) / 15.0))
    pesos = {"fear_greed": 0.3, "vwap_z": 0.2, "acima_vah": 0.1, "prob_bear": 0.25, "fluxo": 0.1, "rsi": 0.15}
    tot = sum(pesos[k] for k in comp)
    score = sum(comp[k] * pesos[k] for k in comp) / tot if tot else 0.0
    confluencias = sum(1 for v in comp.values() if v >= 0.5)   # quantos sinais independentes apontam exaustão
    return {"score": round(score, 3), "componentes": comp, "confluencias": confluencias}


@dataclass
class EstadoHedge:
    suporte: Optional[float] = None
    barreira: Optional[float] = None
    grade: Optional[GradeInversa] = None
    modo: str = "deixa_andar"
    segurando_ate: Optional[float] = None     # alvo de Elliott quando segura o hedge
    historico: List[Dict] = field(default_factory=list)


class HedgeDial:
    def __init__(self, pesos_grade: Optional[Dict[float, float]] = None, subfatias: int = 3, exaustao_minima: float = 0.35,
                 folga_rompimento: float = 0.02, prob_impulso: float = 0.55):
        self.pesos = pesos_grade or {k: v for k, v in PESOS_PADRAO.items() if k <= 1.0}
        tot = sum(self.pesos.values())
        self.pesos = {k: v / tot for k, v in self.pesos.items()}           # 100% na barreira (sem extensões)
        self.subfatias = subfatias
        self.exaustao_minima = exaustao_minima
        self.folga = folga_rompimento
        self.prob_impulso = prob_impulso
        self.estado = EstadoHedge()

    # ------------------------------------------------------------ passo
    def passo(self, ts: int, high: float, low: float, close: float, equity_btc: float, niveis: List[Dict],
              elliott: Dict, sinais: Dict) -> Dict:
        """
        elliott: {'fase', 'vies', 'prob_bull', 'prob_bear', 'alvos', 'invalidacao', 'ciclo_prob_bull'}
        sinais: entradas de exaustao()
        Devolve execuções e o estado.
        """
        est = self.estado
        ex = exaustao(sinais)
        execs: List[Dict] = []
        fase = elliott.get("fase", "indefinido")
        prob_bull = float(elliott.get("prob_bull") or 0)
        prob_bear = float(elliott.get("prob_bear") or 0)
        ciclo_bull = float(elliott.get("ciclo_prob_bull") or 0)
        sc = elliott.get("superciclo") or ""
        # superciclo (log, desde 2011) manda: fundo terminal / novo impulso / impulso imaturo = deixar andar
        impulso_alta = (fase in FASES_IMPULSO_ALTA and prob_bull >= self.prob_impulso) or ciclo_bull >= 0.7 \
            or sc in ("fundo_terminal", "novo_impulso", "impulso_alta", "zona_onda_2")
        if sc in ("impulso_maduro", "correcao_inicial", "correcao_em_curso"):
            impulso_alta = False

        # 1) barreira/suporte atuais (recalcula sempre; a grade só é (re)montada quando muda de verdade)
        b = barreiras(close, niveis)
        R = b["resistencia"]["preco"] if b["resistencia"] else None
        S = b["suporte"]["preco"] if b["suporte"] else None

        # 2) rompimento da barreira com estrutura de alta -> desmonta o hedge (troca de cenário) e sobe a barreira
        if est.grade is not None and close > est.grade.high * (1 + self.folga) and impulso_alta and est.grade.contratos_abertos() > 0:
            for f in est.grade.fatias:
                if f.contratos > 0:
                    pnl = f.contratos * (1 / close - 1 / f.preco_venda)
                    execs.append({"ts": ts, "tipo": "recompra", "nivel": f.nivel, "preco": close, "contratos": f.contratos, "pnl_btc": pnl, "motivo": "rompimento com onda 3"})
                    est.grade.btc_realizado += pnl
                    f.contratos = 0.0
            est.modo = "rompimento"
            est.grade = None
            est.suporte, est.barreira = None, None

        # 3) segurar o hedge SÓ com contagem de baixa forte nos dois graus (onda 2 / C grande) e nunca em impulso de alta
        segurar = (elliott.get("vies") == "bear" and prob_bear >= 0.65 and ciclo_bull < 0.5 and not impulso_alta)
        alvos_baixo = [a for a in (elliott.get("alvos") or []) if a and S and a < S * 0.97] if segurar else []
        est.segurando_ate = max(alvos_baixo) if alvos_baixo else None

        # 4) grade entre suporte e barreira: só (re)montada quando a barreira muda de verdade (> 3%) e a barreira
        #    tem CONFLUÊNCIA (>= 2 fontes); o total em dólar nunca passa de 100% (fatias antigas abertas contam)
        conf_barreira = len(b["resistencia"]["fontes"]) >= 2 if b["resistencia"] else False
        mudou = est.barreira is None or (R and abs(R - est.barreira) / est.barreira > 0.03) or (S and est.suporte and abs(S - est.suporte) / est.suporte > 0.03)
        if R and S and R > S * 1.03 and conf_barreira and (est.grade is None or mudou):
            abertas = [f for f in (est.grade.fatias if est.grade else []) if f.contratos > 0]
            ja_aberto = sum(f.fracao for f in abertas)
            livre = max(0.0, 1.0 - ja_aberto)
            nova = GradeInversa(S, R, pesos={k: v * livre for k, v in self.pesos.items()}, subfatias=self.subfatias)
            if est.grade:
                nova.btc_realizado, nova.taxas_btc = est.grade.btc_realizado, est.grade.taxas_btc
            for f in abertas:
                f.preco_recompra = min(f.preco_recompra, max(S, f.preco_venda * 0.97))
                nova.fatias.append(f)
            nova.desativar_abaixo(close)      # entrada escalonada: nada é vendido de uma vez
            est.grade, est.suporte, est.barreira = nova, S, R
        # venda exige: fora de impulso de alta OU exaustão com confluência (score >= mínimo e >= 2 sinais concordando)
        exausto = ex["score"] >= self.exaustao_minima and ex.get("confluencias", 0) >= 2
        # modo seletivo: vende apenas em fases de TOPO segundo Elliott (onda 5, final da 3, correção A/B iniciando)
        # com cenário de baixa relevante e barreira com >= 3 fontes; fora disso, deixa andar
        fase_topo = fase in ("onda_5", "final_onda_3", "correcao_a", "correcao_b", "onda_4") and prob_bear >= 0.35
        conf3 = bool(b["resistencia"]) and len(b["resistencia"]["fontes"]) >= 3
        pode_hedge = (not impulso_alta) and exausto and (fase_topo or conf3 or sc == "impulso_maduro")
        if sc in ("correcao_inicial", "correcao_em_curso"):
            pode_hedge = True                      # correção de ciclo confirmada: hedge sem exigir exaustão
        grade = est.grade
        if grade is None:
            est.modo = "deixa_andar"
            return {"execs": execs, "modo": est.modo, "hedge": 0.0, "barreira": R, "suporte": S, "exaustao": ex["score"], "motivo": "sem barreira/suporte definidos"}

        # 5) vendas só com permissão, na metade superior da faixa e limitadas pela exaustão (hedge máximo = score);
        #    recompras sempre (são lucro), salvo fatias 'segurando'
        pos_faixa = (close - grade.low) / (grade.high - grade.low) if grade.high > grade.low else 0.0
        teto_hedge = 1.0 if ((ciclo_bull < 0.4 and prob_bear >= 0.5) or sc in ("correcao_inicial", "correcao_em_curso")
                             or (sc == "impulso_maduro" and ex["score"] >= 0.6)) else 0.5   # 100% só com baixa de grau maior
        if pode_hedge and pos_faixa >= 0.5 and grade.fracao_aberta() < teto_hedge:
            mestre = {"vies": "bear", "alvos": [est.segurando_ate], "prob_sucesso": prob_bear, "status": "ativa"} if est.segurando_ate else None
            ejs = grade.processar_candle(ts, high, low, close, max(equity_btc, 1e-6), mestre)
            execs.extend(ejs)
            est.modo = "montando" if any(e["tipo"] == "venda" for e in ejs) else ("desmontando" if any(e["tipo"] == "recompra" for e in ejs) else est.modo)
        else:
            # impulso de alta sem exaustão: não vende; só recompra o que estiver abaixo (lucro) ou segura
            mestre = {"vies": "bear", "alvos": [est.segurando_ate], "prob_sucesso": prob_bear, "status": "ativa"} if est.segurando_ate else None
            ejs = grade.processar_candle(ts, high, low, close, max(equity_btc, 1e-6), mestre, vender=False)
            execs.extend(ejs)
            est.modo = "deixa_andar" if grade.contratos_abertos() <= 0 else "segurando"
        if est.segurando_ate and grade.contratos_abertos() > 0:
            est.modo = "segurando"
        hedge = grade.fracao_aberta()
        Sx, Rx = est.suporte or S, est.barreira or R
        motivo = (f"{est.modo}: S {Sx if Sx is None else round(Sx)} / R {Rx if Rx is None else round(Rx)}, fase {fase} (bull {prob_bull:.0%}, ciclo {ciclo_bull:.0%}), superciclo {sc or '-'}, exaustão {ex['score']:.2f}"
                  + (f", segurando até {est.segurando_ate:.0f}" if est.segurando_ate else ""))
        return {"execs": execs, "modo": est.modo, "hedge": round(hedge, 3), "barreira": Rx, "suporte": Sx, "exaustao": ex["score"],
                "componentes": ex["componentes"], "motivo": motivo}
