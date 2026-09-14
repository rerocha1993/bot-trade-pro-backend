"""Portal Tradeiros na demo: conta de trades (escada, reação, 1 R, R24) e conta de hedge (base, escadas, pedágio)."""
import math
from types import SimpleNamespace

import pytest

import core.tradeiros_executor as tx
from core.bot_executor import BotExecutor
from core.executor_real import OrderExecutor
from core.tpo_sessao import DIA_MS
from tradeiros.regras import MAROJA, SHAKA, Decisao, Plano

DIA0 = 20_000 * DIA_MS


class _Relogio:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class _Con:
    modo_execucao = "demo"
    pode_enviar_ordens = True

    def __init__(self, inverse=False):
        self.inverse = inverse
        self.enviadas, self.stops, self.canceladas_ids = [], [], []
        self.canceladas = 0
        self.posicao = None
        self.exchange = SimpleNamespace(cancel_order=lambda i, s: self.canceladas_ids.append(i))

    def simbolo(self, par):
        return par

    def arredondar_quantidade(self, par, q):
        if self.inverse:
            return float(math.floor(q)) if q >= 1 else 0.0
        q = math.floor(q * 1000) / 1000
        return q if q >= 0.001 else 0.0

    def arredondar_preco(self, par, p):
        return round(p, 1)

    def obter_preco_atual(self, par):
        return 100.0

    def obter_posicao(self, par):
        return self.posicao

    def obter_saldo(self, moeda):
        return {"total": 1.0 if moeda == "BTC" else 10_000.0}

    def obter_pnl_fechado(self, *a, **k):
        raise RuntimeError("sem histórico no teste")

    def cancelar_entradas_abertas(self, par):
        self.canceladas += 1
        return 1

    def atualizar_stop_posicao(self, *a):
        pass

    def criar_ordem(self, par, side, qty, tipo="market", preco=None, **k):
        o = {"id": f"o{len(self.enviadas)}", "side": side, "qty": qty, "tipo": tipo, "preco": preco, **k,
             "average": None if tipo == "limit" else 100.0, "price": preco}
        self.enviadas.append(o)
        return o

    def criar_ordem_stop(self, par, side, qty, gatilho):
        o = {"id": f"s{len(self.stops)}", "side": side, "qty": qty, "gatilho": gatilho}
        self.stops.append(o)
        return o


class _Db:
    def add(self, *a):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def _executor(perfil, plano, inverse=False, relogio=None):
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = SimpleNamespace(id=50, nome="Tradeiros", grade_json=None, banca=10_000.0, risco_pct=0.01, max_alocacao_pct=1.0,
                             position_mode="one-way", trailing_manual=False, max_trades_dia=10, max_perda_dia_pct=0.03)
    ex.par, ex.modo, ex.timeframe, ex.db = ("BTCUSD" if inverse else "BTCUSDT"), "demo", "30m", _Db()
    ex.categoria = "inverse" if inverse else "linear"
    ex.con = _Con(inverse)
    ex.ordens = OrderExecutor(ex.con)
    ex.situacoes = {}
    ex.ordens.situacao_ordem = lambda par, i: ex.situacoes.get(i, {"status": "aberta"})
    ex.alavancagem = 1
    ex.posicao = None
    ex.estado = {"pnl_dia": 0.0, "trades_dia": 0, "dia": "2026-09-14", "ultima_decisao": None}
    ex.logs = []
    ex._log = lambda **kw: ex.logs.append(kw)
    ex._persistir_decisao = lambda *a, **k: None
    ex.alertas = SimpleNamespace(ordem=lambda *a, **k: None)
    ex.servicos = {}
    ex._con_publico = ex.con
    classe = tx.TradeirosHedge if inverse else tx.TradeirosTrades
    ex.tradeiros = classe(ex, perfil, planejador=lambda hedge: plano)
    return ex


def _plano(*decisoes, hedge=0.3):
    return Plano("teste", DIA0, 100.0, hedge, ["R31"], {}, list(decisoes))


COMPRA = Decisao("compra", ["R2", "R20"], "compra na VAL", zona=(95.0, 99.0), pesos_fatias=[0.1, 0.2, 0.3, 0.4], stop=90.0,
                 alvo=130.0, risco=0.01)
VENDA_LONGE = Decisao("venda_direcional", ["R2"], "venda na VAH", zona=(120.0, 125.0), pesos_fatias=[1.0], stop=130.0,
                      alvo=100.0, risco=0.02)


@pytest.fixture
def relogio(monkeypatch):
    r = _Relogio(DIA0 + 3_600_000)
    monkeypatch.setattr(tx, "_agora_ms", r)
    return r


