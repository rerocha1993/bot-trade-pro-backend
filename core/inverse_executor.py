# core/inverse_executor.py
"""
Executor do modo inverse: GRADE de acumulação de BTC (short-only, sem stop de preço, entradas escalonadas).

Ciclo (a cada candle FECHADO do timeframe do bot, 4h por padrão):
    1. range: só opera com range APROVADO pelo usuário (bot.range_low/high, range_status 'aprovado'); sem range,
       publica uma proposta (status 'proposto') a partir da contagem mestre no diário e espera
    2. grade: fatias de Fibonacci de 0 a 100% do range (nada acima do topo), cada uma com 3 sub-fatias progressivas;
       vende quando a máxima do candle toca o preço da fatia, recompra quando a mínima toca o nível abaixo
       (toda recompra é lucro em BTC). Estado da grade persistido em bot.grade_json
    3. short de base: com a contagem mestre (trava ou primário) de baixa e alvo abaixo do fundo, as fatias mais
       baixas só recompram no alvo de Elliott
    4. ROMPIMENTO do range (core/inverse_rompimento.py), regra de preço, não palpite:
         - topo rompido de verdade (2 fechamentos além de 1%, ou 1 além de 3%) -> fecha todo o short, 'encerrado'
         - topo rompido em falso (fechou de volta para dentro) -> o short fica
         - fundo rompido de verdade -> espera o respiro e vende quase 100% no reteste; stop e alvo próprios
         - fundo rompido em falso -> não vende nada
    5. range encerrado ou concluído -> grade zerada e nova proposta
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
from core.inverse_rompimento import MaquinaRompimento, ParametrosRompimento, pesos_inverse
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
        self.maquina = MaquinaRompimento(self._parametros_rompimento())

    def _attr(self, nome, default=None):
        v = getattr(self.bot, nome, None)
        return default if v is None else v

    def _parametros_rompimento(self) -> ParametrosRompimento:
        return ParametrosRompimento(folga=float(self._attr("folga_stop", 0.01) or 0.01))

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
                self.maquina = MaquinaRompimento.from_dict(d.get("rompimento"), self._parametros_rompimento())
            except Exception as e:
                logger.warning("grade salva inválida, recriando: %s", e)
                self.grade = None
        # a grade NOVA é montada no primeiro ciclo, que conhece o preço. Montar aqui, sem preço, era justamente o que
        # deixava todos os níveis ativos e fazia o primeiro candle vender de uma vez tudo abaixo do preço

    def _nova_grade(self, preco: float) -> GradeInversa:
        """
        Monta a grade com o preço de AGORA: os níveis abaixo dele só entram depois que o preço cair abaixo deles.

        Antes ela nascia com todos os níveis ativos, e o primeiro candle vendia de uma vez cada nível que tinha ficado
        abaixo do preço. Medido no range que o robô propunha (57.647–82.800) com o preço em 76.810: 14 fatias, 60% da
        carteira vendida num candle só, a mercado. O guarda (`desativar_abaixo`) existia e o hedge dial usava.
        """
        pesos = None
        try:
            esc = json.loads(self._attr("escada_json") or "null")
            if esc:
                pesos = {float(k): float(v) for k, v in esc.items()}
        except Exception:
            pesos = None
        g = GradeInversa(float(self._attr("range_low")), float(self._attr("range_high")), pesos=pesos or pesos_inverse())
        g.desativar_abaixo(preco)
        self.maquina = MaquinaRompimento(self._parametros_rompimento())
        self._salvar_grade(g)
        return g

    def _encerrar_grade(self):
        self.grade = None
        self.maquina = MaquinaRompimento(self._parametros_rompimento())
        self._salvar_grade(None)

    def _salvar_grade(self, g: Optional[GradeInversa]):
        if g is None:
            self.bot.grade_json = None
        else:
            self.bot.grade_json = json.dumps({"low": g.low, "high": g.high, "pesos": {str(k): v for k, v in g.pesos.items()}, "subfatias": g.subfatias,
                                              "btc_realizado": g.btc_realizado, "taxas_btc": g.taxas_btc,
                                              "fatias": [f.__dict__ for f in g.fatias], "rompimento": self.maquina.as_dict()})
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
        faixa = (float(self._attr("range_low")), float(self._attr("range_high")))
        if self.grade is None or (self.grade.low, self.grade.high) != faixa:
            self.grade = self._nova_grade(close)
        banca = self._banca_btc()
        equity = banca + self.grade.pnl_nao_realizado(close) + self.maquina.pnl_nao_realizado(close)
        guia = leitura.get("guia") or {}
        alvos = [a for a in (guia.get("alvos") or []) if a] if guia.get("vies") == "bear" else []
        r = self.maquina.avaliar(ts, hi, lo, close, max(equity, 1e-6), self.grade.low, self.grade.high, alvos,
                                 fracao_ja_vendida=self.grade.fracao_aberta())
        execs = list(r["execs"])
        # o resultado do short de reteste entra no BTC realizado da grade, para o painel mostrar o resultado inteiro
        self.grade.btc_realizado += sum(e.get("pnl_btc", 0.0) for e in r["execs"] if e["tipo"] == "recompra")
        if r["fechar_grade"]:
            for f in self.grade.fatias:
                if f.contratos > 0:
                    pnl = f.contratos * (1 / close - 1 / f.preco_venda)
                    self.grade.btc_realizado += pnl
                    execs.append({"ts": ts, "tipo": "recompra", "nivel": f.nivel, "preco": close, "contratos": f.contratos, "pnl_btc": pnl})
                    f.contratos = 0.0
        else:
            # só dentro do range a grade vende. Rompendo, esperando o reteste ou vendido no reteste, o range acabou ou
            # está em xeque — as recompras continuam, porque recompra é lucro. O estado vale DEPOIS do fechamento:
            # um pavio acima do topo que fecha de volta dentro vende o pavio, que é o que se quer num falso
            execs += self.grade.processar_candle(ts, hi, lo, close, max(equity, 1e-6), guia or None,
                                                 vender=self.maquina.no_range)
        self._executar(execs, close)
        if r["fechar_grade"] or r["concluido"]:
            realizado = self.grade.btc_realizado
            self.bot.range_status = "encerrado" if r["fechar_grade"] else "concluido"
            self.bot.range_motivo = f"{r['motivo']}; BTC realizado {realizado:.6f}"[:255]
            self.ex.alertas.info(f"{self._attr('nome')}: {r['motivo'][:220]}")
            self._encerrar_grade()
        else:
            self._salvar_grade(self.grade)
        vendas = sum(1 for e in execs if e["tipo"] == "venda"); recompras = sum(1 for e in execs if e["tipo"] == "recompra")
        acao = "sell" if vendas > recompras else "buy" if recompras > vendas else "hold"
        resumo = self.grade.resumo(close) if self.grade else {}
        self._decisao(ts, preco, acao, f"{r['motivo']} | grade: {vendas} vendas, {recompras} recompras | em dólar "
                                       f"{resumo.get('fracao_aberta', 0):.0%} | BTC realizado {resumo.get('btc_realizado', 0):.6f}",
                      leitura)

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
                "posicao": self.posicao.as_dict() if self.posicao else None,
                "rompimento": self.maquina.resumo(self.ex.estado.get("preco") or None)}
