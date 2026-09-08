# core/backtest_engine.py
"""
Backtest do StrategyEngine sobre candles históricos (mesma lógica do bot ao vivo).

    from core.backtest_engine import BacktestEngine, carregar_binance_csv
    ohlcv = carregar_binance_csv("binance_csv")            # 1h BTCUSDT
    bt = BacktestEngine(ohlcv, bot_config, timeframe="1h")
    resultado = bt.executar()                              # dict com métricas e lista de trades

Regras da simulação:
    - decisão em cada candle FECHADO usando os 300 anteriores; entrada no fechamento do candle
    - SL/TP verificados pelo high/low dos candles seguintes (se ambos no mesmo candle, assume SL)
    - saída estrutural (Elliott) reavaliada a cada candle enquanto há posição
    - taxas taker 0,055% por lado; tamanho por risco (banca * risco_pct / distância do SL) limitado por max_alocacao
    - timeframes superiores derivados por reamostragem dos próprios candles (sem look-ahead)
"""
from __future__ import annotations

import glob
import logging
import os
import time
from types import SimpleNamespace
from typing import Dict, List, Optional, Sequence

import pandas as pd

from core.market_data import reamostrar
from core.strategy_engine import StrategyEngine
from core.utils_indicadores import normalizar_timeframe, timeframe_ms

logger = logging.getLogger(__name__)
TAXA = 0.00055
TAXA_MAKER = 0.0002


def carregar_binance_csv(pasta: str = "binance_csv", padrao: str = "BTCUSDT-1h-*.csv") -> List[list]:
    """Lê os CSVs diários da Binance (klines) e devolve OHLCV em ms."""
    cols = ["open_time", "open", "high", "low", "close", "volume", "close_time", "qav", "n", "tb", "tq", "ig"]
    arquivos = sorted(glob.glob(os.path.join(pasta, padrao)))
    if not arquivos:
        raise FileNotFoundError(f"nenhum CSV em {pasta}/{padrao}")
    dfs = [pd.read_csv(f, header=None, names=cols) for f in arquivos]
    df = pd.concat(dfs, ignore_index=True).drop_duplicates("open_time").sort_values("open_time")
    out = []
    for r in df.itertuples(index=False):
        ts = int(r.open_time)
        if ts > 10**14:      # microssegundos (arquivos mais novos da Binance)
            ts //= 1000
        out.append([ts, float(r.open), float(r.high), float(r.low), float(r.close), float(r.volume)])
    return out


def bot_padrao(**kw) -> SimpleNamespace:
    base = dict(id=0, nome="backtest", ativo="BTCUSDT", timeframe="1h", estilo_trade="daytrade", confluencia_tipo="conservador",
                exchange="bybit", modo_execucao="simulador", usar_elliott=True, usar_fibonacci=True, usar_tpo=True, usar_vwap=True,
                usar_orderflow=False, usar_volume_profile=True, usar_orderblock=True, usar_sentimento=False,
                usar_tendencia_macro=True, usar_api_macro=False, banca=10000.0, risco_pct=0.01, max_alocacao_pct=0.5,
                alavancagem=1, quantidade=0.01, usar_trailing_stop=False, ativador_trailing=0.005, distancia_trailing=0.003,
                position_mode="one-way", max_trades_dia=10, usar_filtro_regime=True, prob_sucesso_minima=0.45,
                tipo_entrada="mercado", slippage_pct=0.0002, limite_candles_espera=3, taxa_historica_minima=0.0, rr_minimo=0.0)
    base.update(kw)
    return SimpleNamespace(**base)


