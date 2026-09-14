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
from datetime import datetime, date, timezone
from types import SimpleNamespace
from typing import Dict, Optional

from core.conexoes.conexao_bybit import BybitConnector
from core.executor_real import OrderExecutor, TAXA_MAKER, TAXA_TAKER
from core.alavancagem import normalizar as normalizar_alavancagem, validar_stop
from core.perfil_saida import perfil as perfil_saida
from core.saida_escalonada import (
    avanco as avanco_ate_alvo, escrever_feitas, ler_feitas, ler_plano, montar_fatias, pendentes,
)
from core.motor_fluxo import MotorFluxo
from core.strategy_engine import StrategyEngine
from core.utils_indicadores import normalizar_timeframe, timeframe_ms
from api.database import SessionLocal
from models.decisao_bot import DecisaoBot
from models.log_execucao import LogExecucaoBot
from models.posicao_bot import PosicaoBot
from services.telegram_alert_service import TelegramAlertService

logger = logging.getLogger(__name__)


def _json_puro(x):
    """
    Tipos do numpy não serializam na API. O /status/ junta o estado de TODOS os robôs: um numpy.bool_ na leitura
    do range do robô 10 derrubava a resposta inteira com 500, e a bolinha de saúde do painel parava para todos.
    """
    if isinstance(x, dict):
        return {k: _json_puro(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_puro(v) for v in x]
    if type(x).__module__ == "numpy" and hasattr(x, "item"):
        return x.item()
    return x


def _agora_utc() -> datetime:
    """UTC sem fuso, como o banco guarda (o mesmo valor do antigo datetime.utcnow(), sem o aviso)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ms_utc(momento: datetime) -> int:
    """Epoch em ms de um datetime do banco. Os do banco são UTC SEM fuso (_agora_utc); o .timestamp() do
    Python leria como hora LOCAL e erraria pelo fuso (3 h aqui), jogando a consulta para o futuro."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return int(momento.timestamp() * 1000)


MODOS = {"simulador": "simulador", "paper": "simulador", "demo": "demo", "testnet": "testnet", "real": "real"}


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
        # identidade em texto puro: o painel pergunta o status pela thread da API, e ler o objeto ORM de lá
        # dispara um SELECT na sessão que a thread do robô está usando ("concurrent operations are not permitted")
        self.bot_id = getattr(bot, "id", None)
        self.nome = getattr(bot, "nome", "") or ""
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
        if self.modo not in ("simulador",) and self.categoria != "inverse":
            # dados públicos continuam no conector compartilhado (rate limiter único); só ordens usam as chaves
            self._con_publico = self.servicos.get("connectors", {}).get("simulador") or self.con
        else:
            self._con_publico = self.con
        self.inverse = None
        if self.estrategia == "inverse_range":
            from core.inverse_executor import InverseRangeExecutor
            self.inverse = InverseRangeExecutor(self)
        # votação dos indicadores + entrada em 5 fatias (o robô que saiu do laboratório, core/estrategia_votacao.py)
        self.fatias = None
        if self.estrategia == "votacao_fatias":
            from core.fatias_executor import FatiasExecutor
            self.fatias = FatiasExecutor(self)
        # jogo do range do Tradeiros: compra no VAL, vende no VAH, com o contexto de presos (core/range_executor.py)
        self.range = None
        if self.estrategia == "range_tradeiros":
            from core.range_executor import RangeExecutor
            self.range = RangeExecutor(self)
        # portal Tradeiros na demo: Shaka ou Maroja, conta de trades (linear) ou de hedge (inverse)
        self.tradeiros = None
        if str(self.estrategia).startswith("tradeiros_"):
            from core.tradeiros_executor import criar_executor_tradeiros
            self.tradeiros = criar_executor_tradeiros(self)
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
        # INTERVENÇÃO MANUAL do painel: a thread da API não pode tocar no ORM desta sessão, então ela só deixa o
        # pedido aqui e acorda o robô; quem executa (e grava) é sempre a thread do robô.
        self._acordar = threading.Event()
        self._pedidos: list = []
        self._trava_pedidos = threading.Lock()
        self.intervencoes: Dict[str, Dict] = {}
        self.ordem_pendente: Optional[Dict] = None   # ordem limitada aguardando execução
        self.ws = None                               # DataSourceWebsocketUniversal (scalp)
        # motor de fluxo: o scalp decide por barra de volume, nao por candle de 1m (core/motor_fluxo.py)
        self.motor: Optional[MotorFluxo] = None
        self._seq_trades = 0                         # cursor dos negocios ja consumidos do websocket
        self._ohlcv_cache: Optional[list] = None
        self._ohlcv_cache_ts = 0.0
        self._ultimo_hold_persistido = 0.0
        self.estado: Dict = {"modo": self.modo, "par": self.par, "timeframe": self.timeframe, "ciclos": 0, "erros": 0,
                             "ultima_decisao": None, "ultimo_ciclo": None, "posicao": None, "pnl_dia": 0.0,
                             "trades_dia": 0, "dia": date.today().isoformat(), "inicio": _agora_utc().isoformat()}
        self._engine: Optional[StrategyEngine] = None

    # ------------------------------------------------------------ util
    def _attr(self, nome, default=None):
        v = getattr(self.bot, nome, None)
        return default if v is None else v

    def _log(self, **kw):
        """
        Grava o log em UMA SESSÃO PRÓPRIA, separada da sessão do robô.

        Antes o log entrava na mesma transação, e o rollback de um log que não coubesse levava junto o que o robô
        acabara de fazer. Foi assim que uma realização parcial saiu três vezes na corretora: a ordem foi enviada,
        o log de 'saida_parcial' não coube na coluna, o rollback apagou o registro da fatia realizada, e o ciclo
        seguinte achou que ela ainda estava pendente. O que o robô mudou é gravado ANTES; o log vem depois e, se
        falhar, falha sozinho.
        """
        try:
            self.db.commit()
        except Exception as e:
            logger.error("falha ao gravar o estado do robô: %s", e)
            self.db.rollback()
        sessao = SessionLocal()
        try:
            sessao.add(LogExecucaoBot(bot_id=self._attr("id"), data_execucao=_agora_utc(), **kw))
            sessao.commit()
        except Exception as e:
            logger.error("falha ao gravar log: %s", e)
            sessao.rollback()
        finally:
            sessao.close()

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
    def _manda_ordem(self) -> bool:
        """Demo, testnet e real mandam ordem de verdade para a corretora; só o simulador não."""
        return self.modo != "simulador" and bool(self.con.pode_enviar_ordens)

    def inicializar(self):
        logger.info("[%s] inicializando modo=%s par=%s tf=%s", self._attr("nome"), self.modo, self.par, self.timeframe)
        if self._manda_ordem():
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
        if getattr(self, "tradeiros", None) is not None:
            # a escada no livro é deste robô e está no estado: não é "entrada esquecida"
            if self.categoria != "inverse":
                self._reconciliar()
            self.tradeiros.carregar()
            return
        if self.inverse is not None:
            self.inverse.carregar()
            return
        self._reconciliar()
        if self.fatias is not None:
            # as fatias pendentes são ordens de entrada DESTE robô, guardadas no estado: não são esquecidas
            self.fatias.carregar()
            return
        if self.range is not None:
            # a escada no livro é deste robô e está guardada no estado: não é "entrada esquecida"
            self.range.carregar()
            return
        self._cancelar_entradas_esquecidas()

    def _cancelar_entradas_esquecidas(self):
        """
        Ordem de ENTRADA que ficou no livro de um processo anterior não tem mais ninguém cuidando: a ordem
        pendente vive na memória do robô, e um reinício a apaga. Aconteceu de verdade: uma compra limitada das
        03:35 executou 11 h depois, às 15:07, sem registro no banco — e o stop anexado, calculado para o preço da
        madrugada, disparou 4 s depois (−50,26). Na subida, o que é entrada (não reduce-only, não condicional)
        é cancelado. O SL/TP de uma posição aberta não é tocado.
        """
        if not self._manda_ordem():
            return
        try:
            n = self.con.cancelar_entradas_abertas(self.par)
        except Exception as e:
            logger.warning("[%s] não consegui conferir ordens esquecidas: %s", self._attr("nome"), e)
            return
        if n:
            self._log(acao="hold", tipo_operacao="info", preco=None,
                      motivo=f"{n} ordem(ns) de entrada esquecida(s) de um processo anterior cancelada(s) na subida")

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
            quantidade_inicial=exec_["quantidade"], saidas_feitas=None, pnl_parcial=0.0,
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
        """
        Fecha o registro. O P&L gravado é o da operação INTEIRA: parciais já realizadas + o resto + todas as taxas.

        Pela corretora (pnl_exchange): soma o P&L fechado desde a abertura — as parciais estão lá, líquidas.
        Pela conta local: pnl_parcial (já líquido da taxa de cada fatia) + o resto − (taxa de entrada + taxa final).
        Antes a conta local usava só o resto e esquecia as parciais, e a da corretora pegava o preço de saída do
        registro MAIS ANTIGO (a Bybit devolve do mais novo para o mais velho).
        """
        pos = self.posicao
        if not pos:
            return
        parcial = float(pos.pnl_parcial or 0)
        pnl = None
        if pnl_exchange and self.con.pode_enviar_ordens:
            try:
                # 5 s de folga para relógio; uma janela maior pegaria o fechamento da operação anterior
                desde = _ms_utc(pos.aberto_em) - 5_000
                fechados = [f for f in (self.con.obter_pnl_fechado(self.par, desde) or [])
                            if not f.get("timestamp") or f["timestamp"] >= desde]
                if fechados:
                    pnl = sum(f["pnl"] for f in fechados)
                    ultimo = max(fechados, key=lambda f: f.get("timestamp") or 0)
                    preco_saida = ultimo["preco_saida"] or preco_saida
            except Exception as e:
                logger.warning("pnl da exchange indisponível: %s", e)
        if pnl is None:
            s = 1 if pos.direcao == "buy" else -1
            taxas = (pos.taxas or 0.0) + (taxa_saida if taxa_saida is not None else preco_saida * pos.quantidade * TAXA_TAKER)
            pnl = parcial + (preco_saida - pos.preco_entrada) * pos.quantidade * s - taxas
            pos.taxas = taxas
        pos.status = "fechada"
        pos.preco_saida = preco_saida
        pos.pnl = round(pnl, 4)
        pos.motivo_saida = motivo[:255]
        pos.fechado_em = _agora_utc()
        self.db.commit()
        # as parciais já entraram no resultado do dia quando saíram: aqui entra só o que faltava
        self.estado["pnl_dia"] += pos.pnl - parcial
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
                # NÃO pode sair daqui: antes, uma consulta que falhava pulava a checagem de validade logo
                # abaixo, e a ordem ficava pendente para sempre. Como um sinal novo é ignorado enquanto há
                # ordem pendente, o robô parava de operar CALADO. Aconteceu de verdade: uma ordem de 14:06
                # seguia "pendente" sete horas depois, com 311 candles de espera num limite de 2, enquanto
                # 28 sinais de compra eram descartados sem deixar registro. Ordem que não dá para conferir
                # tem que envelhecer e morrer como qualquer outra.
                logger.warning("situação da ordem falhou (%s): a ordem segue envelhecendo", e)
                sit = {"status": "desconhecida"}
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
            if self._adotar_se_executou(ped, preco):
                return
            extra = " (sem conseguir confirmar a situação na corretora)" if sit["status"] == "desconhecida" else ""
            self._log(acao="hold", tipo_operacao="info", preco=preco,
                      motivo=f"Ordem limitada a {ped['preco']} expirou sem execução{extra}")

    def _adotar_se_executou(self, ped: Dict, preco: float) -> bool:
        """
        Depois de cancelar por tempo, confere a POSIÇÃO na corretora. A ordem pode ter executado sem o robô ver
        (consulta que falhou, ou execução entre a última consulta e o cancelamento). Foi o que aconteceu às 14:06
        de 09/09: a compra executou em 29 s, o robô não conseguia consultar a ordem, deu por vencida — e a
        posição ficou na corretora sem gestão até o stop anexado fechar (−96,41), fora do banco.
        """
        if self.ordens.simulado or self.posicao is not None:
            return False
        try:
            pos_ex = self.con.obter_posicao(self.par)
        except Exception as e:
            logger.warning("[%s] conferência de posição após vencer a ordem falhou: %s", self._attr("nome"), e)
            return False
        if not pos_ex or pos_ex["side"] != ped["direcao"]:
            return False
        q, p = float(pos_ex["quantidade"]), float(pos_ex["preco_entrada"] or ped["preco"])
        exec_ = {"ordem_id": ped["ordem_id"], "preco_exec": p, "quantidade": q, "simulado": False,
                 "taxa": p * q * TAXA_MAKER}
        decisao = dict(ped["decisao"])
        decisao["motivo"] = f"[executada sem confirmação, adotada da corretora] {decisao.get('motivo') or ''}"
        self._registrar_entrada(decisao, exec_, p, pos_ex.get("sl") or ped["sl"], pos_ex.get("tp") or ped["tp"])
        logger.warning("[%s] ordem %s executou sem confirmação: posição adotada (%s @ %s)",
                       self._attr("nome"), ped["ordem_id"], q, p)
        return True

    # ---------------------------------------------------- gestão posição
    def aplicar_trailing_stop(self, preco: float):
        pos = self.posicao
        if not pos or not (self._attr("usar_trailing_stop", False) or pos.trailing_ativo or self._attr("trailing_manual", False)):
            return
        # sem valor próprio, vale o perfil do estilo: 0,30% de distância mataria um swing no primeiro pavio
        padrao = perfil_saida(self._attr("estilo_trade", ""))
        ativador = float(self._attr("ativador_trailing", 0) or padrao.ativador_trailing)
        dist = float(self._attr("distancia_trailing", 0) or padrao.distancia_trailing)
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

    def aplicar_saida_escalonada(self, preco: float):
        """
        Realiza pedaços da posição conforme o preço avança rumo ao alvo (core/saida_escalonada.py).
        A régua é o AVANÇO até o alvo, não o preço, então o mesmo plano serve para qualquer par e timeframe.
        """
        pos = self.posicao
        if not pos or not self._attr("usar_saida_escalonada", False) or not pos.tp:
            return
        q0 = float(pos.quantidade_inicial or pos.quantidade or 0)
        if q0 <= 0:
            return
        try:
            info = self.con.info_mercado(self.par)
            min_qty, step = float(info.get("min_qty") or 0), float(info.get("qty_step") or 0)
        except Exception:
            min_qty, step = 0.0, 0.0
        plano_txt = self._attr("saida_escalonada") or perfil_saida(self._attr("estilo_trade", "")).saida_escalonada
        fatias = montar_fatias(q0, ler_plano(plano_txt), min_qty, step)
        if not fatias:
            return
        feitas = ler_feitas(pos.saidas_feitas)
        av = avanco_ate_alvo(float(pos.preco_entrada), float(pos.tp), preco, pos.direcao)
        disparadas = pendentes(fatias, feitas, av)
        if not disparadas:
            return
        for f in disparadas:
            restante = float(pos.quantidade or 0)
            qty = min(f["quantidade"], restante)
            if min_qty and (qty < min_qty or restante - qty < min_qty):
                continue          # não deixa um resto impossível de fechar na corretora
            try:
                ex = self.ordens.reduzir(self.par, pos.direcao, qty, self._attr("position_mode", "one-way"), preco_ref=preco)
            except Exception as e:
                logger.warning("[%s] realização parcial falhou: %s", self._attr("nome"), e)
                return
            executada = float(ex.get("quantidade") or 0)
            if executada <= 0:
                continue
            pexec = float(ex.get("preco_exec") or preco)
            sinal = 1 if pos.direcao == "buy" else -1
            lucro = (pexec - float(pos.preco_entrada)) * executada * sinal - float(ex.get("taxa") or 0)
            pos.quantidade = round(restante - executada, 8)
            pos.pnl_parcial = round(float(pos.pnl_parcial or 0) + lucro, 8)
            feitas.append(f["avanco"])
            pos.saidas_feitas = escrever_feitas(feitas)
            self.estado["pnl_dia"] += lucro
            # a fatia já saiu na corretora: o registro vai para o banco AGORA, antes de qualquer coisa que possa
            # falhar. Sem isso, o ciclo seguinte acha que a fatia ainda está pendente e manda a ordem de novo.
            self.db.commit()
            self._log(acao="parcial", tipo_operacao="saida_parcial", direcao=pos.direcao, preco=pexec,
                      quantidade=executada, resultado=lucro,
                      motivo=f"Realização de {f['fracao']:.0%} da mão aos {f['avanco']:.0%} do caminho até o alvo")
            logger.info("[%s] PARCIAL %s%% @ %s (avanço %.0f%%) lucro %.2f, resta %s",
                        self._attr("nome"), round(f["fracao"] * 100), pexec, f["avanco"] * 100, lucro, pos.quantidade)
            # depois da primeira realização, o zero a zero fica travado: a operação não pode mais virar prejuízo
            if self._attr("mover_stop_para_entrada", True) and len(feitas) == 1:
                entrada = float(pos.preco_entrada)
                melhor = (pos.sl is None or (entrada > pos.sl if pos.direcao == "buy" else entrada < pos.sl))
                if melhor:
                    alvo_sl = self.con.arredondar_preco(self.par, entrada)
                    if self.ordens.atualizar_stop(self.par, alvo_sl, pos.tp, self._attr("position_mode", "one-way"), pos.direcao):
                        pos.sl = alvo_sl
                        self._log(acao="ajuste_sl", tipo_operacao="info", preco=preco, sl=alvo_sl,
                                  motivo="Stop movido para o preço de entrada após a primeira realização")
        self.db.commit()
        if float(pos.quantidade or 0) <= 0:
            self._registrar_saida(preco, "Posição totalmente realizada nas parciais")

    def gerir_posicao(self, preco: float, ultimo_candle: list, candle_novo: bool):
        pos = self.posicao
        if not pos:
            return
        self.aplicar_saida_escalonada(preco)
        if not self.posicao:
            return                      # as parciais fecharam a posição inteira
        self.aplicar_trailing_stop(preco)
        # 1) exchange já fechou por SL/TP? Vale para TODO modo que manda ordem de verdade — inclusive o demo.
        # Antes só testnet/real consultavam a corretora; o demo caía no ramo do simulador e deduzia o stop pela
        # mínima do candle: gravava o preço do stop em vez do executado e podia dar a posição por fechada
        # enquanto ela seguia aberta na corretora (ou o contrário).
        if self._manda_ordem():
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
            # plano, trader e trava entram para a auditoria responder "por que o robô não operou?": sem eles a
            # decisão gravada não mostrava qual estado do ciclo, qual escopo do plano nem qual trilho valia
            detalhes = {k: d.get(k) for k in ("cenarios", "alinhamento", "elliott", "validadores", "niveis",
                                              "zonas_institucionais", "votos_contra", "plano", "trader", "trava_mestre",
                                              "motor", "contexto_fluxo", "fluxo", "barras")}
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

    # ------------------------------------------------- motor de fluxo (scalp)
    def _motor_fluxo_ligado(self) -> bool:
        """O motor de fluxo só vale para o scalp: nos graus maiores o candle de tempo é uma régua honesta."""
        if self.inverse is not None or not self._attr("usar_motor_fluxo", False):
            return False
        return "scalp" in (self._attr("estilo_trade", "") or "").lower()

    def _montar_motor(self) -> MotorFluxo:
        return MotorFluxo(self.bot, lambda tf, n: self._con_publico.obter_ohlcv(self.par, tf, n, somente_fechados=True))

    def _leituras_estruturais(self) -> Dict:
        """
        Plano do par, contagem mestre e leitura do trader — as mesmas que o StrategyEngine usa.

        Só é chamado quando o contexto vence (a cada poucos minutos): são consultas de banco e de rede, e
        rodá-las a cada barra de fluxo seria pagar caro por um número que muda devagar.
        """
        out: Dict = {"plano": None, "trava": None, "trader": None}
        try:
            p = self.servicos.get("plano")
            if p is not None:
                out["plano"] = p.plano(self.par) if hasattr(p, "plano") else p
            elif self.db is not None:
                from services.plano_service import PlanoService
                out["plano"] = PlanoService(self.servicos, db=self.db).plano(self.par)
        except Exception as e:
            logger.warning("[%s] plano do par indisponível: %s", self._attr("nome"), e)
        try:
            if self.db is not None:
                from services.elliott_mestre_service import ElliottMestreService
                out["trava"] = ElliottMestreService(self.db, self.con).trava_ativa(self.par, self.estado.get("preco") or 0)
        except Exception as e:
            logger.warning("[%s] trava mestre indisponível: %s", self._attr("nome"), e)
        try:
            t = self.servicos.get("trader")
            if t is not None:
                out["trader"] = t.leitura(self.par) if hasattr(t, "leitura") else t
            elif self.db is not None:
                from services.trader_service import TraderService
                out["trader"] = TraderService(self.con).leitura(self.par)
        except Exception as e:
            logger.warning("[%s] leitura do trader indisponível: %s", self._attr("nome"), e)
        return out

    def _preco_agora(self, novos: list) -> float:
        """O último negócio do stream é mais fresco e mais barato que uma chamada REST de preço."""
        if novos:
            return float(novos[-1]["price"])
        try:
            recentes = self.ws.get_trades() if self.ws is not None else []
            if recentes:
                return float(recentes[-1]["price"])
        except Exception:
            pass
        return float(self._con_publico.obter_preco_atual(self.par))

    def _candle_pode_ter_mudado(self) -> bool:
        """
        Já pode existir candle fechado novo desde a última busca?

        Rebuscar 300 candles a cada ciclo é jogar chamada fora: o Hedge Inverso opera em 4h com ciclo de 10s
        e buscava 1440 vezes o MESMO candle para cada um que trazia dado novo; os quatro robôs somavam 52
        chamadas por minuto de onde caberiam 2. Era isso que enchia o balde e fazia o 10006 estourar em
        rajada nas viradas de 15 minutos e de hora, quando as decisões pesadas coincidem.

        O candle mais recente abriu em `ultimo_candle_ts` e fechou um período depois; o PRÓXIMO só fecha um
        período adiante disso. Antes desse instante, buscar de novo devolve exatamente a mesma coisa.
        """
        if self._ohlcv_cache is None or self.ultimo_candle_ts is None:
            return True
        dur = timeframe_ms(self.timeframe)
        # margem MÍNIMA para o atraso da corretora em publicar o candle recém-fechado. Ela é pequena de
        # propósito: se o candle ainda não saiu, a condição continua verdadeira e o ciclo seguinte busca de
        # novo — ou seja, degrada exatamente para o comportamento antigo justamente quando precisa. Margem
        # grande custaria tempo real de reação no robô de 1m sem comprar nada em troca.
        return time.time() * 1000 >= self.ultimo_candle_ts + 2 * dur + 500

    def _candles_para_gestao(self, intervalo_s: float = 30.0):
        """
        O motor de fluxo não decide por candle, mas a gestão de posição ainda precisa de um: o simulador
        usa máxima/mínima e a manutenção institucional usa o fechamento.
        """
        agora = time.time()
        if self._ohlcv_cache is None or (self._candle_pode_ter_mudado()
                                         and agora - self._ohlcv_cache_ts >= intervalo_s):
            try:
                self._ohlcv_cache = self._con_publico.obter_ohlcv(self.par, self.timeframe, 300,
                                                                  somente_fechados=True)
                self._ohlcv_cache_ts = agora
            except Exception as e:
                # deixar a excecao subir aqui derrubava o ciclo INTEIRO, e com ele a gestao da posicao --
                # trailing que nao sobe, parcial que nao sai -- justamente durante a instabilidade que
                # causou a falha. Um candle de meio minuto atras serve para maxima/minima e fechamento.
                if self._ohlcv_cache is None:
                    raise
                logger.warning("[%s] candles nao renovaram (%s): seguindo com os de %.0fs atras",
                               self._attr("nome"), str(e)[:120], agora - self._ohlcv_cache_ts)
        return self._ohlcv_cache

    def _persistir_do_fluxo(self, decisao: Dict, candle_ts: int, preco: float):
        """
        Uma barra de fluxo fecha a cada poucos segundos: gravar todo 'hold' encheria a tabela de decisões
        sem informação nova. Entrada sempre grava; espera grava no máximo uma por minuto.
        """
        agora = time.time()
        if decisao["acao"] == "hold":
            if agora - self._ultimo_hold_persistido < 60:
                return
            self._ultimo_hold_persistido = agora
        self._persistir_decisao(decisao, candle_ts, preco)

    def _ciclo_fluxo(self):
        """
        Ciclo do scalp por fluxo: o gatilho é a barra de volume fechando, não o minuto virando.

        Elliott continua sendo a lei — só que lido em 15m/1h (onde a contagem para de pé) e como contexto:
        ele diz o lado e os níveis, a fita diz a hora.
        """
        self._iniciar_websocket(forcar=True)
        if self.ws is None:
            logger.warning("[%s] sem websocket: o motor de fluxo não opera, voltando ao ciclo por candle",
                           self._attr("nome"))
            return self._ciclo_candle()
        if self.motor is None:
            self.motor = self._montar_motor()
        novos, self._seq_trades, perdidos = self.ws.trades_desde(self._seq_trades)
        if perdidos:
            # o buffer girou antes de consumirmos: a barra em formação está incompleta e o delta dela mente
            self.motor.agregador.lacunas += perdidos
            logger.warning("[%s] %d negócios perdidos no buffer do websocket", self._attr("nome"), perdidos)
        preco = self._preco_agora(novos)
        ohlcv = self._candles_para_gestao()
        if not ohlcv:
            raise RuntimeError("sem candles para a gestão de posição")
        ultimo = ohlcv[-1]
        candle_novo = self.ultimo_candle_ts != int(ultimo[0])
        if candle_novo:
            self.ultimo_candle_ts = int(ultimo[0])
        self.manutencao(preco, float(ultimo[4]))
        self.gerir_ordem_pendente(preco, ultimo, candle_novo)
        self.gerir_posicao(preco, ultimo, candle_novo)

        barras = self.motor.ingerir(novos)
        if barras:
            leituras = self._leituras_estruturais() if self.motor.contexto_vencido else {}
            decisao = self.motor.avaliar(preco, imbalance=self._imbalance(), **leituras)
            self.estado["ultima_decisao"] = {k: decisao.get(k) for k in ("acao", "motivo", "tp", "sl", "votos")}
            self._persistir_do_fluxo(decisao, int(barras[-1].inicio_ms), preco)
            self._agir_no_fluxo(decisao, preco)
        # o contexto virando contra é motivo para sair: foi ele que autorizou a entrada
        self._saida_por_contexto(preco)
        self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=_agora_utc().isoformat(), preco=preco,
                           posicao=self.posicao.as_dict() if self.posicao else None, fluxo=self.motor.status())

    def _imbalance(self) -> Optional[float]:
        try:
            livro = self.ws.get_order_book() if self.ws is not None else None
            bids, asks = (livro or {}).get("bids") or [], (livro or {}).get("asks") or []
            sb, sa = sum(float(q) for _, q in bids[:10]), sum(float(q) for _, q in asks[:10])
            return (sb - sa) / (sb + sa) if sb + sa > 0 else None
        except Exception:
            return None

    def _agir_no_fluxo(self, decisao: Dict, preco: float):
        if decisao["acao"] not in ("buy", "sell"):
            return
        if self.ordem_pendente:
            # já há uma ordem limitada esperando no nível. Se o fluxo virou de lado, aquela leitura morreu;
            # se é do mesmo lado, mandar outra só empilharia duas ordens para a mesma ideia.
            if self.ordem_pendente["direcao"] != decisao["acao"]:
                self.ordens.cancelar_ordem(self.par, self.ordem_pendente["ordem_id"])
                self.ordem_pendente = None
                self._log(acao="hold", tipo_operacao="info", preco=preco,
                          motivo="Ordem limitada cancelada: o fluxo virou de lado")
            else:
                # descartar isto em silêncio era o mesmo buraco que deixou o robô parado sete horas sem
                # ninguém ver, só que na metade do código que decide por fluxo. Uma barra fecha a cada ~30s,
                # então seriam ~120 sinais por hora sumindo sem uma linha no painel.
                if not self.ordem_pendente.get("avisado"):
                    self.ordem_pendente["avisado"] = True
                    self._log(acao="hold", tipo_operacao="info", preco=preco,
                              motivo=f"Sinal {decisao['acao']} ignorado: ordem limitada a "
                                     f"{self.ordem_pendente['preco']} ainda pendente")
                return
        if self.posicao:
            if self.posicao.direcao != decisao["acao"] and (self._attr("position_mode", "one-way") or "one-way") == "one-way":
                self.fechar_posicao(f"Fluxo contrário: {decisao['motivo'][:120]}", preco)
                self.abrir_posicao(decisao, preco)
            return
        ok, motivo = self._pode_operar()
        if ok:
            self.abrir_posicao(decisao, preco)
        else:
            self._log(acao="hold", tipo_operacao="info", preco=preco, motivo=motivo)

    def _saida_por_contexto(self, preco: float):
        """
        Fecha quando os graus maiores viram para o LADO OPOSTO. Contexto sem lado não fecha nada: isso é
        motivo para não abrir, não para desmontar uma posição que já está correndo.
        """
        pos, ctx = self.posicao, (self.motor.contexto if self.motor else None)
        if not pos or ctx is None or ctx.direcao not in ("buy", "sell"):
            return
        if ctx.direcao != pos.direcao:
            self.fechar_posicao(f"Contexto virou para {ctx.direcao}: {ctx.motivo[:150]}", preco)

    def ciclo(self):
        if self._motor_fluxo_ligado():
            return self._ciclo_fluxo()
        return self._ciclo_candle()

    def _ciclo_candle(self):
        if self._candle_pode_ter_mudado():
            self._ohlcv_cache = self._con_publico.obter_ohlcv(self.par, self.timeframe, 300, somente_fechados=True)
            self._ohlcv_cache_ts = time.time()
        ohlcv = self._ohlcv_cache or []
        if len(ohlcv) < 60:
            raise RuntimeError("candles insuficientes")
        preco = self._con_publico.obter_preco_atual(self.par)
        ultimo = ohlcv[-1]
        candle_novo = self.ultimo_candle_ts != int(ultimo[0])
        if self.inverse is not None:
            # modo inverse: escada de range; nada do fluxo de Elliott operacional
            self.inverse.ciclo(ohlcv, preco, candle_novo)
            self.ultimo_candle_ts = int(ultimo[0])
            self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=_agora_utc().isoformat(), preco=preco,
                               posicao=self.inverse.posicao.as_dict() if self.inverse.posicao else None, inverse=self.inverse.status())
            return
        if self.fatias is not None:
            # votação + fatias: decisão e gestão próprias (stop, alvo e tempo), sem o fluxo de Elliott
            self.fatias.ciclo(ohlcv, preco, candle_novo)
            if candle_novo:
                self.ultimo_candle_ts = int(ultimo[0])
            self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=_agora_utc().isoformat(), preco=preco,
                               posicao=self.posicao.as_dict() if self.posicao else None, fatias=self.fatias.status())
            return
        if self.range is not None:
            # jogo do range: leitura por bloco de 30 min fechado, escada, tirar o risco e tempo próprios
            self.range.ciclo(ohlcv, preco, candle_novo)
            if candle_novo:
                self.ultimo_candle_ts = int(ultimo[0])
            self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=_agora_utc().isoformat(), preco=preco,
                               posicao=self.posicao.as_dict() if self.posicao else None, range=self.range.status())
            return
        if getattr(self, "tradeiros", None) is not None:
            # portal Tradeiros: plano do dia, escada, tirar o risco e hedge próprios
            self.tradeiros.ciclo(ohlcv, preco, candle_novo)
            if candle_novo:
                self.ultimo_candle_ts = int(ultimo[0])
            self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=_agora_utc().isoformat(), preco=preco,
                               posicao=self.posicao.as_dict() if self.posicao else None, tradeiros=self.tradeiros.status())
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
                ped_avisado = bool(self.ordem_pendente.get("avisado"))
                if self.ordem_pendente["direcao"] != decisao["acao"]:
                    self.ordens.cancelar_ordem(self.par, self.ordem_pendente["ordem_id"])
                    self.ordem_pendente = None
                    self._log(acao="hold", tipo_operacao="info", preco=preco, motivo="Ordem limitada cancelada: sinal mudou de direção")
                else:
                    # sinal engolido por ordem pendente era invisível: só ia para o console. Se a ordem
                    # travar, o painel precisa mostrar POR QUE o robô parou de agir.
                    logger.info("[%s] ordem limitada já pendente", self._attr("nome"))
                    if not ped_avisado:
                        self._log(acao="hold", tipo_operacao="info", preco=preco,
                                  motivo=f"Sinal {decisao['acao']} ignorado: ordem limitada a "
                                         f"{self.ordem_pendente['preco']} ainda pendente "
                                         f"({self.ordem_pendente['candles']} candles de espera)")
                        self.ordem_pendente["avisado"] = True
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
        self.estado.update(ciclos=self.estado["ciclos"] + 1, ultimo_ciclo=_agora_utc().isoformat(), preco=preco,
                           posicao=self.posicao.as_dict() if self.posicao else None)

    def _iniciar_websocket(self, forcar: bool = False):
        """Stream público de trades/livro da Bybit (linear) para scalp: menos chamadas REST e delta em tempo real."""
        if self.ws is not None or not (forcar or self._attr("usar_websocket", False)):
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
                # a ccxt usa a URL como mensagem: sem o NOME da exceção, o log não diz se foi timeout,
                # corretora fora do ar ou rate limit — e todos viram "erro: bybit GET https://..."
                self._log(acao="erro", tipo_operacao="info", erro=f"{type(e).__name__}: {e}"[:500], motivo="erro no ciclo")
                if self.estado["erros"] % 10 == 1:
                    self.alertas.erro(self._attr("nome"), e)
                time.sleep(5)
            self._processar_pedidos()
            gasto = time.time() - t0
            if self._acordar.wait(max(1.0, self.delay - gasto)):
                self._acordar.clear()
                self._processar_pedidos()
        logger.info("[%s] loop encerrado", self._attr("nome"))

    def parar(self):
        self._rodando.clear()
        self.bot.ativo_bot = False
        if self.ws is not None:
            try:
                self.ws.stop()
            except Exception:
                pass

    # ---------------------------------------------------- intervenção manual
    def pedir_intervencao(self, acao: str, fracao: Optional[float] = None, motivo: Optional[str] = None,
                          dados: Optional[Dict] = None) -> str:
        """
        Chamado pela thread da API. Só enfileira e acorda o robô — nada de ORM nem de ordem aqui.
        `acao`: 'fechar' | 'parcial' | 'zero_a_zero' | 'cancelar_escada' | 'stop_alvo' (com dados sl/tp).
        """
        token = f"{self.bot_id}-{int(time.time() * 1000)}"
        pedido = {"token": token, "acao": acao, "fracao": fracao, "dados": dados or {},
                  "motivo": motivo or "Intervenção manual pelo painel"}
        with self._trava_pedidos:
            self._pedidos.append(pedido)
            self.intervencoes[token] = {**pedido, "status": "pendente"}
        self._acordar.set()
        return token

    def resultado_intervencao(self, token: str) -> Optional[Dict]:
        return self.intervencoes.get(token)

    def _processar_pedidos(self):
        with self._trava_pedidos:
            pedidos, self._pedidos = self._pedidos, []
        for p in pedidos:
            try:
                r = self._executar_intervencao(p)
                self.intervencoes[p["token"]] = {**p, "status": "feita", **r}
            except Exception as e:
                logger.exception("[%s] intervenção %s falhou: %s", self._attr("nome"), p["acao"], e)
                try:
                    self.db.rollback()
                except Exception:
                    pass
                self.intervencoes[p["token"]] = {**p, "status": "erro", "erro": str(e)[:300]}

    def _executar_intervencao(self, p: Dict) -> Dict:
        """Roda na thread do robô: pode mandar ordem e gravar no banco."""
        acao, motivo = p["acao"], p["motivo"]
        if self.inverse is not None:
            raise RuntimeError("O hedge inverso tem grade própria: use a tela do inverse")
        if getattr(self, "tradeiros", None) is not None and self.categoria == "inverse":
            raise RuntimeError("O hedge do Tradeiros é uma escada com um stop por venda: acompanhe no portal")
        preco = self._con_publico.obter_preco_atual(self.par)
        if acao == "cancelar_escada":
            n = self._cancelar_escada(motivo)
            return {"canceladas": n, "preco": preco}
        if acao == "zero_a_zero":
            if not self.posicao:
                raise RuntimeError("Sem posição aberta")
            alvo = self.con.arredondar_preco(self.par, float(self.posicao.preco_entrada))
            if not self.ordens.atualizar_stop(self.par, alvo, self.posicao.tp, self._attr("position_mode", "one-way"), self.posicao.direcao):
                raise RuntimeError("A corretora não aceitou mover o stop")
            self.posicao.sl = alvo
            self.db.commit()
            self._log(acao="ajuste_sl", tipo_operacao="info", preco=preco, sl=alvo, motivo=f"{motivo}: stop no zero a zero")
            return {"stop": alvo, "preco": preco}
        if acao == "stop_alvo":
            if not self.posicao:
                raise RuntimeError("Sem posição aberta")
            return {**self._mover_stop_alvo(p.get("dados") or {}, preco, motivo), "preco": preco}
        if acao == "parcial":
            if not self.posicao:
                raise RuntimeError("Sem posição aberta")
            fracao = float(p.get("fracao") or 0.5)
            return {**self.realizar_fracao(fracao, preco, motivo), "preco": preco}
        if acao == "fechar":
            if not self.posicao:
                raise RuntimeError("Sem posição aberta")
            self._cancelar_escada(motivo)
            pos = self.posicao
            self.fechar_posicao(f"{motivo} (fechada pelo usuário)", preco)
            for mod in (self.fatias, self.range, getattr(self, "tradeiros", None)):
                if mod is not None and getattr(mod, "trade", None) is not None:
                    mod._encerrar()
            # o resultado é o da operação inteira: parciais + o resto, líquido de taxas
            return {"fechada": True, "preco": preco, "resultado": round(float(pos.pnl or 0), 4),
                    "preco_saida": pos.preco_saida}
        raise RuntimeError(f"Ação desconhecida: {acao}")

    def _mover_stop_alvo(self, dados: Dict, preco: float, motivo: str) -> Dict:
        """
        Stop e alvo novos, escolhidos pelo usuário. O lado é conferido contra o PREÇO ATUAL: stop do lado errado
        vira ordem a mercado disfarçada, e alvo do lado errado executa na hora — os dois fechariam a posição sem
        o usuário entender por quê.
        """
        pos = self.posicao
        s = 1 if pos.direcao == "buy" else -1
        sl = dados.get("sl")
        tp = dados.get("tp")
        novo_sl = self.con.arredondar_preco(self.par, float(sl)) if sl not in (None, "") else pos.sl
        novo_tp = self.con.arredondar_preco(self.par, float(tp)) if tp not in (None, "") else pos.tp
        if sl not in (None, "") and (novo_sl >= preco if s == 1 else novo_sl <= preco):
            raise RuntimeError(f"Stop {novo_sl:,.1f} está do lado errado do preço {preco:,.1f}")
        if tp not in (None, "") and (novo_tp <= preco if s == 1 else novo_tp >= preco):
            raise RuntimeError(f"Alvo {novo_tp:,.1f} está do lado errado do preço {preco:,.1f}")
        if not self.ordens.atualizar_stop(self.par, novo_sl, novo_tp, self._attr("position_mode", "one-way"), pos.direcao):
            raise RuntimeError("A corretora não aceitou o stop/alvo novos")
        pos.sl, pos.tp = novo_sl, novo_tp
        # a estratégia gerencia pelo estado dela: sem isto, o robô voltaria a usar o stop antigo no ciclo seguinte
        for mod, chaves in ((self.fatias, ("stop", "alvo")), (self.range, ("stop", "alvo2")),
                            (getattr(self, "tradeiros", None), ("stop", "alvo"))):
            if mod is not None and getattr(mod, "trade", None) is not None:
                mod.trade[chaves[0]] = novo_sl
                if novo_tp:
                    mod.trade[chaves[1]] = novo_tp
                mod._salvar()
        self.db.commit()
        self._log(acao="ajuste_sl", tipo_operacao="info", preco=preco, sl=novo_sl, tp=novo_tp,
                  motivo=f"{motivo}: stop {novo_sl:,.1f}" + (f", alvo {novo_tp:,.1f}" if novo_tp else ""))
        return {"sl": novo_sl, "tp": novo_tp}

    def _cancelar_escada(self, motivo: str) -> int:
        """Cancela as ordens de ENTRADA ainda no livro (fatias do robô 9/10 ou ordem limitada pendente)."""
        n = 0
        for mod in (self.fatias, self.range, getattr(self, "tradeiros", None)):
            if mod is not None and getattr(mod, "trade", None) is not None and mod.trade.get("pendentes"):
                n += len(mod.trade["pendentes"])
                mod._cancelar_pendentes(motivo)
                mod._salvar()
        if self.ordem_pendente:
            self.ordens.cancelar_ordem(self.par, self.ordem_pendente["ordem_id"])
            self.ordem_pendente = None
            n += 1
        return n

    def realizar_fracao(self, fracao: float, preco: float, motivo: str) -> Dict:
        """Realiza uma fração da posição a mercado (reduce-only) e registra o lucro da fatia."""
        pos = self.posicao
        fracao = min(max(fracao, 0.01), 1.0)
        qty = self.con.arredondar_quantidade(self.par, float(pos.quantidade) * fracao)
        if qty <= 0:
            raise RuntimeError("Fração abaixo do mínimo negociável")
        ex = self.ordens.reduzir(self.par, pos.direcao, qty, self._attr("position_mode", "one-way"), preco_ref=preco)
        feita = float(ex.get("quantidade") or 0)
        if feita <= 0:
            raise RuntimeError("A corretora não executou a redução")
        pexec = float(ex.get("preco_exec") or preco)
        sinal = 1 if pos.direcao == "buy" else -1
        lucro = (pexec - float(pos.preco_entrada)) * feita * sinal - float(ex.get("taxa") or 0)
        pos.quantidade = round(float(pos.quantidade) - feita, 8)
        pos.pnl_parcial = round(float(pos.pnl_parcial or 0) + lucro, 8)
        self.estado["pnl_dia"] += lucro
        self.db.commit()
        self._log(acao="parcial", tipo_operacao="saida_parcial", direcao=pos.direcao, preco=pexec, quantidade=feita,
                  resultado=lucro, motivo=f"{motivo}: {fracao:.0%} da mão realizados")
        if float(pos.quantidade or 0) <= 0:
            self._registrar_saida(pexec, f"{motivo}: posição toda realizada")
            for mod in (self.fatias, self.range, getattr(self, "tradeiros", None)):
                if mod is not None and getattr(mod, "trade", None) is not None:
                    mod._encerrar()
        return {"quantidade": feita, "preco_exec": pexec, "resultado": round(lucro, 4), "resta": float(pos.quantidade or 0)}

    def status(self) -> Dict:
        """Chamado pela thread da API: NÃO pode tocar no ORM, que pertence à sessão da thread do robô."""
        s = dict(self.estado)
        s["rodando"] = self._rodando.is_set()
        s["bot_id"] = self.bot_id
        s["nome"] = self.nome
        s["ordem_pendente"] = {k: v for k, v in (self.ordem_pendente or {}).items() if k != "decisao"} or None
        return _json_puro(s)
