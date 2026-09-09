"""Saída escalonada: realizar em pedaços conforme o preço avança rumo ao alvo."""
import pytest

from core.saida_escalonada import (
    PLANO_PADRAO, avanco, escrever_feitas, escrever_plano, ler_feitas, ler_plano, montar_fatias, pendentes,
)


# ------------------------------------------------------------------ a régua é o avanço, não o preço
def test_avanco_mede_o_caminho_ate_o_alvo():
    assert avanco(100.0, 110.0, 105.0, "buy") == pytest.approx(0.5)
    assert avanco(100.0, 110.0, 100.0, "buy") == pytest.approx(0.0)
    assert avanco(100.0, 110.0, 110.0, "buy") == pytest.approx(1.0)
    assert avanco(100.0, 110.0, 112.0, "buy") == pytest.approx(1.2), "pode passar de 1 se estourou o alvo"


def test_avanco_na_venda_conta_para_baixo():
    assert avanco(100.0, 90.0, 95.0, "sell") == pytest.approx(0.5)
    assert avanco(100.0, 90.0, 105.0, "sell") == pytest.approx(-0.5), "contra a posição é negativo"


def test_avanco_recusa_alvo_incoerente():
    assert avanco(100.0, 90.0, 95.0, "buy") is None, "compra com alvo abaixo da entrada não faz sentido"
    assert avanco(100.0, 110.0, 105.0, "sell") is None
    assert avanco(100.0, None, 105.0, "buy") is None
    assert avanco(0, 110.0, 105.0, "buy") is None


# ------------------------------------------------------------------ o plano se adapta ao tamanho da mão
def test_mao_grande_usa_o_plano_inteiro():
    fatias = montar_fatias(1.0, PLANO_PADRAO, min_qty=0.001, step=0.001)
    assert len(fatias) == 3
    assert [f["quantidade"] for f in fatias] == [0.3, 0.3, 0.25]
    assert sum(f["quantidade"] for f in fatias) < 1.0, "tem que sobrar posição para o alvo"


def test_mao_media_encolhe_o_plano():
    """Com pouca quantidade, as fatias menores nao alcancam o minimo: o plano encolhe em vez de gerar ordem invalida."""
    fatias = montar_fatias(0.01, PLANO_PADRAO, min_qty=0.004, step=0.001)
    assert len(fatias) < 3
    for f in fatias:
        assert f["quantidade"] >= 0.004
    resto = 0.01 - sum(f["quantidade"] for f in fatias)
    assert resto >= 0.004, "o que sobra para o alvo também respeita o mínimo"


def test_mao_pequena_nao_escalona():
    assert montar_fatias(0.002, PLANO_PADRAO, min_qty=0.001, step=0.001) == []
    assert montar_fatias(0.0, PLANO_PADRAO, min_qty=0.001, step=0.001) == []


def test_quantidades_respeitam_o_passo_da_corretora():
    fatias = montar_fatias(1.0, ((0.5, 0.333),), min_qty=0.0, step=0.01)
    assert fatias[0]["quantidade"] == pytest.approx(0.33), "0.333 arredonda para baixo no passo de 0.01"


def test_sobra_sempre_positiva():
    for q in (0.05, 0.5, 3.0, 17.77):
        fatias = montar_fatias(q, PLANO_PADRAO, min_qty=0.001, step=0.001)
        assert sum(f["quantidade"] for f in fatias) < q


# ------------------------------------------------------------------ o que dispara agora
def test_dispara_so_o_que_o_avanco_alcancou():
    fatias = montar_fatias(1.0, PLANO_PADRAO, min_qty=0.001, step=0.001)
    assert pendentes(fatias, [], 0.30) == []
    assert [f["avanco"] for f in pendentes(fatias, [], 0.60)] == [0.5]
    assert [f["avanco"] for f in pendentes(fatias, [], 0.80)] == [0.5, 0.75]
    assert len(pendentes(fatias, [], 1.20)) == 3, "estourou o alvo: todas as fatias valem"


def test_nao_repete_fatia_ja_realizada():
    fatias = montar_fatias(1.0, PLANO_PADRAO, min_qty=0.001, step=0.001)
    assert [f["avanco"] for f in pendentes(fatias, [0.5], 0.80)] == [0.75]
    assert pendentes(fatias, [0.5, 0.75, 0.9], 1.0) == []


