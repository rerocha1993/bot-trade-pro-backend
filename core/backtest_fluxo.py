# core/backtest_fluxo.py
"""
Backtest do MOTOR DE FLUXO sobre os negócios históricos da Bybit.

    from core.backtest_fluxo import BacktestFluxo
    bt = BacktestFluxo(bot, series_contexto={"15m": c15, "1h": c1h})
    resultado = bt.executar(fluxo("BTCUSDT", inicio, fim))

Por que negócio a negócio e não candle: a barra de fluxo fecha por quantidade negociada, então o teste
precisa saber COMO o volume chegou, não só quanto chegou no minuto. De brinde, a simulação de SL/TP fica
mais honesta do que a de candles: em vez de supor o pior quando máxima e mínima cabem no mesmo candle, aqui
se sabe qual preço veio primeiro, porque os negócios estão em ordem.

O contexto (15m/1h) vem de candles, e a função de leitura só enxerga os FECHADOS até o instante simulado —
o mesmo cuidado com look-ahead que o backtest de candles já tomava.

Modelo de custo: maker na entrada quando a ordem é limitada (que é o padrão do motor de fluxo — a absorção
é uma ordem esperando NO nível, não uma corrida atrás do preço) e taker na saída, com slippage opcional.
Limite de trades e de perda no dia valem, porque valem no robô ao vivo e mudam bastante um scalp.
"""
from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Sequence

from core.executor_real import TAXA_MAKER, TAXA_TAKER
from core.gatilho_fluxo import ParametrosFluxo
from core.motor_fluxo import MotorFluxo
from core.perfil_saida import perfil as perfil_saida
from core.saida_escalonada import avanco as avanco_ate_alvo, ler_plano, montar_fatias, pendentes
from core.utils_indicadores import timeframe_ms

logger = logging.getLogger(__name__)


def bot_fluxo(**kw) -> SimpleNamespace:
    base = dict(id=0, nome="backtest fluxo", ativo="BTCUSDT", timeframe="1m", estilo_trade="scalping",
                confluencia_tipo="conservador", exchange="bybit", modo_execucao="simulador",
                usar_motor_fluxo=True, barra_tipo="volume", barra_tamanho=0.0, barra_segundos_alvo=30.0,
                banca=10000.0, risco_pct=0.005, max_alocacao_pct=0.5, alavancagem=1, quantidade=0.001,
                max_trades_dia=30, max_perda_dia_pct=0.03, rr_minimo=0,
                tipo_entrada="limite", espera_limite_s=180,
                usar_trailing_stop=True, usar_saida_escalonada=True, mover_stop_para_entrada=True,
                ativador_trailing=None, distancia_trailing=None, saida_escalonada=None,
                slippage_pct=0.0)
    base.update(kw)
    b = SimpleNamespace(**base)
    p = perfil_saida(b.estilo_trade)
    if b.ativador_trailing is None:
        b.ativador_trailing = p.ativador_trailing
    if b.distancia_trailing is None:
        b.distancia_trailing = p.distancia_trailing
    if b.saida_escalonada is None:
        b.saida_escalonada = p.saida_escalonada
    return b