class BacktestEngine:
    def __init__(self, ohlcv: Sequence, bot=None, timeframe: str = "1h", janela: int = 300, passo: int = 1,
                 banca: Optional[float] = None, verbose: bool = False, arquivo_csv: str = None):
        if arquivo_csv and not ohlcv:
            df = pd.read_csv(arquivo_csv)
            ohlcv = [[int(r.timestamp) * (1000 if int(r.timestamp) < 10**12 else 1), r.open, r.high, r.low, r.close, r.volume]
                     for r in df.itertuples()]
        self.ohlcv = [list(map(float, c[:6])) for c in ohlcv]
        for c in self.ohlcv:
            c[0] = int(c[0])
        self.bot = bot or bot_padrao(timeframe=timeframe)
        self.bot.timeframe = normalizar_timeframe(timeframe)
        self.timeframe = self.bot.timeframe
        self.janela = janela
        self.passo = passo
        self.banca_inicial = float(banca if banca is not None else getattr(self.bot, "banca", 10000.0))
        self.banca = self.banca_inicial
        self.verbose = verbose
        self.trades: List[Dict] = []
        self.decisoes: List[Dict] = []
        self.pendentes_executadas = 0
        self.pendentes_expiradas = 0
        self.curva: List[float] = []
        self._cache_tf: Dict[str, List[list]] = {}

    # ------------------------------------------------------------ dados
    def _serie_tf(self, tf: str) -> List[list]:
        tf = normalizar_timeframe(tf)
        if tf not in self._cache_tf:
            if timeframe_ms(tf) <= timeframe_ms(self.timeframe):
                self._cache_tf[tf] = self.ohlcv
            else:
                self._cache_tf[tf] = reamostrar(self.ohlcv, self.timeframe, tf)
        return self._cache_tf[tf]

    def _fetch_ate(self, ts_limite: int):
        """fetch_ohlcv(tf, n) que só enxerga candles FECHADOS até ts_limite (sem look-ahead)."""
        def fetch(tf, n):
            serie = self._serie_tf(tf)
            dur = timeframe_ms(tf)
            fechados = [c for c in serie if c[0] + dur <= ts_limite + timeframe_ms(self.timeframe)]
            return fechados[-n:]
        return fetch

    # ------------------------------------------------------- simulação
    def _tamanho(self, preco: float, sl: float, fator: float) -> float:
        if not preco or sl is None or abs(preco - sl) < preco * 1e-5:
            return 0.0
        risco = self.banca * float(getattr(self.bot, "risco_pct", 0.01)) * fator
        qty = risco / abs(preco - sl)
        teto = self.banca * float(getattr(self.bot, "max_alocacao_pct", 0.5)) * max(int(getattr(self.bot, "alavancagem", 1)), 1) / preco
        return round(min(qty, teto), 6)

    def executar(self) -> Dict:
        t0 = time.time()
        pos: Optional[Dict] = None
        pendente: Optional[Dict] = None
        engine: Optional[StrategyEngine] = None
        n = len(self.ohlcv)
        slip = float(getattr(self.bot, "slippage_pct", 0.0) or 0.0)
        limite = getattr(self.bot, "tipo_entrada", "mercado") == "limite"
        espera = int(getattr(self.bot, "limite_candles_espera", 3) or 3)
        for i in range(self.janela, n):
            c = self.ohlcv[i]           # candle "atual" que acabou de fechar
            preco = c[4]
            # 0) ordem limitada pendente: executa se o candle tocou o preço (taxa maker), expira após `espera` candles
            if pendente and not pos:
                tocou = c[3] <= pendente["preco"] if pendente["direcao"] == "buy" else c[2] >= pendente["preco"]
                if tocou:
                    pos = {**pendente["pos"], "preco_entrada": pendente["preco"], "ts_entrada": c[0], "taxa_entrada": TAXA_MAKER}
                    pendente = None
                    self.pendentes_executadas += 1
                else:
                    pendente["candles"] += 1
                    if pendente["candles"] >= espera:
                        pendente = None
                        self.pendentes_expiradas += 1
            # 1) gestão da posição com o candle i (que ocorreu após a decisão)
            if pos:
                hi, lo = c[2], c[3]
                saida = None
                if pos["direcao"] == "buy":
                    if lo <= pos["sl"]:
                        saida = (pos["sl"], "SL")
                    elif hi >= pos["tp"]:
                        saida = (pos["tp"], "TP")
                else:
                    if hi >= pos["sl"]:
                        saida = (pos["sl"], "SL")
                    elif lo <= pos["tp"]:
                        saida = (pos["tp"], "TP")
                if saida:
                    self._fechar(pos, saida[0], saida[1], c[0])
                    pos = None
            if (i - self.janela) % self.passo != 0:
                self.curva.append(self.banca)
                continue
            janela = self.ohlcv[i - self.janela + 1:i + 1]
            try:
                engine = StrategyEngine(janela, self.bot, db=None, servicos={
                    "fetch_ohlcv": self._fetch_ate(c[0]), "preco_atual": preco, "ohlcv_composto": janela})
                if pos:
                    s = engine.sinal_saida(pos["direcao"])
                    if s.get("sair"):
                        self._fechar(pos, preco, f"estrutural: {s.get('motivo')}", c[0])
                        pos = None
                d = engine.decidir()
            except Exception as e:
                logger.warning("erro no candle %s: %s", c[0], e)
                self.curva.append(self.banca)
                continue
            self.decisoes.append({"ts": c[0], "acao": d["acao"], "fase": d.get("fase_onda"), "motivo": d.get("motivo", "")[:160]})
            if d["acao"] in ("buy", "sell") and not pos and d.get("sl"):
                s = 1 if d["acao"] == "buy" else -1
                if limite and d.get("preco_limite"):
                    qty = self._tamanho(d["preco_limite"], d["sl"], d.get("tamanho_fator", 1.0))
                    if qty > 0:
                        pendente = {"direcao": d["acao"], "preco": d["preco_limite"], "candles": 0,
                                    "pos": {"direcao": d["acao"], "qty": qty, "sl": d["sl"], "tp": d["tp"], "fase": d.get("fase_onda"),
                                            "cenario": d.get("cenario"), "motivo": d.get("motivo", "")[:200]}}
                else:
                    preco_exec = preco * (1 + s * slip)   # slippage da ordem a mercado
                    qty = self._tamanho(preco_exec, d["sl"], d.get("tamanho_fator", 1.0))
                    if qty > 0:
                        pos = {"direcao": d["acao"], "preco_entrada": preco_exec, "qty": qty, "sl": d["sl"], "tp": d["tp"], "ts_entrada": c[0],
                               "fase": d.get("fase_onda"), "cenario": d.get("cenario"), "motivo": d.get("motivo", "")[:200], "taxa_entrada": TAXA}
                        if self.verbose:
                            print(f"{pd.to_datetime(c[0], unit='ms')} ENTRADA {d['acao']} @ {preco_exec:.2f} sl={d['sl']} tp={d['tp']} qty={qty} | {d.get('fase_onda')}")
            self.curva.append(self.banca)
        if pos:
            self._fechar(pos, self.ohlcv[-1][4], "fim do backtest", self.ohlcv[-1][0])
        return self.relatorio(time.time() - t0)

    def _fechar(self, pos: Dict, preco_saida: float, motivo: str, ts: int):
        s = 1 if pos["direcao"] == "buy" else -1
        slip = float(getattr(self.bot, "slippage_pct", 0.0) or 0.0)
        if motivo == "SL" or motivo.startswith("estrutural"):
            preco_saida = preco_saida * (1 - s * slip)   # saídas a mercado sofrem slippage contra
        taxas = pos["preco_entrada"] * pos["qty"] * pos.get("taxa_entrada", TAXA) + preco_saida * pos["qty"] * TAXA
        pnl = (preco_saida - pos["preco_entrada"]) * pos["qty"] * s - taxas
        r = (preco_saida - pos["preco_entrada"]) * s / abs(pos["preco_entrada"] - pos["sl"]) if pos["sl"] else 0.0
        self.banca += pnl
        self.trades.append({**pos, "preco_saida": preco_saida, "pnl": round(pnl, 2), "r": round(r, 2), "motivo_saida": motivo,
                            "ts_saida": ts, "banca": round(self.banca, 2)})
        if self.verbose:
            print(f"{pd.to_datetime(ts, unit='ms')} SAÍDA {pos['direcao']} @ {preco_saida:.2f} pnl={pnl:+.2f} ({motivo}) banca={self.banca:.2f}")

    # -------------------------------------------------------- relatório
    def relatorio(self, tempo: float = 0.0) -> Dict:
        t = self.trades
        ganhos = [x["pnl"] for x in t if x["pnl"] > 0]
        perdas = [x["pnl"] for x in t if x["pnl"] <= 0]
        pico, dd_max = self.banca_inicial, 0.0
        for v in self.curva:
            pico = max(pico, v)
            dd_max = max(dd_max, (pico - v) / pico if pico else 0.0)
        acoes = {}
        for d in self.decisoes:
            acoes[d["acao"]] = acoes.get(d["acao"], 0) + 1
        fases = {}
        for d in self.decisoes:
            fases[d["fase"]] = fases.get(d["fase"], 0) + 1
        return {
            "candles": len(self.ohlcv), "timeframe": self.timeframe, "perfil": getattr(self.bot, "confluencia_tipo", None),
            "estilo": getattr(self.bot, "estilo_trade", None), "trades": len(t), "ganhos": len(ganhos), "perdas": len(perdas),
            "taxa_acerto": round(len(ganhos) / len(t), 3) if t else None,
            "pnl_total": round(sum(x["pnl"] for x in t), 2), "retorno_pct": round((self.banca / self.banca_inicial - 1) * 100, 2),
            "fator_lucro": round(sum(ganhos) / abs(sum(perdas)), 2) if perdas and sum(perdas) else None,
            "r_medio": round(sum(x["r"] for x in t) / len(t), 2) if t else None,
            "drawdown_max_pct": round(dd_max * 100, 2), "banca_final": round(self.banca, 2),
            "decisoes": acoes, "fases": fases, "tempo_s": round(tempo, 1), "lista_trades": t,
            "ordens_limite": {"executadas": self.pendentes_executadas, "expiradas": self.pendentes_expiradas},
        }

    def salvar_resultado(self, caminho_saida: str):
        pd.DataFrame(self.trades).to_csv(caminho_saida, index=False)
