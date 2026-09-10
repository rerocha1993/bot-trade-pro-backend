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
# quantos intervalos o contexto pode envelhecer antes de deixar de valer. Se a leitura dos graus maiores
# falha de forma persistente, o contexto anterior fica de pé e continuaria autorizando entradas com um viés
# de horas atrás — com um warning no console como única pista.
IDADE_MAXIMA_CONTEXTO = 3.0
# piso do stop: fora do ruído da barra e bem acima do custo. Ver `_risco_minimo`.
RISCO_MINIMO_RANGES = 3.0
RISCO_MINIMO_PCT = 0.0012
# teto do alvo, em múltiplos do risco. O "próximo nível" às vezes está a 1,7% — isso é alvo de daytrade, e
# uma posição de scalp segurada por 2 horas esperando por ele deixa de ser scalp.
ALVO_MAXIMO_R = 3.0


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
        # piso do risco e teto do alvo sao a alavanca economica do scalp: com stop de 0,12%% e ida e volta de
        # 0,075%%, a taxa sozinha vale 0,6R por trade, e o ponto de equilibrio sobe para 40%% de acerto. Stop
        # mais largo dilui esse custo fixo, ao preco de o trade demorar mais. Ficam configuraveis para poder
        # medir, em vez de ficar no chute.
        self.risco_minimo_pct = float(getattr(bot, "risco_minimo_pct", 0) or RISCO_MINIMO_PCT)
        self.alvo_maximo_r = float(getattr(bot, "alvo_maximo_r", 0) or ALVO_MAXIMO_R)
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

    def _risco_minimo(self, barras: Sequence[Barra], preco: float) -> float:
        """
        Piso do stop: fora do ruído da própria barra, e bem acima do custo de ida e volta.

        É o mesmo princípio que já rege o trailing por estilo (core/perfil_saida.py) — a distância tem que
        ficar FORA do ruído do timeframe, senão o stop é acionado por nada. O backtest mostrou o preço de
        esquecer isso: stops de 0,05% do preço (uns 40 dólares no BTC) com alvos de 0,7% a 1,7%. No papel é
        risco:retorno de 15 para 1; na prática o stop morria em 6 segundos, e 16 dos 19 trades saíram no
        stop. Risco:retorno alto com stop dentro do ruído não é vantagem, é ilusão de conta.
        """
        rng = self.gatilho._range_medio(barras)
        custo = preco * (self.taxa_entrada + self.taxa_saida)
        return max(rng * RISCO_MINIMO_RANGES, preco * self.risco_minimo_pct, custo * 1.5)

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
        # o stop nunca fica dentro do ruído da barra, nem que para isso ele se afaste do nível
        risco_min = self._risco_minimo(barras, preco)
        piso_aplicado = False
        if abs(preco - sl) < risco_min:
            sl = preco - risco_min if direcao == "buy" else preco + risco_min
            piso_aplicado = True
        risco = abs(preco - sl)
        if risco <= 0:
            return {"sl": None, "tp": None, "rr": 0.0, "rr_liquido": 0.0, "rr_minimo": 0.0,
                    "fonte_tp": None, "fonte_sl": None}
        s = 1 if direcao == "buy" else -1
        teto = preco + s * risco * self.alvo_maximo_r
        alvo = contexto.alvo_na_direcao(preco, direcao)
        if alvo is not None:
            # para no nível contrário, com uma folga para dentro: quem espera o preço exato costuma não ser servido
            tp = alvo.preco - folga * 0.5 if direcao == "buy" else alvo.preco + folga * 0.5
            fonte_tp = alvo.fonte
            # nível longe demais vira alvo de daytrade: o scalp encurta e realiza no que cabe no seu tempo
            if (tp > teto) if direcao == "buy" else (tp < teto):
                tp, fonte_tp = teto, f"{self.alvo_maximo_r:g}R (nível {alvo.fonte} longe demais para scalp)"
        else:
            tp = preco + s * risco * 2.0
            fonte_tp = "2R (sem nível adiante)"
        # as duas pernas custam diferente: o alvo é servido por ordem limitada (maker dos dois lados), o
        # stop sai a mercado (maker na entrada, taker na saída). Cobrar taker na perna que dá certo
        # encarece justamente o cenário bom e reprova trade que na corretora pagaria menos.
        custo_ganho = preco * (self.taxa_entrada + TAXA_MAKER)
        custo_perda = preco * (self.taxa_entrada + TAXA_TAKER)
        rr = abs(tp - preco) / risco
        rr_liquido = max(abs(tp - preco) - custo_ganho, 0.0) / (risco + custo_perda)
        custo = custo_perda
        rr_min = float(getattr(self.bot, "rr_minimo", 0) or 0) or RR_MINIMO.get(self.perfil, 1.2)
        return {"sl": round(sl, 2), "tp": round(tp, 2), "rr": round(rr, 2),
                "rr_liquido": round(rr_liquido, 2), "rr_minimo": rr_min,
                "fonte_tp": fonte_tp,
                "fonte_sl": (f"piso de ruído ({risco_min:,.2f})" if piso_aplicado
                             else f"{nivel.fonte} - folga {folga:,.2f}"),
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
        idade = time.time() - contexto.calculado_em
        if idade > self.intervalo_contexto * IDADE_MAXIMA_CONTEXTO:
            return _hold(f"Contexto dos graus maiores está velho ({idade / 60:.0f} min): não dá para "
                         f"autorizar entrada com um viés que pode ter virado. {contexto.motivo[:120]}",
                         **detalhes_base)
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
        # com ordem limitada quem entra no nível é a ordem, não o preço de agora: o risco:retorno tem que ser
        # medido a partir de onde a posição realmente vai nascer, senão a conta sai torta em favor do trade
        entrada = nivel.preco if self.limitada else preco
        niveis = self._sl_tp(direcao, entrada, nivel, barras, contexto)
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
