"""
Robô "votação + fatias": o que roda ao vivo tem que ser o que foi testado no laboratório.
"""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import core.fatias_executor as fe
from core.bot_executor import BotExecutor
from core.estrategia_votacao import PADRAO, niveis_fatias, quantidade_total
from core.executor_real import OrderExecutor
from core.lab_combinacoes import Variante, lado_da_votacao, lados


# ------------------------------------------------------------------ paridade com o backtest
def test_votacao_ao_vivo_e_a_mesma_do_backtest():
    rng = np.random.default_rng(3)
    cols = ["VWAP_janela", "VWAP_sessao", "TPO", "Volume_Profile", "Order_Block", "Fibonacci", "Regime", "Elliott"]
    d = pd.DataFrame({c: rng.integers(-1, 2, 400) for c in cols})
    for v in (PADRAO.variante, Variante(("TPO", "Order_Block", "Fibonacci"), 2, True, False),
              Variante(("VWAP_janela", "VWAP_sessao", "Fibonacci"), 3, False, False)):
        vet = lados(d, v)
        um_a_um = [lado_da_votacao(row._asdict(), v) for row in d.itertuples(index=False)]
        assert list(vet) == um_a_um


def test_fatias_e_tamanho_perdem_o_risco_no_pior_caso():
    niveis = niveis_fatias(1, 100.0, 10.0)
    assert niveis == pytest.approx([100, 98, 96, 94, 92])
    q = quantidade_total(10_000, 0.01, 1, 100.0, 10.0)          # risco 1% = 100
    medio = sum(niveis) / 5
    assert q * (medio - 90.0) == pytest.approx(100.0)


# ------------------------------------------------------------------ executor
class _Con:
    modo_execucao = "simulador"
    pode_enviar_ordens = False

    def __init__(self):
        self.canceladas = 0
        self.posicao = "nao_consultada"

    def arredondar_quantidade(self, par, q):
        return round(q, 4)

    def arredondar_preco(self, par, p):
        return round(p, 1)

    def obter_preco_atual(self, par):
        return 100.0

    def obter_posicao(self, par):
        return None if self.posicao == "nao_consultada" else self.posicao

    def cancelar_entradas_abertas(self, par):
        self.canceladas += 1
        return 3


class _Db:
    def add(self, *a):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def _executor(simulado=True):
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = SimpleNamespace(id=9, nome="Fatias", grade_json=None, banca=10_000.0, risco_pct=0.01, max_alocacao_pct=5.0,
                             position_mode="one-way", trailing_manual=False, max_trades_dia=10, max_perda_dia_pct=0.03)
    ex.par, ex.modo, ex.timeframe, ex.db = "BTCUSDT", "simulador" if simulado else "demo", "4h", _Db()
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
    ex.fatias = fe.FatiasExecutor(ex)
    return ex


COMPRA = {"acao": "buy", "lado": 1, "preco": 100.0, "risco": 10.0, "sl": 90.0, "tp": 130.0, "candle_ts": 1,
          "niveis": [100.0, 98.0, 96.0, 94.0, 92.0], "votos": {"TPO": 1, "Volume_Profile": 1}, "motivo": "teste"}


def _candle(hi, lo, close):
    return [0, close, hi, lo, close, 1.0]


def test_abre_a_primeira_fatia_e_deixa_quatro_no_livro(monkeypatch):
    monkeypatch.setattr(fe, "decidir", lambda ohlcv, cfg: dict(COMPRA))
    ex = _executor()
    ex.fatias.ciclo([_candle(100, 100, 100)], 100.0, candle_novo=True)
    assert ex.posicao is not None and ex.posicao.direcao == "buy"
    t = ex.fatias.trade
    assert len(t["executadas"]) == 1 and [p["preco"] for p in t["pendentes"]] == [98.0, 96.0, 94.0, 92.0]
    assert json.loads(ex.bot.grade_json)["trade"]["stop"] == 90.0, "o estado sobrevive a um reinício"


def test_recuo_executa_fatias_e_o_alvo_fecha(monkeypatch):
    monkeypatch.setattr(fe, "decidir", lambda ohlcv, cfg: dict(COMPRA))
    ex = _executor()
    ex.fatias.ciclo([_candle(100, 100, 100)], 100.0, candle_novo=True)
    ex.fatias.ciclo([_candle(99, 95, 97)], 97.0, candle_novo=True)          # executa 98 e 96
    assert len(ex.fatias.trade["executadas"]) == 3
    assert ex.posicao.preco_entrada == pytest.approx(98.0)
    pos = ex.posicao
    ex.fatias.ciclo([_candle(131, 100, 130)], 130.0, candle_novo=True)      # alvo
    assert ex.posicao is None and ex.fatias.trade is None and ex.bot.grade_json is None
    assert pos.status == "fechada" and pos.pnl > 0


