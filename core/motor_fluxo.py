# core/motor_fluxo.py
"""
MOTOR DE FLUXO: o motor de decisão do scalp.

Junta as três peças e substitui o relógio de 1m como gatilho:

    core/barras_fluxo.py    fecha barra por quantidade negociada, não por minuto
    core/contexto_fluxo.py  Elliott em 15m/1h diz o LADO permitido e os NÍVEIS
    core/gatilho_fluxo.py   a fita diz a HORA, em cima desses níveis

Por que: medido no robô ao vivo, a contagem de Elliott em 1m trocou de fase em 45% das leituras, e era ela
que segurava o scalp parado ("Elliott sem direção operável" em 16 de 48 decisões). O 1m não tem contagem
boa — tem ruído. Scalp de verdade se mede por fluxo.

O contexto é recalculado por tempo (é caro: puxa 15m e 1h e roda cenários). O gatilho roda a cada barra de
fluxo que fecha — que em mercado agitado é a cada poucos segundos, e em mercado parado quase nunca, que é
exatamente o ritmo certo.

Nada aqui envia ordem: devolve uma decisão no mesmo formato do StrategyEngine e o executor faz o resto.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional, Sequence

from core.barras_fluxo import AgregadorBarras, Barra
from core.contexto_fluxo import Contexto, LeitorContexto, Nivel
from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.gatilho_fluxo import GatilhoFluxo, ParametrosFluxo

logger = logging.getLogger(__name__)

RR_MINIMO = {"conservador": 1.2, "turbo": 1.0}
# o contexto vem dos graus 15m/1h: recalcular a cada 3 minutos já é mais frequente do que eles mudam
INTERVALO_CONTEXTO_S = 180.0


def _hold(motivo: str, **extra) -> Dict:
    """Decisão no formato que o executor e o painel já entendem."""
    base = {"acao": "hold", "motivo": motivo, "fase_onda": None, "votos": [], "indicadores_ativos": [],
            "tp": None, "sl": None, "cenario": None, "probabilidade": None, "cenarios": [],
            "tamanho_fator": 1.0, "contra_tendencia": False, "motor": "fluxo"}
    base.update(extra)
    return base


class MotorFluxo:
    """
    Motor de scalp por fluxo. Um por robô.

    `fetch_ohlcv(timeframe, n)` é usado só para o contexto (15m/1h). O operacional vem das barras de fluxo,
    montadas a partir dos negócios do websocket.
    """

    def __init__(self, bot, fetch_ohlcv: Callable[[str, int], Sequence],
                 parametros: Optional[ParametrosFluxo] = None,
                 intervalo_contexto_s: float = INTERVALO_CONTEXTO_S):
        self.bot = bot
        self.par = (getattr(bot, "ativo", "BTCUSDT") or "BTCUSDT").replace("/", "")
        self.perfil = (getattr(bot, "confluencia_tipo", "conservador") or "conservador").lower()
        self.agregador = AgregadorBarras(
            tipo=(getattr(bot, "barra_tipo", None) or "volume"),
            tamanho=float(getattr(bot, "barra_tamanho", 0) or 0),
            segundos_alvo=float(getattr(bot, "barra_segundos_alvo", 0) or 30.0))
        self.gatilho = GatilhoFluxo(parametros)
        self.leitor = LeitorContexto(fetch_ohlcv, self.par,
                                     timeframe_bot=getattr(bot, "timeframe", "1m") or "1m",
                                     perfil_confluencia=self.perfil)
        self.intervalo_contexto = float(intervalo_contexto_s)
        self.contexto: Optional[Contexto] = None
        self._proximo_contexto = 0.0
        # a absorcao e, por natureza, uma ordem LIMITADA no nivel: o preco esta ali porque alguem esta
        # segurando, e pagar o spread para entrar junto e jogar fora boa parte do ganho. Com entrada
        # limitada o custo cai de 0,110% (taker dos dois lados) para 0,075% de ida e volta.
        self.limitada = (getattr(bot, "tipo_entrada", "mercado") or "mercado") == "limite"
        self.taxa_entrada = TAXA_MAKER if self.limitada else TAXA_TAKER
        self.taxa_saida = TAXA_TAKER
        self.ultima_barra: Optional[Barra] = None
        self.barras_avaliadas = 0
        self.ultimo_motivo: str = "ainda não avaliou nada"

    # ------------------------------------------------------------------ contexto
    @property
    def contexto_vencido(self) -> bool:
        """Quem chama consulta isto ANTES de buscar plano/trava/trader: são caros e só servem se for recalcular."""
        return self.contexto is None or time.time() >= self._proximo_contexto

    def atualizar_contexto(self, preco: float, plano: Optional[Dict] = None, trava: Optional[Dict] = None,
                           trader: Optional[Dict] = None, forcar: bool = False) -> Optional[Contexto]:
        """Recalcula os graus maiores quando vence o intervalo. Caro: nunca a cada barra."""
        agora = time.time()
        if not forcar and self.contexto is not None and agora < self._proximo_contexto:
            return self.contexto
        try:
            self.contexto = self.leitor.ler(preco, plano=plano, trava=trava, trader=trader)
        except Exception as e:
            logger.warning("[%s] contexto do scalp falhou: %s", getattr(self.bot, "nome", "?"), e)
            # mantém o contexto anterior em vez de operar sem estrutura nenhuma
            if self.contexto is None:
                self.contexto = Contexto(direcao="hold", motivo=f"contexto indisponível: {e}", erro=str(e)[:160])
        self._proximo_contexto = agora + self.intervalo_contexto
        return self.contexto

    # ------------------------------------------------------------------ níveis -> SL/TP
    def _folga(self, barras: Sequence[Barra], preco: float) -> float:
        """
        Espaço a dar ao stop além do nível: meio range médio de barra, com piso de 0,05% do preço.

        Stop colado no nível é stop caçado. Stop longe do nível não é scalp: se o nível não segurou, a
        leitura estava errada e não há motivo para continuar pagando por ela.
        """
        rng = self.gatilho._range_medio(barras)
        return max(rng * 0.5, preco * 0.0005)

    def _sl_tp(self, direcao: str, preco: float, nivel: Nivel, barras: Sequence[Barra],
               contexto: Contexto) -> Dict:
        """
        Stop atrás do nível, alvo no próximo nível contrário, e o risco:retorno medido LÍQUIDO DE CUSTO.

        O R:R bruto mente no scalp, e o backtest mostrou o tamanho da mentira: num dia de BTC o motor fez
        27 trades com resultado bruto de −15 dólares e pagou 147 de taxa. O stop médio ficou em 0,129% e a
        ida e volta a mercado custa 0,110% — ou seja, quase 1R de custo por trade. Havia até trade que
        BATEU NO ALVO e mesmo assim deu prejuízo. Um filtro de R:R que ignora a taxa aprova exatamente esse
        tipo de operação.
        """
        janela = self.gatilho._janela(barras)
        folga = self._folga(barras, preco)
        if direcao == "buy":
            # o stop mora abaixo do que o nível defendeu na janela, não abaixo do preço de entrada
            base = min(min(b.minima for b in janela), nivel.preco)
            sl = base - folga
        else:
            base = max(max(b.maxima for b in janela), nivel.preco)
            sl = base + folga
        risco = abs(preco - sl)
        if risco <= 0:
            return {"sl": None, "tp": None, "rr": 0.0, "rr_liquido": 0.0, "rr_minimo": 0.0,
                    "fonte_tp": None, "fonte_sl": None}
        alvo = contexto.alvo_na_direcao(preco, direcao)
        if alvo is not None:
            # para no nível contrário, com uma folga para dentro: quem espera o preço exato costuma não ser servido
            tp = alvo.preco - folga * 0.5 if direcao == "buy" else alvo.preco + folga * 0.5
            fonte_tp = alvo.fonte
        else:
            tp = preco + risco * 2.0 if direcao == "buy" else preco - risco * 2.0
            fonte_tp = "2R (sem nível adiante)"
        custo = preco * (self.taxa_entrada + self.taxa_saida)
        rr = abs(tp - preco) / risco
        rr_liquido = max(abs(tp - preco) - custo, 0.0) / (risco + custo)
        rr_min = float(getattr(self.bot, "rr_minimo", 0) or 0) or RR_MINIMO.get(self.perfil, 1.2)
        return {"sl": round(sl, 2), "tp": round(tp, 2), "rr": round(rr, 2),
                "rr_liquido": round(rr_liquido, 2), "rr_minimo": rr_min,
                "fonte_tp": fonte_tp, "fonte_sl": f"{nivel.fonte} - folga {folga:,.2f}",
                "risco": round(risco, 2), "custo": round(custo, 2),
                "custo_em_r": round(custo / risco, 2)}

    # ------------------------------------------------------------------ ciclo
    def ingerir(self, trades: Sequence[Dict]) -> List[Barra]:
        """Alimenta o agregador com negócios NOVOS e devolve as barras que fecharam."""
        novas = self.agregador.ingerir(trades)
        if novas:
            self.ultima_barra = novas[-1]
        return novas

    def avaliar(self, preco: float, imbalance: Optional[float] = None, plano: Optional[Dict] = None,
                trava: Optional[Dict] = None, trader: Optional[Dict] = None) -> Dict:
        """
        Decide em cima do estado atual das barras. Chamado quando uma barra de fluxo FECHA.

        Devolve uma decisão no formato do StrategyEngine: o executor não precisa saber qual motor decidiu.
        """
        self.barras_avaliadas += 1
        contexto = self.atualizar_contexto(preco, plano=plano, trava=trava, trader=trader)
        detalhes_base = {"motor": "fluxo", "contexto_fluxo": contexto.as_dict() if contexto else None,
                         "barras": self.agregador.status()}
        if contexto is None:
            return _hold("Sem contexto para o scalp", **detalhes_base)
        if not self.agregador.calibrado:
            return _hold(f"Régua da barra ainda calibrando pelo fluxo "
                         f"({self.agregador.negocios_vistos} negócios vistos)", **detalhes_base)

        barras = list(self.agregador.fechadas)
        leitura = self.gatilho.avaliar(barras, contexto, preco, imbalance=imbalance)
        self.ultimo_motivo = leitura["motivo"]
        detalhes_base["fluxo"] = {k: v for k, v in leitura.items() if k not in ("nivel_obj",)}
        # o contexto vem dos graus maiores: a fase que vai para o banco é a do contexto, não uma contagem de 1m
        detalhes_base.update({"tendencia_macro": contexto.vies_macro,
                              "fase_onda": None, "cenario": f"contexto {contexto.vies_contexto}"[:60]})
        if leitura["acao"] == "hold":
            return _hold(leitura["motivo"], **detalhes_base)

        direcao, nivel = leitura["acao"], leitura["nivel_obj"]
        niveis = self._sl_tp(direcao, preco, nivel, barras, contexto)
        detalhes_base["niveis"] = niveis
        if niveis["sl"] is None:
            return _hold("Não foi possível montar um stop a partir do nível", **detalhes_base)
        if niveis["rr_liquido"] < niveis["rr_minimo"]:
            return _hold(f"{leitura['motivo']} — mas o risco:retorno líquido de taxa é {niveis['rr_liquido']} "
                         f"(bruto {niveis['rr']}), abaixo do mínimo {niveis['rr_minimo']}: o custo sozinho "
                         f"vale {niveis['custo_em_r']}R", **detalhes_base)
        return {**_hold(""), **detalhes_base, "acao": direcao, "sl": niveis["sl"], "tp": niveis["tp"],
                "preco_limite": round(nivel.preco, 2) if self.limitada else None,
                "tamanho_fator": contexto.fator_tamanho,
                "votos": [f"fluxo:{leitura['gatilho']}"],
                "probabilidade": leitura.get("forca"),
                "contra_tendencia": contexto.direcao == "ambos",
                "motivo": (f"Fluxo [{leitura['gatilho']}] {leitura['motivo']} | contexto "
                           f"{contexto.vies_contexto}/{contexto.vies_macro} "
                           f"({contexto.timeframes.get('contexto')}/{contexto.timeframes.get('macro')}) "
                           f"| SL {niveis['sl']} TP {niveis['tp']} R:R {niveis['rr_liquido']} "
                           f"líquido ({niveis['rr']} bruto, custo {niveis['custo_em_r']}R)")}

    # ------------------------------------------------------------------ leitura
    def status(self) -> Dict:
        return {"motor": "fluxo", "barras": self.agregador.status(),
                "barras_avaliadas": self.barras_avaliadas,
                "ultima_barra": self.ultima_barra.as_dict() if self.ultima_barra else None,
                "ultimo_motivo": self.ultimo_motivo[:300],
                "contexto": self.contexto.as_dict() if self.contexto else None}
