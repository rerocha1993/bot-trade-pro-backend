# core/contexto_fluxo.py
"""
CONTEXTO DO SCALP: Elliott sai do gatilho e vira contexto.

Medido no robô ao vivo, a contagem de Elliott em 1m trocou de fase em 45% das leituras — o mesmo cenário
aparecia com probabilidade 0,32, depois 0,52, depois 0,46. Isso não serve de gatilho: serve de moeda. Mas
Elliott continua sendo a lei nos graus em que a contagem é estável (15m e 1h para o scalp), e é de lá que
vêm as duas coisas que o scalp precisa:

    1. DIREÇÃO PERMITIDA  -- de que lado é aceitável operar (nunca "entre agora")
    2. NÍVEIS             -- onde entrar: VWAP, POC/VAH/VAL, order blocks, invalidação e alvos do cenário

O momento da entrada não sai daqui: sai da fita (core/gatilho_fluxo.py). Aqui é a estrutura.

O plano do par (orquestrador) continua mandando: se ele bloqueia compra, não há fluxo que autorize compra.
Nada aqui envia ordem.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from core.elliott_pro.multidegree import analisar_serie, timeframes_do_perfil
from core.order_block import OrderBlockDetector
from core.tpo import TPOProfile
from core.utils_indicadores import atr as calc_atr
from core.volume_profile_pro import VolumeProfilePRO
from core.vwap import VWAPCalculator

logger = logging.getLogger(__name__)

# viés de um grau: precisa de maioria clara, senão é neutro (mesmo corte que a análise multi-grau usa)
LIMIAR_VIES = 0.6


@dataclass
class Nivel:
    """Um preço que interessa. `tipo` é em relação ao preço atual, não à natureza do indicador."""
    preco: float
    fonte: str
    tipo: str                       # 'suporte' (abaixo do preço) | 'resistencia' (acima)
    forca: float = 1.0

    def distancia_pct(self, preco: float) -> float:
        return abs(self.preco - preco) / preco if preco else 1.0

    def as_dict(self) -> Dict:
        return {"preco": round(self.preco, 2), "fonte": self.fonte, "tipo": self.tipo,
                "forca": round(self.forca, 2)}


@dataclass
class Contexto:
    direcao: str                    # 'buy' | 'sell' | 'ambos' | 'hold'
    motivo: str
    niveis: List[Nivel] = field(default_factory=list)
    atr: float = 0.0                # ATR do grau de contexto, em preço
    fator_tamanho: float = 1.0
    vies_contexto: str = "neutro"
    vies_macro: str = "neutro"
    timeframes: Dict[str, str] = field(default_factory=dict)
    calculado_em: float = field(default_factory=time.time)
    erro: Optional[str] = None

    def permite(self, direcao: str) -> bool:
        return self.direcao == "ambos" or self.direcao == direcao

    def suportes(self) -> List[Nivel]:
        return [n for n in self.niveis if n.tipo == "suporte"]

    def resistencias(self) -> List[Nivel]:
        return [n for n in self.niveis if n.tipo == "resistencia"]

    def nivel_proximo(self, preco: float, tipo: str, tolerancia: float) -> Optional[Nivel]:
        """O nível mais próximo do tipo pedido, se o preço estiver dentro da tolerância dele."""
        candidatos = [n for n in self.niveis if n.tipo == tipo and n.distancia_pct(preco) <= tolerancia]
        return min(candidatos, key=lambda n: n.distancia_pct(preco)) if candidatos else None

    def alvo_na_direcao(self, preco: float, direcao: str) -> Optional[Nivel]:
        """O primeiro nível contrário no caminho: é até ali que o scalp tem espaço para correr."""
        lista = self.resistencias() if direcao == "buy" else self.suportes()
        adiante = [n for n in lista if (n.preco > preco if direcao == "buy" else n.preco < preco)]
        return min(adiante, key=lambda n: abs(n.preco - preco)) if adiante else None

    def as_dict(self) -> Dict:
        return {"direcao": self.direcao, "motivo": self.motivo, "atr": round(self.atr, 2),
                "fator_tamanho": round(self.fator_tamanho, 3), "vies_contexto": self.vies_contexto,
                "vies_macro": self.vies_macro, "timeframes": self.timeframes,
                "idade_s": round(time.time() - self.calculado_em, 1), "erro": self.erro,
                "niveis": [n.as_dict() for n in self.niveis[:12]]}


def _vies(grau: Dict) -> str:
    pb, pr = grau.get("prob_bull", 0) or 0, grau.get("prob_bear", 0) or 0
    if pb >= LIMIAR_VIES:
        return "buy"
    if pr >= LIMIAR_VIES:
        return "sell"
    return "neutro"


class LeitorContexto:
    """
    Lê os graus maiores e monta o contexto do scalp.

    `fetch_ohlcv(timeframe, n)` devolve candles fechados. `plano`, `trava` e `trader` são as mesmas leituras
    que o StrategyEngine usa — passadas de fora para não duplicar chamada de rede nem de banco.
    """

    def __init__(self, fetch_ohlcv: Callable[[str, int], Sequence], par: str, timeframe_bot: str = "1m",
                 perfil_confluencia: str = "conservador", candles: int = 300):
        self.fetch = fetch_ohlcv
        self.par = par
        self.cfg = timeframes_do_perfil("scalping", timeframe_bot)
        self.perfil = (perfil_confluencia or "conservador").lower()
        self.candles = int(candles)

    # ------------------------------------------------------------------ direção
    def _direcao(self, ctx: Dict, macro: Dict, plano: Optional[Dict], trava: Optional[Dict],
                 trader: Optional[Dict]) -> tuple:
        v_ctx, v_macro = _vies(ctx), _vies(macro)
        motivo = [f"contexto {ctx.get('timeframe')}: {ctx.get('fase')} viés {v_ctx} "
                  f"(bull {ctx.get('prob_bull', 0):.0%}/bear {ctx.get('prob_bear', 0):.0%})",
                  f"macro {macro.get('timeframe')}: {macro.get('fase')} viés {v_macro}"]
        fator = 1.0

        # os dois graus concordam -> um lado só. Discordam -> o macro manda no conservador.
        if v_ctx != "neutro" and v_macro != "neutro":
            if v_ctx == v_macro:
                direcao = v_ctx
            elif self.perfil == "conservador":
                direcao = "hold"
                motivo.append("contexto e macro em desacordo: sem lado definido (conservador)")
            else:
                direcao, fator = v_ctx, 0.5
                motivo.append("turbo: seguindo o contexto contra o macro, tamanho reduzido")
        elif v_ctx != "neutro":
            direcao = v_ctx
        elif v_macro != "neutro":
            # só o macro tem lado: o scalp pode operar a favor dele, com tamanho menor
            direcao, fator = v_macro, 0.75
            motivo.append("só o macro tem lado: tamanho reduzido")
        else:
            # nenhum grau tem lado. Não é motivo para parar: sem tendência, o scalp opera as duas pontas
            # do range — que é justamente o que ele faz de melhor. Mas com tamanho menor.
            direcao, fator = "ambos", 0.6
            motivo.append("graus maiores sem lado: opera as duas pontas, tamanho reduzido")

        # a contagem mestre travada pelo usuário manda sobre a leitura automática
        if trava and trava.get("status", "ativa") == "ativa":
            v_mestre = "buy" if trava.get("vies") == "bull" else "sell"
            motivo.append(f"mestre travado ({trava.get('grau', '?')}): viés {v_mestre}")
            if direcao == "ambos":
                direcao = v_mestre
            elif direcao != v_mestre:
                if self.perfil == "conservador":
                    direcao = "hold"
                    motivo.append("contra a contagem mestre: bloqueado (conservador)")
                else:
                    fator *= 0.5
                    motivo.append("turbo: contra a contagem mestre, tamanho reduzido")

        # o trader (superciclo) nunca vende fundo de ciclo nem persegue impulso maduro
        estado = (trader or {}).get("superciclo", {}).get("estado") if trader else None
        if estado:
            motivo.append(f"trader: superciclo {estado}")
            if direcao in ("sell", "ambos") and estado in ("fundo_terminal", "novo_impulso", "zona_onda_2"):
                direcao = "buy" if direcao == "ambos" else ("hold" if self.perfil == "conservador" else "sell")
                if direcao == "sell":
                    fator *= 0.5
                motivo.append(f"venda contra o superciclo ({estado})")
            elif direcao in ("buy", "ambos") and estado == "correcao_inicial":
                direcao = "sell" if direcao == "ambos" else ("hold" if self.perfil == "conservador" else "buy")
                if direcao == "buy":
                    fator *= 0.5
                motivo.append("compra em correção de ciclo recém-iniciada")
            elif direcao == "buy" and estado == "impulso_maduro":
                fator *= 0.5
                motivo.append("impulso de ciclo maduro: não perseguir")

        # o PLANO DO PAR é a última palavra: o robô é tático, o orquestrador é estratégico
        if plano and not plano.get("erro"):
            pode_c, pode_v = plano.get("pode_comprar", True), plano.get("pode_vender", True)
            if not pode_c and not pode_v:
                direcao = "hold"
            elif not pode_c and direcao in ("buy", "ambos"):
                direcao = "sell" if direcao == "ambos" else "hold"
            elif not pode_v and direcao in ("sell", "ambos"):
                direcao = "buy" if direcao == "ambos" else "hold"
            if not pode_c or not pode_v:
                motivo.append(f"plano do par ({plano.get('modo')}): "
                              f"compra {'ok' if pode_c else 'bloqueada'}, venda {'ok' if pode_v else 'bloqueada'}")
            if plano.get("risco_permitido") is not None:
                fator = min(fator, float(plano["risco_permitido"]))
        return direcao, fator, v_ctx, v_macro, " | ".join(motivo)

    # ------------------------------------------------------------------ níveis
    def _niveis(self, serie: Sequence, preco: float, cenario: Optional[Dict]) -> List[Nivel]:
        """
        Os preços onde o scalp tem o direito de tentar. Um nível ACIMA do preço é resistência e um ABAIXO é
        suporte, seja qual for o indicador que o produziu: o que vale é de que lado ele está agora.
        """
        brutos: List[tuple] = []      # (preco, fonte, forca)
        try:
            v = VWAPCalculator(serie).obter_vwap_atual()
            if v:
                brutos.append((float(v), "VWAP", 1.2))
        except Exception as e:
            logger.debug("VWAP do contexto indisponível: %s", e)
        try:
            vp = VolumeProfilePRO(serie, num_bins=40).poc_va()
            for chave, forca in (("POC", 1.5), ("VAH", 1.0), ("VAL", 1.0)):
                if vp.get(chave):
                    brutos.append((float(vp[chave]), f"VP.{chave}", forca))
        except Exception as e:
            logger.debug("volume profile do contexto indisponível: %s", e)
        try:
            tp = TPOProfile(serie, bins=30).calculate_poc_val_vah()
            for chave, forca in (("POC", 1.3), ("VAH", 0.9), ("VAL", 0.9)):
                if tp.get(chave):
                    brutos.append((float(tp[chave]), f"TPO.{chave}", forca))
        except Exception as e:
            logger.debug("TPO do contexto indisponível: %s", e)
        try:
            obd = OrderBlockDetector(serie)
            for tipo in ("bullish", "bearish"):
                for b in obd.blocos_proximos(preco, tipo, max_dist_pct=0.03, n=2):
                    brutos.append((float(b["preco"]), f"OB.{tipo}", 1.0 + min(float(b.get("forca") or 0), 1.0)))
        except Exception as e:
            logger.debug("order blocks do contexto indisponíveis: %s", e)
        if cenario:
            if cenario.get("invalidacao"):
                brutos.append((float(cenario["invalidacao"]), "Elliott.invalidacao", 2.0))
            for i, alvo in enumerate(cenario.get("alvos") or []):
                try:
                    brutos.append((float(alvo), f"Elliott.alvo{i + 1}", 1.6))
                except (TypeError, ValueError):
                    continue

        # níveis colados viram um só: dois indicadores apontando o mesmo preço é confirmação, não dois níveis
        brutos.sort(key=lambda x: x[0])
        agrupados: List[Nivel] = []
        for p, fonte, forca in brutos:
            if p <= 0:
                continue
            if agrupados and abs(p - agrupados[-1].preco) / p <= 0.0006:
                anterior = agrupados[-1]
                anterior.fonte = f"{anterior.fonte}+{fonte}"
                anterior.forca += forca
                anterior.preco = (anterior.preco + p) / 2.0
                continue
            agrupados.append(Nivel(preco=p, fonte=fonte, tipo="suporte" if p < preco else "resistencia",
                                   forca=forca))
        return agrupados

    # ------------------------------------------------------------------ leitura
    def ler(self, preco: float, plano: Optional[Dict] = None, trava: Optional[Dict] = None,
            trader: Optional[Dict] = None) -> Contexto:
        tf_ctx, tf_macro = self.cfg["contexto"], self.cfg["macro"]
        try:
            serie_ctx = self.fetch(tf_ctx, self.candles)
            serie_macro = self.fetch(tf_macro, self.candles)
        except Exception as e:
            logger.warning("contexto do scalp indisponível: %s", e)
            return Contexto(direcao="hold", motivo=f"contexto indisponível: {e}", erro=str(e)[:160],
                            timeframes={"contexto": tf_ctx, "macro": tf_macro})
        ctx = analisar_serie(serie_ctx, self.cfg["fator_atr"], timeframe=tf_ctx, par=self.par)
        macro = analisar_serie(serie_macro, self.cfg["fator_atr"], timeframe=tf_macro, par=self.par)
        ctx["timeframe"], macro["timeframe"] = tf_ctx, tf_macro
        direcao, fator, v_ctx, v_macro, motivo = self._direcao(ctx, macro, plano, trava, trader)
        niveis = self._niveis(serie_ctx, preco, ctx.get("primario"))
        return Contexto(direcao=direcao, motivo=motivo, niveis=niveis,
                        atr=float(calc_atr(serie_ctx, 14) or 0.0), fator_tamanho=fator,
                        vies_contexto=v_ctx, vies_macro=v_macro,
                        timeframes={"contexto": tf_ctx, "macro": tf_macro})
