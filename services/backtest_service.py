# services/backtest_service.py
"""
Backtest de validação obrigatório antes de ativar um bot (moeda nova, timeframe novo, perfil novo).

Fluxo:
    1. valida que o par existe na Bybit (linear)
    2. baixa/atualiza o histórico do par no timeframe do bot (cache em data/historico/<PAR>_bybit_<tf>.csv)
    3. roda o BacktestEngine com a MESMA configuração do bot
    4. avalia critérios de aprovação e grava em BacktestsBot
    5. BotManager.start_bot recusa ativar sem backtest aprovado nos últimos `VALIDADE_DIAS`

Critérios (padrão, configuráveis por chamada):
    trades >= 30 | fator de lucro >= 1.0 | drawdown máximo <= 25% | retorno > 0
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pandas as pd

from core.backtest_engine import BacktestEngine
from core.utils_indicadores import normalizar_timeframe, timeframe_ms
from models.backtest_bot import BacktestBot
from models.bot import Bot

logger = logging.getLogger(__name__)

VALIDADE_DIAS = 30
CRITERIOS_PADRAO = {"min_trades": 30, "min_fator_lucro": 1.0, "max_drawdown_pct": 25.0, "min_retorno_pct": 0.0}
DIAS_PADRAO = {"1m": 30, "3m": 45, "5m": 90, "15m": 180, "30m": 365, "1h": 730, "2h": 730, "4h": 1460, "1d": 2190}
PASTA = os.path.join("data", "historico")


class BacktestService:
    def __init__(self, session_factory, connector=None):
        self.session_factory = session_factory
        self.connector = connector
        self._rodando: Dict[int, threading.Thread] = {}

    def _con(self):
        if self.connector is None:
            from core.conexoes.conexao_bybit import BybitConnector
            self.connector = BybitConnector("simulador")
        return self.connector

    # ----------------------------------------------------------- histórico
    def historico(self, par: str, timeframe: str, dias: int) -> list:
        """Candles do par na Bybit (linear), com cache incremental em CSV."""
        par = par.replace("/", "").upper()
        tf = normalizar_timeframe(timeframe)
        os.makedirs(PASTA, exist_ok=True)
        caminho = os.path.join(PASTA, f"{par}_bybit_{tf}.csv")
        agora = int(time.time() * 1000)
        desde = agora - dias * 86_400_000
        existente = None
        if os.path.exists(caminho):
            existente = pd.read_csv(caminho).sort_values("timestamp")
            ultimo = int(existente.timestamp.max())
            primeiro = int(existente.timestamp.min())
            inicio_busca = ultimo + 1 if primeiro <= desde + timeframe_ms(tf) else desde
        else:
            inicio_busca = desde
        con = self._con()
        novos = con.obter_ohlcv_historico(par, tf, inicio_busca, agora) if inicio_busca < agora - timeframe_ms(tf) else []
        df_novos = pd.DataFrame(novos, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = pd.concat([existente, df_novos]) if existente is not None else df_novos
        if df.empty:
            raise RuntimeError(f"Sem histórico para {par} {tf} na Bybit")
        df = df.drop_duplicates("timestamp").sort_values("timestamp")
        df.to_csv(caminho, index=False)
        df = df[df.timestamp >= desde]
        return df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()

    # ---------------------------------------------------------------- rodar
    def validar_par(self, par: str) -> Dict:
        return self._con().info_mercado(par)

    def rodar(self, bot, dias: Optional[int] = None, criterios: Optional[Dict] = None, session=None) -> BacktestBot:
        crit = {**CRITERIOS_PADRAO, **(criterios or {})}
        tf = normalizar_timeframe(getattr(bot, "timeframe", "15m"))
        par = getattr(bot, "ativo", "BTCUSDT").replace("/", "").upper()
        dias = dias or DIAS_PADRAO.get(tf, 365)
        db = session or self.session_factory()
        reg = BacktestBot(bot_id=getattr(bot, "id", None), par=par, timeframe=tf, estilo_trade=getattr(bot, "estilo_trade", None),
                          confluencia_tipo=getattr(bot, "confluencia_tipo", None), dias=dias, status="rodando",
                          parametros=json.dumps({k: v for k, v in (bot.as_dict() if hasattr(bot, "as_dict") else vars(bot)).items()
                                                 if not k.startswith("_")}, default=str))
        db.add(reg)
        db.commit()
        try:
            self.validar_par(par)
            ohlcv = self.historico(par, tf, dias)
            r = BacktestEngine(ohlcv, bot, timeframe=tf).executar()
            trades = r.pop("lista_trades")
            reg.candles = r["candles"]
            reg.data_inicio = datetime.fromtimestamp(ohlcv[0][0] / 1000, tz=timezone.utc).replace(tzinfo=None)
            reg.data_fim = datetime.fromtimestamp(ohlcv[-1][0] / 1000, tz=timezone.utc).replace(tzinfo=None)
            reg.trades, reg.taxa_acerto, reg.retorno_pct = r["trades"], r["taxa_acerto"], r["retorno_pct"]
            reg.fator_lucro, reg.drawdown_max_pct, reg.r_medio = r["fator_lucro"], r["drawdown_max_pct"], r["r_medio"]
            aprovado, motivo = self.avaliar(r, crit)
            reg.aprovado, reg.motivo, reg.status = aprovado, motivo, "concluido"
            reg.detalhes = json.dumps({"resumo": r, "ultimos_trades": trades[-20:], "criterios": crit}, default=str)[:200000]
            db.commit()
            logger.info("backtest %s %s: %s (%s)", par, tf, "APROVADO" if aprovado else "REPROVADO", motivo)
        except Exception as e:
            reg.status, reg.motivo = "erro", str(e)[:255]
            db.commit()
            logger.exception("backtest falhou: %s", e)
        finally:
            if session is None:
                db.close()
        return reg

    @staticmethod
    def avaliar(r: Dict, crit: Dict):
        falhas = []
        if (r.get("trades") or 0) < crit["min_trades"]:
            falhas.append(f"trades {r.get('trades')} < {crit['min_trades']}")
        if r.get("fator_lucro") is None or r["fator_lucro"] < crit["min_fator_lucro"]:
            falhas.append(f"fator de lucro {r.get('fator_lucro')} < {crit['min_fator_lucro']}")
        if (r.get("drawdown_max_pct") or 0) > crit["max_drawdown_pct"]:
            falhas.append(f"drawdown {r.get('drawdown_max_pct')}% > {crit['max_drawdown_pct']}%")
        if (r.get("retorno_pct") or 0) <= crit["min_retorno_pct"]:
            falhas.append(f"retorno {r.get('retorno_pct')}% <= {crit['min_retorno_pct']}%")
        if falhas:
            return False, "; ".join(falhas)[:255]
        return True, f"aprovado: {r['trades']} trades, PF {r['fator_lucro']}, retorno {r['retorno_pct']}%, DD {r['drawdown_max_pct']}%"

    def rodar_em_background(self, bot_id: int, dias: Optional[int] = None, criterios: Optional[Dict] = None) -> bool:
        th = self._rodando.get(bot_id)
        if th and th.is_alive():
            return False

        def alvo():
            db = self.session_factory()
            try:
                bot = db.query(Bot).filter(Bot.id == bot_id).first()
                if bot:
                    self.rodar(bot, dias, criterios, session=db)
            finally:
                db.close()
        th = threading.Thread(target=alvo, name=f"backtest-{bot_id}", daemon=True)
        self._rodando[bot_id] = th
        th.start()
        return True

    def em_andamento(self, bot_id: int) -> bool:
        th = self._rodando.get(bot_id)
        return bool(th and th.is_alive())

    # ------------------------------------------------------------- consulta
    @staticmethod
    def ultimo_aprovado(db, bot, validade_dias: int = VALIDADE_DIAS) -> Optional[BacktestBot]:
        corte = datetime.utcnow() - timedelta(days=validade_dias)
        return (db.query(BacktestBot).filter(
            BacktestBot.par == getattr(bot, "ativo", "").replace("/", "").upper(),
            BacktestBot.timeframe == normalizar_timeframe(getattr(bot, "timeframe", "15m")),
            BacktestBot.estilo_trade == getattr(bot, "estilo_trade", None),
            BacktestBot.confluencia_tipo == getattr(bot, "confluencia_tipo", None),
            BacktestBot.aprovado == True, BacktestBot.criado_em >= corte)  # noqa: E712
            .order_by(BacktestBot.id.desc()).first())

    @staticmethod
    def pode_ativar(db, bot, validade_dias: int = VALIDADE_DIAS):
        """(ok, motivo). Simulador e demo não arriscam dinheiro e não precisam de backtest; testnet e real precisam."""
        modo = (getattr(bot, "modo_execucao", "simulador") or "simulador").lower()
        if modo in ("simulador", "demo"):
            return True, f"modo {modo}: sem dinheiro real, backtest não obrigatório"
        bt = BacktestService.ultimo_aprovado(db, bot, validade_dias)
        if bt:
            return True, f"backtest #{bt.id} aprovado em {bt.criado_em:%Y-%m-%d} ({bt.motivo})"
        return False, (f"Sem backtest aprovado nos últimos {validade_dias} dias para {getattr(bot, 'ativo')} {getattr(bot, 'timeframe')} "
                       f"{getattr(bot, 'estilo_trade')}/{getattr(bot, 'confluencia_tipo')}. Rode POST /backtest/bots/{getattr(bot, 'id')}")

    @staticmethod
    def listar(db, bot_id: Optional[int] = None, par: Optional[str] = None, limite: int = 50):
        q = db.query(BacktestBot)
        if bot_id:
            q = q.filter(BacktestBot.bot_id == bot_id)
        if par:
            q = q.filter(BacktestBot.par == par.replace("/", "").upper())
        return q.order_by(BacktestBot.id.desc()).limit(limite).all()