def _c(hi, lo, close):
    return [0, close, hi, lo, close, 1.0]


# ------------------------------------------------------------------ conta de trades
def test_arma_a_decisao_mais_perto_com_as_fatias_do_plano(relogio):
    ex = _executor(SHAKA, _plano(VENDA_LONGE, COMPRA))
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    t = ex.tradeiros.trade
    assert t["tipo"] == "compra" and ex.posicao is None
    limitadas = [o for o in ex.con.enviadas if o["tipo"] == "limit"]
    assert [o["preco"] for o in limitadas] == [99.0, 97.7, 96.3, 95.0]
    assert [o["qty"] for o in limitadas] == sorted(o["qty"] for o in limitadas), "a fatia mais longe é a maior"
    medio = sum(o["preco"] * o["qty"] for o in limitadas) / sum(o["qty"] for o in limitadas)
    assert sum(o["qty"] for o in limitadas) * (medio - 90.0) == pytest.approx(100.0, rel=0.02), "todas as fatias + stop = 1% da banca"
    assert all(o["post_only"] and o["stop_loss"] == 90.0 and o["take_profit"] == 130.0 for o in limitadas)


def test_maroja_fora_do_valor_so_arma_depois_do_candle_de_reacao(relogio):
    reacao = Decisao("compra", ["R10"], "abaixo do valor", zona=(95.0, 99.0), pesos_fatias=[0.5, 0.5], stop=90.0, alvo=130.0,
                     risco=0.01, exige_reacao=True)
    ex = _executor(MAROJA, _plano(reacao))
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    assert not ex.con.enviadas and not ex.tradeiros.trade["armado"]
    ex.tradeiros.ciclo([_c(100, 96, 96.3)], 96.3, candle_novo=True)             # tocou e fechou embaixo
    assert not ex.con.enviadas
    ex.tradeiros.ciclo([_c(98.5, 94.5, 98.2)], 98.2, candle_novo=True)          # reação: fecha na metade de cima
    assert ex.tradeiros.trade["armado"] and ex.posicao is not None
    assert [o["tipo"] for o in ex.con.enviadas] == ["market"], "as duas fatias tocadas entram juntas a mercado"


def test_adota_as_limitadas_e_tira_o_risco_em_1r(relogio):
    ex = _executor(MAROJA, _plano(COMPRA))
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    q = [o["qty"] for o in ex.con.enviadas]
    ex.con.posicao = {"side": "buy", "quantidade": q[0] + q[1], "preco_entrada": 98.3}
    ex.tradeiros.ciclo([_c(100, 97, 97.5)], 97.5, candle_novo=False)
    assert ex.posicao is not None and len(ex.tradeiros.trade["executadas"]) == 2
    ex.tradeiros.ciclo([_c(107, 100, 106.8)], 106.8, candle_novo=False)          # 98,3 + 8,3 = 1 R
    t = ex.tradeiros.trade
    assert t["risco_tirado"] and t["stop"] == pytest.approx(98.3) and not t["pendentes"]
    reducao = [o for o in ex.con.enviadas if o.get("reduce_only")]
    assert reducao and reducao[0]["qty"] == pytest.approx(math.floor((q[0] + q[1]) * 0.25 * 1000) / 1000)
    assert ex.con.canceladas == 1


def test_entrada_mal_preenchida_que_saiu_da_zona_fecha_r24(relogio):
    ex = _executor(SHAKA, _plano(COMPRA))
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    q0 = ex.con.enviadas[0]["qty"]
    ex.con.posicao = {"side": "buy", "quantidade": q0, "preco_entrada": 99.0}
    ex.tradeiros.ciclo([_c(100, 98.9, 99.5)], 99.5, candle_novo=False)
    ex.tradeiros.ciclo([_c(104, 102, 103.5)], 103.5, candle_novo=True)           # acima de 99 + 4 de largura
    assert ex.tradeiros.trade is None
    assert any("R24" in (l.get("motivo") or "") for l in ex.logs)


def test_virada_do_dia_cancela_a_escada_que_nao_executou(relogio):
    ex = _executor(SHAKA, _plano(COMPRA))
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    assert ex.con.canceladas == 0
    relogio.t += DIA_MS
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    assert ex.con.canceladas == 1 and ex.tradeiros.trade is not None and ex.tradeiros.trade["dia"] == DIA0 // DIA_MS + 1