def test_sem_avanco_nao_dispara_nada():
    fatias = montar_fatias(1.0, PLANO_PADRAO, min_qty=0.001, step=0.001)
    assert pendentes(fatias, [], None) == []
    assert pendentes(fatias, [], -0.4) == [], "preço contra a posição não realiza"


# ------------------------------------------------------------------ configuração em texto
def test_le_e_escreve_o_plano():
    assert ler_plano("50/30, 75/30, 90/25") == ((0.5, 0.3), (0.75, 0.3), (0.9, 0.25))
    assert escrever_plano(PLANO_PADRAO) == "50/30, 75/30, 90/25"
    assert ler_plano("60/50; 80/25") == ((0.6, 0.5), (0.8, 0.25))


def test_plano_invalido_cai_no_padrao():
    for ruim in (None, "", "abc", "50", "50/", "150/30", "50/0", "50/60, 75/50"):
        assert ler_plano(ruim) == PLANO_PADRAO, f"{ruim!r} deveria cair no padrão"


def test_plano_que_zera_a_posicao_e_recusado():
    """Se as fatias somam 100% não sobra nada para o alvo: é erro de configuração, não um plano."""
    assert ler_plano("50/50, 75/50") == PLANO_PADRAO


def test_plano_sai_ordenado_por_avanco():
    assert ler_plano("90/25, 50/30, 75/30") == ((0.5, 0.3), (0.75, 0.3), (0.9, 0.25))


def test_registro_das_fatias_feitas():
    assert ler_feitas("0.5,0.75") == [0.5, 0.75]
    assert ler_feitas("") == []
    assert ler_feitas("0.5,lixo,0.9") == [0.5, 0.9]
    assert escrever_feitas([0.5, 0.75]) == "0.5,0.75"


# ------------------------------------------------------------------ ligada no executor, não só na fórmula
def _executor(quantidade=1.0, entrada=100.0, tp=110.0, **kw):
    from core.backtest_engine import bot_padrao
    from core.bot_executor import BotExecutor
    from models.posicao_bot import PosicaoBot

    class DB:
        def add(self, *a): pass
        def commit(self): pass
        def rollback(self): pass

    class Ordens:
        simulado = True
        def __init__(self): self.reducoes, self.stops = [], []
        def reduzir(self, par, direcao, qty, position_mode="one-way", preco_ref=None):
            self.reducoes.append(qty)
            return {"ordem_id": "x", "preco_exec": preco_ref, "quantidade": qty, "simulado": True, "taxa": 0.0}
        def atualizar_stop(self, par, sl=None, tp=None, position_mode="one-way", direcao=None):
            self.stops.append(sl)
            return True

    class Con:
        def info_mercado(self, par): return {"min_qty": 0.001, "qty_step": 0.001}
        def arredondar_preco(self, par, p): return round(p, 2)
        def arredondar_quantidade(self, par, q): return round(q, 3)

    bot = bot_padrao(usar_saida_escalonada=True, saida_escalonada="50/30, 75/30, 90/25",
                     mover_stop_para_entrada=True, **kw)
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot, ex.db, ex.modo, ex.par = bot, DB(), "simulador", "BTCUSDT"
    ex.con, ex.ordens = Con(), Ordens()
    ex.estado = {"dia": "x", "pnl_dia": 0.0, "trades_dia": 0}
    ex.logs = []
    ex._log = lambda **kw2: ex.logs.append(kw2)
    ex.posicao = PosicaoBot(bot_id=1, par="BTCUSDT", modo_execucao="simulador", direcao="buy",
                            quantidade=quantidade, quantidade_inicial=quantidade, preco_entrada=entrada,
                            sl=entrada * 0.98, tp=tp, status="aberta", pnl_parcial=0.0)
    return ex


def test_executor_realiza_a_fatia_no_avanco_certo():
    ex = _executor()
    ex.aplicar_saida_escalonada(104.0)          # 40% do caminho: nada ainda
    assert ex.ordens.reducoes == []
    ex.aplicar_saida_escalonada(105.0)          # 50%: primeira fatia
    assert ex.ordens.reducoes == [0.3]
    assert ex.posicao.quantidade == pytest.approx(0.7)
    assert ex.posicao.pnl_parcial == pytest.approx(0.3 * 5.0)


