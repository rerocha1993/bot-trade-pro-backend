"""
Robô do jogo do range: o que roda ao vivo tem que ser o que foi testado no backtest.
"""
import datetime as dt
import os
from types import SimpleNamespace

import pandas as pd
import pytest

import core.range_executor as rx
from core.bot_executor import BotExecutor
from core.executor_real import OrderExecutor
from core.range_tradeiros import BacktestRange, Plano, leitura_ao_vivo
from core.tpo_sessao import blocos_30m

CSV = os.path.join("data", "historico", "BTCUSDT_binance_15m.csv")


def _ms(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


# ------------------------------------------------------------------ paridade com o backtest
@pytest.mark.skipif(not os.path.exists(CSV), reason="sem o histórico de 15m")
def test_leitura_ao_vivo_arma_os_mesmos_planos_do_backtest():
    df = pd.read_csv(CSV)
    df = df[(df.timestamp >= _ms("2025-01-01")) & (df.timestamp < _ms("2025-05-01"))].sort_values("timestamp")
    blocos = blocos_30m(df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist())
    armados = []

    class Espiao(BacktestRange):
        def _sinal(self, ctx, b, ac, toques, desvio):
            pl = super()._sinal(ctx, b, ac, toques, desvio)
            if pl is not None:
                armados.append((b[0], pl))
            return pl

    Espiao(blocos, "borda", "tradeiros").executar(_ms("2025-02-01"))
    assert len(armados) >= 3, "o período precisa ter escadas armadas para a comparação valer"
    idx = {b[0]: i for i, b in enumerate(blocos)}
    for ts, pl in armados:
        ao_vivo = leitura_ao_vivo(blocos[:idx[ts] + 1], "borda")["plano"]
        assert ao_vivo is not None
        assert (ao_vivo.lado, ao_vivo.stop, ao_vivo.alvo1, ao_vivo.alvo2) == (pl.lado, pl.stop, pl.alvo1, pl.alvo2)
        assert ao_vivo.niveis == pytest.approx(pl.niveis)


# ------------------------------------------------------------------ executor
class _Con:
    modo_execucao = "simulador"
    pode_enviar_ordens = False

    def __init__(self):
        self.canceladas = 0
        self.posicao = None

    def arredondar_quantidade(self, par, q):
        return round(q, 4)

    def arredondar_preco(self, par, p):
        return round(p, 1)

    def obter_preco_atual(self, par):
        return 100.0

    def obter_posicao(self, par):
        return self.posicao

    def cancelar_entradas_abertas(self, par):
        self.canceladas += 1
        return 1

    def atualizar_stop_posicao(self, *a):
        pass

    def criar_ordem(self, par, side, qty, tipo="market", preco=None, **k):
        return {"id": f"o-{side}-{preco}", "average": None if tipo == "limit" else 100.0, "price": preco}


class _Db:
    def add(self, *a):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def _executor(simulado=True):
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = SimpleNamespace(id=10, nome="Range", grade_json=None, banca=10_000.0, risco_pct=0.01, max_alocacao_pct=5.0,
                             position_mode="one-way", trailing_manual=False, max_trades_dia=10, max_perda_dia_pct=0.03)
    ex.par, ex.modo, ex.timeframe, ex.db = "BTCUSDT", "simulador" if simulado else "demo", "30m", _Db()
    ex.con = _Con()
    if not simulado:
        ex.con.modo_execucao, ex.con.pode_enviar_ordens = "demo", True
    ex.ordens = OrderExecutor(ex.con)
    ex.alavancagem = 1
    ex.posicao = None
    ex.estado = {"pnl_dia": 0.0, "trades_dia": 0, "dia": "2026-09-11", "ultima_decisao": None}
    ex.logs = []
    ex._log = lambda **kw: ex.logs.append(kw)
    ex._persistir_decisao = lambda *a, **k: None
    ex.alertas = SimpleNamespace(ordem=lambda *a, **k: None)
    ex.range = rx.RangeExecutor(ex, leitor_lsr=SimpleNamespace(contexto=lambda: None))
    return ex


COMPRA = Plano(lado=1, niveis=[100.0, 99.0, 98.0, 97.0, 96.0], stop=90.0, alvo1=105.0, alvo2=120.0, jogada="borda",
               motivo="borda: compra no VAL")


def _leitura(plano):
    return lambda self: {"plano": plano, "contexto": None, "motivo": plano.motivo if plano else "no meio do range",
                         "candle_ts": 1}


def _c(hi, lo, close):
    return [0, close, hi, lo, close, 1.0]


def test_arma_a_escada_inteira_no_livro_quando_o_preco_ainda_nao_chegou(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor()
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    t = ex.range.trade
    assert ex.posicao is None and [p["preco"] for p in t["pendentes"]] == [100.0, 99.0, 98.0, 97.0, 96.0]
    assert t["q"] == pytest.approx(100 / 8 / 5), "todas as fatias + stop = perde 1% da banca"


def test_fatias_que_o_preco_ja_passou_saem_a_mercado(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor()
    ex.range.ciclo([_c(99, 98.5, 98.5)], 98.5, candle_novo=True)
    assert ex.posicao is not None and ex.posicao.quantidade == pytest.approx(2 * 2.5)
    assert [p["preco"] for p in ex.range.trade["pendentes"]] == [98.0, 97.0, 96.0]


def test_tira_o_risco_no_poc_e_sai_no_zero_a_zero(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor()
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    ex.range.ciclo([_c(100.4, 98.5, 99)], 99.0, candle_novo=True)             # executa 100 e 99
    assert ex.posicao.preco_entrada == pytest.approx(99.5) and ex.posicao.quantidade == pytest.approx(5.0)
    ex.range.ciclo([_c(105.2, 99.6, 104)], 104.0, candle_novo=True)           # POC: metade sai, stop no médio
    t, pos = ex.range.trade, ex.posicao
    assert t["parcial_feita"] and t["stop"] == pytest.approx(99.5) and not t["pendentes"]
    assert pos.quantidade == pytest.approx(2.5) and pos.pnl_parcial == pytest.approx(5.5 * 2.5, rel=0.01)
    ex.range.ciclo([_c(104, 99.4, 99.6)], 99.6, candle_novo=True)             # volta: zero a zero
    assert ex.posicao is None and ex.range.trade is None and ex.bot.grade_json is None
    assert pos.pnl > 0 and "Zero a zero" in pos.motivo_saida


def test_stop_com_todas_as_fatias_perde_o_risco_planejado(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor()
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    ex.range.ciclo([_c(100.4, 95.5, 96)], 96.0, candle_novo=True)             # todas executam
    pos = ex.posicao
    ex.range.ciclo([_c(96, 89, 89.5)], 89.5, candle_novo=True)
    assert pos.status == "fechada" and pos.pnl == pytest.approx(-100.0, rel=0.1)


def test_escada_sem_execucao_vence_em_8_blocos(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor()
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    for _ in range(7):
        ex.range.ciclo([_c(102, 100.5, 101)], 101.0, candle_novo=True)
        assert ex.range.trade is not None
    ex.range.ciclo([_c(102, 100.5, 101)], 101.0, candle_novo=True)
    assert ex.range.trade is None and ex.posicao is None


def test_preco_foi_ao_poc_sem_executar_cancela_a_escada(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor()
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    ex.range.ciclo([_c(105.5, 100.2, 105)], 105.0, candle_novo=True)
    assert ex.range.trade is None and "POC" in ex.logs[-1]["motivo"]


def test_sem_plano_nao_arma(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(None))
    ex = _executor()
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    assert ex.range.trade is None and ex.estado["ultima_decisao"]["acao"] == "hold"


def test_demo_adota_a_posicao_quando_as_limitadas_executam(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor(simulado=False)
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    assert ex.posicao is None and len(ex.range.trade["pendentes"]) == 5
    ex.con.posicao = {"side": "buy", "quantidade": 5.0, "preco_entrada": 99.5}
    ex.range.ciclo([_c(100.4, 98.5, 99)], 99.0, candle_novo=False)
    assert ex.posicao is not None and ex.posicao.quantidade == 5.0
    assert len(ex.range.trade["executadas"]) == 2 and len(ex.range.trade["pendentes"]) == 3


def test_demo_corretora_fechou_cancela_o_que_sobrou():
    ex = _executor(simulado=False)
    ex.posicao = SimpleNamespace(direcao="buy", quantidade=5.0, preco_entrada=99.5, taxas=0.0)
    ex.range.trade = {"lado": 1, "niveis": COMPRA.niveis, "stop": 90.0, "stop_inicial": 90.0, "alvo1": 105.0, "alvo2": 120.0,
                      "q": 2.5, "executadas": [{"preco": 100.0, "q": 2.5}], "blocos_armado": 0, "blocos": 3,
                      "pendentes": [{"preco": 98.0, "q": 2.5, "ordem_id": "x"}], "parcial_feita": False, "motivo": "t"}
    saidas = []
    ex._registrar_saida = lambda preco, motivo, **k: saidas.append(motivo)
    ex.range.ciclo([_c(121, 100, 120)], 120.0, candle_novo=False)
    assert ex.con.canceladas == 1 and saidas == ["SL/TP executado pela exchange"] and ex.range.trade is None


def test_bloco_que_atravessa_a_escada_ate_o_stop_perde_o_risco_inteiro(monkeypatch):
    """Sem posição, um bloco de 100,4 até 89 executa as 5 fatias e bate o stop no MESMO bloco."""
    monkeypatch.setattr(rx.RangeExecutor, "ler", _leitura(COMPRA))
    ex = _executor()
    ex.range.ciclo([_c(101, 100.5, 100.5)], 100.5, candle_novo=True)
    ex.range.ciclo([_c(100.4, 89, 89.5)], 89.5, candle_novo=True)
    assert ex.posicao is None and ex.range.trade is None, "antes a posição ficava aberta até o bloco seguinte"
    saida = [x for x in ex.logs if x.get("tipo_operacao") == "saida"]
    assert len(saida) == 1 and saida[0]["resultado"] == pytest.approx(-100.0, rel=0.1)
