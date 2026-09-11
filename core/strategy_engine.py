# core/strategy_engine.py
"""
Motor de decisão do bot.

Ordem (Elliott é a lei):
    1. Elliott multi-grau (cenários concorrentes, fase, invalidação, alvos) -> direção candidata
    2. Regras da fase x perfil (conservador/turbo): a fase permite operar? em que direção?
    3. Validadores (TPO, VWAP, Order Flow, Volume Profile, Order Block) votam a favor/contra
    4. Confluência: conservador exige todos os votantes alinhados (≥1 voto); turbo exige ≥1
    5. Filtros: sentimento contrário (extremos), zonas institucionais contra, eventos macro
    6. TP/SL: Elliott (invalidação/alvos) como fonte prioritária, senão Fibonacci/TPO/VWAP/OB,
       fallback de SL por ATR; exige risco:retorno mínimo
    7. Decisão auditável (todos os cenários, votos e níveis ficam no resultado)

Nada aqui envia ordem: o executor decide tamanho/entrada/saída com base neste resultado.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional, Sequence

from core.elliott_pro import AnaliseMultiGrau
from core.fase_onda_rules import (
    INDICADORES_VOTANTES, bloquear_zona_institucional, direcao_permitida, get_tolerancia_preco,
    get_tp_sl_prioritario, indicadores_para_fase,
)
from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.fibonacci_strategies import FibonacciStrategies
from core.order_block import OrderBlockDetector
from core.order_flow import OrderFlowAnalyzerPro
from core.tpo import TPOProfile
from core.utils_indicadores import atr as calc_atr
from core.volume_profile_pro import VolumeProfilePRO
from core.vwap import VWAPCalculator

logger = logging.getLogger(__name__)

JANELA_POR_PERFIL = {"scalping": 150, "daytrade": 200, "swing": 300}
RR_MINIMO = {"conservador": 1.2, "turbo": 1.0}
# piso do stop em fração do preço. O mesmo número que o backtest de 30 dias do motor de fluxo pediu: abaixo
# disso a taxa de ida e volta passa a valer uma fatia grande do risco e o stop fica dentro do ruído. Nos graus
# maiores ele praticamente nunca age, porque meio ATR de 15m ou de 4h já é maior que isso.
RISCO_MINIMO_PCT = 0.0012


def _hold(motivo: str, **extra) -> Dict:
    base = {"acao": "hold", "motivo": motivo, "fase_onda": extra.pop("fase_onda", None), "votos": [],
            "indicadores_ativos": [], "tp": None, "sl": None, "cenario": None, "probabilidade": None,
            "cenarios": [], "tamanho_fator": 1.0, "contra_tendencia": False}
    base.update(extra)
    return base


class StrategyEngine:
    def __init__(self, ohlcv: Sequence, bot, db=None, trades: Optional[List[Dict]] = None,
                 order_book: Optional[Dict] = None, servicos: Optional[Dict] = None):
        if not ohlcv or len(ohlcv) < 30:
            raise ValueError("StrategyEngine precisa de pelo menos 30 candles")
        self.ohlcv = [list(map(float, c[:6])) for c in ohlcv]
        self.bot = bot
        self.db = db
        self.trades = trades or []
        self.order_book = order_book or {"bids": [], "asks": []}
        self.servicos = servicos or {}
        self.perfil = (getattr(bot, "confluencia_tipo", "conservador") or "conservador").lower()
        self.estilo = self._estilo()
        self.preco_atual = float(self.servicos.get("preco_atual") or self.ohlcv[-1][4])
        self.atr = max(calc_atr(self.ohlcv, 14) or 0.0, self.preco_atual * 0.001)
        self.timeframe = getattr(bot, "timeframe", "15m")
        self.par = getattr(bot, "ativo", "BTCUSDT")
        self.exchange = (getattr(bot, "exchange", "bybit") or "bybit").split("-")[0]
        self.ohlcv_composto = self.servicos.get("ohlcv_composto") or self.ohlcv
        self.detalhes: Dict = {}

    def _estilo(self) -> str:
        e = (getattr(self.bot, "estilo_trade", "daytrade") or "daytrade").lower()
        return "scalping" if "scalp" in e else "swing" if "swing" in e else "daytrade"

    # -------------------------------------------------------------- Elliott
    def _fetch_ohlcv(self):
        fn = self.servicos.get("fetch_ohlcv")
        if fn:
            return fn
        from core.conexoes.conexao_bybit import BybitConnector
        con = self.servicos.get("connector") or BybitConnector("simulador")
        return lambda tf, n: con.obter_ohlcv(self.par, tf, n, somente_fechados=True)

    def _trava_mestre(self) -> Optional[Dict]:
        if "mestre" in self.servicos:
            return self.servicos.get("mestre")
        if self.db is None:
            return None
        try:
            from services.elliott_mestre_service import ElliottMestreService
            return ElliottMestreService(self.db, self.servicos.get("connector")).trava_ativa(self.par, self.preco_atual)
        except Exception as e:
            logger.warning("trava mestre indisponível: %s", e)
            return None

    def _leitura_trader(self) -> Optional[Dict]:
        """Leitura do TraderService (superciclo + contagens maduras). Só ao vivo: em backtest (db None) seria look-ahead."""
        if "trader" in self.servicos:
            t = self.servicos.get("trader")
            try:
                return t.leitura(self.par) if hasattr(t, "leitura") else t
            except Exception as e:
                logger.warning("leitura do trader indisponível: %s", e)
                return None
        if self.db is None:
            return None
        try:
            from services.trader_service import TraderService
            return TraderService(self.servicos.get("connector")).leitura(self.par)
        except Exception as e:
            logger.warning("leitura do trader indisponível: %s", e)
            return None

    def _plano_mercado(self) -> Optional[Dict]:
        """
        PLANO DE MERCADO do par (core/orquestrador/plano.py). Um plano por par: todos os bots do par leem o mesmo.
        Só ao vivo; em backtest (db None) seria look-ahead, então não é usado.
        """
        if "plano" in self.servicos:
            p = self.servicos.get("plano")
            try:
                return p.plano(self.par) if hasattr(p, "plano") else p
            except Exception as e:
                logger.warning("plano de mercado indisponível: %s", e)
                return None
        if self.db is None:
            return None
        try:
            from services.plano_service import PlanoService
            return PlanoService(self.servicos, db=self.db).plano(self.par)
        except Exception as e:
            logger.warning("plano de mercado indisponível: %s", e)
            return None

    def analisar_elliott(self) -> Dict:
        self._trava = self._trava_mestre()
        self._trader = self._leitura_trader()
        analise = AnaliseMultiGrau(self._fetch_ohlcv(), self.par, self.estilo, self.timeframe, self.perfil, trava=self._trava,
                                   trader=self._trader)
        res = analise.analisar(ohlcv_operacional=self.ohlcv)
        self._multigrau = analise
        return res

    # ---------------------------------------------------------- validadores
    def _janela(self) -> int:
        return JANELA_POR_PERFIL.get(self.estilo, 200)

    def verificar_vwap(self) -> Dict:
        try:
            return VWAPCalculator(self.ohlcv[-self._janela():]).sinal(self.preco_atual)
        except Exception as e:
            return {"acao": "hold", "motivo": f"VWAP erro: {e}", "forca": 0.0}

    def verificar_tpo(self) -> Dict:
        try:
            dados = self.ohlcv_composto[-self._janela():]
            bins = {"scalping": 24, "daytrade": 30, "swing": 40}[self.estilo]
            return TPOProfile(dados, bins=bins).sinal_estrategico(self.preco_atual)
        except Exception as e:
            return {"acao": "hold", "motivo": f"TPO erro: {e}", "forca": 0.0}

    def verificar_volume_profile(self) -> Dict:
        try:
            dados = self.ohlcv_composto[-self._janela():]
            return VolumeProfilePRO(dados, num_bins=40).price_signal(self.preco_atual)
        except Exception as e:
            return {"acao": "hold", "motivo": f"VP erro: {e}", "forca": 0.0}

    def verificar_orderflow(self) -> Dict:
        try:
            return OrderFlowAnalyzerPro(self.order_book, self.trades, self.ohlcv, timeframe=self.timeframe).analisar()
        except Exception as e:
            return {"acao": "hold", "motivo": f"OrderFlow erro: {e}", "forca": 0.0}

    def verificar_orderblock(self) -> Dict:
        try:
            self._obd = OrderBlockDetector(self.ohlcv[-self._janela():])
            return self._obd.sinal(self.preco_atual)
        except Exception as e:
            self._obd = None
            return {"acao": "hold", "motivo": f"OrderBlock erro: {e}", "forca": 0.0}

    def indicadores_habilitados(self) -> List[str]:
        b = self.bot
        hab = []
        if getattr(b, "usar_vwap", False): hab.append("VWAP")
        if getattr(b, "usar_fibonacci", False): hab.append("Fibonacci")
        if getattr(b, "usar_tpo", False): hab.append("TPO")
        if getattr(b, "usar_orderflow", False): hab.append("OrderFlow")
        if getattr(b, "usar_volume_profile", False): hab.append("VolumeProfile")
        if getattr(b, "usar_orderblock", False): hab.append("OrderBlock")
        return hab

    # -------------------------------------------------------------- filtros
    def _sentimento(self) -> Optional[Dict]:
        if not getattr(self.bot, "usar_sentimento", True):
            return None
        svc = self.servicos.get("sentimento")
        if svc is None:
            return None
        try:
            return svc.score(self.par)
        except Exception as e:
            logger.warning("sentimento indisponível: %s", e)
            return None

    def _evento_macro(self) -> bool:
        if not getattr(self.bot, "usar_api_macro", False):
            return False
        try:
            from core.macro_event_checker import evento_importante_agora
            return bool(evento_importante_agora())
        except Exception:
            return False

    def _zonas_institucionais(self, direcao: str, fase: str) -> List[Dict]:
        """Pontos institucionais CONTRA a direção, dentro do raio da fase (só se houver sessão de banco)."""
        if self.db is None or not bloquear_zona_institucional(fase):
            return []
        try:
            from services.ponto_institucional_service import PontoInstitucionalService
            raio = get_tolerancia_preco(fase) or 0.003
            return PontoInstitucionalService.pontos_contra_direcao(
                self.db, self.par, self.exchange, self.preco_atual, direcao, raio, relevancia_minima=1.5)
        except Exception as e:
            logger.warning("zonas institucionais indisponíveis: %s", e)
            return []

    # ---------------------------------------------------------------- TP/SL
    def calcular_tp_sl(self, direcao: str, fase: str, indicadores_ativos: List[str], cenario: Optional[Dict],
                       resultados: Dict) -> Dict:
        preco = self.preco_atual
        up = direcao == "buy"
        s = 1 if up else -1
        tps: List[tuple] = []   # (preco, fonte)
        sls: List[tuple] = []

        # Elliott: invalidação -> SL (com folga de 0,15 ATR); alvos -> TPs
        if cenario:
            inv = cenario.get("invalidacao")
            if inv is not None and ((up and inv < preco) or (not up and inv > preco)):
                sls.append((inv - s * 0.15 * self.atr, "elliott"))
            for a in cenario.get("alvos", []):
                if (up and a > preco) or (not up and a < preco):
                    tps.append((a, "elliott"))
        # Fibonacci
        if "Fibonacci" in indicadores_ativos or getattr(self.bot, "usar_fibonacci", False):
            try:
                fib = FibonacciStrategies(self.ohlcv, janela=self._janela()).para_fase(fase, direcao)
                if fib.get("tp"): tps.append((fib["tp"], "fibonacci"))
                if fib.get("sl") and not fib.get("sl_fallback"): sls.append((fib["sl"], "fibonacci"))
                resultados["Fibonacci"] = fib
            except Exception as e:
                resultados["Fibonacci"] = {"erro": str(e)}
        # TPO / Volume Profile: value area como alvo/proteção
        for nome in ("TPO", "VolumeProfile"):
            r = resultados.get(nome) or {}
            vah, val = r.get("VAH"), r.get("VAL")
            if vah and val:
                if up:
                    if vah > preco: tps.append((vah, nome.lower()))
                    if val < preco: sls.append((val, nome.lower()))
                else:
                    if val < preco: tps.append((val, nome.lower()))
                    if vah > preco: sls.append((vah, nome.lower()))
        # VWAP bandas
        r = resultados.get("VWAP") or {}
        bandas = r.get("bandas") or {}
        if bandas:
            alvo = bandas.get("+2σ") if up else bandas.get("-2σ")
            prot = bandas.get("-2σ") if up else bandas.get("+2σ")
            if alvo and ((up and alvo > preco) or (not up and alvo < preco)): tps.append((alvo, "vwap"))
            if prot and ((up and prot < preco) or (not up and prot > preco)): sls.append((prot, "vwap"))
        # Order blocks do gráfico (zona oposta = alvo; zona a favor = proteção)
        obd = getattr(self, "_obd", None)
        if obd:
            try:
                for b in obd.blocos_proximos(preco, "bearish" if up else "bullish", 0.05):
                    lo, hi = b["zona"]
                    tps.append((lo if up else hi, "orderblock"))
                for b in obd.blocos_proximos(preco, "bullish" if up else "bearish", 0.03):
                    lo, hi = b["zona"]
                    sls.append(((lo if up else hi) - s * 0.1 * self.atr, "orderblock"))
            except Exception:
                pass
        # Order blocks institucionais do banco
        if self.db is not None and "OrderBlock" in indicadores_ativos:
            try:
                from services.orderblock_institutional_service import OrderBlockInstitutionalService
                for b in OrderBlockInstitutionalService.consultar_blocos_ativos(self.db, self.par, "sell" if up else "buy"):
                    if (up and b.preco > preco) or (not up and b.preco < preco):
                        tps.append((float(b.preco), "orderblock_db"))
            except Exception:
                pass

        # ---- seleção
        fonte_prior = get_tp_sl_prioritario(fase) or "elliott"
        rr_min = float(getattr(self.bot, "rr_minimo", 0) or 0) or RR_MINIMO.get(self.perfil, 1.2)
        # SL: estrutural mais próximo (até 3 ATR); prioridade Elliott
        sl_validos = [(p, f) for p, f in sls if (up and p < preco) or (not up and p > preco)]
        sl_validos = [(p, f) for p, f in sl_validos if abs(preco - p) <= 3.0 * self.atr]
        sl, fonte_sl = None, None
        prior_sl = [x for x in sl_validos if x[1] == fonte_prior]
        if prior_sl:
            sl, fonte_sl = max(prior_sl, key=lambda x: -abs(preco - x[0]) if self.perfil == "turbo" else abs(preco - x[0]))
        elif sl_validos:
            if self.perfil == "conservador":
                sl, fonte_sl = min(sl_validos, key=lambda x: abs(preco - x[0]))  # mais apertado
            else:
                sl, fonte_sl = max(sl_validos, key=lambda x: abs(preco - x[0]))  # mais folgado
        # PISO DO STOP. Meio ATR sozinho não bastava no 1m: dá uns 38 dólares, e o scalp saiu com stop a 39 dólares
        # da entrada (0,05%) — acionado por ruído em 1m39s. O stop tem que ficar fora do ruído E bem acima do custo
        # de ida e volta, senão a taxa sozinha come boa parte do que ele arrisca.
        custo = preco * ((TAXA_MAKER if getattr(self.bot, "tipo_entrada", "mercado") == "limite" else TAXA_TAKER)
                         + TAXA_TAKER)
        piso = max(0.5 * self.atr, preco * RISCO_MINIMO_PCT, custo * 1.5)
        if sl is None or abs(preco - sl) < piso:
            sl, fonte_sl = preco - s * max(1.5 * self.atr, piso), "atr"
        risco = abs(preco - sl)

        # TP: candidatos além do preço com R:R >= mínimo; conservador pega o mais próximo, turbo o 2º mais distante
        tp_validos = sorted({(round(p, 2), f) for p, f in tps if (up and p > preco) or (not up and p < preco)},
                            key=lambda x: abs(x[0] - preco))
        tp_ok = [(p, f) for p, f in tp_validos if abs(p - preco) / risco >= rr_min]
        tp, fonte_tp = None, None
        if tp_ok:
            prior_tp = [x for x in tp_ok if x[1] == fonte_prior]
            lista = prior_tp or tp_ok
            if self.perfil == "conservador":
                tp, fonte_tp = lista[0]
            else:
                tp, fonte_tp = lista[min(1, len(lista) - 1)]
        if tp is None:
            # fallback: 2R
            tp, fonte_tp = preco + s * max(2.0, rr_min) * risco, "2R"
        rr = abs(tp - preco) / risco if risco else 0.0
        # preço para ordem limitada (post-only): pequeno recuo a favor da entrada, nunca a menos de 0,5 ATR do SL
        recuo = 0.25 * self.atr if self.estilo == "scalping" else 0.35 * self.atr
        preco_limite = preco - s * recuo
        vwap = (resultados.get("VWAP") or {}).get("vwap")
        if vwap and ((up and sl < vwap < preco) or (not up and preco < vwap < sl)) and abs(vwap - preco) < 1.0 * self.atr:
            preco_limite = vwap
        # o piso vale para onde a posição NASCE: com ordem limitada é o preço da ordem, não o de agora. Medido do
        # preço atual, a distância real até o stop saía menor que o próprio piso.
        if abs(preco_limite - sl) < piso:
            preco_limite = sl + s * piso
        return {"tp": round(tp, 2), "sl": round(sl, 2), "preco_limite": round(preco_limite, 2), "fonte_tp": fonte_tp, "fonte_sl": fonte_sl, "rr": round(rr, 2),
                "rr_minimo": rr_min, "candidatos_tp": [(round(p, 2), f) for p, f in tp_validos[:8]],
                "candidatos_sl": [(round(p, 2), f) for p, f in sl_validos[:8]]}

    # ---------------------------------------------------------------- decidir
    def decidir(self) -> Dict:
        t0 = time.time()
        preco = self.preco_atual
        if not getattr(self.bot, "usar_elliott", True):
            return _hold("Elliott desabilitado no bot: sem lei, sem trade")

        # 1. Elliott multi-grau (e o plano do par, que manda em todos os bots do par)
        elliott = self.analisar_elliott()
        self._plano = self._plano_mercado()
        alin = elliott["alinhamento"]
        op = elliott["graus"]["operacional"]
        fase = alin.get("fase", "indefinido")
        primario = op.get("primario") or {}
        cenarios = op.get("cenarios", [])
        base = {"fase_onda": fase, "cenario": primario.get("nome"), "probabilidade": primario.get("probabilidade"), "trava_mestre": getattr(self, "_trava", None),
                "trader": ({"direcao": self._trader.get("direcao"), "superciclo": (self._trader.get("superciclo") or {}).get("estado"),
                            "leitura": (self._trader.get("superciclo") or {}).get("leitura")} if getattr(self, "_trader", None) else None),
                "plano": ({k: (self._plano or {}).get(k) for k in
                           ("modo", "estado", "direcao_grau_maior", "risco_permitido", "teto_hedge",
                            "pode_comprar", "pode_vender", "motivo")} if self._plano else None),
                "cenarios": cenarios[:6], "alinhamento": alin, "elliott": {
                    "operacional": {k: op.get(k) for k in ("timeframe", "prob_bull", "prob_bear", "consenso", "n_cenarios")},
                    "contexto": {k: elliott["graus"]["contexto"].get(k) for k in ("timeframe", "fase", "prob_bull", "prob_bear")},
                    "macro": {k: elliott["graus"]["macro"].get(k) for k in ("timeframe", "fase", "prob_bull", "prob_bear")},
                }, "preco": preco, "tendencia_macro": alin.get("tendencia_macro")}

        # o plano do par vale para cada robô no alcance do seu grau (core/orquestrador/plano.py: escopo_do_plano).
        # Fica registrado na decisão para dar para auditar POR QUE um robô obedeceu ou não obedeceu o plano.
        from core.orquestrador.plano import escopo_do_plano
        esc = escopo_do_plano(self._plano, self.estilo)
        if base.get("plano") is not None:
            base["plano"]["escopo"] = esc["escopo"]

        direcao = alin.get("direcao", "hold")
        if direcao not in ("buy", "sell"):
            return _hold(f"Elliott sem direção operável: {alin.get('motivo')}", **base)

        # 1b. O PLANO DO PAR manda: o bot é tático, quem decide a direção do grau maior é o orquestrador.
        plano = self._plano
        if plano and not plano.get("erro"):
            if direcao == "buy" and not esc["pode_comprar"]:
                return _hold(f"Plano do par em modo '{plano.get('modo')}' ({plano.get('estado')}): compra bloqueada "
                             f"[{esc['escopo']}]. {plano.get('motivo', '')[:200]}", **base)
            if direcao == "sell" and not esc["pode_vender"]:
                return _hold(f"Plano do par em modo '{plano.get('modo')}' ({plano.get('estado')}): venda bloqueada "
                             f"[{esc['escopo']}]. {plano.get('motivo', '')[:200]}", **base)

        # 2. Regras da fase x perfil, regime e probabilidade calibrada
        regime = op.get("regime") or {}
        base["regime"] = regime
        if getattr(self.bot, "usar_filtro_regime", True) and regime and not regime.get("permite_entrada", True):
            return _hold(f"Regime {regime.get('regime')}: {regime.get('motivo')}", **base)
        prob_sucesso = primario.get("prob_sucesso")
        base["prob_sucesso"] = prob_sucesso
        # modo seletivo: só opera tipos de cenário (padrão|fase) com acerto histórico >= taxa mínima na calibração
        taxa_min = float(getattr(self.bot, "taxa_historica_minima", 0.0) or 0.0)
        if taxa_min > 0:
            from core.elliott_pro.multidegree import calibrador_padrao
            cal = calibrador_padrao(self.par)
            tabela = (cal.modelo or {}).get("tabela", {}) if cal and cal.ativo else {}
            t = tabela.get(f"{primario.get('padrao')}|{fase}")
            taxa_hist = t.get("taxa") if t and t.get("n", 0) >= 300 else None
            base["taxa_historica"] = taxa_hist
            if taxa_hist is None or taxa_hist < taxa_min:
                return _hold(f"Tipo de cenário {primario.get('padrao')}|{fase} com acerto histórico {taxa_hist} abaixo de {taxa_min:.0%}", **base)
        minimo_sucesso = float(getattr(self.bot, "prob_sucesso_minima", 0.45) or 0.45)
        if prob_sucesso is not None and prob_sucesso < minimo_sucesso:
            return _hold(f"Probabilidade calibrada do cenário ({prob_sucesso:.0%}) abaixo do mínimo ({minimo_sucesso:.0%})", **base)
        permitido = direcao_permitida(fase, self.perfil)
        if permitido is None:
            return _hold(f"Fase {fase} não permite entrada no perfil {self.perfil}", **base)
        if getattr(self.bot, "usar_tendencia_macro", True) and alin.get("bloqueado"):
            return _hold(f"Bloqueado pelo alinhamento multi-grau: {alin.get('motivo')}", **base)

        # 3. Validadores
        habilitados = self.indicadores_habilitados()
        ativos = indicadores_para_fase(fase, habilitados)
        base["indicadores_ativos"] = ativos
        funcoes: Dict[str, Callable[[], Dict]] = {
            "VWAP": self.verificar_vwap, "TPO": self.verificar_tpo, "OrderFlow": self.verificar_orderflow,
            "VolumeProfile": self.verificar_volume_profile, "OrderBlock": self.verificar_orderblock,
        }
        resultados: Dict[str, Dict] = {}
        votos, contra, total = [], [], 0
        for nome in ativos:
            fn = funcoes.get(nome)
            if not fn:
                continue
            r = fn()
            resultados[nome] = r
            ac = r.get("acao")
            if ac in ("buy", "sell"):
                total += 1
                (votos if ac == direcao else contra).append(nome)
        # TPO/VP sempre calculados para níveis, mesmo sem votar
        for nome in ("TPO", "VolumeProfile", "VWAP"):
            if nome not in resultados and nome in habilitados:
                resultados[nome] = funcoes[nome]()
        base["validadores"] = {k: {kk: vv for kk, vv in v.items() if kk in ("acao", "motivo", "forca", "POC", "VAL", "VAH", "vwap", "z", "delta", "imbalance")} for k, v in resultados.items()}
        base["votos"] = votos
        base["votos_contra"] = contra

        # 4. Confluência
        votantes = [n for n in ativos if n in INDICADORES_VOTANTES]
        if votantes:
            if self.perfil == "conservador":
                ok = total >= 1 and not contra and len(votos) == total
            else:
                ok = len(votos) >= 1
            if not ok:
                return _hold(f"Sem confluência [{self.perfil}]: a favor {votos} / contra {contra} (fase {fase})", **base)
        # sem votantes habilitados: Elliott + Fibonacci decidem sozinhos (turbo) ou exigem ≥ 60% de probabilidade (conservador)
        elif self.perfil == "conservador" and (op.get("prob_bull" if direcao == "buy" else "prob_bear", 0) < 0.6):
            return _hold(f"Sem validadores habilitados e cenários {direcao} abaixo de 60% (fase {fase})", **base)

        # 5. Filtros
        tamanho_fator = 1.0
        sent = self._sentimento()
        base["sentimento"] = sent
        if sent:
            if (direcao == "buy" and sent.get("bloqueia_compra")) or (direcao == "sell" and sent.get("bloqueia_venda")):
                if self.perfil == "conservador":
                    return _hold(f"Sentimento em {sent['zona']} ({sent['score']:+.2f}) bloqueia {direcao}", **base)
                tamanho_fator *= 0.5
        if self._evento_macro():
            return _hold("Evento macro de alta relevância nos próximos minutos", **base)
        zonas = self._zonas_institucionais(direcao, fase)
        base["zonas_institucionais"] = zonas
        if zonas:
            return _hold(f"Zona institucional contra a direção a menos de {get_tolerancia_preco(fase):.1%}: {zonas[:3]}", **base)
        if alin.get("contra_tendencia"):
            tamanho_fator *= 0.5
        # o trader (superciclo) reduz o tamanho em impulso maduro / contra o ciclo. O plano e o alinhamento vêm da
        # MESMA leitura de superciclo, então aplica-se o menor dos dois, nunca o produto (evita contar duas vezes).
        limite_grau_maior = float(alin.get("fator_tamanho") or 1.0)
        if plano and not plano.get("erro") and plano.get("risco_permitido") is not None:
            limite_grau_maior = min(limite_grau_maior, float(plano["risco_permitido"]))
        tamanho_fator *= limite_grau_maior
        # dimensiona pela probabilidade calibrada (Kelly fracionado, entre 0,5x e 1,25x)
        if prob_sucesso is not None:
            tamanho_fator *= max(0.5, min(1.25, 0.5 + (prob_sucesso - 0.4) * 2.5))

        # 6. TP/SL
        niveis = self.calcular_tp_sl(direcao, fase, ativos + (["Fibonacci"] if "Fibonacci" in habilitados else []), primario, resultados)
        base["niveis"] = niveis
        if niveis["rr"] < niveis["rr_minimo"]:
            return _hold(f"Risco:retorno {niveis['rr']} abaixo do mínimo {niveis['rr_minimo']}", **base)

        # 7. Decisão
        base.update({
            "acao": direcao, "tp": niveis["tp"], "sl": niveis["sl"], "preco_limite": niveis.get("preco_limite"), "tamanho_fator": tamanho_fator,
            "contra_tendencia": bool(alin.get("contra_tendencia")),
            "motivo": (f"Elliott {fase} [{primario.get('nome')} p={primario.get('probabilidade', 0):.0%}, "
                       f"bull {op.get('prob_bull', 0):.0%}/bear {op.get('prob_bear', 0):.0%}] | contexto {alin.get('vies_contexto')} "
                       f"| votos {votos or 'n/a'} [{self.perfil}] | TP {niveis['tp']} ({niveis['fonte_tp']}) SL {niveis['sl']} "
                       f"({niveis['fonte_sl']}) R:R {niveis['rr']}"
                       + (f" | sentimento {sent['zona']} {sent['score']:+.2f}" if sent else "")),
            "tempo_ms": int((time.time() - t0) * 1000),
        })
        return base

    def sinal_saida(self, direcao_posicao: str) -> Dict:
        """Usa a última análise multi-grau para dizer se a posição deve ser encerrada por estrutura."""
        mg = getattr(self, "_multigrau", None)
        if mg is None:
            self.analisar_elliott()
            mg = self._multigrau
        return mg.sinal_saida(direcao_posicao)