def test_stop_fecha_com_todas_as_fatias_executadas(monkeypatch):
    monkeypatch.setattr(fe, "decidir", lambda ohlcv, cfg: dict(COMPRA))
    ex = _executor()
    ex.fatias.ciclo([_candle(100, 100, 100)], 100.0, candle_novo=True)
    ex.fatias.ciclo([_candle(99, 91, 92)], 92.0, candle_novo=True)          # todas executam
    pos = ex.posicao
    ex.fatias.ciclo([_candle(92, 89, 89)], 89.0, candle_novo=True)          # stop
    assert pos.status == "fechada" and pos.pnl < 0
    assert pos.pnl == pytest.approx(-100.0, rel=0.1), "o pior caso perde o risco planejado (1% da banca)"


def test_sai_por_tempo_depois_de_24_candles(monkeypatch):
    monkeypatch.setattr(fe, "decidir", lambda ohlcv, cfg: dict(COMPRA))
    ex = _executor()
    ex.fatias.ciclo([_candle(100, 100, 100)], 100.0, candle_novo=True)
    pos = ex.posicao
    for _ in range(23):
        ex.fatias.ciclo([_candle(101, 99.5, 100)], 100.0, candle_novo=True)
        assert ex.posicao is not None
    ex.fatias.ciclo([_candle(101, 99.5, 100.5)], 100.5, candle_novo=True)
    assert ex.posicao is None and "tempo" in pos.motivo_saida


def test_sem_votos_nao_abre(monkeypatch):
    monkeypatch.setattr(fe, "decidir", lambda ohlcv, cfg: {"acao": "hold", "motivo": "sem votos", "candle_ts": 1})
    ex = _executor()
    ex.fatias.ciclo([_candle(100, 100, 100)], 100.0, candle_novo=True)
    assert ex.posicao is None and ex.fatias.trade is None


def test_corretora_fechou_a_posicao_cancela_as_fatias_que_sobraram():
    """Alvo executado na corretora com fatias ainda no livro: se ficassem, virariam entradas sem gestão."""
    ex = _executor(simulado=False)
    ex.posicao = SimpleNamespace(direcao="buy", quantidade=0.2, preco_entrada=100.0, taxas=0.0)
    ex.fatias.trade = {"lado": 1, "stop": 90.0, "alvo": 130.0, "risco": 10.0, "candles": 3, "q": 0.2,
                       "executadas": [{"k": 1}], "pendentes": [{"k": 2, "preco": 98.0, "q": 0.2, "ordem_id": "x"}]}
    saidas = []
    ex._registrar_saida = lambda preco, motivo, **k: saidas.append(motivo)
    ex.fatias.ciclo([_candle(131, 100, 130)], 130.0, candle_novo=False)
    assert ex.con.canceladas == 1 and saidas == ["SL/TP executado pela exchange"]
    assert ex.fatias.trade is None


def test_corretora_executou_fatias_atualiza_preco_medio():
    ex = _executor(simulado=False)
    ex.posicao = SimpleNamespace(direcao="buy", quantidade=0.2, preco_entrada=100.0, taxas=0.0, quantidade_inicial=0.2)
    ex.fatias.trade = {"lado": 1, "stop": 90.0, "alvo": 130.0, "risco": 10.0, "candles": 0, "q": 0.2,
                       "executadas": [{"k": 1, "preco": 100.0, "q": 0.2}],
                       "pendentes": [{"k": 2, "preco": 98.0, "q": 0.2, "ordem_id": "a"},
                                     {"k": 3, "preco": 96.0, "q": 0.2, "ordem_id": "b"}]}
    ex.con.posicao = {"side": "buy", "quantidade": 0.6, "preco_entrada": 98.0}
    ex.fatias.ciclo([_candle(99, 95, 97)], 97.0, candle_novo=False)
    assert ex.posicao.quantidade == 0.6 and ex.posicao.preco_entrada == 98.0
    assert len(ex.fatias.trade["executadas"]) == 3 and not ex.fatias.trade["pendentes"]


def test_queda_ate_o_stop_executa_as_fatias_do_caminho_antes(monkeypatch):
    """Um candle de 100 até 89 passa por 98, 96, 94 e 92 antes do stop de 90: perde o risco inteiro, não 1/5 dele."""
    monkeypatch.setattr(fe, "decidir", lambda ohlcv, cfg: dict(COMPRA))
    ex = _executor()
    ex.fatias.ciclo([_candle(100, 100, 100)], 100.0, candle_novo=True)
    pos = ex.posicao
    ex.fatias.ciclo([_candle(100, 89, 89)], 89.0, candle_novo=True)
    assert pos.status == "fechada" and pos.pnl == pytest.approx(-100.0, rel=0.1)
