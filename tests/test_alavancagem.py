"""Alavancagem: o risco real de 50x e 100x é a liquidação chegar antes do stop."""
import pytest

from core.alavancagem import (
    ALAVANCAGENS, alavancagem_maxima, distancia_liquidacao, normalizar, tabela, validar_stop,
)


def test_opcoes_pedidas_existem():
    for a in (10, 20, 30, 50, 100):
        assert a in ALAVANCAGENS


def test_distancia_cai_com_a_alavancagem():
    dists = [distancia_liquidacao(a) for a in ALAVANCAGENS]
    assert dists == sorted(dists, reverse=True)
    assert distancia_liquidacao(100) == pytest.approx(0.005, abs=1e-6)
    assert distancia_liquidacao(50) == pytest.approx(0.015, abs=1e-6)
    assert distancia_liquidacao(10) == pytest.approx(0.095, abs=1e-6)


def test_normalizar_arredonda_para_baixo_e_respeita_teto():
    assert normalizar(37) == 30
    assert normalizar(100) == 100
    assert normalizar(0) == 1
    assert normalizar("abc") == 1
    assert normalizar(100, maximo_exchange=25) == 20


def test_stop_alem_da_liquidacao_e_recusado():
    """Stop de 1,5% com 100x: a liquidação está a 0,5%, então a posição morre antes do stop."""
    r = validar_stop(80_000, 78_800, alavancagem=100)
    assert r["ok"] is False
    assert r["alavancagem_maxima"] < 100
    assert "liquidada antes do stop" in r["motivo"]


def test_stop_curto_permite_alavancagem_alta():
    r = validar_stop(80_000, 79_760, alavancagem=100)   # stop de 0,30%
    assert r["ok"] is True
    assert r["preco_liquidacao"] < 79_760


def test_alavancagem_maxima_e_coerente_com_validar():
    for dist in (0.002, 0.005, 0.01, 0.02, 0.05, 0.12):
        a = alavancagem_maxima(dist)
        entrada = 100.0
        sl = entrada * (1 - dist)
        assert validar_stop(entrada, sl, a)["ok"], f"{a}x deveria aceitar stop de {dist:.2%}"
        maiores = [x for x in ALAVANCAGENS if x > a]
        if maiores:
            assert not validar_stop(entrada, sl, maiores[0])["ok"], f"{maiores[0]}x não deveria aceitar {dist:.2%}"


def test_venda_calcula_liquidacao_acima_da_entrada():
    r = validar_stop(80_000, 80_200, alavancagem=20)   # short com stop acima
    assert r["preco_liquidacao"] > 80_000


def test_alavancagem_1_nunca_bloqueia_stop_normal():
    """Bots em 1x (o padrão) não podem ser afetados pela trava."""
    for dist in (0.005, 0.02, 0.10, 0.30):
        r = validar_stop(80_000, 80_000 * (1 - dist), alavancagem=1)
        assert r["ok"] is True


def test_margem_cruzada_usa_a_banca():
    """Em cruzada a banca inteira sustenta a posição, então a distância é maior que em isolada."""
    isolada = distancia_liquidacao(50, margin_mode="isolated")
    cruzada = distancia_liquidacao(50, margin_mode="cross", banca=10_000, notional=20_000)
    assert cruzada > isolada


def test_sem_stop_nao_bloqueia():
    r = validar_stop(80_000, None, alavancagem=100)
    assert r["ok"] is True


def test_tabela_tem_uma_linha_por_opcao():
    t = tabela()
    assert [l["alavancagem"] for l in t] == list(ALAVANCAGENS)
    for l in t:
        assert l["stop_maximo_pct"] < l["distancia_liquidacao_pct"]


def test_executor_recusa_entrada_que_liquidaria_antes_do_stop():
    """Prova que a trava está ligada no executor, não só na fórmula."""
    from core.backtest_engine import bot_padrao
    from core.bot_executor import BotExecutor

    class DB:
        def add(self, *a): pass
        def commit(self): pass
        def rollback(self): pass

    class OrdensEspiao:
        def __init__(self): self.chamou = False
        def abrir(self, *a, **k):
            self.chamou = True
            return {"preco_exec": 100.0, "quantidade": 1.0, "ordem_id": "x", "taxa": 0.0}

    class Conector:
        def arredondar_quantidade(self, par, qty): return round(qty, 3)

    def montar(alavancagem):
        bot = bot_padrao(banca=10_000, risco_pct=0.01, max_alocacao_pct=0.5, alavancagem=alavancagem,
                         margin_mode="isolated", tipo_entrada="mercado")
        ex = BotExecutor.__new__(BotExecutor)
        ex.bot, ex.db, ex.modo, ex.par = bot, DB(), "simulador", "BTCUSDT"
        ex.con = Conector()
        ex.alavancagem = alavancagem
        ex.ordens = OrdensEspiao()
        ex.estado = {"dia": "x", "pnl_dia": 0.0, "trades_dia": 0}
        ex.logs = []
        ex._log = lambda **kw: ex.logs.append(kw)
        ex.ultimo_candle_ts = 0
        return ex

    decisao = {"acao": "buy", "sl": 98.5, "tp": 105.0, "motivo": "teste"}   # stop de 1,5%

    caro = montar(100)
    caro.abrir_posicao(dict(decisao), 100.0)
    assert caro.ordens.chamou is False, "entrada com 100x e stop de 1,5% deveria ser recusada"
    assert any("recusada" in (l.get("motivo") or "") for l in caro.logs)

    seguro = montar(10)
    seguro.alertas = type("A", (), {"ordem": lambda *a, **k: None})()
    seguro.abrir_posicao(dict(decisao), 100.0)
    assert seguro.ordens.chamou is True, "com 10x o mesmo stop cabe antes da liquidação"
