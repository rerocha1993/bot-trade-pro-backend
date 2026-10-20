# core/elliott_pro/memoria.py
"""
MEMÓRIA DE CONTAGENS: as hipóteses de Elliott nascem, sobrevivem a testes, são invalidadas ou se cumprem.

Princípio (do usuário): em 2011 havia N contagens possíveis; anos depois, olhando para trás, uma se consolidou.
Ninguém sabe o caminho; o que se sabe é quais caminhos ainda são possíveis, qual é o mais maduro e o que
invalida cada um. O motor, portanto, não recomeça do zero a cada análise: ele mantém um registro de
hipóteses com identidade estável (padrão + viés + pivô de origem) e as acompanha passo a passo.

Ciclo de vida de uma hipótese:
    nasce        quando o ScenarioEngine a gera pela primeira vez
    viva         enquanto o preço não cruza a invalidação; a cada passo atualiza fase, alvos e invalidação
    testada      quando o preço chega a <= 3% da invalidação e não cruza (sobreviveu a um teste)
    alvo batido  quando o preço atinge um dos alvos
    invalidada   quando o preço cruza a invalidação (fechamento do passo)
    cumprida     quando o padrão completo se realizou (todos os alvos batidos ou a estrutura foi concluída)
    abandonada   quando deixa de ser gerada por muitos passos sem ter sido invalidada (absorvida por outra contagem)

Maturidade (peso na probabilidade):
    peso = share_bruto x prob_sucesso_calibrada x (1 + 0,15 ln(1 + idade)) x (1 + 0,25 testes) x (1 + 0,35 alvos_batidos)
    probabilidade_madura = peso / soma dos pesos das hipóteses vivas
Consenso: soma das probabilidades maduras por viés (bull/bear) e grau de concordância entre as vivas.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from conselho.indicadores import atr as calc_atr
from .mestre import zigzag_pct
from .pivots import zigzag_atr
from .scenarios import ScenarioEngine

MAX_PASSOS_SEM_VER = {"ciclo": 26, "primario": 60, "intermediario": 90, "operacional": 120}


def _data(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def chave_hipotese(c: Dict) -> str:
    ondas = c.get("ondas") or []
    origem = ondas[0].get("ts_inicio") if ondas else "?"
    return f"{c.get('padrao')}|{c.get('vies')}|{origem}"


class MemoriaContagens:
    def __init__(self, grau: str = "primario", pct: Optional[float] = 0.22, fator_atr: Optional[float] = None,
                 calibrador=None, max_pivots: int = 60):
        self.grau = grau
        self.pct = pct
        self.fator_atr = fator_atr
        self.calibrador = calibrador
        self.max_pivots = max_pivots
        self.hipoteses: Dict[str, Dict] = {}
        self.eventos: List[Dict] = []
        self.passos = 0

    # ------------------------------------------------------------- geração
    def _cenarios(self, ohlcv: Sequence) -> Dict:
        if self.pct:
            piv = zigzag_pct(ohlcv, self.pct)
            limiar = float(ohlcv[-1][4]) * self.pct
        else:
            piv, limiar = zigzag_atr(ohlcv, fator_atr=self.fator_atr or 2.0)
        a = calc_atr(ohlcv, 14) or limiar / 4
        res = ScenarioEngine(piv, float(ohlcv[-1][4]), limiar, a, max_pivots=self.max_pivots).analisar()
        if self.calibrador is not None and self.calibrador.ativo:
            from .calibracao import features_cenario
            for c in res["cenarios"]:
                try:
                    c["prob_sucesso"] = self.calibrador.prob(features_cenario(c, res["preco"], a, res, "1d" if self.grau != "ciclo" else "1w"))
                except Exception:
                    c["prob_sucesso"] = None
        return res

    # ---------------------------------------------------------------- passo
    def passo(self, ohlcv: Sequence, high: float, low: float, close: float, ts: int) -> Dict:
        """Atualiza a memória com a série até `ts` (candle fechado). Devolve o consenso maduro."""
        self.passos += 1
        res = self._cenarios(ohlcv)
        vistos = set()
        for c in res["cenarios"]:
            k = chave_hipotese(c)
            vistos.add(k)
            h = self.hipoteses.get(k)
            if h is None or h["status"] != "viva":
                if h is not None and h["status"] in ("invalidada", "cumprida"):
                    continue   # não ressuscita hipótese morta com a mesma identidade
                h = {"chave": k, "padrao": c["padrao"], "vies": c["vies"], "nascimento": ts, "nascimento_preco": close,
                     "status": "viva", "testes": 0, "alvos_batidos": 0, "passos_vivos": 0, "passos_sem_ver": 0,
                     "historico_fases": [], "ultima_atualizacao": ts, "alvos_originais": list(c.get("alvos") or [])}
                self.hipoteses[k] = h
                self.eventos.append({"ts": ts, "data": _data(ts), "evento": "nasce", "chave": k, "nome": c["nome"], "preco": close,
                                     "invalidacao": c.get("invalidacao"), "alvos": c.get("alvos")})
            # atualização da hipótese viva
            if not h["historico_fases"] or h["historico_fases"][-1]["fase"] != c["fase"]:
                h["historico_fases"].append({"data": _data(ts), "fase": c["fase"], "preco": close})
            h.update({"nome": c["nome"], "fase": c["fase"], "invalidacao": c.get("invalidacao"), "alvos": c.get("alvos") or [],
                      "share": c.get("probabilidade", 0.0), "prob_sucesso": c.get("prob_sucesso"), "ondas": c.get("ondas"),
                      "direcao_trade": c.get("direcao_trade"), "ultima_atualizacao": ts, "passos_sem_ver": 0})
        # hipóteses vivas: testes, alvos, invalidação, abandono
        for k, h in self.hipoteses.items():
            if h["status"] != "viva":
                continue
            h["passos_vivos"] += 1
            if k not in vistos:
                h["passos_sem_ver"] += 1
            inv = h.get("invalidacao")
            up = h["vies"] == "bull"
            if inv is not None:
                cruzou = close < inv if up else close > inv
                if cruzou:
                    h["status"], h["fim"], h["fim_preco"] = "invalidada", ts, close
                    self.eventos.append({"ts": ts, "data": _data(ts), "evento": "invalidada", "chave": k, "nome": h.get("nome"), "preco": close,
                                         "invalidacao": inv, "idade_passos": h["passos_vivos"]})
                    continue
                perto = (low <= inv * 1.03) if up else (high >= inv * 0.97)
                if perto and not h.get("_em_teste"):
                    h["testes"] += 1
                    h["_em_teste"] = True
                    self.eventos.append({"ts": ts, "data": _data(ts), "evento": "teste_sobrevivido", "chave": k, "nome": h.get("nome"), "preco": close, "invalidacao": inv})
                elif not perto:
                    h["_em_teste"] = False
            if not h.get("alvos_originais") and h.get("alvos"):
                h["alvos_originais"] = list(h["alvos"])
            alvos = h.get("alvos_originais") or []
            batidos = [a for a in alvos if (high >= a if up else low <= a)]
            if batidos and len(batidos) > h["alvos_batidos"]:
                h["alvos_batidos"] = len(batidos)
                self.eventos.append({"ts": ts, "data": _data(ts), "evento": "alvo_batido", "chave": k, "nome": h.get("nome"), "preco": close,
                                     "alvo": max(batidos) if up else min(batidos), "n": len(batidos)})
                if len(batidos) >= len(alvos) and alvos:
                    h["status"], h["fim"], h["fim_preco"] = "cumprida", ts, close
                    self.eventos.append({"ts": ts, "data": _data(ts), "evento": "cumprida", "chave": k, "nome": h.get("nome"), "preco": close,
                                         "idade_passos": h["passos_vivos"]})
                    continue
            if h["passos_sem_ver"] >= MAX_PASSOS_SEM_VER.get(self.grau, 60):
                h["status"], h["fim"], h["fim_preco"] = "abandonada", ts, close
                self.eventos.append({"ts": ts, "data": _data(ts), "evento": "abandonada", "chave": k, "nome": h.get("nome"), "preco": close,
                                     "idade_passos": h["passos_vivos"]})
        return self.consenso(ts, close)

    # -------------------------------------------------------------- consenso
    def vivas(self) -> List[Dict]:
        return [h for h in self.hipoteses.values() if h["status"] == "viva"]

    FASES_CONTINUACAO = ("inicio_onda_3", "meio_onda_3", "final_onda_3", "onda_5", "onda_1")

    @classmethod
    def peso(cls, h: Dict) -> float:
        """
        Maturidade com a lógica de Elliott: uma hipótese de CONTINUAÇÃO (onda 3/5 em andamento) que já bateu alvos
        está mais perto do fim (perde peso); uma hipótese de REVERSÃO/retomada que bateu alvos está se confirmando
        (ganha peso). A calibração histórica entra ao quadrado para dominar o ranking.
        """
        share = max(float(h.get("share") or 0.0), 0.02)
        ps = h.get("prob_sucesso")
        ps = float(ps) if ps is not None else 0.6
        idade = h.get("passos_vivos", 0)
        batidos = h.get("alvos_batidos", 0)
        if h.get("fase") in cls.FASES_CONTINUACAO:
            fator_alvos = max(0.3, 1 - 0.25 * batidos)
        else:
            fator_alvos = 1 + 0.35 * batidos
        return share * (ps ** 2) * (1 + 0.15 * math.log1p(idade)) * (1 + 0.25 * h.get("testes", 0)) * fator_alvos

    def consenso(self, ts: int, preco: float) -> Dict:
        vivas = self.vivas()
        pesos = {h["chave"]: self.peso(h) for h in vivas}
        tot = sum(pesos.values())
        for h in vivas:
            h["probabilidade_madura"] = round(pesos[h["chave"]] / tot, 3) if tot else 0.0
        bull = round(sum(h["probabilidade_madura"] for h in vivas if h["vies"] == "bull"), 3)
        bear = round(sum(h["probabilidade_madura"] for h in vivas if h["vies"] == "bear"), 3)
        ordenadas = sorted(vivas, key=lambda h: -h["probabilidade_madura"])
        concordancia = max(bull, bear)
        return {"ts": ts, "data": _data(ts), "preco": preco, "grau": self.grau, "n_vivas": len(vivas), "prob_bull": bull, "prob_bear": bear,
                "concordancia": concordancia, "direcao": "buy" if bull >= 0.65 else "sell" if bear >= 0.65 else "hold",
                "primaria": self._resumo(ordenadas[0]) if ordenadas else None,
                "vivas": [self._resumo(h) for h in ordenadas[:6]]}

    @staticmethod
    def _resumo(h: Dict) -> Dict:
        return {"chave": h["chave"], "nome": h.get("nome"), "padrao": h["padrao"], "vies": h["vies"], "fase": h.get("fase"),
                "nascimento": _data(h["nascimento"]), "idade_passos": h.get("passos_vivos", 0), "testes": h.get("testes", 0),
                "alvos_batidos": h.get("alvos_batidos", 0), "invalidacao": h.get("invalidacao"), "alvos": h.get("alvos"),
                "share": h.get("share"), "prob_sucesso": h.get("prob_sucesso"), "probabilidade_madura": h.get("probabilidade_madura"),
                "status": h.get("status"), "fases": h.get("historico_fases", [])[-4:]}

    def historico(self) -> List[Dict]:
        return [self._resumo(h) | {"fim": _data(h["fim"]) if h.get("fim") else None, "fim_preco": h.get("fim_preco")}
                for h in sorted(self.hipoteses.values(), key=lambda x: x["nascimento"])]


def evoluir(serie: Sequence, grau: str, pct: float, passo_candles: int = 1, janela: int = 400, calibrador=None,
            desde_ms: int = 0, snapshots: Optional[List[int]] = None) -> Dict:
    """
    Reproduz a memória ao longo de uma série (semanal para ciclo, diária para primário), passo a passo, SEM look-ahead.
    snapshots: timestamps (ms) em que gravar o estado (ex.: fim de cada ano). Devolve eventos, snapshots e histórico.
    """
    dados = [list(map(float, c[:6])) for c in serie]
    for c in dados:
        c[0] = int(c[0])
    mem = MemoriaContagens(grau, pct=pct, calibrador=calibrador)
    snaps: List[Dict] = []
    alvo_snaps = sorted(snapshots or [])
    for i in range(30, len(dados), passo_candles):
        c = dados[i]
        if c[0] < desde_ms:
            continue
        win = dados[max(0, i - janela + 1):i + 1]
        cons = mem.passo(win, c[2], c[3], c[4], c[0])
        while alvo_snaps and c[0] >= alvo_snaps[0]:
            snaps.append(cons)
            alvo_snaps.pop(0)
    return {"consenso_final": mem.consenso(dados[-1][0], dados[-1][4]), "eventos": mem.eventos, "snapshots": snaps,
            "historico": mem.historico(), "memoria": mem}


# =============================================================== hierarquia de graus
class MemoriaHierarquica:
    """
    O TRADER: o grau maior (ciclo, semanal) manda no grau menor (primário, diário).

    Regras de subordinação (Elliott):
      - estrutura COMPLETA no grau maior (hipótese de continuação que já bateu >= 2 alvos, ou cumprida há pouco)
        => no grau menor, continuação na mesma direção perde peso (x0,4) e reversão ganha (x1,6);
      - consenso forte do grau maior (>= 70%) => hipóteses do menor contra ele perdem peso (x0,5),
        salvo se o maior estiver exaurido;
      - uma hipótese do menor cujo alvo está ALÉM da invalidação da primária do maior é vetada (x0,2).
    """

    def __init__(self, calibrador=None, pct_ciclo: float = 0.40, pct_primario: float = 0.22):
        from conselho.elliott.superciclo import ContextoSuperciclo
        self.ciclo = MemoriaContagens("ciclo", pct=pct_ciclo, calibrador=calibrador)
        self.primario = MemoriaContagens("primario", pct=pct_primario, calibrador=calibrador)
        self.superciclo = ContextoSuperciclo()
        self._ultimo_ciclo_ts = 0

    def trader(self, ts: int, preco: float) -> Dict:
        """
        O TRADER HUMANO: lê o superciclo (escala log) primeiro, depois as contagens subordinadas.
        Direção final:
          - estados com direção própria (fundo_terminal, novo_impulso, zona_onda_2, impulso_alta,
            correcao_inicial, recuo_profundo) mandam;
          - 'memoria' segue as contagens subordinadas; 'memoria_venda' (impulso maduro) vende só se
            as contagens estiverem >= 50% bear, senão hold.
        """
        from conselho.elliott.superciclo import aplicar_contexto
        ctx = self.superciclo.estado()
        sub = self.consenso(ts, preco)
        vivas = self.primario.vivas()
        # compõe: peso já subordinado ao ciclo (probabilidade_madura de consenso()) x multiplicadores do superciclo
        pesos = aplicar_contexto(vivas, ctx.get("estado", ""), lambda h: float(h.get("probabilidade_madura") or 0.0),
                                 MemoriaContagens.FASES_CONTINUACAO)
        tot = sum(pesos.values())
        bull = round(sum(pesos[h["chave"]] for h in vivas if h["vies"] == "bull") / tot, 3) if tot else 0.0
        bear = round(1 - bull, 3) if tot else 0.0
        d = ctx.get("direcao", "memoria")
        if d == "memoria":
            direcao = "buy" if sub["prob_bull"] >= 0.65 else "sell" if sub["prob_bear"] >= 0.65 else "hold"
        elif d == "memoria_venda":
            direcao = "sell" if max(sub["prob_bear"], bear) >= 0.5 else "hold"
        else:
            direcao = d
        if d in ("memoria", "memoria_venda"):
            pb, pr = bull, bear
        else:
            pb = 1.0 if direcao == "buy" else 0.0 if direcao == "sell" else bull
            pr = 1.0 if direcao == "sell" else 0.0 if direcao == "buy" else bear
        return {"ts": ts, "data": _data(ts), "preco": preco, "grau": "trader", "direcao": direcao,
                "prob_bull": pb, "prob_bear": pr, "superciclo": ctx,
                "subordinado": {"direcao": sub["direcao"], "prob_bull": sub["prob_bull"], "prob_bear": sub["prob_bear"]},
                "n_vivas": sub["n_vivas"], "primaria": sub["primaria"], "vivas": sub["vivas"], "ciclo": sub["ciclo"]}

    def exaustao_ciclo(self) -> Dict[str, bool]:
        vivas = self.ciclo.vivas()
        recentes = [h for h in self.ciclo.hipoteses.values() if h["status"] == "cumprida" and h.get("fim") and
                    (self.ciclo.passos - h.get("passos_vivos", 0)) <= 26]
        def exaurido(vies):
            return any(h["vies"] == vies and h.get("fase") in MemoriaContagens.FASES_CONTINUACAO and h.get("alvos_batidos", 0) >= 2 for h in vivas)                 or any(h["vies"] == vies for h in recentes)
        return {"bull": exaurido("bull"), "bear": exaurido("bear")}

    def consenso(self, ts: int, preco: float) -> Dict:
        cc = self.ciclo.consenso(ts, preco)
        ex = self.exaustao_ciclo()
        vivas = self.primario.vivas()
        prim_ciclo = cc.get("primaria") or {}
        inv_ciclo = prim_ciclo.get("invalidacao")
        pesos = {}
        for h in vivas:
            w = MemoriaContagens.peso(h)
            continuacao = h.get("fase") in MemoriaContagens.FASES_CONTINUACAO
            if ex.get(h["vies"]) and continuacao:
                w *= 0.4
            oposto = "bear" if h["vies"] == "bull" else "bull"
            if ex.get(oposto):
                w *= 1.6
            forte = cc["prob_bull"] >= 0.7 and h["vies"] == "bear" or cc["prob_bear"] >= 0.7 and h["vies"] == "bull"
            if forte and not ex.get(oposto):
                w *= 0.5
            # veto: alvo do menor além da invalidação da primária do maior
            alvos = h.get("alvos") or []
            if inv_ciclo and alvos and prim_ciclo.get("vies"):
                if prim_ciclo["vies"] == "bull" and h["vies"] == "bear" and min(alvos) < inv_ciclo:
                    w *= 0.2
                if prim_ciclo["vies"] == "bear" and h["vies"] == "bull" and max(alvos) > inv_ciclo:
                    w *= 0.2
            pesos[h["chave"]] = w
        tot = sum(pesos.values())
        for h in vivas:
            h["probabilidade_madura"] = round(pesos[h["chave"]] / tot, 3) if tot else 0.0
        bull = round(sum(h["probabilidade_madura"] for h in vivas if h["vies"] == "bull"), 3)
        bear = round(sum(h["probabilidade_madura"] for h in vivas if h["vies"] == "bear"), 3)
        ordenadas = sorted(vivas, key=lambda h: -h["probabilidade_madura"])
        return {"ts": ts, "data": _data(ts), "preco": preco, "grau": "primario_subordinado", "n_vivas": len(vivas),
                "prob_bull": bull, "prob_bear": bear, "concordancia": max(bull, bear),
                "direcao": "buy" if bull >= 0.65 else "sell" if bear >= 0.65 else "hold",
                "ciclo": {"prob_bull": cc["prob_bull"], "prob_bear": cc["prob_bear"], "direcao": cc["direcao"],
                          "primaria": prim_ciclo.get("nome"), "exaurido": ex},
                "primaria": MemoriaContagens._resumo(ordenadas[0]) if ordenadas else None,
                "vivas": [MemoriaContagens._resumo(h) for h in ordenadas[:6]]}


def evoluir_hierarquico(d1: Sequence, calibrador=None, desde_ms: int = 0, snapshots: Optional[List[int]] = None,
                        janela_d: int = 400, janela_w: int = 300) -> Dict:
    """Evolui ciclo (semanal) e primário (diário) juntos, sem look-ahead, com o primário subordinado ao ciclo."""
    from conselho.indicadores import reamostrar
    dados = [list(map(float, c[:6])) for c in d1]
    for c in dados:
        c[0] = int(c[0])
    w1 = reamostrar(dados, "1d", "1w")
    mem = MemoriaHierarquica(calibrador=calibrador)
    snaps: List[Dict] = []
    alvo_snaps = sorted(snapshots or [])
    wi = 0
    for c in dados[:30]:
        mem.superciclo.passo(c[0], c[2], c[3], c[4])
    for i in range(30, len(dados)):
        c = dados[i]
        if c[0] < desde_ms:
            mem.superciclo.passo(c[0], c[2], c[3], c[4])
            continue
        # passo semanal do ciclo quando uma semana fechou (candle semanal cujo fim <= agora)
        while wi < len(w1) and w1[wi][0] + 7 * 86_400_000 <= c[0] + 86_400_000:
            if wi >= 30:
                win_w = w1[max(0, wi - janela_w + 1):wi + 1]
                mem.ciclo.passo(win_w, w1[wi][2], w1[wi][3], w1[wi][4], w1[wi][0])
            wi += 1
        win_d = dados[max(0, i - janela_d + 1):i + 1]
        mem.primario.passo(win_d, c[2], c[3], c[4], c[0])
        mem.superciclo.passo(c[0], c[2], c[3], c[4])
        if alvo_snaps and c[0] >= alvo_snaps[0]:
            cons = mem.trader(c[0], c[4])
            while alvo_snaps and c[0] >= alvo_snaps[0]:
                snaps.append(cons)
                alvo_snaps.pop(0)
    return {"consenso_final": mem.trader(dados[-1][0], dados[-1][4]), "eventos": mem.primario.eventos + mem.ciclo.eventos,
            "snapshots": snaps, "historico": mem.primario.historico(), "memoria": mem}
