# core/elliott_pro/scenarios.py
"""
Gerador de cenários de Elliott concorrentes.

Em Elliott sempre há mais de uma contagem possível. Este módulo gera TODAS as hipóteses
compatíveis com os pivôs recentes (padrões completos + padrões em andamento), atribui a cada
uma um score (regras/diretrizes) x prior do padrão x recência, normaliza em probabilidade e
devolve:
    cenarios     lista ordenada por probabilidade (cada um com viés, fase, invalidação, alvos)
    primario     cenário mais provável
    prob_bull    soma das probabilidades dos cenários cujo PRÓXIMO movimento é de alta
    prob_bear    idem para baixa
    direcao      'buy' | 'sell' | 'hold' (consenso: ≥ 60% de um lado)

Vocabulário de fases (compatível com core/fase_onda_rules.py):
    onda_1, onda_2, inicio_onda_3, meio_onda_3, final_onda_3, onda_4, onda_5,
    correcao_a, correcao_b, correcao_c, triangulo, consolidacao, indefinido
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .patterns import Leg, PatternFit, ajustar_todos, ajustar_flat, ajustar_impulso, ajustar_zigzag, legs_de_pivots
from .pivots import Pivot

PRIOR_PADRAO = {
    "impulso": 1.0, "zigzag": 0.9, "flat_regular": 0.7, "flat_expandido": 0.7, "flat_running": 0.55,
    "duplo_tres": 0.6, "triplo_tres": 0.4, "triangulo_contratil": 0.6, "triangulo_barreira": 0.55,
    "triangulo_expansivo": 0.4, "diagonal_leading": 0.5, "diagonal_ending": 0.55,
}
RECENCIA = {0: 1.0, 1: 0.85, 2: 0.7, 3: 0.5}
PESO_INDEFINIDO = 0.4   # massa da hipótese "nenhum dos cenários" na normalização (evita 100% com 1 cenário fraco)


@dataclass
class Cenario:
    id: str
    nome: str
    padrao: str
    vies: str                    # 'bull' | 'bear' -> próximo movimento esperado
    fase: str
    direcao_trade: str           # 'buy' | 'sell' | 'hold' (sugestão bruta; o motor aplica perfil/regras)
    horizonte: str               # 'impulso' (movimento maior) | 'correcao' (movimento menor/momentâneo)
    score: float
    probabilidade: float = 0.0
    invalidacao: Optional[float] = None
    alvos: List[float] = field(default_factory=list)
    ondas: List[Dict] = field(default_factory=list)
    completo: bool = True
    offset: int = 0
    motivo: str = ""
    regras: List[Dict] = field(default_factory=list)

    def dict(self) -> Dict:
        return {
            "id": self.id, "nome": self.nome, "padrao": self.padrao, "vies": self.vies, "fase": self.fase,
            "direcao_trade": self.direcao_trade, "horizonte": self.horizonte, "score": round(self.score, 3),
            "probabilidade": round(self.probabilidade, 3), "invalidacao": self.invalidacao,
            "alvos": [round(a, 2) for a in self.alvos], "ondas": self.ondas, "completo": self.completo,
            "offset": self.offset, "motivo": self.motivo,
        }


def _alem(a: float, b: float, up: bool) -> bool:
    return a > b if up else a < b


class ScenarioEngine:
    def __init__(self, pivots: Sequence[Pivot], preco_atual: float, limiar: float, atr_valor: float = 0.0,
                 max_pivots: int = 40):
        self.pivots = list(pivots)[-max_pivots:]
        self.conf = [p for p in self.pivots if p.confirmado]
        self.prov = self.pivots[-1] if self.pivots and not self.pivots[-1].confirmado else None
        self.preco = float(preco_atual)
        self.limiar = float(limiar)
        self.atr = float(atr_valor)
        self._contador = 0

    # ----------------------------------------------------------- helpers
    def _novo_id(self, prefixo: str) -> str:
        self._contador += 1
        return f"{prefixo}_{self._contador}"

    @staticmethod
    def _ondas_dict(fit: PatternFit) -> List[Dict]:
        return [{"rotulo": r, **l.dict()} for r, l in zip(fit.rotulos, fit.legs)]

    def _legs_com_prov(self, n_conf: int) -> Optional[List[Leg]]:
        """n_conf pivôs confirmados finais + o provisório."""
        if not self.prov or len(self.conf) < n_conf:
            return None
        return legs_de_pivots(self.conf[-n_conf:] + [self.prov])

    def _posteriores(self, fim_idx_conf: int) -> List[Pivot]:
        """Pivôs confirmados após a posição `fim_idx_conf` (exclusiva)."""
        return self.conf[fim_idx_conf + 1:]

    # ------------------------------------------------------------ geração
    def gerar(self) -> List[Cenario]:
        cen: List[Cenario] = []
        n = len(self.conf)
        if n < 2:
            return cen
        # A) padrões COMPLETOS terminando em pivô confirmado, com 0..3 pivôs posteriores
        for offset in range(0, 4):
            fim = n - 1 - offset
            for n_legs in (5, 3):
                ini = fim - n_legs
                if ini < 0:
                    continue
                legs = legs_de_pivots(self.conf[ini:fim + 1])
                for fit in ajustar_todos(legs):
                    cen.extend(self._derivar_de_completo(fit, offset, fim))
        # B) impulsos EM ANDAMENTO (última perna = provisória)
        cen.extend(self._impulsos_em_andamento())
        # C) correções EM ANDAMENTO sem exigir impulso anterior
        cen.extend(self._correcoes_em_andamento())
        # D) consolidação
        if not cen and self._consolidacao():
            cen.append(Cenario(self._novo_id("cons"), "Consolidação (pivôs em faixa estreita)", "consolidacao",
                               "bull" if self.prov and self.prov.tipo == "H" else "bear", "consolidacao", "hold",
                               "correcao", 0.5, motivo="Faixa estreita; aguardar rompimento"))
        return self._finalizar(cen)

    # ------------------------------------------ A) derivados de padrões completos
    def _derivar_de_completo(self, fit: PatternFit, offset: int, fim_idx: int) -> List[Cenario]:
        up = fit.direcao == "up"
        s = 1 if up else -1
        P0, Pf = fit.inicio, fit.fim
        amplitude = abs(Pf - P0)
        post = self._posteriores(fim_idx)          # pivôs confirmados após o padrão
        preco = self.preco
        saida: List[Cenario] = []
        base_score = fit.score * PRIOR_PADRAO.get(fit.padrao, 0.5) * RECENCIA.get(offset, 0.4)
        ondas = self._ondas_dict(fit)

        if fit.classe == "motriz" and fit.padrao in ("impulso", "diagonal_leading"):
            # impulso completo -> espera correção ABC contra a tendência
            vies = "bear" if up else "bull"
            alvos = [Pf - s * 0.382 * amplitude, Pf - s * 0.5 * amplitude, Pf - s * 0.618 * amplitude]
            if offset == 0:
                if _alem(preco, Pf, up):
                    # preço além do fim da 5: onda 5 estendendo
                    saida.append(Cenario(self._novo_id("imp"), f"Impulso de {'alta' if up else 'baixa'} com onda 5 estendendo",
                                         fit.padrao, "bull" if up else "bear", "onda_5", "buy" if up else "sell", "impulso",
                                         base_score * 0.8, invalidacao=fit.legs[3].fim,
                                         alvos=[Pf + s * 0.382 * fit.legs[0].tamanho, Pf + s * 0.618 * fit.legs[0].tamanho],
                                         ondas=ondas, offset=offset, motivo="Onda 5 ultrapassou o topo anterior e segue", regras=fit.regras))
                else:
                    saida.append(Cenario(self._novo_id("imp"), f"Impulso de {'alta' if up else 'baixa'} completo: correção A em andamento",
                                         fit.padrao, vies, "correcao_a", "sell" if up else "buy", "correcao", base_score,
                                         invalidacao=Pf, alvos=alvos, ondas=ondas, offset=offset,
                                         motivo="5 ondas completas; esperado ABC de retração 38-62%", regras=fit.regras))
            elif offset == 1:
                A_fim = post[0].preco
                saida.append(Cenario(self._novo_id("imp"), f"Impulso de {'alta' if up else 'baixa'} completo: onda B em andamento",
                                     fit.padrao, vies, "correcao_b", "hold", "correcao", base_score,
                                     invalidacao=Pf, alvos=[A_fim - s * 1.0 * abs(Pf - A_fim), A_fim - s * 1.618 * abs(Pf - A_fim)],
                                     ondas=ondas, offset=offset, motivo="A concluída; B retraindo (não operar)", regras=fit.regras))
            elif offset == 2:
                A_fim, B_fim = post[0].preco, post[1].preco
                tA = abs(Pf - A_fim)
                saida.append(Cenario(self._novo_id("imp"), f"Impulso de {'alta' if up else 'baixa'} completo: onda C em andamento",
                                     fit.padrao, vies, "correcao_c", "sell" if up else "buy", "correcao", base_score,
                                     invalidacao=B_fim, alvos=[B_fim - s * 0.618 * tA, B_fim - s * 1.0 * tA, B_fim - s * 1.618 * tA],
                                     ondas=ondas, offset=offset, motivo="B concluída; C costuma igualar A (1,0) ou 1,618", regras=fit.regras))
            else:
                # 3 pivôs posteriores: ABC pode ter terminado -> novo impulso na direção anterior
                legs_corr = legs_de_pivots([self.conf[fim_idx]] + post[:3])
                corr = ajustar_zigzag(legs_corr) or ajustar_flat(legs_corr)
                if corr:
                    C_fim = post[2].preco
                    saida.append(Cenario(self._novo_id("imp"), f"Correção ABC concluída após impulso de {'alta' if up else 'baixa'}: novo impulso (onda 1)",
                                         fit.padrao, "bull" if up else "bear", "onda_1", "buy" if up else "sell", "impulso",
                                         base_score * 0.8, invalidacao=C_fim,
                                         alvos=[C_fim + s * 0.618 * amplitude, C_fim + s * 1.0 * amplitude],
                                         ondas=ondas + self._ondas_dict(corr), offset=offset,
                                         motivo=f"{corr.padrao} concluído; retomada da tendência", regras=fit.regras))
        elif fit.padrao == "diagonal_ending":
            # diagonal final -> reversão brusca até a origem da diagonal
            saida.append(Cenario(self._novo_id("diag"), f"Diagonal final de {'alta' if up else 'baixa'}: reversão esperada",
                                 fit.padrao, "bear" if up else "bull", "correcao_a", "sell" if up else "buy", "impulso",
                                 base_score, invalidacao=Pf, alvos=[Pf - s * 0.618 * amplitude, P0], ondas=ondas, offset=offset,
                                 motivo="Diagonais finais são revertidas rapidamente até sua origem", regras=fit.regras))
        elif fit.padrao.startswith("triangulo"):
            # triângulo completo -> thrust na direção contrária à perna 'a'
            a = fit.legs[0]
            thrust_up = not a.sobe
            st = 1 if thrust_up else -1
            e_fim = fit.fim
            saida.append(Cenario(self._novo_id("tri"), f"Triângulo completo: thrust de {'alta' if thrust_up else 'baixa'}",
                                 fit.padrao, "bull" if thrust_up else "bear", "onda_5" if offset == 0 else "onda_1",
                                 "buy" if thrust_up else "sell", "impulso", base_score, invalidacao=fit.legs[3].fim,
                                 alvos=[e_fim + st * 0.75 * a.tamanho, e_fim + st * 1.0 * a.tamanho], ondas=ondas, offset=offset,
                                 motivo="Alvo do thrust = largura do triângulo (perna a)", regras=fit.regras))
        elif fit.classe == "corretivo":
            # zigzag / flat / WXY completos -> retomada na direção oposta à correção
            vies_up = not up
            sv = 1 if vies_up else -1
            saida.append(Cenario(self._novo_id("corr"), f"{fit.padrao.replace('_', ' ').title()} de {'alta' if up else 'baixa'} concluído: retomada {'de alta' if vies_up else 'de baixa'}",
                                 fit.padrao, "bull" if vies_up else "bear", "onda_1" if offset == 0 else "onda_2" if offset == 1 else "inicio_onda_3",
                                 ("buy" if vies_up else "sell") if offset != 1 else "hold", "impulso", base_score * 0.9,
                                 invalidacao=Pf, alvos=[Pf + sv * 0.618 * amplitude, Pf + sv * 1.0 * amplitude, Pf + sv * 1.618 * amplitude],
                                 ondas=ondas, offset=offset, motivo="Correção completa; espera-se impulso contrário", regras=fit.regras))
        return saida

    # ------------------------------------------ B) impulsos em andamento
    def _impulsos_em_andamento(self) -> List[Cenario]:
        saida = []
        preco = self.preco
        for n_conf in (5, 4, 3, 2):
            legs = self._legs_com_prov(n_conf)
            if not legs:
                continue
            up = legs[0].sobe
            s = 1 if up else -1
            t = [l.tamanho for l in legs]
            if t[0] < 1.5 * self.limiar:
                continue
            w = legs
            # regras parciais obrigatórias
            if len(legs) >= 2 and _alem(w[1].fim, w[0].inicio, not up):
                continue  # onda 2 além do início da 1
            if len(legs) >= 3 and not _alem(w[2].fim if len(legs) == 3 else w[2].fim, w[0].fim, up):
                continue  # onda 3 não rompeu o fim da 1
            if len(legs) >= 4 and _alem(w[3].fim, w[0].fim, not up):
                continue  # onda 4 sobrepôs a 1
            if len(legs) >= 4 and t[2] < t[0]:
                continue  # onda 3 menor que a 1 (será a mais curta ou diagonal)
            r2 = t[1] / t[0] if len(legs) >= 2 else None
            qual = 0.7 + (0.3 if (r2 is not None and 0.382 <= r2 <= 0.786) else 0.0)
            ondas = [{"rotulo": str(i + 1), **l.dict()} for i, l in enumerate(legs)]

            if len(legs) == 2:
                # onda 1 confirmada, onda 2 retraindo (provisória)
                saida.append(Cenario(self._novo_id("wip"), f"Onda 1 de {'alta' if up else 'baixa'} concluída: onda 2 em andamento",
                                     "impulso", "bull" if up else "bear", "onda_2", "hold", "impulso", 0.45 * qual,
                                     invalidacao=w[0].inicio, alvos=[w[0].fim - s * 0.5 * t[0], w[0].fim - s * 0.618 * t[0]],
                                     ondas=ondas, completo=False, motivo=f"Onda 2 retraiu {r2:.0%} da onda 1"))
            elif len(legs) == 3:
                L2 = w[1].fim
                prog = abs(preco - L2) / t[0] if t[0] else 0
                if not _alem(preco, w[0].fim, up):
                    fase = "inicio_onda_3"
                elif prog < 1.618:
                    fase = "meio_onda_3"
                else:
                    fase = "final_onda_3"
                saida.append(Cenario(self._novo_id("wip"), f"Impulso de {'alta' if up else 'baixa'}: onda 3 em andamento ({prog:.2f}x onda 1)",
                                     "impulso", "bull" if up else "bear", fase, "buy" if up else "sell", "impulso", 0.9 * qual,
                                     invalidacao=L2, alvos=[L2 + s * 1.0 * t[0], L2 + s * 1.618 * t[0], L2 + s * 2.618 * t[0]],
                                     ondas=ondas, completo=False, motivo="Onda 3 é a mais forte; alvos 1,0 / 1,618 / 2,618 x onda 1"))
            elif len(legs) == 4:
                H3 = w[2].fim
                r4 = t[3] / t[2]
                saida.append(Cenario(self._novo_id("wip"), f"Impulso de {'alta' if up else 'baixa'}: onda 4 em andamento ({r4:.0%} da onda 3)",
                                     "impulso", "bull" if up else "bear", "onda_4", "hold", "impulso", 0.8 * qual * (1.0 if r4 <= 0.5 else 0.7),
                                     invalidacao=w[0].fim, alvos=[H3 - s * 0.382 * t[2], H3 - s * 0.5 * t[2]],
                                     ondas=ondas, completo=False, motivo="Onda 4 costuma parar em 23,6-38,2% da 3; não invadir a 1"))
            elif len(legs) == 5:
                L4 = w[3].fim
                ext = abs(preco - L4) / t[0] if t[0] else 0
                esticada = ext > 1.618
                saida.append(Cenario(self._novo_id("wip"), f"Impulso de {'alta' if up else 'baixa'}: onda 5 em andamento ({ext:.2f}x onda 1)",
                                     "impulso", "bull" if up else "bear", "onda_5", "hold" if esticada else ("buy" if up else "sell"),
                                     "impulso", 0.85 * qual * (0.6 if esticada else 1.0), invalidacao=L4,
                                     alvos=[L4 + s * 0.618 * t[0], L4 + s * 1.0 * t[0], L4 + s * 0.618 * (t[0] + t[2])],
                                     ondas=ondas, completo=False, motivo="Onda 5 ≈ onda 1 ou 0,618 x (1+3); euforia = fim próximo"))
        return saida

    # ------------------------------------------ C) correções em andamento
    def _correcoes_em_andamento(self) -> List[Cenario]:
        saida = []
        legs = self._legs_com_prov(2)   # A confirmada, B confirmada, C provisória
        if legs and len(legs) == 3:
            a, b, c = legs
            up = a.sobe
            s = 1 if up else -1
            rb = b.tamanho / a.tamanho if a.tamanho else None
            if rb is not None and 0.382 <= rb < 1.382 and a.tamanho >= 1.5 * self.limiar and _alem(c.fim, b.fim, up):
                flat = rb >= 0.9
                saida.append(Cenario(self._novo_id("cwip"), f"{'Flat' if flat else 'Zigzag'} de {'alta' if up else 'baixa'}: onda C em andamento",
                                     "flat_regular" if flat else "zigzag", "bull" if up else "bear", "correcao_c",
                                     "buy" if up else "sell", "correcao", 0.6, invalidacao=b.fim,
                                     alvos=[b.fim + s * 0.618 * a.tamanho, b.fim + s * 1.0 * a.tamanho, b.fim + s * 1.618 * a.tamanho],
                                     ondas=[{"rotulo": r, **l.dict()} for r, l in zip(["A", "B", "C"], legs)], completo=False,
                                     motivo=f"B retraiu {rb:.0%} de A; C alvo 1,0-1,618 x A"))
        legs = self._legs_com_prov(1)   # A confirmada, B provisória
        if legs and len(legs) == 2:
            a, b = legs
            up = a.sobe
            if a.tamanho >= 2 * self.limiar and b.tamanho < a.tamanho:
                saida.append(Cenario(self._novo_id("cwip"), f"Correção de {'alta' if up else 'baixa'}: onda B em andamento",
                                     "zigzag", "bull" if up else "bear", "correcao_b", "hold", "correcao", 0.35,
                                     invalidacao=a.inicio, alvos=[a.fim - (1 if up else -1) * 0.5 * a.tamanho], completo=False,
                                     ondas=[{"rotulo": r, **l.dict()} for r, l in zip(["A", "B"], legs)],
                                     motivo="Após A, B retrai; C viria na direção de A"))
        legs = self._legs_com_prov(4)   # triângulo a-b-c-d confirmados, e provisória
        if legs and len(legs) == 5:
            t = [l.tamanho for l in legs]
            if min(t) > 0 and all(0.45 <= t[i] / t[i - 1] <= 0.95 for i in range(1, 4)) and t[4] < t[3]:
                a = legs[0]
                thrust_up = not a.sobe
                st = 1 if thrust_up else -1
                saida.append(Cenario(self._novo_id("tri"), "Triângulo contrátil em andamento (onda e)", "triangulo_contratil",
                                     "bull" if thrust_up else "bear", "triangulo", "hold", "correcao", 0.5,
                                     invalidacao=legs[3].fim, alvos=[legs[3].fim + st * 0.75 * a.tamanho, legs[3].fim + st * a.tamanho],
                                     ondas=[{"rotulo": r, **l.dict()} for r, l in zip(["a", "b", "c", "d", "e"], legs)], completo=False,
                                     motivo="Esperar rompimento; thrust = largura do triângulo"))
        return saida

    def _consolidacao(self) -> bool:
        ult = self.conf[-5:]
        if len(ult) < 4:
            return False
        precos = [p.preco for p in ult]
        return (max(precos) - min(precos)) <= 2.5 * self.limiar

    # ------------------------------------------------------------ pós-processo
    def _finalizar(self, cen: List[Cenario]) -> List[Cenario]:
        ativos = []
        for c in cen:
            # invalidação: preço já cruzou o nível de invalidação na direção contrária ao viés
            if c.invalidacao is not None:
                if c.vies == "bull" and self.preco < c.invalidacao:
                    continue
                if c.vies == "bear" and self.preco > c.invalidacao:
                    continue
            # alvos coerentes com o viés (descarta alvos já ultrapassados e preços impossíveis <= 15% do atual)
            if c.vies == "bull":
                c.alvos = [a for a in c.alvos if a > self.preco]
            else:
                c.alvos = [a for a in c.alvos if self.preco * 0.15 < a < self.preco]
            ativos.append(c)
        # dedupe por (fase, viés, invalidação aproximada): mantém maior score
        melhores: Dict[tuple, Cenario] = {}
        for c in ativos:
            chave = (c.fase, c.vies, round(c.invalidacao / max(self.limiar, 1e-9)) if c.invalidacao else None)
            if chave not in melhores or c.score > melhores[chave].score:
                melhores[chave] = c
        ativos = list(melhores.values())
        total = sum(c.score for c in ativos) + PESO_INDEFINIDO
        for c in ativos:
            c.probabilidade = round(c.score / total, 3) if total else 0.0
        ativos.sort(key=lambda c: -c.probabilidade)
        return ativos

    # ------------------------------------------------------------- resumo
    def analisar(self) -> Dict:
        cen = self.gerar()
        prob_bull = round(sum(c.probabilidade for c in cen if c.vies == "bull"), 3)
        prob_bear = round(sum(c.probabilidade for c in cen if c.vies == "bear"), 3)
        prob_indefinido = round(max(0.0, 1.0 - prob_bull - prob_bear), 3)
        primario = cen[0] if cen else None
        if prob_bull >= 0.6:
            consenso = "buy"
        elif prob_bear >= 0.6:
            consenso = "sell"
        else:
            consenso = "hold"
        return {
            "preco": self.preco,
            "n_cenarios": len(cen),
            "prob_bull": prob_bull,
            "prob_bear": prob_bear,
            "prob_indefinido": prob_indefinido,
            "consenso": consenso,
            "fase": primario.fase if primario else "indefinido",
            "direcao": (primario.direcao_trade if primario else "hold"),
            "tendencia": ("alta" if prob_bull > prob_bear else "baixa" if prob_bear > prob_bull else "lateral"),
            "primario": primario.dict() if primario else None,
            "alternativos": [c.dict() for c in cen[1:5]],
            "cenarios": [c.dict() for c in cen],
            "invalidacao": primario.invalidacao if primario else None,
            "alvos": primario.alvos if primario else [],
            "limiar_zigzag": self.limiar,
            "pivots": [p.dict() for p in self.pivots[-12:]],
        }
