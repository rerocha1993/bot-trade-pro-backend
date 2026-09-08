# core/bot_executor.py
"""
Loop de execução de UM bot.

Ciclo (a cada `delay_execucao` segundos):
    1. candles fechados + preço atual (Bybit) ; candles compostos (cesta TradingView) para TPO/VP
    2. manutenção institucional (pontos testados/rompidos, order blocks) em intervalos
    3. gestão da posição aberta: SL/TP (exchange ou simulado), trailing, saída estrutural (Elliott)
    4. em CANDLE NOVO fechado: decisão do StrategyEngine -> persiste DecisaoBot -> abre posição se permitido
    5. limites de risco diário (trades e perda) e reconciliação com a exchange

A posição é persistida em PosicoesBot e reconciliada com a exchange (testnet/real) no início.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, date
from types import SimpleNamespace
from typing import Dict, Optional

from core.conexoes.conexao_bybit import BybitConnector
from core.executor_real import OrderExecutor, TAXA_MAKER, TAXA_TAKER
from core.alavancagem import normalizar as normalizar_alavancagem, validar_stop
from core.strategy_engine import StrategyEngine
from core.utils_indicadores import normalizar_timeframe
from models.decisao_bot import DecisaoBot
from models.log_execucao import LogExecucaoBot
from models.posicao_bot import PosicaoBot
from services.telegram_alert_service import TelegramAlertService

logger = logging.getLogger(__name__)

MODOS = {"simulador": "simulador", "paper": "simulador", "testnet": "testnet", "real": "real"}


def _modo(bot) -> str:
    m = (getattr(bot, "modo_execucao", "simulador") or "simulador").lower()
    ex = (getattr(bot, "exchange", "") or "").lower()
    if m == "simulador" and "testnet" in ex:
        return "simulador"  # bots antigos: exchange 'bybit-testnet' + simulador = paper trading
    return MODOS.get(m, "simulador")


class BotExecutor:
    def __init__(self, bot, db, servicos: Optional[Dict] = None):
        if isinstance(bot, dict):
            bot = SimpleNamespace(**bot)
        self.bot = bot
        self.db = db
        self.servicos = servicos or {}
        self.modo = _modo(bot)
        self.par = getattr(bot, "ativo", "BTCUSDT").replace("/", "")
        self.timeframe = normalizar_timeframe(getattr(bot, "timeframe", "15m"))
        self.categoria = (getattr(bot, "categoria", "linear") or "linear")
        self.estrategia = (getattr(bot, "estrategia", "elliott") or "elliott")
        # cada robô opera na SUA subconta: em testnet/real nunca reutiliza um conector compartilhado, senão dois
        # robôs no mesmo par disputariam a mesma posição (a Bybit tem uma posição por símbolo por conta)
        self.subconta = (getattr(bot, "subconta", None) or "principal")
        cat = "inverse" if self.categoria == "inverse" else "linear"
        if self.modo == "simulador":
            self.con: BybitConnector = (self.servicos.get("connectors", {}).get(self.modo)
                                        if cat == "linear" else None) or BybitConnector(self.modo, cat)
        else:
            self.con = BybitConnector(self.modo, cat, subconta=self.subconta)
        if self.modo != "simulador" and self.categoria != "inverse":
            # dados públicos continuam no conector compartilhado (rate limiter único); só ordens usam as chaves
            self._con_publico = self.servicos.get("connectors", {}).get("simulador") or self.con
        else:
            self._con_publico = self.con
        self.inverse = None
        if self.estrategia == "inverse_range":
            from core.inverse_executor import InverseRangeExecutor
            self.inverse = InverseRangeExecutor(self)
        self.alavancagem = normalizar_alavancagem(getattr(bot, "alavancagem", 1) or 1)
        self.ordens = OrderExecutor(self.con)
        self.alertas: TelegramAlertService = self.servicos.get("telegram") or TelegramAlertService()
        self.market_data = self.servicos.get("market_data")
        self.sentimento = self.servicos.get("sentimento")
        self.delay = int(getattr(bot, "delay_execucao", None) or 10)
        self.posicao: Optional[PosicaoBot] = None
        self.ultimo_candle_ts: Optional[int] = None
        self._ultima_manutencao = 0.0
        self._ultimo_orderblock = 0.0
        self._rodando = threading.Event()
        self.ordem_pendente: Optional[Dict] = None   # ordem limitada aguardando execução
        self.ws = None                               # DataSourceWebsocketUniversal (scalp)
        self.estado: Dict = {"modo": self.modo, "par": self.par, "timeframe": self.timeframe, "ciclos": 0, "erros": 0,
                             "ultima_decisao": None, "ultimo_ciclo": None, "posicao": None, "pnl_dia": 0.0,
                             "trades_dia": 0, "dia": date.today().isoformat(), "inicio": datetime.utcnow().isoformat()}
        self._engine: Optional[StrategyEngine] = None

    # ------------------------------------------------------------ util
    def _attr(self, nome, default=None):
        v = getattr(self.bot, nome, None)
        return default if v is None else v

    def _log(self, **kw):
        try:
            self.db.add(LogExecucaoBot(bot_id=self._attr("id"), data_execucao=datetime.utcnow(), **kw))
            self.db.commit()
        except Exception as e:
            logger.error("falha ao gravar log: %s", e)
            self.db.rollback()

    def _novo_dia(self):
        hoje = date.today().isoformat()
        if self.estado["dia"] != hoje:
            self.estado.update(dia=hoje, pnl_dia=0.0, trades_dia=0)

    def _banca(self) -> float:
        banca = float(self._attr("banca", 0) or 0)
        if banca <= 0 and self.modo != "simulador":
            try:
                banca = self.con.obter_saldo("USDT")["total"]
            except Exception:
                banca = 0.0
        return banca

    # ---------------------------------------------------- inicialização
    def inicializar(self):
        logger.info("[%s] inicializando modo=%s par=%s tf=%s", self._attr("nome"), self.modo, self.par, self.timeframe)
        if self.modo in ("testnet", "real") and self.con.pode_enviar_ordens:
            try:
                try:
                    teto = (self.con.info_mercado(self.par) or {}).get("max_leverage")
                except Exception:
                    teto = None
                self.alavancagem = normalizar_alavancagem(self._attr("alavancagem", 1), teto)
                r = self.con.configurar_conta(self.par, self.alavancagem, self._attr("margin_mode", "cross"),
                                              self._attr("position_mode", "one-way"))
                logger.info("[%s] conta configurada: %s", self._attr("nome"), r)
            except Exception as e:
                logger.warning("[%s] não foi possível configurar conta: %s", self._attr("nome"), e)
        self._carregar_posicao()
        if self.inverse is not None:
            self.inverse.carregar()
            return
        self._reconciliar()

    def _carregar_posicao(self):
        self.posicao = self.db.query(PosicaoBot).filter_by(bot_id=self._attr("id"), status="aberta").order_by(PosicaoBot.id.desc()).first()

    def _reconciliar(self):
        """Compara posição do banco com a da exchange (testnet/real)."""
        if self.modo == "simulador" or not self.con.pode_enviar_ordens:
            return
        try:
            pos_ex = self.con.obter_posicao(self.par)
        except Exception as e:
            logger.warning("[%s] reconciliação falhou: %s", self._attr("nome"), e)
            return
        if self.posicao and not pos_ex:
            logger.warning("[%s] posição %s no banco mas não na exchange: fechando registro", self._attr("nome"), self.posicao.id)
            self._registrar_saida(self.posicao.preco_entrada, "Reconciliação: posição não existe na exchange", pnl_exchange=True)
        elif pos_ex and not self.posicao:
            logger.warning("[%s] posição na exchange sem registro no banco: adotando", self._attr("nome"))
            self.posicao = PosicaoBot(bot_id=self._attr("id"), par=self.par, modo_execucao=self.modo, direcao=pos_ex["side"],
                                      quantidade=pos_ex["quantidade"], preco_entrada=pos_ex["preco_entrada"], sl=pos_ex.get("sl"),
                                      tp=pos_ex.get("tp"), sl_inicial=pos_ex.get("sl"), status="aberta",
                                      motivo_entrada="Adotada da exchange na inicialização")
            self.db.add(self.posicao)
            self.db.commit()
        elif pos_ex and self.posicao:
            self.posicao.quantidade = pos_ex["quantidade"]
            if pos_ex.get("sl"):
                self.posicao.sl = pos_ex["sl"]
            self.db.commit()

    # ------------------------------------------------------- tamanho
    def calcular_tamanho_ordem(self, preco_entrada: float, sl: Optional[float], fator: float = 1.0) -> float:
        if preco_entrada is None or sl is None or preco_entrada == sl:
            return 0.0
        banca = self._banca()
        risco_pct = float(self._attr("risco_pct", 0.01) or 0.01)
        max_aloc = float(self._attr("max_alocacao_pct", 0.5) or 0.5)
        alav = max(int(getattr(self, "alavancagem", 1) or 1), 1)
        if banca > 0:
            risco = banca * risco_pct * fator
            qty = risco / abs(preco_entrada - sl)
            teto = banca * max_aloc * alav / preco_entrada
            qty = min(qty, teto)
        else:
            qty = float(self._attr("quantidade", 0) or 0) * fator
        mn, mx = self._attr("min_quantidade"), self._attr("max_quantidade")
        if mn:
            qty = max(qty, float(mn))
        if mx:
            qty = min(qty, float(mx))
        return self.con.arredondar_quantidade(self.par, qty)

    # -------------------------------------------------------- risco diário
    def _pode_operar(self) -> tuple:
        self._novo_dia()
        max_trades = int(self._attr("max_trades_dia", 10) or 10)
        if self.estado["trades_dia"] >= max_trades:
            return False, f"Limite diário de {max_trades} trades atingido"
        banca = self._banca()
        max_perda = float(self._attr("max_perda_dia_pct", 0.03) or 0.03) * banca if banca else None
        if max_perda and self.estado["pnl_dia"] <= -max_perda:
            return False, f"Limite de perda diária atingido ({self.estado['pnl_dia']:.2f})"
        return True, ""

    # ---------------------------------------------------------- entrada
    def abrir_posicao(self, decisao: Dict, preco: float):
        direcao, sl, tp = decisao["acao"], decisao.get("sl"), decisao.get("tp")
        if sl is None:
            self._log(acao="hold", tipo_operacao="info", preco=preco, motivo="Decisão sem SL: entrada recusada")
            return
        preco_ref = decisao.get("preco_limite") if self._attr("tipo_entrada", "mercado") == "limite" and decisao.get("preco_limite") else preco
        qty = self.calcular_tamanho_ordem(preco_ref, sl, decisao.get("tamanho_fator", 1.0))
        if qty <= 0:
            self._log(acao="hold", tipo_operacao="info", preco=preco, motivo=f"Quantidade calculada {qty} abaixo do mínimo")
            return
        # o stop precisa caber ANTES da liquidação: com 50x ou 100x a liquidação chega primeiro que o stop
        liq = validar_stop(preco_ref, sl, self.alavancagem, self._attr("margin_mode", "cross"),
                           banca=self._banca(), quantidade=qty)
        if not liq["ok"]:
            self._log(acao="hold", tipo_operacao="info", preco=preco, sl=sl, quantidade=qty,
                      motivo=f"Entrada recusada: {liq['motivo']}")
            logger.warning("[%s] entrada recusada por liquidação: %s", self._attr("nome"), liq["motivo"])
            return
        decisao["liquidacao"] = liq
        if self._attr("tipo_entrada", "mercado") == "limite" and decisao.get("preco_limite"):
            ped = self.ordens.abrir_limite(self.par, direcao, qty, decisao["preco_limite"], sl, tp, self._attr("position_mode", "one-way"))
            self.ordem_pendente = {**ped, "direcao": direcao, "sl": sl, "tp": tp, "decisao": decisao, "candle_ts": self.ultimo_candle_ts,
                                   "candles": 0}
            self._log(acao=direcao, tipo_operacao="info", preco=ped["preco"], sl=sl, tp=tp, quantidade=qty,
                      motivo=f"Ordem limitada post-only enviada a {ped['preco']} (espera até {self._attr('limite_candles_espera', 3)} candles)")
            logger.info("[%s] LIMITE %s %s qty=%s @ %s", self._attr("nome"), direcao, self.par, qty, ped["preco"])
            return
        exec_ = self.ordens.abrir(self.par, direcao, qty, sl, tp, self._attr("position_mode", "one-way"), preco_ref=preco)
        self._registrar_entrada(decisao, exec_, exec_["preco_exec"], sl, tp)

    def _registrar_entrada(self, decisao: Dict, exec_: Dict, preco_exec: float, sl, tp):
        direcao = decisao["acao"]
        self.posicao = PosicaoBot(
            bot_id=self._attr("id"), par=self.par, modo_execucao=self.modo, direcao=direcao, quantidade=exec_["quantidade"],
            preco_entrada=preco_exec, sl=sl, tp=tp, sl_inicial=sl, trailing_ativo=bool(self._attr("trailing_manual", False)),
            status="aberta", motivo_entrada=decisao.get("motivo"), fase_onda=decisao.get("fase_onda"),
            cenario=(decisao.get("cenario") or "")[:60], ordem_id=str(exec_.get("ordem_id") or "")[:64], taxas=exec_.get("taxa", 0.0))
        self.db.add(self.posicao)
        self.db.commit()
        self.estado["trades_dia"] += 1
        self._log(acao=direcao, tipo_operacao="entrada", direcao=direcao, preco=preco_exec, preco_entrada=preco_exec,
                  sl=sl, tp=tp, quantidade=exec_["quantidade"], motivo=decisao.get("motivo"))
        preco = preco_exec
        self.alertas.ordem(self._attr("nome"), self.par, direcao, preco_exec,
                           f"qty {exec_['quantidade']} SL {sl} TP {tp} | {decisao.get('fase_onda')} | {self.modo}")
        logger.info("[%s] ENTRADA %s %s qty=%s @ %s sl=%s tp=%s", self._attr("nome"), direcao, self.par, exec_["quantidade"], preco_exec, sl, tp)

    # ------------------------------------------------------------ saída
    def _registrar_saida(self, preco_saida: float, motivo: str, pnl_exchange: bool = False, taxa_saida: float = None):
        pos = self.posicao
        if not pos:
            return
        pnl = None
        if pnl_exchange and self.con.pode_enviar_ordens:
            try:
                desde = int(pos.aberto_em.timestamp() * 1000) - 60_000
                fechados = self.con.obter_pnl_fechado(self.par, desde)
                if fechados:
                    pnl = sum(f["pnl"] for f in fechados)
                    preco_saida = fechados[-1]["preco_saida"] or preco_saida
            except Exception as e:
                logger.warning("pnl da exchange indisponível: %s", e)
        if pnl is None:
            s = 1 if pos.direcao == "buy" else -1
            taxas = (pos.taxas or 0.0) + (taxa_saida if taxa_saida is not None else preco_saida * pos.quantidade * TAXA_TAKER)
            pnl = (preco_saida - pos.preco_entrada) * pos.quantidade * s - taxas
            pos.taxas = taxas
        pos.status = "fechada"
        pos.preco_saida = preco_saida
        pos.pnl = round(pnl, 4)
        pos.motivo_saida = motivo[:255]
        pos.fechado_em = datetime.utcnow()
        self.db.commit()
        self.estado["pnl_dia"] += pos.pnl
        self._log(acao="sell" if pos.direcao == "buy" else "buy", tipo_operacao="saida", direcao=pos.direcao, preco=preco_saida,
                  preco_entrada=pos.preco_entrada, preco_saida=preco_saida, quantidade=pos.quantidade, resultado=pos.pnl, motivo=motivo)
        self.alertas.ordem(self._attr("nome"), self.par, f"saída {pos.direcao}", preco_saida, f"P&L {pos.pnl:+.2f} USDT | {motivo}")
        logger.info("[%s] SAÍDA %s @ %s pnl=%.2f (%s)", self._attr("nome"), pos.direcao, preco_saida, pos.pnl, motivo)
        self.posicao = None

    def fechar_posicao(self, motivo: str, preco: float):
        if not self.posicao:
            return
        exec_ = self.ordens.fechar(self.par, self.posicao.direcao, self.posicao.quantidade, self._attr("position_mode", "one-way"), preco_ref=preco)
        if exec_.get("ja_fechada"):
            self._registrar_saida(preco, motivo + " (já fechada na exchange)", pnl_exchange=True)
            return
        self._registrar_saida(exec_["preco_exec"] or preco, motivo, pnl_exchange=not exec_["simulado"], taxa_saida=exec_.get("taxa"))

    # ------------------------------------------------- ordem pendente
    def gerir_ordem_pendente(self, preco: float, ultimo_candle: list, candle_novo: bool):
        ped = self.ordem_pendente
        if not ped:
            return
        if candle_novo:
            ped["candles"] += 1
        if self.ordens.simulado:
            lo, hi = float(ultimo_candle[3]), float(ultimo_candle[2])
            tocou = (min(lo, preco) <= ped["preco"]) if ped["direcao"] == "buy" else (max(hi, preco) >= ped["preco"])
            sit = {"status": "executada", "preco_exec": ped["preco"], "quantidade": ped["quantidade"],
                   "taxa": ped["preco"] * ped["quantidade"] * TAXA_MAKER} if tocou else {"status": "aberta"}
        else:
            try:
                sit = self.ordens.situacao_ordem(self.par, ped["ordem_id"])
            except Exception as e:
                logger.warning("situação da ordem falhou: %s", e)
                return
        if sit["status"] == "executada":
            exec_ = {"ordem_id": ped["ordem_id"], "preco_exec": sit["preco_exec"], "quantidade": sit["quantidade"],
                     "simulado": self.ordens.simulado, "taxa": sit.get("taxa", 0.0)}
            self.ordem_pendente = None
            self._registrar_entrada(ped["decisao"], exec_, sit["preco_exec"], ped["sl"], ped["tp"])
        elif sit["status"] == "cancelada":
            self.ordem_pendente = None
            self._log(acao="hold", tipo_operacao="info", preco=preco, motivo="Ordem limitada cancelada na exchange")
        elif ped["candles"] >= int(self._attr("limite_candles_espera", 3) or 3):
            self.ordens.cancelar_ordem(self.par, ped["ordem_id"])
            self.ordem_pendente = None
            self._log(acao="hold", tipo_operacao="info", preco=preco, motivo=f"Ordem limitada a {ped['preco']} expirou sem execução")

    # ---------------------------------------------------- gestão posição
    def aplicar_trailing_stop(self, preco: float):
        pos = self.posicao
        if not pos or not (self._attr("usar_trailing_stop", False) or pos.trailing_ativo or self._attr("trailing_manual", False)):
            return
        ativador = float(self._attr("ativador_trailing", 0.005) or 0.005)
        dist = float(self._attr("distancia_trailing", 0.003) or 0.003)
        if not pos.trailing_ativo:
            if pos.direcao == "buy" and preco >= pos.preco_entrada * (1 + ativador):
                pos.trailing_ativo = True
            elif pos.direcao == "sell" and preco <= pos.preco_entrada * (1 - ativador):
                pos.trailing_ativo = True
        if not pos.trailing_ativo:
            return
        novo = None
        if pos.direcao == "buy":
            cand = preco * (1 - dist)
            if pos.sl is None or cand > pos.sl:
                novo = cand
        else:
            cand = preco * (1 + dist)
            if pos.sl is None or cand < pos.sl:
                novo = cand
        if novo is not None and abs(novo - (pos.sl or 0)) >= preco * 0.0005:
            novo = self.con.arredondar_preco(self.par, novo)
            if self.ordens.atualizar_stop(self.par, novo, pos.tp, self._attr("position_mode", "one-way"), pos.direcao):
                pos.sl = novo
                self.db.commit()
                self._log(acao="ajuste_sl", tipo_operacao="info", preco=preco, sl=novo, motivo="Trailing stop")

    def gerir_posicao(self, preco: float, ultimo_candle: list, candle_novo: bool):
        pos = self.posicao
        if not pos:
            return
        self.aplicar_trailing_stop(preco)
        # 1) exchange já fechou por SL/TP?
        if self.modo in ("testnet", "real") and self.con.pode_enviar_ordens:
            try:
                if self.con.obter_posicao(self.par) is None:
                    self._registrar_saida(preco, "SL/TP executado pela exchange", pnl_exchange=True)
                    return
            except Exception as e:
                logger.warning("consulta de posição falhou: %s", e)
        else:
            # simulador: usa high/low do último candle fechado + preço atual
            hi, lo = float(ultimo_candle[2]), float(ultimo_candle[3])
            if pos.direcao == "buy":
                if pos.sl and min(lo, preco) <= pos.sl:
                    self._registrar_saida(pos.sl, "Stop loss (simulado)"); return
                if pos.tp and max(hi, preco) >= pos.tp:
                    self._registrar_saida(pos.tp, "Take profit (simulado)"); return
            else:
                if pos.sl and max(hi, preco) >= pos.sl:
                    self._registrar_saida(pos.sl, "Stop loss (simulado)"); return
                if pos.tp and min(lo, preco) <= pos.tp:
                    self._registrar_saida(pos.tp, "Take profit (simulado)"); return
        # 2) saída estrutural por Elliott (só em candle novo, para não reagir a ruído)
        if candle_novo and self._engine is not None:
            try:
                s = self._engine.sinal_saida(pos.direcao)
                if s.get("sair"):
                    self.fechar_posicao(f"Saída estrutural: {s.get('motivo')}", preco)
            except Exception as e:
                logger.warning("sinal de saída falhou: %s", e)

    # ------------------------------------------------------- manutenção
    def manutencao(self, preco: float, fechamento: float):
        agora = time.time()
        if agora - self._ultima_manutencao >= 60:
            self._ultima_manutencao = agora
            try:
                from services.ponto_institucional_service import PontoInstitucionalService
                PontoInstitucionalService.atualizar_pontos_testados_ou_rompidos(self.db, preco, self.par, "bybit", preco_fechamento=fechamento)
            except Exception as e:
                logger.warning("manutenção de pontos falhou: %s", e)
                self.db.rollback()
        if self._attr("usar_orderblock", False) and agora - self._ultimo_orderblock >= 300:
            self._ultimo_orderblock = agora
            try:
                from services.orderblock_institutional_service import OrderBlockInstitutionalService
                svc = self.servicos.get("orderblocks") or OrderBlockInstitutionalService(self.market_data)
                svc.atualizar_blocos_rompidos(self.db, self.par, preco)
                svc.atualizar_blocos(self.db, self.par)
            except Exception as e:
                logger.warning("manutenção de order blocks falhou: %s", e)
                self.db.rollback()

    # ---------------------------------------------------------- decisão
    def _persistir_decisao(self, d: Dict, candle_ts: int, preco: float):
        try:
            sent = d.get("sentimento") or {}
            detalhes = {k: d.get(k) for k in ("cenarios", "alinhamento", "elliott", "validadores", "niveis", "zonas_institucionais", "votos_contra")}
            self.db.add(DecisaoBot(
                bot_id=self._attr("id"), par=self.par, timeframe=self.timeframe, candle_ts=candle_ts, preco=preco, acao=d["acao"],
                fase_onda=d.get("fase_onda"), cenario=(d.get("cenario") or "")[:60], probabilidade=d.get("probabilidade"),
                tendencia_macro=d.get("tendencia_macro"), votos=",".join(d.get("votos") or [])[:255], tp=d.get("tp"), sl=d.get("sl"),
                sentimento=sent.get("score") if sent else None, motivo=d.get("motivo"),
                detalhes=json.dumps(detalhes, default=str, ensure_ascii=False)[:60000]))
            self.db.commit()
        except Exception as e:
            logger.error("falha ao persistir decisão: %s", e)
            self.db.rollback()

    def ciclo(self):
        ohlcv = self._con_publico.obter_ohlcv(self.par, self.timeframe, 300, somente_fechados=True)
        if len(ohlcv) < 60:
            raise RuntimeError("candles insuficientes")
        preco = self._con_publico.obter_preco_atual(self.par)
        ultimo = ohlcv[-1]
        candle_novo = self.ultimo_candle_ts != int(ultimo[0])
        if self.inverse is not None:
            # modo inverse: escada de range; nada do fluxo de Elliott operacional
            self.inverse.ciclo(ohlcv, preco, candle_novo)
            self.ultimo_candle_ts = int(ultimo[0])
            self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=datetime.utcnow().isoformat(), preco=preco,
                               posicao=self.inverse.posicao.as_dict() if self.inverse.posicao else None, inverse=self.inverse.status())
            return
        self.manutencao(preco, float(ultimo[4]))

        # ordem limitada pendente e gestão da posição (todo ciclo)
        self.gerir_ordem_pendente(preco, ultimo, candle_novo)
        if self.posicao and self._engine is None:
            self._engine = self._montar_engine(ohlcv, preco)
        self.gerir_posicao(preco, ultimo, candle_novo)

        if candle_novo:
            self.ultimo_candle_ts = int(ultimo[0])
            self._engine = self._montar_engine(ohlcv, preco)
            decisao = self._engine.decidir()
            self.estado["ultima_decisao"] = {k: decisao.get(k) for k in ("acao", "motivo", "fase_onda", "cenario", "probabilidade", "tp", "sl", "votos")}
            self._persistir_decisao(decisao, int(ultimo[0]), preco)
            if decisao["acao"] in ("buy", "sell") and self.ordem_pendente:
                if self.ordem_pendente["direcao"] != decisao["acao"]:
                    self.ordens.cancelar_ordem(self.par, self.ordem_pendente["ordem_id"])
                    self.ordem_pendente = None
                    self._log(acao="hold", tipo_operacao="info", preco=preco, motivo="Ordem limitada cancelada: sinal mudou de direção")
                else:
                    logger.info("[%s] ordem limitada já pendente", self._attr("nome"))
                    decisao = dict(decisao, acao="hold")
            if decisao["acao"] in ("buy", "sell"):
                if self.posicao:
                    if self.posicao.direcao != decisao["acao"] and (self._attr("position_mode", "one-way") or "one-way") == "one-way":
                        self.fechar_posicao(f"Sinal contrário: {decisao['motivo'][:120]}", preco)
                        self.abrir_posicao(decisao, preco)
                    else:
                        logger.info("[%s] sinal %s ignorado: posição aberta", self._attr("nome"), decisao["acao"])
                else:
                    ok, motivo = self._pode_operar()
                    if ok:
                        self.abrir_posicao(decisao, preco)
                    else:
                        self._log(acao="hold", tipo_operacao="info", preco=preco, motivo=motivo)
        self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=datetime.utcnow().isoformat(), preco=preco,
                           posicao=self.posicao.as_dict() if self.posicao else None)

    def _iniciar_websocket(self):
        """Stream público de trades/livro da Bybit (linear) para scalp: menos chamadas REST e delta em tempo real."""
        if self.ws is not None or not self._attr("usar_websocket", False):
            return
        try:
            from core.datasource_ws_universal import DataSourceWebsocketUniversal
            self.ws = DataSourceWebsocketUniversal(exchange="bybit" + ("-testnet" if self.modo == "testnet" else ""), symbol_spot=self.par)
            self.ws.start()
            logger.info("[%s] websocket iniciado", self._attr("nome"))
        except Exception as e:
            logger.warning("websocket indisponível, usando REST: %s", e)
            self.ws = None

    def _montar_engine(self, ohlcv, preco) -> StrategyEngine:
        trades, book, comp = [], None, None
        if self._attr("usar_orderflow", False):
            self._iniciar_websocket()
            try:
                if self.ws is not None and self.ws.get_trades():
                    trades = self.ws.get_trades()
                    book = self.ws.get_order_book() or self.con.obter_order_book(self.par, 50)
                else:
                    trades = self._con_publico.obter_trades(self.par, 500)
                    book = self._con_publico.obter_order_book(self.par, 50)
            except Exception as e:
                logger.warning("order flow indisponível: %s", e)
        if self.market_data is not None and (self._attr("usar_tpo", False) or self._attr("usar_volume_profile", False)):
            try:
                comp = self.market_data.ohlcv_composto(self.par, self.timeframe, 300)
            except Exception as e:
                logger.warning("candles compostos indisponíveis (usando Bybit): %s", e)
        servicos = {"fetch_ohlcv": lambda tf, n: self._con_publico.obter_ohlcv(self.par, tf, n, somente_fechados=True),
                    "sentimento": self.sentimento, "ohlcv_composto": comp, "preco_atual": preco, "connector": self.con}
        for nome in ("trader", "plano"):
            if self.servicos.get(nome) is not None:
                servicos[nome] = self.servicos[nome]
        return StrategyEngine(ohlcv, self.bot, db=self.db, trades=trades, order_book=book, servicos=servicos)

    # ------------------------------------------------------------- loop
    def executar(self):
        self._rodando.set()
        try:
            self.inicializar()
        except Exception as e:
            logger.error("[%s] falha na inicialização: %s", self._attr("nome"), e)
        while self._rodando.is_set() and getattr(self.bot, "ativo_bot", True):
            t0 = time.time()
            try:
                self.ciclo()
            except Exception as e:
                self.estado["erros"] += 1
                logger.exception("[%s] erro no ciclo: %s", self._attr("nome"), e)
                try:
                    self.db.rollback()
                except Exception:
                    pass
                self._log(acao="erro", tipo_operacao="info", erro=str(e)[:500], motivo="erro no ciclo")
                if self.estado["erros"] % 10 == 1:
                    self.alertas.erro(self._attr("nome"), e)
                time.sleep(5)
            gasto = time.time() - t0
            time.sleep(max(1.0, self.delay - gasto))
        logger.info("[%s] loop encerrado", self._attr("nome"))

    def parar(self):
        self._rodando.clear()
        self.bot.ativo_bot = False
        if self.ws is not None:
            try:
                self.ws.stop()
            except Exception:
                pass

    def status(self) -> Dict:
        s = dict(self.estado)
        s["rodando"] = self._rodando.is_set()
        s["bot_id"] = self._attr("id")
        s["nome"] = self._attr("nome")
        s["ordem_pendente"] = {k: v for k, v in (self.ordem_pendente or {}).items() if k != "decisao"} or None
        return s
