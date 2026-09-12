"""
Intervenção manual pelo painel: quem manda a ordem é a thread do robô, o painel só deixa o pedido.
"""
from types import SimpleNamespace

import pytest

import core.range_executor as rx
from core.bot_executor import BotExecutor
from core.executor_real import OrderExecutor
from core.range_tradeiros import Plano


class _Con:
    modo_execucao = "simulador"
    pode_enviar_ordens = False

    def __init__(self):
        self.canceladas = 0
        self.stops = []

    def arredondar_quantidade(self, par, q):
        return round(q, 4)

    def arredondar_preco(self, par, p):
        return round(p, 1)

    def obter_preco_atual(self, par):
        return 104.0

    def obter_posicao(self, par):
        return None

    def cancelar_entradas_abertas(self, par):
        self.canceladas += 1
        return 2

    def atualizar_stop_posicao(self, par, sl=None, tp=None, idx=0):
        self.stops.append(sl)


class _Db:
    def add(self, *a):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


COMPRA = Plano(lado=1, niveis=[100.0, 99.0, 98.0, 97.0, 96.0], stop=90.0, alvo1=105.0, alvo2=120.0, jogada="borda",
               motivo="borda: compra no VAL")


def _executor(monkeypatch):
    monkeypatch.setattr(rx.RangeExecutor, "ler", lambda self: {"plano": COMPRA, "contexto": None, "motivo": "teste", "candle_ts": 1})
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = SimpleNamespace(id=10, nome="Range", grade_json=None, banca=10_000.0, risco_pct=0.01, max_alocacao_pct=5.0,
                             position_mode="one-way", trailing_manual=False, max_trades_dia=10, max_perda_dia_pct=0.03)
    ex.bot_id, ex.nome = 10, "Range"
    ex.par, ex.modo, ex.timeframe, ex.db = "BTCUSDT", "simulador", "30m", _Db()
    ex.con = _Con()
    ex._con_publico = ex.con
    ex.ordens = OrderExecutor(ex.con)
    ex.alavancagem = 1
    ex.posicao = None
    ex.inverse = ex.fatias = None
    ex.ordem_pendente = None
    ex.estado = {"pnl_dia": 0.0, "trades_dia": 0, "dia": "2026-09-11", "ultima_decisao": None}
    ex.logs = []
    ex._log = lambda **kw: ex.logs.append(kw)
    ex._persistir_decisao = lambda *a, **k: None
    ex.alertas = SimpleNamespace(ordem=lambda *a, **k: None)
    ex.range = rx.RangeExecutor(ex, leitor_lsr=SimpleNamespace(contexto=lambda: None))
    ex._acordar = __import__("threading").Event()
    ex._pedidos, ex._trava_pedidos, ex.intervencoes = [], __import__("threading").Lock(), {}
    return ex


def _com_posicao(monkeypatch):
    """Robô 10 com a escada armada e duas fatias executadas (preço médio 99,5)."""
    ex = _executor(monkeypatch)
    ex.range.ciclo([[0, 100.5, 101, 100.5, 100.5, 1.0]], 100.5, candle_novo=True)
    ex.range.ciclo([[0, 99, 100.4, 98.5, 99, 1.0]], 99.0, candle_novo=True)
    assert ex.posicao is not None and len(ex.range.trade["pendentes"]) == 3
    return ex


def test_pedido_do_painel_nao_executa_sozinho(monkeypatch):
    ex = _com_posicao(monkeypatch)
    token = ex.pedir_intervencao("fechar")
    assert ex.resultado_intervencao(token)["status"] == "pendente"
    assert ex.posicao is not None, "a thread da API não pode mexer na posição"
    assert ex._acordar.is_set(), "o robô é acordado para executar no ato"


def test_fechar_encerra_a_posicao_e_cancela_a_escada(monkeypatch):
    ex = _com_posicao(monkeypatch)
    pos = ex.posicao
    token = ex.pedir_intervencao("fechar", motivo="Quero garantir o ganho")
    ex._processar_pedidos()
    r = ex.resultado_intervencao(token)
    assert r["status"] == "feita" and r["fechada"] is True and r["resultado"] > 0
    assert ex.posicao is None and ex.range.trade is None
    assert pos.status == "fechada" and pos.pnl > 0 and "Quero garantir o ganho" in pos.motivo_saida