def test_executor_nao_repete_a_mesma_fatia():
    ex = _executor()
    ex.aplicar_saida_escalonada(105.0)
    ex.aplicar_saida_escalonada(105.5)
    ex.aplicar_saida_escalonada(106.0)
    assert ex.ordens.reducoes == [0.3], "o mesmo avanço não pode realizar duas vezes"


def test_primeira_realizacao_trava_o_zero_a_zero():
    ex = _executor()
    ex.aplicar_saida_escalonada(105.0)
    assert ex.ordens.stops == [100.0], "o stop tem que ir para o preço de entrada"
    assert ex.posicao.sl == 100.0


def test_avanco_grande_realiza_todas_as_fatias_de_uma_vez():
    ex = _executor()
    ex.aplicar_saida_escalonada(109.5)          # 95% do caminho
    assert ex.ordens.reducoes == [0.3, 0.3, 0.25]
    assert ex.posicao.quantidade == pytest.approx(0.15), "sobra a última fatia para o alvo"


def test_desligado_nao_realiza_nada():
    ex = _executor()
    ex.bot.usar_saida_escalonada = False
    ex.aplicar_saida_escalonada(109.0)
    assert ex.ordens.reducoes == []


def test_sem_alvo_nao_realiza():
    ex = _executor(tp=None)
    ex.aplicar_saida_escalonada(109.0)
    assert ex.ordens.reducoes == []


def test_mao_pequena_nao_gera_ordem_invalida():
    ex = _executor(quantidade=0.002)
    ex.aplicar_saida_escalonada(109.5)
    assert ex.ordens.reducoes == [], "posição pequena demais: sai tudo no alvo"


# ------------------------------------------------------------------ o painel recusa o plano torto
def test_analisar_separa_invalido_de_padrao():
    """`ler_plano` cai no padrão para o robô não parar; `analisar_plano` diz que o texto é inválido."""
    from core.saida_escalonada import analisar_plano

    assert analisar_plano("50/30, 75/30, 90/25") == PLANO_PADRAO
    assert analisar_plano("abc") is None
    assert analisar_plano("") is None
    assert analisar_plano("50/50, 75/50") is None, "somar 100% não deixa nada para o alvo"
    assert analisar_plano("50/30, 50/20") is None, "o mesmo avanço duas vezes só realizaria uma"
    assert ler_plano("abc") == PLANO_PADRAO


def _normalizar(**campos):
    from services.bot_service import BotService
    return BotService._normalizar(campos)


def test_servico_recusa_plano_ilegivel():
    with pytest.raises(ValueError, match="escalonada inválido"):
        _normalizar(saida_escalonada="abc")
    with pytest.raises(ValueError, match="escalonada inválido"):
        _normalizar(saida_escalonada="50/60, 75/50")


def test_servico_normaliza_o_plano_aceito():
    assert _normalizar(saida_escalonada="90/25, 50/30, 75/30")["saida_escalonada"] == "50/30, 75/30, 90/25"


def test_plano_em_branco_vira_o_do_estilo():
    from core.perfil_saida import PERFIS

    assert _normalizar(saida_escalonada="", estilo_trade="swing")["saida_escalonada"] == PERFIS["swing"].saida_escalonada


def test_servico_recusa_trailing_que_trava_prejuizo():
    with pytest.raises(ValueError, match="Trailing inválido"):
        _normalizar(ativador_trailing=0.003, distancia_trailing=0.005)
    ok = _normalizar(ativador_trailing=0.03, distancia_trailing=0.02)
    assert ok["ativador_trailing"] == 0.03


def test_fatia_realizada_e_gravada_antes_do_log():
    """A ordem já saiu na corretora: se o registro não for gravado na hora, o ciclo seguinte repete a ordem."""
    ex = _executor()
    momentos = []
    ex.db.commit = lambda: momentos.append(('commit', ex.posicao.saidas_feitas))
    ex._log = lambda **kw: momentos.append(('log', ex.posicao.saidas_feitas))
    ex.aplicar_saida_escalonada(105.0)
    assert momentos, "nada foi gravado"
    assert momentos[0] == ('commit', '0.5'), f"a fatia tem que ser gravada antes do log, veio {momentos}"
