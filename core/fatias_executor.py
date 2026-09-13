# core/fatias_executor.py
"""
Executor da estratégia "votação + fatias" (core/estrategia_votacao.py) — o robô que saiu do laboratório.

Ciclo:
    sem posição, candle novo    decide pela votação; se houver lado, abre a 1ª fatia a mercado COM stop e alvo
                                na corretora (valem para a posição inteira) e deixa as outras 4 como ordens
                                limitadas post-only no caminho até o stop
    com posição (todo ciclo)    demo/testnet/real: confere a posição na corretora — cresceu, uma fatia executou;
                                sumiu, o stop ou o alvo executou (cancela o que sobrou no livro e registra a saída)
                                simulador: stop, alvo e fatias pelo candle fechado, na ordem do backtest
    com posição, candle novo    conta os candles; no 24º fecha a mercado (saída por tempo, como no backtest)

O estado da operação (fatias pendentes, stop, alvo, candles) fica em `bot.grade_json`, para sobreviver a um
reinício. Uma fatia que ficou no livro depois de a posição fechar seria uma entrada sem gestão: ao ver a posição
zerada, o executor cancela TODAS as entradas abertas do par nesta subconta.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from core.estrategia_votacao import PADRAO, ConfigVotacao, decidir, quantidade_total
from core.executor_real import TAXA_MAKER

logger = logging.getLogger(__name__)


class FatiasExecutor:
    def __init__(self, executor, cfg: ConfigVotacao = PADRAO):
        self.ex = executor
        self.cfg = cfg
        self.trade: Optional[Dict] = None        # estado da operação aberta

    # ------------------------------------------------------------ util
    def _attr(self, nome, default=None):
        return self.ex._attr(nome, default)

    def _salvar(self):
        self.ex.bot.grade_json = json.dumps({"estrategia": "votacao_fatias", "trade": self.trade}) if self.trade else None
        self.ex.db.commit()

    def carregar(self):
        raw = self._attr("grade_json")
        try:
            d = json.loads(raw) if raw else None
            self.trade = (d or {}).get("trade") if (d or {}).get("estrategia") == "votacao_fatias" else None
        except Exception:
            self.trade = None
        if self.trade and self.ex.posicao is None:
            # a posição fechou enquanto o servidor estava parado: o que sobrou no livro não tem mais gestão
            self._cancelar_pendentes("posição já fechada ao reiniciar")
            self.trade = None
            self._salvar()

    def status(self) -> Optional[Dict]:
        if not self.trade:
            return None
        t = self.trade
        return {"lado": t["lado"], "stop": t["stop"], "alvo": t["alvo"], "candles": t["candles"],
                "horizonte": self.cfg.horizonte, "fatias_executadas": len(t["executadas"]),
                "fatias_pendentes": len(t["pendentes"]),
                "precos_pendentes": [x["preco"] for x in t["pendentes"]], "de": self.cfg.n_entradas}

    def _cancelar_pendentes(self, motivo: str):
        if not self.trade or not self.trade.get("pendentes"):
            return
        if self.ex.ordens.simulado:
            self.trade["pendentes"] = []
            return
        try:
            n = self.ex.con.cancelar_entradas_abertas(self.ex.par)
            if n:
                self.ex._log(acao="hold", tipo_operacao="info", preco=None, motivo=f"{n} fatia(s) pendente(s) cancelada(s): {motivo}")
        except Exception as e:
            logger.warning("[%s] cancelar fatias pendentes falhou: %s", self._attr("nome"), e)
        self.trade["pendentes"] = []

    def _encerrar(self):
        self.trade = None
        self._salvar()

    # ------------------------------------------------------------ ciclo
    def ciclo(self, ohlcv, preco: float, candle_novo: bool):
        if self.trade is not None:
            self._gerir(ohlcv, preco, candle_novo)
            return
        if not candle_novo:
            return
        d = decidir(ohlcv, self.cfg)
        self._persistir(d, preco)
        if d["acao"] not in ("buy", "sell"):
            return
        pode, motivo = self.ex._pode_operar()
        if not pode:
            self.ex._log(acao="hold", tipo_operacao="info", preco=preco, motivo=f"Sinal {d['acao']} ignorado: {motivo}")
            return
        self._abrir(d, preco)

    def _persistir(self, d: Dict, preco: float):
        lado = d.get("lado", 0)
        votos = [i for i, v in (d.get("votos") or {}).items() if lado and v == lado]
        registro = {"acao": d["acao"], "motivo": d.get("motivo"), "tp": d.get("tp"), "sl": d.get("sl"), "votos": votos,
                    "cenario": f"votação {self.cfg.votos_min} de {len(self.cfg.indicadores)}", "fase_onda": None,
                    "probabilidade": None}
        self.ex.estado["ultima_decisao"] = {k: registro.get(k) for k in ("acao", "motivo", "fase_onda", "cenario", "probabilidade", "tp", "sl", "votos")}
        if d.get("candle_ts"):
            self.ex._persistir_decisao(registro, int(d["candle_ts"]), preco)

    # ------------------------------------------------------------ entrada
    def _abrir(self, d: Dict, preco: float):
        lado = d["lado"]
        banca = self.ex._banca()
        q_total = quantidade_total(banca, float(self._attr("risco_pct", 0.01) or 0.01), lado, preco, d["risco"], self.cfg)
        teto = banca * float(self._attr("max_alocacao_pct", 0.5) or 0.5) * max(int(getattr(self.ex, "alavancagem", 1) or 1), 1) / preco
        q_total = min(q_total, teto)
        q = self.ex.con.arredondar_quantidade(self.ex.par, q_total / self.cfg.n_entradas)
        if q <= 0:
            self.ex._log(acao="hold", tipo_operacao="info", preco=preco,
                         motivo=f"Fatia de {q_total / self.cfg.n_entradas:.5f} abaixo do mínimo negociável: entrada recusada")
            return
        pm = self._attr("position_mode", "one-way")
        exec_ = self.ex.ordens.abrir(self.ex.par, d["acao"], q, d["sl"], d["tp"], pm, preco_ref=preco)
        d = {**d, "motivo": f"[fatia 1 de {self.cfg.n_entradas}] {d['motivo']}"}
        self.ex._registrar_entrada(d, exec_, exec_["preco_exec"], d["sl"], d["tp"])
        pendentes = []
        for k, nivel in enumerate(d["niveis"][1:], start=2):
            try:
                ped = self.ex.ordens.abrir_limite(self.ex.par, d["acao"], q, nivel, None, None, pm)
                pendentes.append({"k": k, "preco": ped["preco"], "q": ped["quantidade"], "ordem_id": ped["ordem_id"]})
            except Exception as e:
                logger.warning("[%s] fatia %d não foi enviada: %s", self._attr("nome"), k, e)
        self.trade = {"lado": lado, "stop": d["sl"], "alvo": d["tp"], "risco": d["risco"], "candles": 0,
                      "ts_sinal": d.get("candle_ts"), "q": q,
                      "executadas": [{"k": 1, "preco": exec_["preco_exec"], "q": exec_["quantidade"]}], "pendentes": pendentes}
        self._salvar()
        self.ex._log(acao=d["acao"], tipo_operacao="info", preco=preco, sl=d["sl"], tp=d["tp"], quantidade=q,
                     motivo=f"{len(pendentes)} fatias limitadas no livro: " + ", ".join(f"{p['preco']:,.0f}" for p in pendentes))

    # ------------------------------------------------------------ gestão
    def _gerir(self, ohlcv, preco: float, candle_novo: bool):
        t = self.trade
        if self.ex.posicao is None:
            self._cancelar_pendentes("posição não existe mais")
            self._encerrar()
            return
        if self.ex.ordens.simulado:
            if candle_novo:
                self._gerir_simulado(ohlcv[-1])
            return
        try:
            pos_ex = self.ex.con.obter_posicao(self.ex.par)
        except Exception as e:
            logger.warning("[%s] consulta de posição falhou: %s", self._attr("nome"), e)
            return
        if pos_ex is None:
            # stop ou alvo executados na corretora: o que sobrou no livro vira entrada sem dono
            self._cancelar_pendentes("stop ou alvo executado")
            self.ex._registrar_saida(preco, "SL/TP executado pela exchange", pnl_exchange=True)
            self._encerrar()
            return
        self._sincronizar(pos_ex)
        if candle_novo:
            t["candles"] += 1
            if t["candles"] >= self.cfg.horizonte:
                self._cancelar_pendentes("saída por tempo")
                self.ex.fechar_posicao(f"Saída por tempo ({self.cfg.horizonte} candles)", preco)
                self._encerrar()
                return
            self._salvar()

    def _sincronizar(self, pos_ex: Dict):
        """A posição cresceu na corretora: fatias executaram. Atualiza quantidade, preço médio e taxa."""
        pos = self.ex.posicao
        q_ex, q_db = float(pos_ex["quantidade"]), float(pos.quantidade or 0)
        if q_ex <= q_db + 1e-9:
            return
        novas = max(1, round((q_ex - q_db) / (self.trade["q"] or q_ex)))
        feitas = self.trade["pendentes"][:novas]
        self.trade["pendentes"] = self.trade["pendentes"][novas:]
        for f in feitas:
            self.trade["executadas"].append(f)
            pos.taxas = float(pos.taxas or 0) + f["preco"] * f["q"] * TAXA_MAKER
        pos.quantidade = q_ex
        pos.quantidade_inicial = q_ex
        pos.preco_entrada = float(pos_ex["preco_entrada"] or pos.preco_entrada)
        self._salvar()
        self.ex._log(acao="buy" if self.trade["lado"] == 1 else "sell", tipo_operacao="info", preco=pos.preco_entrada,
                     quantidade=q_ex, motivo=f"{len(feitas)} fatia(s) executada(s): {len(self.trade['executadas'])} de "
                                             f"{self.cfg.n_entradas}, preço médio {pos.preco_entrada:,.1f}")

    def _executar_fatia_simulada(self, f: Dict):
        """Uma fatia limitada executada no simulador: soma à posição, recalcula o preço médio e a taxa."""
        t, pos = self.trade, self.ex.posicao
        q0, p0 = float(pos.quantidade), float(pos.preco_entrada)
        pos.quantidade = q0 + f["q"]
        pos.quantidade_inicial = pos.quantidade
        pos.preco_entrada = (q0 * p0 + f["q"] * f["preco"]) / pos.quantidade
        pos.taxas = float(pos.taxas or 0) + f["preco"] * f["q"] * TAXA_MAKER
        t["executadas"].append(f)
        t["pendentes"].remove(f)

    def _gerir_simulado(self, c):
        """Simulador: a mesma ordem do backtest — stop, alvo, fatias novas, tempo."""
        t, pos = self.trade, self.ex.posicao
        hi, lo, close = float(c[2]), float(c[3]), float(c[4])
        s = t["lado"]
        t["candles"] += 1
        # numa ida até o stop, as fatias no meio do caminho são tomadas ANTES dele, como na corretora. Antes o stop
        # vinha primeiro e o simulador perdia só a 1ª fatia (o mesmo defeito do motor de backtest, commit 35413cad).
        if (lo <= t["stop"]) if s == 1 else (hi >= t["stop"]):
            for f in list(t["pendentes"]):
                self._executar_fatia_simulada(f)
        if (lo <= t["stop"]) if s == 1 else (hi >= t["stop"]):
            self._cancelar_pendentes("stop")
            self.ex._registrar_saida(t["stop"], "Stop loss (simulado)")
            self._encerrar()
            return
        if (hi >= t["alvo"]) if s == 1 else (lo <= t["alvo"]):
            self._cancelar_pendentes("alvo")
            self.ex._registrar_saida(t["alvo"], "Take profit (simulado)", taxa_saida=t["alvo"] * float(pos.quantidade) * TAXA_MAKER)
            self._encerrar()
            return
        for f in list(t["pendentes"]):
            if (lo <= f["preco"]) if s == 1 else (hi >= f["preco"]):
                self._executar_fatia_simulada(f)
        if t["candles"] >= self.cfg.horizonte:
            self._cancelar_pendentes("saída por tempo")
            self.ex._registrar_saida(close, f"Saída por tempo ({self.cfg.horizonte} candles, simulado)")
            self._encerrar()
            return
        self._salvar()