def test_parcial_realiza_metade_e_mantem_o_resto(monkeypatch):
    ex = _com_posicao(monkeypatch)
    q0 = float(ex.posicao.quantidade)
    token = ex.pedir_intervencao("parcial", fracao=0.5)
    ex._processar_pedidos()
    r = ex.resultado_intervencao(token)
    assert r["status"] == "feita" and r["quantidade"] == pytest.approx(q0 / 2)
    assert ex.posicao is not None and float(ex.posicao.quantidade) == pytest.approx(q0 / 2)
    assert float(ex.posicao.pnl_parcial) > 0 and ex.estado["pnl_dia"] > 0


def test_zero_a_zero_move_o_stop_para_a_entrada(monkeypatch):
    ex = _com_posicao(monkeypatch)
    token = ex.pedir_intervencao("zero_a_zero")
    ex._processar_pedidos()
    assert ex.resultado_intervencao(token)["status"] == "feita"
    assert float(ex.posicao.sl) == pytest.approx(float(ex.posicao.preco_entrada), abs=0.1)


def test_cancelar_escada_nao_toca_na_posicao(monkeypatch):
    ex = _com_posicao(monkeypatch)
    token = ex.pedir_intervencao("cancelar_escada")
    ex._processar_pedidos()
    assert ex.resultado_intervencao(token)["canceladas"] == 3
    assert ex.posicao is not None and not ex.range.trade["pendentes"]


def test_sem_posicao_devolve_erro_em_vez_de_quebrar_o_ciclo(monkeypatch):
    ex = _executor(monkeypatch)
    token = ex.pedir_intervencao("fechar")
    ex._processar_pedidos()
    r = ex.resultado_intervencao(token)
    assert r["status"] == "erro" and "posição" in r["erro"].lower()


def test_hedge_inverso_nao_aceita_intervencao_por_aqui(monkeypatch):
    ex = _executor(monkeypatch)
    ex.inverse = object()
    token = ex.pedir_intervencao("fechar")
    ex._processar_pedidos()
    assert ex.resultado_intervencao(token)["status"] == "erro"


def test_stop_e_alvo_novos_valem_para_a_corretora_e_para_a_estrategia(monkeypatch):
    ex = _com_posicao(monkeypatch)
    enviados = []
    ex.ordens.atualizar_stop = lambda par, sl=None, tp=None, pm="one-way", direcao="buy": enviados.append((sl, tp)) or True
    token = ex.pedir_intervencao("stop_alvo", dados={"sl": 97.0, "tp": 130.0})
    ex._processar_pedidos()
    r = ex.resultado_intervencao(token)
    assert r["status"] == "feita" and r["sl"] == 97.0 and r["tp"] == 130.0
    assert float(ex.posicao.sl) == 97.0 and float(ex.posicao.tp) == 130.0
    assert enviados[-1] == (97.0, 130.0), "o stop e o alvo novos foram para a corretora"
    assert ex.range.trade["stop"] == 97.0 and ex.range.trade["alvo2"] == 130.0, "a estratégia passa a gerir pelo novo"


def test_stop_do_lado_errado_e_recusado(monkeypatch):
    """Preço em 104: um stop acima dele fecharia a compra na hora, como se fosse ordem a mercado."""
    ex = _com_posicao(monkeypatch)
    token = ex.pedir_intervencao("stop_alvo", dados={"sl": 110.0})
    ex._processar_pedidos()
    r = ex.resultado_intervencao(token)
    assert r["status"] == "erro" and "lado errado" in r["erro"]
    assert float(ex.posicao.sl) != 110.0


def test_alvo_do_lado_errado_e_recusado(monkeypatch):
    ex = _com_posicao(monkeypatch)
    token = ex.pedir_intervencao("stop_alvo", dados={"tp": 100.0})
    ex._processar_pedidos()
    assert ex.resultado_intervencao(token)["status"] == "erro"
