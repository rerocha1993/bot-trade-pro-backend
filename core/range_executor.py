# core/range_executor.py
"""
Executor do JOGO DO RANGE do Tradeiros (core/range_tradeiros.py) — a mesma leitura do backtest, ao vivo.

A cada bloco de 30 min fechado, sem operação:
    lê o range (merge adaptativo dos dias anteriores), os toques e o desvio do dia com `leitura_ao_vivo`, que é o
    mesmo código do backtest; o contexto de order flow (long/short de contas contra a mediana de 30 dias) só
    deixa entrar com a multidão presa do outro lado. Havendo plano, arma a escada de 5 fatias na zona da borda:
    as que o preço já passou saem a mercado, o resto como limitadas post-only, todas com o stop além do extremo do
    range e o alvo final na borda oposta.

Com a escada armada e nada executado: cancela depois de 8 blocos, ou se o preço chegar no POC antes (o trade
fugiu sem a gente).

Com posição:
    tirar o risco   no POC ou no 1:1 (o que vier antes) realiza metade, leva o stop para o preço médio e cancela
                    as fatias que sobraram
    alvo            a borda oposta (TP na corretora)
    tempo           144 blocos (3 dias) depois da primeira fatia, fecha a mercado

O estado fica em `bot.grade_json` para sobreviver a um reinício. O simulador executa pelo candle fechado, na
ordem do backtest: stop, tirar o risco, alvo, tempo, fatias novas.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.contexto_derivativos import LeitorLSR
from core.executor_real import TAXA_MAKER
from core.range_tradeiros import ParametrosRange, leitura_ao_vivo
from core.tpo_sessao import BLOCO_MS, DIA_MS, blocos_30m

logger = logging.getLogger(__name__)

ESTRATEGIA = "range_tradeiros"


@dataclass(frozen=True)
class ConfigRangeRobo:
    jogada: str = "borda"
    usar_presos: bool = True            # contexto de order flow (estudo das bordas)
    dias_historico: int = 23            # até 20 dias de merge + hoje + folga
    p: ParametrosRange = field(default_factory=ParametrosRange)


class RangeExecutor:
    def __init__(self, executor, cfg: ConfigRangeRobo = ConfigRangeRobo(), leitor_lsr: Optional[LeitorLSR] = None):
        self.ex = executor
        self.cfg = cfg
        self.lsr = leitor_lsr or LeitorLSR()
        self.trade: Optional[Dict] = None
        self.ultima_leitura: Optional[Dict] = None

    # ------------------------------------------------------------ util
    def _attr(self, nome, default=None):
        return self.ex._attr(nome, default)

    def _pm(self) -> str:
        return self._attr("position_mode", "one-way")

    def _salvar(self):
        self.ex.bot.grade_json = json.dumps({"estrategia": ESTRATEGIA, "trade": self.trade}) if self.trade else None
        self.ex.db.commit()

    def carregar(self):
        raw = self._attr("grade_json")
        try:
            d = json.loads(raw) if raw else None
            self.trade = (d or {}).get("trade") if (d or {}).get("estrategia") == ESTRATEGIA else None
        except Exception:
            self.trade = None
        if self.trade and self.trade["executadas"] and self.ex.posicao is None:
            # a posição fechou enquanto o servidor estava parado: o que sobrou no livro não tem mais gestão
            self._cancelar_pendentes("posição já fechada ao reiniciar")
            self.trade = None
            self._salvar()

    def status(self) -> Optional[Dict]:
        base = {"leitura": self.ultima_leitura}
        if not self.trade:
            return base
        t = self.trade
        return {**base, "lado": t["lado"], "stop": t["stop"], "alvo1": t["alvo1"], "alvo2": t["alvo2"],
                "parcial_feita": t["parcial_feita"], "blocos": t["blocos"], "fatias_executadas": len(t["executadas"]),
                "fatias_pendentes": len(t["pendentes"]),
                "precos_pendentes": [x["preco"] for x in t["pendentes"]], "de": self.cfg.p.n_fatias}

    def _cancelar_pendentes(self, motivo: str):
        if not self.trade or not self.trade.get("pendentes"):
            return
        if not self.ex.ordens.simulado:
            try:
                n = self.ex.con.cancelar_entradas_abertas(self.ex.par)
                if n:
                    self.ex._log(acao="hold", tipo_operacao="info", preco=None,
                                 motivo=f"{n} fatia(s) pendente(s) cancelada(s): {motivo}")
            except Exception as e:
                logger.warning("[%s] cancelar fatias pendentes falhou: %s", self._attr("nome"), e)
        self.trade["pendentes"] = []

    def _encerrar(self):
        self.trade = None
        self._salvar()

    # ------------------------------------------------------------ leitura
    def _blocos(self) -> List[tuple]:
        """Blocos de 30 min FECHADOS dos últimos `dias_historico` dias (a mesma régua do backtest)."""
        agora = int(time.time() * 1000)
        desde = (agora // DIA_MS - self.cfg.dias_historico) * DIA_MS
        candles = self.ex._con_publico.obter_ohlcv_historico(self.ex.par, "30m", desde)
        fechados = [c for c in candles if c[0] + BLOCO_MS <= agora]
        return blocos_30m(fechados)

    def _filtro(self):
        if not self.cfg.usar_presos:
            return None
        ctx = self.lsr.contexto()
        if ctx is None:
            return lambda ts, lado: False           # sem o contexto, o método não entra
        return ctx.filtro()

    def ler(self) -> Dict:
        blocos = self._blocos()
        leitura = leitura_ao_vivo(blocos, self.cfg.jogada, self.cfg.p, self._filtro())
        leitura["candle_ts"] = blocos[-1][0] if blocos else None
        return leitura

    # ------------------------------------------------------------ ciclo
    def ciclo(self, ohlcv, preco: float, candle_novo: bool):
        if self.trade is not None:
            self._gerir(ohlcv, preco, candle_novo)
            return
        if not candle_novo:
            return
        try:
            leitura = self.ler()
        except Exception as e:
            logger.warning("[%s] leitura do range falhou: %s", self._attr("nome"), e)
            return
        self._persistir(leitura, preco)
        pl = leitura["plano"]
        if pl is None:
            return
        pode, motivo = self.ex._pode_operar()
        if not pode:
            self.ex._log(acao="hold", tipo_operacao="info", preco=preco, motivo=f"Plano do range ignorado: {motivo}")
            return
        self._armar(pl, preco, leitura.get("candle_ts"))

    def _persistir(self, leitura: Dict, preco: float):
        pl, ctx = leitura["plano"], leitura["contexto"]
        lsr = self.lsr.contexto() if self.cfg.usar_presos else None
        agora = int(time.time() * 1000)
        faixa = {"val": round(float(ctx.val), 1), "poc": round(float(ctx.poc), 1), "vah": round(float(ctx.vah), 1),
                 "minima": round(float(ctx.minima), 1), "maxima": round(float(ctx.maxima), 1), "dias": int(ctx.dias),
                 "valido": bool(ctx.valido)} if ctx else None
        fluxo = {"long_short": lsr.atual(agora), "mediana_30d": lsr.mediana(agora)} if lsr else None
        self.ultima_leitura = {"range": faixa, "toques": leitura.get("toques"), "aceitacao": leitura.get("aceitacao"),
                               "long_short": fluxo, "motivo": leitura["motivo"]}
        acao = ("buy" if pl.lado == 1 else "sell") if pl else "hold"
        registro = {"acao": acao, "motivo": leitura["motivo"], "tp": pl.alvo2 if pl else None, "sl": pl.stop if pl else None,
                    "votos": [], "cenario": f"range {ctx.dias} dias" if ctx else "sem range", "fase_onda": None,
                    "probabilidade": None, "niveis": {"range": faixa, "fatias": [round(x, 1) for x in pl.niveis] if pl else None},
                    "fluxo": fluxo}
        self.ex.estado["ultima_decisao"] = {k: registro.get(k) for k in ("acao", "motivo", "fase_onda", "cenario", "probabilidade", "tp", "sl", "votos")}
        if leitura.get("candle_ts"):
            self.ex._persistir_decisao(registro, int(leitura["candle_ts"]), preco)

    # ------------------------------------------------------------ entrada
    def _armar(self, pl, preco: float, candle_ts: Optional[int]):
        lado, acao = pl.lado, "buy" if pl.lado == 1 else "sell"
        banca = self.ex._banca()
        risco = banca * float(self._attr("risco_pct", 0.01) or 0.01)
        q_total = risco / abs(pl.medio_todas - pl.stop)                 # todas as fatias + stop = perde o risco
        teto = banca * float(self._attr("max_alocacao_pct", 0.5) or 0.5) * max(int(getattr(self.ex, "alavancagem", 1) or 1), 1) / preco
        q = self.ex.con.arredondar_quantidade(self.ex.par, min(q_total, teto) / len(pl.niveis))
        if q <= 0:
            self.ex._log(acao="hold", tipo_operacao="info", preco=preco,
                         motivo=f"Fatia de {min(q_total, teto) / len(pl.niveis):.5f} abaixo do mínimo negociável: plano recusado")
            return
        self.trade = {"lado": lado, "niveis": list(pl.niveis), "stop": pl.stop, "stop_inicial": pl.stop, "alvo1": pl.alvo1,
                      "alvo2": pl.alvo2, "q": q, "executadas": [], "pendentes": [], "blocos_armado": 0, "blocos": 0,
                      "parcial_feita": False, "motivo": pl.motivo, "ts_sinal": candle_ts}
        passou = [n for n in pl.niveis if (n >= preco if lado == 1 else n <= preco)]
        no_livro = [n for n in pl.niveis if n not in passou]
        pm = self._pm()
        if passou:
            # o preço já está além destas fatias: uma limitada post-only seria recusada; sai a mercado (melhor preço)
            exec_ = self.ex.ordens.abrir(self.ex.par, acao, q * len(passou), pl.stop, pl.alvo2, pm, preco_ref=preco)
            self.trade["executadas"] = [{"preco": exec_["preco_exec"], "q": exec_["quantidade"] / len(passou)} for _ in passou]
            d = {"acao": acao, "motivo": f"[{len(passou)} de {len(pl.niveis)} fatias a mercado] {pl.motivo}",
                 "cenario": "range tradeiros"}
            self.ex._registrar_entrada(d, exec_, exec_["preco_exec"], pl.stop, pl.alvo2)
        for nivel in no_livro:
            try:
                ped = self.ex.ordens.abrir_limite(self.ex.par, acao, q, nivel, pl.stop, pl.alvo2, pm)
                self.trade["pendentes"].append({"preco": ped["preco"], "q": ped["quantidade"], "ordem_id": ped["ordem_id"]})
            except Exception as e:
                logger.warning("[%s] fatia a %.1f não foi enviada: %s", self._attr("nome"), nivel, e)
        self._salvar()
        self.ex._log(acao=acao, tipo_operacao="info", preco=preco, sl=pl.stop, tp=pl.alvo2, quantidade=q,
                     motivo=f"Escada armada: {len(self.trade['pendentes'])} limitada(s) em "
                            + ", ".join(f"{p['preco']:,.0f}" for p in self.trade["pendentes"])
                            + f" | tirar o risco em {pl.alvo1:,.0f} ou 1:1")

    # ------------------------------------------------------------ gestão
    def _gerir(self, ohlcv, preco: float, candle_novo: bool):
        if self.ex.ordens.simulado:
            if candle_novo:
                self._gerir_simulado(ohlcv[-1])
            return
        t = self.trade
        try:
            pos_ex = self.ex.con.obter_posicao(self.ex.par)
        except Exception as e:
            logger.warning("[%s] consulta de posição falhou: %s", self._attr("nome"), e)
            return
        if self.ex.posicao is None:
            if pos_ex and pos_ex["side"] == ("buy" if t["lado"] == 1 else "sell"):
                self._adotar(pos_ex)                    # fatias limitadas executaram: nasce a posição
            elif candle_novo:
                self._envelhecer_escada(ohlcv[-1])
            return
        if pos_ex is None:
            self._cancelar_pendentes("stop ou alvo executado")
            self.ex._registrar_saida(preco, "SL/TP executado pela exchange", pnl_exchange=True)
            self._encerrar()
            return
        self._sincronizar(pos_ex)
        if not t["parcial_feita"] and self._chegou_no_gatilho(preco, preco):
            self._tirar_o_risco(preco)
        if candle_novo:
            t["blocos"] += 1
            if t["blocos"] >= self.cfg.p.tempo_max:
                self._cancelar_pendentes("saída por tempo")
                self.ex.fechar_posicao(f"Saída por tempo ({self.cfg.p.tempo_max} blocos de 30 min)", preco)
                self._encerrar()
                return
            self._salvar()

    def _gatilho(self) -> float:
        """Tirar o risco: no POC ou no 1:1 do preço médio, o que vier antes."""
        t, pos = self.trade, self.ex.posicao
        medio = float(pos.preco_entrada)
        um_r = medio + t["lado"] * abs(medio - t["stop_inicial"])
        return min(t["alvo1"], um_r) if t["lado"] == 1 else max(t["alvo1"], um_r)

    def _chegou_no_gatilho(self, hi: float, lo: float) -> bool:
        g = self._gatilho()
        return hi >= g if self.trade["lado"] == 1 else lo <= g

    def _envelhecer_escada(self, c):
        """Escada no livro sem nada executado: morre em 8 blocos ou se o preço fugir até o POC."""
        t = self.trade
        t["blocos_armado"] += 1
        hi, lo = float(c[2]), float(c[3])
        fugiu = hi >= t["alvo1"] if t["lado"] == 1 else lo <= t["alvo1"]
        if t["blocos_armado"] >= self.cfg.p.espera_armado or fugiu:
            self._cancelar_pendentes("o preço foi até o POC sem executar" if fugiu else "escada venceu sem execução")
            self.ex._log(acao="hold", tipo_operacao="info", preco=float(c[4]),
                         motivo="Escada do range cancelada: " + ("o preço foi até o POC sem executar" if fugiu else
                                                                 f"{self.cfg.p.espera_armado} blocos sem execução"))
            self._encerrar()
            return
        self._salvar()

    def _adotar(self, pos_ex: Dict):
        t = self.trade
        q, p = float(pos_ex["quantidade"]), float(pos_ex["preco_entrada"])
        n = max(1, round(q / (t["q"] or q)))
        t["executadas"], t["pendentes"] = t["pendentes"][:n], t["pendentes"][n:]
        exec_ = {"ordem_id": (t["executadas"][0].get("ordem_id") if t["executadas"] else None), "preco_exec": p,
                 "quantidade": q, "simulado": False, "taxa": p * q * TAXA_MAKER}
        d = {"acao": "buy" if t["lado"] == 1 else "sell", "cenario": "range tradeiros",
             "motivo": f"[{n} de {len(t['niveis'])} fatias limitadas executadas] {t['motivo']}"}
        self.ex._registrar_entrada(d, exec_, p, t["stop"], t["alvo2"])
        self._salvar()

    def _sincronizar(self, pos_ex: Dict):
        """A posição cresceu na corretora: fatias executaram. Atualiza quantidade, preço médio e taxa."""
        pos, t = self.ex.posicao, self.trade
        q_ex, q_db = float(pos_ex["quantidade"]), float(pos.quantidade or 0)
        if q_ex <= q_db + 1e-9 or t["parcial_feita"]:
            return
        novas = max(1, round((q_ex - q_db) / (t["q"] or q_ex)))
        feitas, t["pendentes"] = t["pendentes"][:novas], t["pendentes"][novas:]
        for f in feitas:
            t["executadas"].append(f)
            pos.taxas = float(pos.taxas or 0) + f["preco"] * f["q"] * TAXA_MAKER
        pos.quantidade = q_ex
        pos.quantidade_inicial = q_ex
        pos.preco_entrada = float(pos_ex["preco_entrada"] or pos.preco_entrada)
        self._salvar()
        self.ex._log(acao="buy" if t["lado"] == 1 else "sell", tipo_operacao="info", preco=pos.preco_entrada, quantidade=q_ex,
                     motivo=f"{len(feitas)} fatia(s) executada(s): {len(t['executadas'])} de {len(t['niveis'])}, "
                            f"preço médio {pos.preco_entrada:,.1f}")

    def _tirar_o_risco(self, preco_ref: float):
        """Realiza metade da mão, leva o stop para o preço médio e cancela as fatias que sobraram."""
        t, pos = self.trade, self.ex.posicao
        self._cancelar_pendentes("risco tirado")
        q_real = self.ex.con.arredondar_quantidade(self.ex.par, float(pos.quantidade) * self.cfg.p.realizar)
        medio = float(pos.preco_entrada)
        if q_real > 0:
            try:
                r = self.ex.ordens.reduzir(self.ex.par, pos.direcao, q_real, self._pm(), preco_ref=preco_ref)
            except Exception as e:
                logger.warning("[%s] realização da metade falhou: %s", self._attr("nome"), e)
                return
            feita = float(r.get("quantidade") or 0)
            if feita > 0:
                pexec = float(r.get("preco_exec") or preco_ref)
                taxa = pexec * feita * TAXA_MAKER if self.ex.ordens.simulado else float(r.get("taxa") or 0)
                lucro = (pexec - medio) * feita * t["lado"] - taxa
                pos.quantidade = round(float(pos.quantidade) - feita, 8)
                pos.pnl_parcial = round(float(pos.pnl_parcial or 0) + lucro, 8)
                self.ex.estado["pnl_dia"] += lucro
                self.ex.db.commit()
                self.ex._log(acao="parcial", tipo_operacao="saida_parcial", direcao=pos.direcao, preco=pexec, quantidade=feita,
                             resultado=lucro, motivo="Tirar o risco: metade realizada no POC/1:1")
        stop = self.ex.con.arredondar_preco(self.ex.par, medio)
        if self.ex.ordens.atualizar_stop(self.ex.par, stop, t["alvo2"], self._pm(), pos.direcao):
            pos.sl = stop
            t["stop"] = stop
        t["parcial_feita"] = True
        self._salvar()
        self.ex._log(acao="ajuste_sl", tipo_operacao="info", preco=preco_ref, sl=stop, motivo="Stop no zero a zero depois de tirar o risco")

    def _executar_fatia_simulada(self, f: Dict):
        """Uma fatia limitada executada no simulador: abre a posição na primeira, soma nas seguintes."""
        t = self.trade
        s = t["lado"]
        t["pendentes"].remove(f)
        t["executadas"].append(f)
        if self.ex.posicao is None:
            exec_ = {"ordem_id": f["ordem_id"], "preco_exec": f["preco"], "quantidade": f["q"], "simulado": True,
                     "taxa": f["preco"] * f["q"] * TAXA_MAKER}
            d = {"acao": "buy" if s == 1 else "sell", "cenario": "range tradeiros",
                 "motivo": f"[fatia limitada executada] {t['motivo']}"}
            self.ex._registrar_entrada(d, exec_, f["preco"], t["stop"], t["alvo2"])
            return
        p0 = self.ex.posicao
        q0, m0 = float(p0.quantidade), float(p0.preco_entrada)
        p0.quantidade = q0 + f["q"]
        p0.quantidade_inicial = p0.quantidade
        p0.preco_entrada = (q0 * m0 + f["q"] * f["preco"]) / p0.quantidade
        p0.taxas = float(p0.taxas or 0) + f["preco"] * f["q"] * TAXA_MAKER

    def _gerir_simulado(self, c):
        """Simulador: a ordem do backtest (passo_posicao) — stop, tirar o risco, alvo, tempo, fatias novas."""
        t, pos = self.trade, self.ex.posicao
        hi, lo, close = float(c[2]), float(c[3]), float(c[4])
        s = t["lado"]
        # numa ida até o stop, as fatias no meio do caminho são tomadas ANTES dele (como em passo_posicao). Antes, sem
        # posição, um bloco que atravessava a escada até o stop deixava a posição ABERTA até o bloco seguinte.
        if t["pendentes"] and ((lo <= t["stop"]) if s == 1 else (hi >= t["stop"])):
            for f in list(t["pendentes"]):
                self._executar_fatia_simulada(f)
            pos = self.ex.posicao
        if pos is not None:
            t["blocos"] += 1
            if (lo <= t["stop"]) if s == 1 else (hi >= t["stop"]):
                self._cancelar_pendentes("stop")
                self.ex._registrar_saida(t["stop"], "Zero a zero (simulado)" if t["parcial_feita"] else "Stop loss (simulado)")
                self._encerrar()
                return
            if not t["parcial_feita"] and self._chegou_no_gatilho(hi, lo):
                self._tirar_o_risco(self._gatilho())
                pos = self.ex.posicao
            if (hi >= t["alvo2"]) if s == 1 else (lo <= t["alvo2"]):
                self._cancelar_pendentes("alvo")
                self.ex._registrar_saida(t["alvo2"], "Alvo na borda oposta (simulado)",
                                         taxa_saida=t["alvo2"] * float(pos.quantidade) * TAXA_MAKER)
                self._encerrar()
                return
            if t["blocos"] >= self.cfg.p.tempo_max:
                self._cancelar_pendentes("saída por tempo")
                self.ex._registrar_saida(close, f"Saída por tempo ({self.cfg.p.tempo_max} blocos, simulado)")
                self._encerrar()
                return
        executou = False
        for f in list(t["pendentes"]):
            if (lo <= f["preco"]) if s == 1 else (hi >= f["preco"]):
                self._executar_fatia_simulada(f)
                executou = True
        if self.ex.posicao is None and not executou:
            self._envelhecer_escada(c)
            return
        self._salvar()
