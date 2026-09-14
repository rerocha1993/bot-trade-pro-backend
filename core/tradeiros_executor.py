# core/tradeiros_executor.py
"""
PORTAL TRADEIROS NA DEMO: os robôs do Shaka e do Maroja operando o plano do dia (tradeiros/regras.py) — a mesma
carteira do backtest (tradeiros/carteira.py), agora com ordens na conta de Demo Trading.

Cada operador tem DUAS subcontas (a Bybit tem uma posição por símbolo por conta):

    trades (linear BTCUSDT)   compra ou venda direcional do plano: limitadas post-only nas fatias da zona (a mais longe
                              é a maior), stop na invalidação e alvo anexados à posição; o que o preço já passou entra a
                              mercado. Em 1 R realiza a fração do perfil (Shaka 50%, Maroja 25%), leva o stop ao médio e
                              cancela o resto da escada (R22). Mal preenchida e o preço saiu da zona: fecha (R24). Fora do
                              valor, o Maroja só arma depois do candle de 30 min de reação. Um trade por vez (one-way:
                              uma venda executando fecharia a compra); havendo compra e venda no plano, arma a mais perto.
    hedge (inverse BTCUSD)    na primeira vez vende a mercado até o hedge do plano; depois, só limitadas: escada de venda
                              na VAH e recompra (reduce-only) na VAL. Cada venda da escada ganha um stop CONDICIONAL na
                              corretora (o "pedágio", R27), que vale com o servidor desligado. A recompra realiza o que
                              foi vendido por último (LIFO). Contratos a menos na corretora = stop executado.

O plano é refeito à 00:00 UTC com os candles fechados (tradeiros/ao_vivo.py); o que não executou no dia anterior é
cancelado (a posição e os stops ficam). Só roda com ordem de verdade (demo/testnet/real). Estado em bot.grade_json.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, Dict, List, Optional

from core.executor_real import TAXA_MAKER
from core.tpo_sessao import DIA_MS
from models.posicao_bot import PosicaoBot
from tradeiros.ao_vivo import plano_do_dia, resumo_do_plano
from tradeiros.carteira import SLIPPAGE, pnl_btc
from tradeiros.regras import PERFIS, Perfil, Plano, medio_das_fatias, precos_das_fatias

logger = logging.getLogger(__name__)

CHECAR_ORDENS_S = 60                 # a escada do hedge é conferida na corretora a cada minuto
REPETIR_PLANO_S = 60                 # plano que falhou (rede) tenta de novo depois de um minuto


def _agora_ms() -> int:
    return int(time.time() * 1000)


def operador(estrategia: str) -> str:
    return estrategia.split("_", 1)[1]


def criar_executor_tradeiros(executor):
    perfil = PERFIS[operador(executor.estrategia)]
    if executor.categoria == "inverse":
        return TradeirosHedge(executor, perfil)
    return TradeirosTrades(executor, perfil)


class _Base:
    ESTADO = ""

    def __init__(self, executor, perfil: Perfil, planejador: Optional[Callable[[Optional[float]], Plano]] = None):
        self.ex = executor
        self.perfil = perfil
        self.planejador = planejador or self._plano_ao_vivo
        self.dia: Optional[int] = None
        self.ultimo_plano: Optional[Dict] = None
        self._tentativa = -1e18

    def _plano_ao_vivo(self, hedge_atual: Optional[float]) -> Plano:
        # dados públicos sempre pelo conector linear compartilhado (o do hedge é inverse)
        con = (getattr(self.ex, "servicos", None) or {}).get("connectors", {}).get("simulador") or self.ex._con_publico
        return plano_do_dia(con, self.perfil, hedge_atual)

    def _attr(self, nome, default=None):
        return self.ex._attr(nome, default)

    def _nome(self) -> str:
        return f"Tradeiros {self.perfil.nome}"

    def _ler_estado(self) -> Dict:
        raw = self._attr("grade_json")
        try:
            d = json.loads(raw) if raw else None
        except Exception:
            d = None
        return d if (d or {}).get("estrategia") == self.ESTADO else {}

    def _novo_plano(self, hedge_atual: Optional[float], preco: float) -> Optional[Plano]:
        agora = _agora_ms()
        if agora - self._tentativa < REPETIR_PLANO_S * 1000:
            return None
        self._tentativa = agora
        try:
            plano = self.planejador(hedge_atual)
        except Exception as e:
            logger.warning("[%s] plano do dia falhou: %s", self._attr("nome"), f"{type(e).__name__}: {e}"[:200])
            return None
        self.ultimo_plano = resumo_do_plano(plano)
        dia = agora // DIA_MS
        tipos = [d.tipo for d in plano.decisoes]
        acao = "buy" if "compra" in tipos else "sell" if "venda_direcional" in tipos else "hold"
        motivo = (f"plano {self.perfil.nome} do dia: hedge {plano.hedge_alvo:.0%} | "
                  + "; ".join(f"{d.tipo} {'/'.join(d.regras)}" for d in plano.decisoes))[:3900]
        self.ex.estado["ultima_decisao"] = {"acao": acao, "motivo": motivo, "fase_onda": None, "cenario": f"tradeiros {self.perfil.nome}",
                                            "probabilidade": None, "tp": None, "sl": None, "votos": []}
        try:
            self.ex._persistir_decisao({"acao": acao, "motivo": motivo, "tp": None, "sl": None, "votos": [],
                                        "cenario": f"tradeiros {self.perfil.nome}", "fase_onda": None, "probabilidade": None,
                                        "niveis": self.ultimo_plano}, dia * DIA_MS, preco)
        except Exception as e:
            logger.warning("[%s] decisão do plano não foi gravada: %s", self._attr("nome"), e)
        return plano


# ====================================================================== conta de trades (linear)
class TradeirosTrades(_Base):
    ESTADO = "tradeiros_trades"

    def __init__(self, executor, perfil: Perfil, planejador=None):
        super().__init__(executor, perfil, planejador)
        self.trade: Optional[Dict] = None

    def _pm(self) -> str:
        return self._attr("position_mode", "one-way")

    def _salvar(self):
        self.ex.bot.grade_json = json.dumps({"estrategia": self.ESTADO, "dia": self.dia, "trade": self.trade})
        self.ex.db.commit()

    def carregar(self):
        d = self._ler_estado()
        self.dia, self.trade = d.get("dia"), d.get("trade")
        if self.trade and self.trade["executadas"] and self.ex.posicao is None:
            # a posição fechou com o servidor parado: o que sobrou no livro não tem mais gestão
            self._cancelar_pendentes("posição já fechada ao reiniciar")
            self.trade = None
            self._salvar()

    def status(self) -> Dict:
        t = self.trade
        return {"operador": self.perfil.nome, "conta": "trades", "dia": self.dia, "plano": self.ultimo_plano,
                "trade": None if not t else {
                    "lado": t["lado"], "zona": t["zona"], "stop": t["stop"], "alvo": t["alvo"], "armado": t["armado"],
                    "risco_tirado": t["risco_tirado"], "fatias_executadas": len(t["executadas"]),
                    "fatias_pendentes": len(t["pendentes"]) + len(t["a_colocar"]),
                    "precos_pendentes": [x["preco"] for x in t["pendentes"] + t["a_colocar"]], "regras": t["regras"]}}

    def _cancelar_pendentes(self, motivo: str):
        t = self.trade
        if not t or not (t.get("pendentes") or t.get("a_colocar")):
            return
        if t.get("pendentes") and not self.ex.ordens.simulado:
            try:
                n = self.ex.con.cancelar_entradas_abertas(self.ex.par)
                if n:
                    self.ex._log(acao="hold", tipo_operacao="info", preco=None, motivo=f"{n} fatia(s) cancelada(s): {motivo}")
            except Exception as e:
                logger.warning("[%s] cancelar fatias falhou: %s", self._attr("nome"), e)
        t["pendentes"], t["a_colocar"] = [], []

    def _encerrar(self):
        self.trade = None
        self._salvar()

    # ------------------------------------------------------------ ciclo
    def ciclo(self, ohlcv, preco: float, candle_novo: bool):
        if self.ex.ordens.simulado:
            return
        dia = _agora_ms() // DIA_MS
        if dia != self.dia:
            self._virar_dia(dia, preco)
        if self.trade is None:
            return
        if not self.trade["armado"]:
            if candle_novo and ohlcv:
                self._conferir_reacao(ohlcv[-1])
            return
        self._gerir(preco)

    def _virar_dia(self, dia: int, preco: float):
        if self.trade is not None and self.trade.get("dia") != dia:
            self._cancelar_pendentes("ordens do dia anterior")
            if not self.trade["executadas"]:
                self.trade = None
        plano = self._novo_plano(None, preco)
        if plano is None:
            return
        self.dia = dia
        if self.trade is None:
            d = self._escolher(plano, preco)
            if d is not None:
                pode, motivo = self.ex._pode_operar()
                if pode:
                    self._armar(d, preco)
                else:
                    self.ex._log(acao="hold", tipo_operacao="info", preco=preco, motivo=f"Plano {self.perfil.nome} ignorado: {motivo}")
        self._salvar()

    @staticmethod
    def _escolher(plano: Plano, preco: float):
        candidatas = [d for d in plano.decisoes
                      if d.tipo in ("compra", "venda_direcional") and d.zona and d.stop and d.alvo and d.risco > 0]
        if not candidatas:
            return None
        distancia = lambda d: 0.0 if d.zona[0] <= preco <= d.zona[1] else min(abs(preco - d.zona[0]), abs(preco - d.zona[1]))
        return min(candidatas, key=distancia)

    # ------------------------------------------------------------ entrada
    def _armar(self, d, preco: float):
        lado = 1 if d.tipo == "compra" else -1
        par = self.ex.par
        pesos = d.pesos_fatias or [1.0]
        medio = medio_das_fatias(d.zona, pesos, d.tipo)
        banca = self.ex._banca()
        q_total = banca * d.risco / abs(medio - d.stop)
        teto = banca * float(self._attr("max_alocacao_pct", 1.0) or 1.0) * max(int(getattr(self.ex, "alavancagem", 1) or 1), 1) / medio
        q_total = min(q_total, teto)
        fatias = [{"preco": self.ex.con.arredondar_preco(par, p), "q": self.ex.con.arredondar_quantidade(par, q_total * w)}
                  for p, w in zip(precos_das_fatias(d.zona, len(pesos), d.tipo), pesos)]
        fatias = [f for f in fatias if f["q"] > 0]
        if not fatias:
            self.ex._log(acao="hold", tipo_operacao="info", preco=preco,
                         motivo=f"{self._nome()}: fatias abaixo do mínimo negociável (mão total {q_total:.5f}); {d.tipo} recusada")
            return
        self.trade = {"dia": _agora_ms() // DIA_MS, "lado": lado, "tipo": d.tipo, "zona": list(d.zona), "stop": d.stop,
                      "stop_inicial": d.stop, "alvo": d.alvo, "regras": list(d.regras), "motivo": d.motivo,
                      "planejado": sum(f["q"] for f in fatias), "a_colocar": fatias, "pendentes": [], "executadas": [],
                      "armado": not d.exige_reacao, "risco_tirado": False}
        if self.trade["armado"]:
            self._colocar(preco)
        else:
            self.ex._log(acao="hold", tipo_operacao="info", preco=preco,
                         motivo=f"{self._nome()}: {d.tipo} fora do valor, espera o candle de reação em "
                                f"{d.zona[0]:,.0f}–{d.zona[1]:,.0f} ({'/'.join(d.regras)})")
            self._salvar()

    def _colocar(self, preco: float, tocadas: Optional[List[Dict]] = None):
        """Fatias que o preço já passou (ou que o candle de reação tocou) a mercado; o resto como limitadas post-only."""
        t = self.trade
        lado, acao, par, pm = t["lado"], ("buy" if t["lado"] == 1 else "sell"), self.ex.par, self._pm()
        passou = tocadas if tocadas is not None else [f for f in t["a_colocar"] if (f["preco"] >= preco if lado == 1 else f["preco"] <= preco)]
        resto = [f for f in t["a_colocar"] if f not in passou]
        t["a_colocar"] = []
        if passou:
            exec_ = self.ex.ordens.abrir(par, acao, sum(f["q"] for f in passou), t["stop"], t["alvo"], pm, preco_ref=preco)
            t["executadas"] += [{"preco": exec_["preco_exec"], "q": f["q"]} for f in passou]
            self.ex._registrar_entrada({"acao": acao, "cenario": f"tradeiros {self.perfil.nome}",
                                        "motivo": f"[{self._nome()}: {len(passou)} fatia(s) a mercado] {t['motivo']} ({'/'.join(t['regras'])})"},
                                       exec_, exec_["preco_exec"], t["stop"], t["alvo"])
        for f in resto:
            try:
                ped = self.ex.ordens.abrir_limite(par, acao, f["q"], f["preco"], t["stop"], t["alvo"], pm)
                t["pendentes"].append({"preco": ped["preco"], "q": ped["quantidade"], "ordem_id": ped["ordem_id"]})
            except Exception as e:
                logger.warning("[%s] fatia a %.1f não foi enviada: %s", self._attr("nome"), f["preco"], e)
        self._salvar()
        self.ex._log(acao=acao, tipo_operacao="info", preco=preco, sl=t["stop"], tp=t["alvo"], quantidade=t["planejado"],
                     motivo=f"{self._nome()}: escada de {t['tipo']} com {len(t['pendentes'])} limitada(s) em "
                            + (", ".join(f"{p['preco']:,.0f}" for p in t["pendentes"]) or "—")
                            + f" | stop {t['stop']:,.0f} | alvo {t['alvo']:,.0f}")

    def _conferir_reacao(self, c):
        t = self.trade
        lo_z, hi_z = t["zona"]
        hi, lo, close = float(c[2]), float(c[3]), float(c[4])
        if t["lado"] == 1:
            tocou, reagiu = lo <= hi_z, close >= lo + 0.5 * (hi - lo) and close >= lo_z and lo > t["stop"]
        else:
            tocou, reagiu = hi >= lo_z, close <= hi - 0.5 * (hi - lo) and close <= hi_z and hi < t["stop"]
        if not (tocou and reagiu):
            return
        t["armado"] = True
        tocadas = [f for f in t["a_colocar"] if (f["preco"] >= lo if t["lado"] == 1 else f["preco"] <= hi)]
        self.ex._log(acao="hold", tipo_operacao="info", preco=close, motivo=f"{self._nome()}: candle de reação na zona; arma a escada")
        self._colocar(close, tocadas)

    # ------------------------------------------------------------ gestão
    def _gerir(self, preco: float):
        t = self.trade
        try:
            pos_ex = self.ex.con.obter_posicao(self.ex.par)
        except Exception as e:
            logger.warning("[%s] consulta de posição falhou: %s", self._attr("nome"), e)
            return
        lado_txt = "buy" if t["lado"] == 1 else "sell"
        if self.ex.posicao is None:
            if pos_ex and pos_ex["side"] == lado_txt:
                self._adotar(pos_ex)
            return
        if pos_ex is None:
            self._cancelar_pendentes("stop ou alvo executado")
            self.ex._registrar_saida(preco, "Zero a zero (stop no médio)" if t["risco_tirado"] else "SL/TP executado pela exchange",
                                     pnl_exchange=True)
            self._encerrar()
            return
        self._sincronizar(pos_ex)
        if not t["risco_tirado"] and self._em_1r(preco):
            self._tirar_o_risco(preco)
            return
        if not t["risco_tirado"] and self._mal_preenchida(preco):
            self._cancelar_pendentes("entrada mal preenchida saiu da zona")
            self.ex.fechar_posicao(f"{self._nome()}: entrada mal preenchida e o preço saiu da zona (R24)", preco)
            self._encerrar()

    def _consumir(self, q: float) -> List[Dict]:
        """As limitadas mais perto do preço executam primeiro: tira da fila até cobrir a quantidade que apareceu."""
        t, feitas, soma = self.trade, [], 0.0
        while t["pendentes"] and soma + t["pendentes"][0]["q"] <= q + 1e-9:
            f = t["pendentes"].pop(0)
            feitas.append(f)
            soma += f["q"]
        t["executadas"] += feitas
        return feitas

    def _adotar(self, pos_ex: Dict):
        t = self.trade
        q, p = float(pos_ex["quantidade"]), float(pos_ex["preco_entrada"])
        feitas = self._consumir(q)
        exec_ = {"ordem_id": feitas[0]["ordem_id"] if feitas else None, "preco_exec": p, "quantidade": q, "simulado": False,
                 "taxa": p * q * TAXA_MAKER}
        self.ex._registrar_entrada({"acao": "buy" if t["lado"] == 1 else "sell", "cenario": f"tradeiros {self.perfil.nome}",
                                    "motivo": f"[{self._nome()}: {len(t['executadas'])} fatia(s) limitada(s) executada(s)] {t['motivo']}"},
                                   exec_, p, t["stop"], t["alvo"])
        self._salvar()

    def _sincronizar(self, pos_ex: Dict):
        pos = self.ex.posicao
        q_ex, q_db = float(pos_ex["quantidade"]), float(pos.quantidade or 0)
        if q_ex <= q_db + 1e-9 or self.trade["risco_tirado"]:
            return
        feitas = self._consumir(q_ex - q_db)
        for f in feitas:
            pos.taxas = float(pos.taxas or 0) + f["preco"] * f["q"] * TAXA_MAKER
        pos.quantidade = q_ex
        pos.quantidade_inicial = q_ex
        pos.preco_entrada = float(pos_ex["preco_entrada"] or pos.preco_entrada)
        self._salvar()
        self.ex._log(acao="buy" if self.trade["lado"] == 1 else "sell", tipo_operacao="info", preco=pos.preco_entrada, quantidade=q_ex,
                     motivo=f"{self._nome()}: {len(feitas)} fatia(s) executada(s), preço médio {pos.preco_entrada:,.1f}")

    def _em_1r(self, preco: float) -> bool:
        t, medio = self.trade, float(self.ex.posicao.preco_entrada)
        nivel = medio + t["lado"] * abs(medio - t["stop_inicial"])
        return preco >= nivel if t["lado"] == 1 else preco <= nivel

    def _mal_preenchida(self, preco: float) -> bool:
        t = self.trade
        feito = sum(f["q"] for f in t["executadas"])
        if feito >= self.perfil.preenchimento_minimo * t["planejado"]:
            return False
        lo, hi = t["zona"]
        largura = hi - lo
        return preco > hi + largura if t["lado"] == 1 else preco < lo - largura

    def _tirar_o_risco(self, preco: float):
        """R22: realiza a fração do perfil em 1 R, stop no preço médio, cancela o resto da escada."""
        t, pos = self.trade, self.ex.posicao
        self._cancelar_pendentes("risco tirado")
        q = self.ex.con.arredondar_quantidade(self.ex.par, float(pos.quantidade) * self.perfil.realizar_em_1r)
        medio = float(pos.preco_entrada)
        if q > 0:
            try:
                self.ex.realizar_fracao(self.perfil.realizar_em_1r, preco, f"{self._nome()}: tirar o risco em 1 R (R22)")
            except Exception as e:
                logger.warning("[%s] realização em 1 R falhou: %s", self._attr("nome"), e)
                return
            if self.ex.posicao is None:
                self._encerrar()
                return
        stop = self.ex.con.arredondar_preco(self.ex.par, medio)
        if self.ex.ordens.atualizar_stop(self.ex.par, stop, t["alvo"], self._pm(), self.ex.posicao.direcao):
            self.ex.posicao.sl = stop
            t["stop"] = stop
        t["risco_tirado"] = True
        self._salvar()
        self.ex._log(acao="ajuste_sl", tipo_operacao="info", preco=preco, sl=stop, motivo=f"{self._nome()}: stop no preço médio depois de tirar o risco")


# ====================================================================== conta de hedge (inverse)
class TradeirosHedge(_Base):
    ESTADO = "tradeiros_hedge"

    def __init__(self, executor, perfil: Perfil, planejador=None):
        super().__init__(executor, perfil, planejador)
        self.tranches: List[Dict] = []        # vendas abertas: contratos, preço, stop e o id do stop na corretora
        self.ordens: List[Dict] = []          # limitadas da escada do dia
        self.base_feita = False
        self.stops = 0
        self.realizado_btc = 0.0
        self._checado = -1e18
        self._falta_vista = 0.0

    def _salvar(self):
        self.ex.bot.grade_json = json.dumps({"estrategia": self.ESTADO, "dia": self.dia, "tranches": self.tranches,
                                             "ordens": self.ordens, "base_feita": self.base_feita, "stops": self.stops,
                                             "realizado_btc": self.realizado_btc})
        self.ex.db.commit()

    def carregar(self):
        d = self._ler_estado()
        self.dia = d.get("dia")
        self.tranches, self.ordens = d.get("tranches") or [], d.get("ordens") or []
        self.base_feita, self.stops = bool(d.get("base_feita")), int(d.get("stops") or 0)
        self.realizado_btc = float(d.get("realizado_btc") or 0.0)

    def contratos(self) -> float:
        return sum(tr["c"] for tr in self.tranches)

    def status(self) -> Dict:
        return {"operador": self.perfil.nome, "conta": "hedge", "dia": self.dia, "plano": self.ultimo_plano,
                "contratos_vendidos": self.contratos(), "escadas_abertas": len([tr for tr in self.tranches if tr["stop"]]),
                "ordens": [{"preco": o["preco"], "contratos": o["c"], "vende": o["vende"]} for o in self.ordens],
                "stops_executados": self.stops, "realizado_btc": round(self.realizado_btc, 8)}

    def _equity_btc(self) -> float:
        try:
            return float(self.ex.con.obter_saldo("BTC")["total"] or 0)
        except Exception as e:
            logger.warning("[%s] saldo em BTC indisponível: %s", self._attr("nome"), e)
            return 0.0

    # ------------------------------------------------------------ ciclo
    def ciclo(self, ohlcv, preco: float, candle_novo: bool):
        if self.ex.ordens.simulado:
            return
        agora = _agora_ms()
        if agora // DIA_MS != self.dia:
            self._virar_dia(agora // DIA_MS, preco)
            self._checado = agora             # as ordens acabaram de sair: a corretora pode ainda não mostrar a posição
        if agora - self._checado >= CHECAR_ORDENS_S * 1000:
            self._checado = agora
            self._conferir(preco)

    def _virar_dia(self, dia: int, preco: float):
        eq = self._equity_btc()
        if eq <= 0:
            if _agora_ms() - self._tentativa >= REPETIR_PLANO_S * 1000:
                self._tentativa = _agora_ms()
                self.ex._log(acao="hold", tipo_operacao="info", preco=preco, motivo=f"{self._nome()}: sem saldo em BTC na conta de hedge")
            return
        hedge_atual = self.contratos() / (eq * preco) if self.base_feita else None
        plano = self._novo_plano(hedge_atual, preco)
        if plano is None:
            return
        self._cancelar_ordens("escada do dia anterior")
        self.dia = dia
        par, con = self.ex.par, self.ex.con
        if not self.base_feita:
            c = con.arredondar_quantidade(par, plano.hedge_alvo * eq * preco)
            if c > 0:
                r = con.criar_ordem(par, "sell", c, tipo="market")
                px = float(r.get("average") or r.get("price") or preco)
                self._somar(c, px, None, f"base do hedge a mercado ({plano.hedge_alvo:.0%} da carteira)")
            self.base_feita = True
        for d in plano.decisoes:
            if d.tipo not in ("hedge_aumentar", "hedge_realizar") or not d.zona or d.fracao_hedge <= 0:
                continue
            vende = d.tipo == "hedge_aumentar"
            pesos = d.pesos_fatias or [1.0]
            for p, w in zip(precos_das_fatias(d.zona, len(pesos), "venda_direcional" if vende else "compra"), pesos):
                p = con.arredondar_preco(par, p)
                c = con.arredondar_quantidade(par, d.fracao_hedge * w * eq * p)
                if c <= 0:
                    continue
                try:
                    o = con.criar_ordem(par, "sell" if vende else "buy", c, tipo="limit", preco=p, post_only=True, reduce_only=not vende)
                    self.ordens.append({"id": o.get("id"), "preco": p, "c": c, "vende": vende, "stop": d.stop if vende else None})
                except Exception as e:
                    logger.warning("[%s] ordem da escada a %.1f não foi enviada: %s", self._attr("nome"), p, e)
        self._salvar()
        vendas = [o for o in self.ordens if o["vende"]]
        recompras = [o for o in self.ordens if not o["vende"]]
        self.ex._log(acao="hold", tipo_operacao="info", preco=preco,
                     motivo=f"{self._nome()}: hedge alvo {plano.hedge_alvo:.0%}; vendido {self.contratos():,.0f} contratos; "
                            f"{len(vendas)} venda(s) em " + (", ".join(f"{o['preco']:,.0f}" for o in vendas) or "—")
                            + f"; {len(recompras)} recompra(s) em " + (", ".join(f"{o['preco']:,.0f}" for o in recompras) or "—"))

    def _cancelar_ordens(self, motivo: str):
        n = 0
        for o in self.ordens:
            if self.ex.ordens.cancelar_ordem(self.ex.par, o["id"]):
                n += 1
        if n:
            self.ex._log(acao="hold", tipo_operacao="info", preco=None, motivo=f"{self._nome()}: {n} ordem(ns) cancelada(s): {motivo}")
        self.ordens = []

    def _conferir(self, preco: float):
        par = self.ex.par
        for o in list(self.ordens):
            try:
                sit = self.ex.ordens.situacao_ordem(par, o["id"])
            except Exception as e:
                logger.warning("[%s] situação da ordem %s: %s", self._attr("nome"), o["id"], e)
                continue
            if sit["status"] == "executada":
                self.ordens.remove(o)
                px = float(sit.get("preco_exec") or o["preco"])
                if o["vende"]:
                    self._somar(o["c"], px, o["stop"], f"escada vendeu em {px:,.0f}")
                else:
                    self._recomprar(o["c"], px, f"escada recomprou em {px:,.0f}")
            elif sit["status"] == "cancelada":
                self.ordens.remove(o)
        try:
            pos_ex = self.ex.con.obter_posicao(par)
        except Exception as e:
            logger.warning("[%s] consulta de posição falhou: %s", self._attr("nome"), e)
            self._salvar()
            return
        na_corretora = float(pos_ex["quantidade"]) if pos_ex and pos_ex["side"] == "sell" else 0.0
        falta = self.contratos() - na_corretora
        # só conta como stop se a diferença se repetir na conferência seguinte: uma leitura atrasada da corretora
        # logo depois de uma ordem apagaria a base do hedge do registro
        if falta >= 1 and self._falta_vista and abs(self._falta_vista - falta) < 1:
            self._stops_executados(falta, preco)
            self._falta_vista = 0.0
        else:
            self._falta_vista = falta if falta >= 1 else 0.0
        self._salvar()

    # ------------------------------------------------------------ contabilidade
    def _somar(self, c: float, px: float, stop: Optional[float], motivo: str):
        tr = {"c": c, "preco": px, "stop": stop, "stop_id": None}
        if stop:
            tr["stop_id"] = self._criar_stop(c, stop)
        self.tranches.append(tr)
        pos = self.ex.posicao
        if pos is None:
            self.ex.posicao = PosicaoBot(bot_id=self._attr("id"), par=self.ex.par, modo_execucao=self.ex.modo, direcao="sell",
                                         quantidade=c, quantidade_inicial=c, preco_entrada=px, sl=stop, sl_inicial=stop,
                                         status="aberta", pnl_parcial=0.0, motivo_entrada=f"{self._nome()}: {motivo}",
                                         cenario=f"tradeiros hedge {self.perfil.nome}"[:60], fase_onda="hedge")
            self.ex.db.add(self.ex.posicao)
        else:
            q0, e0 = float(pos.quantidade), float(pos.preco_entrada)
            pos.preco_entrada = (q0 + c) / (q0 / e0 + c / px)       # médio de contratos inverse é harmônico
            pos.quantidade = q0 + c
            pos.quantidade_inicial = max(float(pos.quantidade_inicial or 0), pos.quantidade)
        self.ex.db.commit()
        self.ex._log(acao="sell", tipo_operacao="entrada", direcao="sell", preco=px, quantidade=c, sl=stop,
                     motivo=f"{self._nome()}: {motivo}" + (f" | pedágio em {stop:,.0f}" if stop else ""))

    def _criar_stop(self, c: float, stop: float) -> Optional[str]:
        try:
            return self.ex.con.criar_ordem_stop(self.ex.par, "buy", c, stop).get("id")
        except Exception as e:
            logger.error("[%s] stop do hedge em %.1f NÃO foi criado: %s", self._attr("nome"), stop, e)
            self.ex._log(acao="hold", tipo_operacao="info", preco=None, motivo=f"{self._nome()}: ATENÇÃO, stop do hedge em {stop:,.0f} não foi criado: {e}"[:250])
            return None

    def _baixar(self, c: float, px: float, motivo: str):
        pos = self.ex.posicao
        pnl = 0.0
        restante = c
        while restante > 1e-9 and self.tranches:
            tr = self.tranches[-1]
            q = min(restante, tr["c"])
            pnl += pnl_btc(-1, q, tr["preco"], px)
            tr["c"] -= q
            restante -= q
            if tr["c"] <= 1e-9:
                self.tranches.pop()
        self.realizado_btc += pnl
        self.ex.estado["pnl_dia"] = float(self.ex.estado.get("pnl_dia") or 0) + pnl * px
        if pos is not None:
            pos.quantidade = max(0.0, float(pos.quantidade) - c)
            pos.pnl_parcial = round(float(pos.pnl_parcial or 0) + pnl, 8)
            if pos.quantidade <= 0:
                pos.status, pos.preco_saida, pos.pnl = "fechada", px, pos.pnl_parcial
                pos.motivo_saida = f"{self._nome()}: hedge todo realizado"[:255]
                self.ex.posicao = None
        self.ex.db.commit()
        self.ex._log(acao="buy", tipo_operacao="saida", direcao="sell", preco=px, quantidade=c, resultado=pnl,
                     motivo=f"{self._nome()}: {motivo} ({pnl:+.6f} BTC)")

    def _recomprar(self, c: float, px: float, motivo: str):
        """Recompra da escada: realiza o que foi vendido por último e refaz o stop da escada que sobrou."""
        restante = c
        for tr in reversed(self.tranches):
            if restante <= 1e-9:
                break
            q = min(restante, tr["c"])
            restante -= q
            if tr.get("stop_id"):
                self.ex.ordens.cancelar_ordem(self.ex.par, tr["stop_id"])
                tr["stop_id"] = None
                if tr["c"] - q >= 1 and tr["stop"]:
                    tr["stop_id"] = self._criar_stop(tr["c"] - q, tr["stop"])
        self._baixar(c, px, motivo)

    def _stops_executados(self, falta: float, preco: float):
        """A corretora tem menos contratos que as escadas: os stops mais baixos executaram primeiro (pedágio, R27)."""
        com_stop = sorted([tr for tr in self.tranches if tr["stop"]], key=lambda tr: tr["stop"])
        for tr in com_stop:
            if falta < 1:
                break
            q = min(falta, tr["c"])
            px = tr["stop"] * (1 + SLIPPAGE)
            self.tranches.remove(tr)
            self.tranches.append(tr)                                 # a escada stopada é a que sai (LIFO de _baixar)
            falta -= q
            self.stops += 1
            self._baixar(q, px, f"pedágio: stop da escada em {tr['stop']:,.0f} executado")
        if falta >= 1:
            self._baixar(falta, preco, "contratos a menos na corretora (fora do robô)")