def test_plano_que_falha_tenta_de_novo_depois_de_um_minuto(relogio):
    chamadas = []

    def falha(hedge):
        chamadas.append(1)
        raise ConnectionError("sem rede")

    ex = _executor(SHAKA, None)
    ex.tradeiros.planejador = falha
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=False)
    assert len(chamadas) == 1 and ex.tradeiros.dia is None
    relogio.t += 61_000
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=False)
    assert len(chamadas) == 2


# ------------------------------------------------------------------ conta de hedge
AUMENTAR = Decisao("hedge_aumentar", ["R28"], "escada", zona=(110.0, 115.0), pesos_fatias=[1.0], stop=120.0, fracao_hedge=0.1)
REALIZAR = Decisao("hedge_realizar", ["R28"], "recompra", zona=(85.0, 90.0), pesos_fatias=[1.0], fracao_hedge=0.1)


def test_hedge_vende_a_base_a_mercado_e_arma_as_duas_escadas(relogio):
    ex = _executor(MAROJA, _plano(AUMENTAR, REALIZAR), inverse=True)
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    base, venda, recompra = ex.con.enviadas
    assert (base["tipo"], base["side"], base["qty"]) == ("market", "sell", 30.0)   # 30% de 1 BTC a 100
    assert (venda["side"], venda["preco"], venda["qty"], venda["reduce_only"]) == ("sell", 112.5, 11.0, False)
    assert (recompra["side"], recompra["preco"], recompra["qty"], recompra["reduce_only"]) == ("buy", 87.5, 8.0, True)
    assert ex.tradeiros.contratos() == 30 and not ex.con.stops, "a base não tem stop"


def test_venda_da_escada_ganha_stop_na_corretora_e_recompra_realiza_lifo(relogio):
    ex = _executor(MAROJA, _plano(AUMENTAR, REALIZAR), inverse=True)
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    id_venda, id_recompra = ex.con.enviadas[1]["id"], ex.con.enviadas[2]["id"]
    ex.situacoes[id_venda] = {"status": "executada", "preco_exec": 112.5}
    ex.con.posicao = {"side": "sell", "quantidade": 41.0, "preco_entrada": 103.0}
    relogio.t += 61_000
    ex.tradeiros.ciclo([_c(113, 100, 112)], 112.0, candle_novo=False)
    assert ex.tradeiros.contratos() == 41 and ex.con.stops[-1]["gatilho"] == 120.0 and ex.con.stops[-1]["qty"] == 11.0
    ex.situacoes[id_recompra] = {"status": "executada", "preco_exec": 87.5}
    ex.con.posicao = {"side": "sell", "quantidade": 33.0, "preco_entrada": 103.0}
    relogio.t += 61_000
    ex.tradeiros.ciclo([_c(100, 87, 88)], 88.0, candle_novo=False)
    assert ex.tradeiros.contratos() == 33
    assert "s0" in ex.con.canceladas_ids and ex.con.stops[-1]["qty"] == 3.0, "o stop da escada que sobrou é refeito"
    assert ex.tradeiros.realizado_btc > 0


def test_contratos_a_menos_na_corretora_contam_o_pedagio(relogio):
    ex = _executor(SHAKA, _plano(AUMENTAR), inverse=True)
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    ex.situacoes[ex.con.enviadas[1]["id"]] = {"status": "executada", "preco_exec": 112.5}
    ex.con.posicao = {"side": "sell", "quantidade": 41.0, "preco_entrada": 103.0}
    relogio.t += 61_000
    ex.tradeiros.ciclo([_c(113, 100, 112)], 112.0, candle_novo=False)
    ex.con.posicao = {"side": "sell", "quantidade": 30.0, "preco_entrada": 100.0}  # o stop de 120 executou
    relogio.t += 61_000
    ex.tradeiros.ciclo([_c(121, 112, 119)], 119.0, candle_novo=False)
    assert ex.tradeiros.stops == 0 and ex.tradeiros.contratos() == 41, "uma leitura só pode ser atraso da corretora"
    relogio.t += 61_000
    ex.tradeiros.ciclo([_c(120, 115, 118)], 118.0, candle_novo=False)
    assert ex.tradeiros.stops == 1 and ex.tradeiros.contratos() == 30 and ex.tradeiros.realizado_btc < 0


def test_sem_saldo_em_btc_nao_opera(relogio):
    ex = _executor(SHAKA, _plano(AUMENTAR), inverse=True)
    ex.con.obter_saldo = lambda moeda: {"total": 0.0}
    ex.tradeiros.ciclo([_c(101, 100, 100)], 100.0, candle_novo=True)
    assert not ex.con.enviadas and "sem saldo em BTC" in ex.logs[-1]["motivo"]