class BacktestFluxo:
    def __init__(self, bot=None, series_contexto: Optional[Dict[str, Sequence]] = None,
                 parametros: Optional[ParametrosFluxo] = None, intervalo_contexto_s: float = 180.0,
                 verbose: bool = False):
        self.bot = bot or bot_fluxo()
        self.series = {k: [list(map(float, c[:6])) for c in v] for k, v in (series_contexto or {}).items()}
        self.banca_inicial = float(getattr(self.bot, "banca", 10000.0))
        self.banca = self.banca_inicial
        self.taxa_entrada = TAXA_MAKER if getattr(self.bot, "tipo_entrada", "") == "limite" else TAXA_TAKER
        self.taxa_saida = TAXA_TAKER
        self.espera_limite_ms = int(float(getattr(self.bot, "espera_limite_s", 180) or 180) * 1000)
        self.limitada = getattr(self.bot, "tipo_entrada", "") == "limite"
        self.pendentes_executadas = 0
        self.pendentes_expiradas = 0
        self.slip = float(getattr(self.bot, "slippage_pct", 0.0) or 0.0)
        self.verbose = verbose
        self._agora_ms = 0
        self.motor = MotorFluxo(self.bot, self._fetch, parametros=parametros,
                                intervalo_contexto_s=intervalo_contexto_s)
        # o motor se atualiza por relógio de parede; aqui o relógio é o dos negócios, então quem manda no
        # recálculo do contexto é o backtest. Sem isto, um teste de um dia leria os graus maiores uma vez só.
        self.motor._proximo_contexto = float("inf")
        self._intervalo_ctx_ms = int(intervalo_contexto_s * 1000)
        self._proximo_ctx_ms = 0
        self.trades: List[Dict] = []
        self.decisoes: Dict[str, int] = {}
        self.gatilhos: Dict[str, int] = {}
        self.motivos: Dict[str, int] = {}
        self.curva: List[float] = []
        self.barras_fechadas = 0
        self._dia = None
        self._trades_dia = 0
        self._pnl_dia = 0.0

    # ------------------------------------------------------------------ contexto sem look-ahead
    def _fetch(self, tf: str, n: int) -> List[list]:
        serie = self.series.get(tf) or []
        dur = timeframe_ms(tf)
        fechados = [c for c in serie if c[0] + dur <= self._agora_ms]
        return fechados[-n:]

    # ------------------------------------------------------------------ contabilidade do dia
    def _virar_dia(self, ts_ms: int):
        dia = ts_ms // 86_400_000
        if dia != self._dia:
            self._dia, self._trades_dia, self._pnl_dia = dia, 0, 0.0

    def _pode_operar(self) -> bool:
        if self._trades_dia >= int(getattr(self.bot, "max_trades_dia", 30) or 30):
            return False
        limite = float(getattr(self.bot, "max_perda_dia_pct", 0.03) or 0.03) * self.banca_inicial
        return self._pnl_dia > -limite

    # ------------------------------------------------------------------ tamanho
    def _tamanho(self, preco: float, sl: float, fator: float) -> float:
        if not preco or sl is None or abs(preco - sl) < preco * 1e-6:
            return 0.0
        risco = self.banca * float(getattr(self.bot, "risco_pct", 0.005)) * fator
        qty = risco / abs(preco - sl)
        teto = (self.banca * float(getattr(self.bot, "max_alocacao_pct", 0.5))
                * max(int(getattr(self.bot, "alavancagem", 1) or 1), 1) / preco)
        return round(min(qty, teto), 6)

    # ------------------------------------------------------------------ gestão da posição
    def _abrir(self, d: Dict, preco: float, ts: int, preco_exec: Optional[float] = None):
        s = 1 if d["acao"] == "buy" else -1
        # ordem limitada e servida no preco combinado: nao paga spread nem slippage, so nao ha garantia de fila
        preco_exec = preco_exec if preco_exec is not None else preco * (1 + s * self.slip)
        qty = self._tamanho(preco_exec, d["sl"], d.get("tamanho_fator", 1.0))
        if qty <= 0:
            return None
        plano = montar_fatias(qty, ler_plano(getattr(self.bot, "saida_escalonada", None))) \
            if getattr(self.bot, "usar_saida_escalonada", False) else []
        self._trades_dia += 1
        pos = {"direcao": d["acao"], "preco_entrada": preco_exec, "qty": qty, "qty_inicial": qty,
               "sl": d["sl"], "sl_inicial": d["sl"], "tp": d["tp"], "ts_entrada": ts,
               "gatilho": (d.get("fluxo") or {}).get("gatilho"), "motivo": d.get("motivo", "")[:200],
               "taxas": preco_exec * qty * self.taxa_entrada, "pnl_parcial": 0.0, "plano": plano, "feitas": [],
               "trailing_ativo": False}
        if self.verbose:
            print(f"{ts} ENTRADA {d['acao']} @ {preco_exec:.2f} sl={d['sl']} tp={d['tp']} qty={qty}")
        return pos

    def _trailing(self, pos: Dict, preco: float):
        if not getattr(self.bot, "usar_trailing_stop", False):
            return
        ativador = float(getattr(self.bot, "ativador_trailing", 0) or 0)
        dist = float(getattr(self.bot, "distancia_trailing", 0) or 0)
        if ativador <= 0 or dist <= 0:
            return
        entrada, s = pos["preco_entrada"], (1 if pos["direcao"] == "buy" else -1)
        avanco = (preco - entrada) * s / entrada
        if avanco < ativador:
            return
        pos["trailing_ativo"] = True
        novo = preco * (1 - s * dist)
        if (novo > pos["sl"]) if pos["direcao"] == "buy" else (novo < pos["sl"]):
            pos["sl"] = novo

    def _parciais(self, pos: Dict, preco: float, ts: int):
        if not pos["plano"] or not pos["tp"]:
            return
        av = avanco_ate_alvo(pos["preco_entrada"], pos["tp"], preco, pos["direcao"])
        for f in pendentes(pos["plano"], pos["feitas"], av):
            qty = min(f["quantidade"], pos["qty"])
            if qty <= 0:
                continue
            s = 1 if pos["direcao"] == "buy" else -1
            saida = preco * (1 - s * self.slip)
            taxa = saida * qty * self.taxa_saida
            lucro = (saida - pos["preco_entrada"]) * qty * s - taxa
            pos["qty"] = round(pos["qty"] - qty, 8)
            pos["pnl_parcial"] += lucro
            pos["taxas"] += taxa
            pos["feitas"].append(f["avanco"])
            self.banca += lucro
            self._pnl_dia += lucro
            if getattr(self.bot, "mover_stop_para_entrada", False) and len(pos["feitas"]) == 1:
                # depois da primeira realização o trade não vira prejuízo
                pos["sl"] = pos["preco_entrada"]

    def _fechar(self, pos: Dict, preco_saida: float, motivo: str, ts: int):
        s = 1 if pos["direcao"] == "buy" else -1
        if motivo != "TP":
            preco_saida = preco_saida * (1 - s * self.slip)   # saída a mercado sofre slippage contra
        taxa = preco_saida * pos["qty"] * self.taxa_saida
        pnl_resto = (preco_saida - pos["preco_entrada"]) * pos["qty"] * s - taxa
        pnl = pnl_resto + pos["pnl_parcial"]
        risco = abs(pos["preco_entrada"] - pos["sl_inicial"]) or 1e-9
        self.banca += pnl_resto
        self._pnl_dia += pnl_resto
        self.trades.append({
            "direcao": pos["direcao"], "preco_entrada": round(pos["preco_entrada"], 2),
            "preco_saida": round(preco_saida, 2), "qty": pos["qty_inicial"], "sl": pos["sl_inicial"],
            "tp": pos["tp"], "ts_entrada": pos["ts_entrada"], "ts_saida": ts,
            "duracao_s": round((ts - pos["ts_entrada"]) / 1000, 1), "gatilho": pos["gatilho"],
            "parciais": len(pos["feitas"]), "taxas": round(pos["taxas"] + taxa, 4),
            "pnl": round(pnl, 2), "r": round(pnl / (risco * pos["qty_inicial"]), 2),
            "motivo_saida": motivo, "banca": round(self.banca, 2), "motivo": pos["motivo"]})
        if self.verbose:
            print(f"{ts} SAÍDA {pos['direcao']} @ {preco_saida:.2f} pnl={pnl:+.2f} ({motivo}) banca={self.banca:.2f}")

    def _gerir_pendente(self, pendente: Dict, preco: float, ts: int):
        """
        Ordem limitada esperando no nivel. Executa quando um negocio imprime no preco ou melhor, e expira
        se o preco foi embora sem servir: a leitura era sobre AQUELE nivel, e ela morre junto com ele.
        """
        d = pendente["decisao"]
        tocou = preco <= pendente["preco"] if d["acao"] == "buy" else preco >= pendente["preco"]
        if tocou:
            self.pendentes_executadas += 1
            return self._abrir(d, preco, ts, preco_exec=pendente["preco"]), None
        if ts - pendente["ts"] >= self.espera_limite_ms:
            self.pendentes_expiradas += 1
            return None, None
        return None, pendente

    def _gerir(self, pos: Dict, preco: float, ts: int) -> Optional[Dict]:
        """
        SL/TP conferidos negócio a negócio: sabe-se qual preço veio primeiro, sem o palpite pessimista que o
        backtest de candles precisa fazer quando máxima e mínima cabem no mesmo candle.
        """
        self._parciais(pos, preco, ts)
        if pos["qty"] <= 0:
            self._fechar(pos, preco, "parciais fecharam tudo", ts)
            return None
        self._trailing(pos, preco)
        if pos["direcao"] == "buy":
            if pos["sl"] and preco <= pos["sl"]:
                self._fechar(pos, pos["sl"], "trailing" if pos["trailing_ativo"] else "SL", ts)
                return None
            if pos["tp"] and preco >= pos["tp"]:
                self._fechar(pos, pos["tp"], "TP", ts)
                return None
        else:
            if pos["sl"] and preco >= pos["sl"]:
                self._fechar(pos, pos["sl"], "trailing" if pos["trailing_ativo"] else "SL", ts)
                return None
            if pos["tp"] and preco <= pos["tp"]:
                self._fechar(pos, pos["tp"], "TP", ts)
                return None
        return pos

    # ------------------------------------------------------------------ execução
    def executar(self, negocios: Iterable[Dict]) -> Dict:
        t0 = time.time()
        pos: Optional[Dict] = None
        pendente: Optional[Dict] = None
        ultimo_preco, ultimo_ts = 0.0, 0
        for t in negocios:
            preco, ts = float(t["price"]), int(t["timestamp"])
            ultimo_preco, ultimo_ts = preco, ts
            self._agora_ms = ts
            self._virar_dia(ts)
            if pos:
                pos = self._gerir(pos, preco, ts)
            elif pendente:
                pos, pendente = self._gerir_pendente(pendente, preco, ts)
            for _ in self.motor.ingerir([t]):
                self.barras_fechadas += 1
                if ts >= self._proximo_ctx_ms:
                    self.motor.contexto = self.motor.leitor.ler(preco)
                    self._proximo_ctx_ms = ts + self._intervalo_ctx_ms
                d = self.motor.avaliar(preco)
                self._marcar(d)
                if d["acao"] in ("buy", "sell") and pos is None and self._pode_operar():
                    if self.limitada and d.get("preco_limite"):
                        pendente = {"decisao": d, "preco": float(d["preco_limite"]), "ts": ts}
                    else:
                        pos = self._abrir(d, preco, ts)
                self.curva.append(self.banca)
        if pos:
            self._fechar(pos, ultimo_preco, "fim do backtest", ultimo_ts)
        return self.relatorio(time.time() - t0)

    def _marcar(self, d: Dict):
        self.decisoes[d["acao"]] = self.decisoes.get(d["acao"], 0) + 1
        g = (d.get("fluxo") or {}).get("gatilho")
        if g:
            self.gatilhos[g] = self.gatilhos.get(g, 0) + 1
        if d["acao"] == "hold":
            # agrupa o motivo pela primeira parte da frase: interessa O QUE segurou, não o número exato
            chave = (d.get("motivo") or "")[:48]
            self.motivos[chave] = self.motivos.get(chave, 0) + 1

    # ------------------------------------------------------------------ relatório
    def relatorio(self, tempo: float = 0.0) -> Dict:
        t = self.trades
        ganhos = [x["pnl"] for x in t if x["pnl"] > 0]
        perdas = [x["pnl"] for x in t if x["pnl"] <= 0]
        pico, dd = self.banca_inicial, 0.0
        for v in self.curva:
            pico = max(pico, v)
            dd = max(dd, (pico - v) / pico if pico else 0.0)
        saidas: Dict[str, int] = {}
        for x in t:
            saidas[x["motivo_saida"]] = saidas.get(x["motivo_saida"], 0) + 1
        return {
            "motor": "fluxo", "barras": self.barras_fechadas, "regua": self.motor.agregador.status(),
            "trades": len(t), "ganhos": len(ganhos), "perdas": len(perdas),
            "taxa_acerto": round(len(ganhos) / len(t), 3) if t else None,
            "pnl_total": round(sum(x["pnl"] for x in t), 2),
            "retorno_pct": round((self.banca / self.banca_inicial - 1) * 100, 2),
            "fator_lucro": round(sum(ganhos) / abs(sum(perdas)), 2) if perdas and sum(perdas) else None,
            "r_medio": round(sum(x["r"] for x in t) / len(t), 2) if t else None,
            "duracao_media_s": round(sum(x["duracao_s"] for x in t) / len(t), 1) if t else None,
            "drawdown_max_pct": round(dd * 100, 2), "banca_final": round(self.banca, 2),
            "taxas_totais": round(sum(x["taxas"] for x in t), 2),
            "decisoes": self.decisoes, "gatilhos": self.gatilhos, "saidas": saidas,
            "ordens_limite": {"executadas": self.pendentes_executadas, "expiradas": self.pendentes_expiradas},
            "motivos_de_espera": dict(sorted(self.motivos.items(), key=lambda kv: -kv[1])[:8]),
            "tempo_s": round(tempo, 1), "lista_trades": t,
        }
