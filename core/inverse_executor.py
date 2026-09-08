# core/inverse_executor.py
"""
Executor do modo inverse: GRADE de acumulação de BTC (short-only, sem stop de preço, entradas escalonadas).

Ciclo (a cada candle FECHADO do timeframe do bot, 4h por padrão):
    1. range: só opera com range APROVADO pelo usuário (bot.range_low/high, range_status 'aprovado'); sem range,
       publica uma proposta (status 'proposto') a partir da contagem mestre no diário e espera
    2. grade: fatias de Fibonacci (0..100% + extensões 127,2% / 161,8%), cada uma com 3 sub-fatias progressivas;
       vende quando a máxima do candle toca o preço da fatia, recompra quando a mínima toca o nível abaixo
       (toda recompra é lucro em BTC). Estado da grade persistido em bot.grade_json
    3. short de base: com a contagem mestre (trava ou primário) de baixa e alvo abaixo do fundo, as fatias mais
       baixas só recompram no alvo de Elliott
    4. saída de CENÁRIO (opcional, bot.saida_estrutural): se a contagem virou impulso de alta acima do topo,
       fecha as fatias abertas (aceita perda em BTC) e libera a grade para uma nova correção
    5. grade concluída: fechamento abaixo do fundo sem fatia aberta -> range_status 'concluido', nova proposta
Em testnet/real as execuções são ordens a mercado no fechamento do candle que tocou o nível (aproximação das
ordens limitadas); em simulador o preenchimento é no preço do nível.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional

from core.inverse_grade import GradeInversa, Fatia
from core.inverse_range import propor_range
from models.decisao_bot import DecisaoBot
from models.posicao_bot import PosicaoBot

logger = logging.getLogger(__name__)
TAXA_MAKER = 0.0002


class InverseRangeExecutor:
    def __init__(self, executor):
        self.ex = executor
        self.bot = executor.bot
        self.db = executor.db
        self.par = executor.par
        self.grade: Optional[GradeInversa] = None
        self.posicao: Optional[PosicaoBot] = None
        self._mestre_cache: Optional[Dict] = None
        self._mestre_ts = 0.0

    def _attr(self, nome, default=None):
        v = getattr(self.bot, nome, None)
        return default if v is None else v

    # ------------------------------------------------------------ banca
    def _banca_btc(self) -> float:
        banca = float(self._attr("banca", 0) or 0)
        if self.ex.modo != "simulador" and self.ex.con.pode_enviar_ordens:
            try:
                banca = self.ex.con.obter_saldo("BTC")["total"] or banca
            except Exception:
                pass
        return banca

    # ------------------------------------------------------------ persistência da grade
    def carregar(self):
        self.posicao = self.db.query(PosicaoBot).filter_by(bot_id=self._attr("id"), status="aberta").order_by(PosicaoBot.id.desc()).first()
        raw = self._attr("grade_json")
        if raw and self._attr("range_status") == "aprovado":
            try:
                d = json.loads(raw)
                self.grade = GradeInversa(d["low"], d["high"], pesos={float(k): v for k, v in d["pesos"].items()}, subfatias=d.get("subfatias", 3),
                                          fatias=[Fatia(**f) for f in d["fatias"]], btc_realizado=d.get("btc_realizado", 0.0),
                                          taxas_btc=d.get("taxas_btc", 0.0))
            except Exception as e:
                logger.warning("grade salva inválida, recriando: %s", e)
                self.grade = None
        if self.grade is None and self._attr("range_status") == "aprovado" and self._attr("range_low") and self._attr("range_high"):
            self.grade = self._nova_grade()

    def _nova_grade(self) -> GradeInversa:
        pesos = None
        try:
            esc = json.loads(self._attr("escada_json") or "null")
            if esc:
                pesos = {float(k): float(v) for k, v in esc.items()}
        except Exception:
            pesos = None
        g = GradeInversa(float(self._attr("range_low")), float(self._attr("range_high")), pesos=pesos or dict(GradeInversa.__dataclass_fields__["pesos"].default_factory()))
        self._salvar_grade(g)
        return g

    def _salvar_grade(self, g: Optional[GradeInversa]):
        if g is None:
            self.bot.grade_json = None
        else:
            self.bot.grade_json = json.dumps({"low": g.low, "high": g.high, "pesos": {str(k): v for k, v in g.pesos.items()}, "subfatias": g.subfatias,
                                              "btc_realizado": g.btc_realizado, "taxas_btc": g.taxas_btc,
                                              "fatias": [f.__dict__ for f in g.fatias]})
        self.db.commit()

    # ------------------------------------------------------------ mestre
    def leitura_mestre(self, preco: float) -> Dict:
        if self._mestre_cache and time.time() - self._mestre_ts < 3600:
            return self._mestre_cache
        out: Dict = {}
        try:
            from services.elliott_mestre_service import ElliottMestreService
            svc = ElliottMestreService(self.db, self.ex._con_publico)
            trava = svc.trava_ativa(self.par, preco)
            m = svc.calcular(self.par)
            prim = m["graus"].get("primario") or {}
            ciclo = m["graus"].get("ciclo") or {}
            trader = m.get("trader") or {}
            out = {"trava": trava, "primario": prim.get("primario"), "pivots": prim.get("pivots", []), "regime": prim.get("regime"),
                   "ciclo": {"prob_bull": ciclo.get("prob_bull", 0), "fase": ciclo.get("fase")},
                   "trader": {"direcao": trader.get("direcao"), "superciclo": (trader.get("superciclo") or {}).get("estado"),
                              "leitura": (trader.get("superciclo") or {}).get("leitura")},
                   "guia": trava if trava and trava.get("status") == "ativa" else prim.get("primario")}
        except Exception as e:
            logger.warning("leitura mestre indisponível: %s", e)
        self._mestre_cache, self._mestre_ts = out, time.time()
        return out

    def propor(self, preco: float, leitura: Dict):
        prop = propor_range(leitura.get("pivots", []), preco, leitura.get("regime"), leitura.get("primario"), exigir_corretivo=True)
        if prop and prop.get("valido") and self._attr("range_status") not in ("proposto", "aprovado"):
            self.bot.range_low, self.bot.range_high = prop["low"], prop["high"]
            self.bot.range_status, self.bot.range_motivo = "proposto", prop["motivo"][:255]
            self.db.commit()
            self.ex.alertas.info(f"{self._attr('nome')}: range proposto {prop['low']:.0f}-{prop['high']:.0f}. Aprove em POST /inverse/{self._attr('id')}/range/aprovar")
        return prop

    # ------------------------------------------------------------ ordens
    def _executar(self, execs, preco_mercado: float):
        """Aplica as execuções da grade na posição (banco) e, em testnet/real, envia as ordens."""
        if not execs:
            return
        for e in execs:
            contratos = float(e["contratos"])
            if contratos <= 0:
                continue
            preco = e["preco"]
            if not self.ex.ordens.simulado:
                try:
                    lado = "sell" if e["tipo"] == "venda" else "buy"
                    r = self.ex.con.criar_ordem(self.par, lado, contratos, tipo="market", reduce_only=(lado == "buy"))
                    preco = float(r.get("average") or r.get("price") or preco_mercado)
                except Exception as ex:
                    logger.error("ordem inverse falhou: %s", ex)
                    continue
            if e["tipo"] == "venda":
                if self.posicao:
                    q0, e0 = float(self.posicao.quantidade), float(self.posicao.preco_entrada)
                    q1 = q0 + contratos
                    self.posicao.preco_entrada = q1 / (q0 / e0 + contratos / preco)
                    self.posicao.quantidade = q1
                else:
                    self.posicao = PosicaoBot(bot_id=self._attr("id"), par=self.par, modo_execucao=self.ex.modo, direcao="sell", quantidade=contratos,
                                              preco_entrada=preco, status="aberta", motivo_entrada=f"grade nível {e['nivel']}", cenario="grade_inversa", fase_onda="range")
                    self.db.add(self.posicao)
                self.ex._log(acao="sell", tipo_operacao="entrada", direcao="sell", preco=preco, quantidade=contratos, motivo=f"grade: venda nível {e['nivel']}")
            else:
                pnl = e.get("pnl_btc", 0.0)
                if self.posicao:
                    self.posicao.quantidade = max(0.0, float(self.posicao.quantidade) - contratos)
                    self.posicao.pnl = round((self.posicao.pnl or 0) + pnl, 8)
                    if self.posicao.quantidade <= 0:
                        self.posicao.status, self.posicao.preco_saida, self.posicao.fechado_em = "fechada", preco, datetime.utcnow()
                        self.posicao.motivo_saida = "grade totalmente recomprada"
                        self.posicao = None
                self.ex.estado["pnl_dia"] += pnl
                self.ex._log(acao="buy", tipo_operacao="saida", direcao="sell", preco=preco, quantidade=contratos, resultado=pnl,
                             motivo=f"grade: recompra nível {e['nivel']} (+{pnl:.6f} BTC)")
        self.db.commit()

    # ------------------------------------------------------------ ciclo
    def ciclo(self, ohlcv, preco: float, candle_novo: bool):
        if not candle_novo:
            return
        c = ohlcv[-1]
        ts, hi, lo, close = int(c[0]), float(c[2]), float(c[3]), float(c[4])
        leitura = self.leitura_mestre(preco)
        if self._attr("range_status") != "aprovado":
            prop = self.propor(close, leitura)
            self._decisao(ts, preco, "hold", f"sem range aprovado; proposta: {(prop or {}).get('low')}-{(prop or {}).get('high')} ({(prop or {}).get('motivo')})", leitura)
            return
        if self.grade is None:
            self.grade = self._nova_grade()
        banca = self._banca_btc()
        equity = banca + self.grade.pnl_nao_realizado(close)
        # saída de cenário (opcional)
        if self._attr("saida_estrutural", False) and close > self.grade.high and self.grade.contratos_abertos() > 0:
            prim = leitura.get("primario") or {}
            ciclo = leitura.get("ciclo") or {}
            if (prim.get("vies") == "bull" and prim.get("fase") in ("inicio_onda_3", "meio_onda_3", "onda_5", "onda_1", "final_onda_3")) or ciclo.get("prob_bull", 0) >= 0.6:
                execs = []
                for f in self.grade.fatias:
                    if f.contratos > 0:
                        pnl = f.contratos * (1 / close - 1 / f.preco_venda)
                        execs.append({"ts": ts, "tipo": "recompra", "nivel": f.nivel, "preco": close, "contratos": f.contratos, "pnl_btc": pnl})
                        f.contratos = 0.0
                self._executar(execs, close)
                self.bot.range_status, self.bot.range_motivo = "encerrado", "saída de cenário: Elliott virou impulso de alta acima do topo"
                self.grade = None
                self._salvar_grade(None)
                self.ex.alertas.info(f"{self._attr('nome')}: grade encerrada por cenário de alta")
                self._decisao(ts, preco, "buy", "saída de cenário: impulso de alta", leitura)
                return
        execs = self.grade.processar_candle(ts, hi, lo, close, max(equity, 1e-6), leitura.get("guia"))
        self._executar(execs, close)
        self._salvar_grade(self.grade)
        if close < self.grade.low and self.grade.contratos_abertos() <= 0:
            self.bot.range_status, self.bot.range_motivo = "concluido", f"grade concluída abaixo do fundo; BTC realizado {self.grade.btc_realizado:.6f}"
            self.grade = None
            self._salvar_grade(None)
            self.ex.alertas.info(f"{self._attr('nome')}: grade concluída, aguardando novo range")
        vendas = sum(1 for e in execs if e["tipo"] == "venda"); recompras = sum(1 for e in execs if e["tipo"] == "recompra")
        acao = "sell" if vendas > recompras else "buy" if recompras > vendas else "hold"
        resumo = self.grade.resumo(close) if self.grade else {}
        self._decisao(ts, preco, acao, f"grade: {vendas} vendas, {recompras} recompras | em dólar {resumo.get('fracao_aberta', 0):.0%} | BTC realizado {resumo.get('btc_realizado', 0):.6f}", leitura)

    def _decisao(self, ts, preco, acao, motivo, leitura):
        guia = leitura.get("guia") or {}
        self.ex.estado["ultima_decisao"] = {"acao": acao, "motivo": motivo, "range": [self._attr("range_low"), self._attr("range_high"), self._attr("range_status")]}
        try:
            self.db.add(DecisaoBot(bot_id=self._attr("id"), par=self.par, timeframe=self.ex.timeframe, candle_ts=ts, preco=preco, acao=acao,
                                   fase_onda=guia.get("fase"), cenario=(guia.get("nome") or "grade_inversa")[:60],
                                   probabilidade=guia.get("prob_sucesso") or guia.get("probabilidade"), motivo=motivo[:4000],
                                   detalhes=json.dumps({"grade": self.grade.resumo(preco) if self.grade else None, "guia": guia, "ciclo": leitura.get("ciclo")}, default=str)[:60000]))
            self.db.commit()
        except Exception as e:
            logger.error("persistir decisão inverse: %s", e)
            self.db.rollback()

    def status(self) -> Dict:
        return {"range": [self._attr("range_low"), self._attr("range_high"), self._attr("range_status")],
                "grade": self.grade.resumo(self.ex.estado.get("preco") or 0) if self.grade else None,
                "posicao": self.posicao.as_dict() if self.posicao else None}
