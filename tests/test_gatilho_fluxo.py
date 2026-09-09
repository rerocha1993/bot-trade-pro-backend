"""
Gatilho de fluxo: a fita escolhe a HORA, o contexto escolhe o LADO.

O caso que mais importa aqui é o par absorção x continuação. As duas leituras olham a mesma coisa —
agressão forte com preço parado — e chegam a conclusões opostas, porque o que muda é de que lado está quem
agride. Confundir as duas é entrar exatamente contra quem está segurando o preço.
"""
import pytest

from core.barras_fluxo import Barra
from core.contexto_fluxo import Contexto, Nivel
from core.gatilho_fluxo import GatilhoFluxo, ParametrosFluxo


def barra(o, h, l, c, volume=10.0, delta=0.0, por_preco=None, ts=0):
    return Barra(inicio_ms=ts, fim_ms=ts + 1000, abertura=o, maxima=h, minima=l, fechamento=c,
                 volume=volume, delta=delta, negocios=20,
                 por_preco=por_preco or {round(c, 1): volume})


def enchimento(n=20, preco=100.0):
    """Histórico só para passar do mínimo de barras: range de 0,1 para o cálculo de deslocamento."""
    return [barra(preco, preco + 0.05, preco - 0.05, preco, volume=10.0, delta=0.0, ts=i * 1000)
            for i in range(n)]


def contexto(direcao="ambos", niveis=None):
    return Contexto(direcao=direcao, motivo="teste",
                    niveis=niveis if niveis is not None else [Nivel(100.0, "VP.POC", "suporte", 1.5)])


def test_absorcao_no_suporte_vira_compra():
    """Vendedor agredindo em cima do suporte e o suporte não cede: quando a agressão seca, sobra o comprador."""
    janela = [barra(100.10, 100.15, 99.96, 100.02, volume=10, delta=-4,
                    por_preco={100.0: 6.0, 100.2: 4.0}, ts=(20 + i) * 1000) for i in range(4)]
    # a última barra fecha longe do fundo e com metade do esforço: a agressão está secando
    janela.append(barra(100.00, 100.10, 99.97, 100.06, volume=10, delta=-2,
                        por_preco={100.0: 6.0, 100.2: 4.0}, ts=24000))
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(), preco=100.05)
    assert r["acao"] == "buy"
    assert r["gatilho"] == "absorcao"
    assert "segurou" in r["motivo"]


def test_absorcao_na_resistencia_vira_venda():
    niveis = [Nivel(100.0, "VP.POC", "resistencia", 1.5)]
    janela = [barra(99.90, 100.04, 99.85, 99.98, volume=10, delta=4,
                    por_preco={100.0: 6.0, 99.8: 4.0}, ts=(20 + i) * 1000) for i in range(4)]
    janela.append(barra(100.00, 100.03, 99.90, 99.94, volume=10, delta=2,
                        por_preco={100.0: 6.0, 99.8: 4.0}, ts=24000))
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(niveis=niveis), preco=99.95)
    assert r["acao"] == "sell" and r["gatilho"] == "absorcao"


def test_absorcao_nao_vale_se_o_nivel_cedeu():
    """Se o suporte foi perdido, não houve absorção nenhuma: houve rompimento."""
    janela = [barra(100.10, 100.15, 99.50, 99.60, volume=10, delta=-4,
                    por_preco={100.0: 6.0, 99.6: 4.0}, ts=(20 + i) * 1000) for i in range(5)]
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(), preco=100.05)
    assert r["acao"] == "hold"


def test_absorcao_exige_volume_concentrado_no_nivel():
    """Agressão espalhada pelo range não é briga por um preço: é só mercado andando."""
    janela = [barra(100.10, 100.15, 99.96, 100.06, volume=10, delta=-4,
                    por_preco={100.9: 5.0, 101.2: 5.0}, ts=(20 + i) * 1000) for i in range(5)]
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(), preco=100.05)
    assert r["acao"] == "hold"


def test_continuacao_no_suporte_com_fluxo_a_favor():
    janela = [barra(100.02, 100.12, 99.98, 100.08, volume=10, delta=4, ts=(20 + i) * 1000) for i in range(4)]
    janela.append(barra(100.08, 100.20, 100.05, 100.16, volume=10, delta=4, ts=24000))
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(), preco=100.05)
    assert r["acao"] == "buy" and r["gatilho"] == "continuacao"


def test_continuacao_recusada_quando_ha_esforco_sem_resultado():
    """
    Muita agressão compradora e preço parado quer dizer que tem alguém grande vendendo passivo em cima.
    Comprar aqui é comprar justamente o que essa pessoa quer despejar.
    """
    janela = [barra(100.05, 100.12, 99.98, 100.05, volume=10, delta=5, ts=(20 + i) * 1000) for i in range(4)]
    janela.append(barra(100.04, 100.10, 100.00, 100.05, volume=10, delta=5, ts=24000))
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(), preco=100.05)
    assert r["acao"] == "hold"
    assert r["metricas"]["razao_delta"] > 0.25          # a agressão estava lá
    assert abs(r["metricas"]["deslocamento"]) < 0.5     # o preço é que não foi


def test_sem_nivel_por_perto_nao_entra():
    """Entrar longe de qualquer nível é perseguir, e o stop ficaria pendurado no vazio."""
    janela = [barra(105.0, 105.1, 104.9, 105.05, volume=10, delta=5, ts=(20 + i) * 1000) for i in range(5)]
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(), preco=105.0)
    assert r["acao"] == "hold" and "perseguir" in r["motivo"]


def test_espera_o_preco_chegar_no_nivel():
    janela = [barra(100.3, 100.4, 100.25, 100.35, volume=10, delta=5, ts=(20 + i) * 1000) for i in range(5)]
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(), preco=100.3)
    assert r["acao"] == "hold" and "esperando o preço chegar" in r["motivo"]


def test_o_fluxo_nao_escolhe_o_lado_contra_o_contexto():
    """Elliott continua sendo a lei: um sinal de fluxo contra o lado permitido é descartado, não invertido."""
    janela = [barra(100.10, 100.15, 99.96, 100.02, volume=10, delta=-4,
                    por_preco={100.0: 6.0, 100.2: 4.0}, ts=(20 + i) * 1000) for i in range(4)]
    # a última barra fecha longe do fundo e com metade do esforço: a agressão está secando
    janela.append(barra(100.00, 100.10, 99.97, 100.06, volume=10, delta=-2,
                        por_preco={100.0: 6.0, 100.2: 4.0}, ts=24000))
    r = GatilhoFluxo().avaliar(enchimento() + janela, contexto(direcao="sell"), preco=100.05)
    assert r["acao"] == "hold" and "descartado" in r["motivo"]


def test_contexto_sem_lado_nenhum_segura_o_robo():
    r = GatilhoFluxo().avaliar(enchimento(30), contexto(direcao="hold"), preco=100.0)
    assert r["acao"] == "hold" and "não libera nenhum lado" in r["motivo"]


def test_sem_historico_suficiente_nao_decide():
    r = GatilhoFluxo().avaliar(enchimento(5), contexto(), preco=100.0)
    assert r["acao"] == "hold" and "sem histórico" in r["motivo"]


def test_livro_fortemente_contra_barra_a_continuacao():
    janela = [barra(100.02, 100.12, 99.98, 100.08, volume=10, delta=4, ts=(20 + i) * 1000) for i in range(4)]
    janela.append(barra(100.08, 100.20, 100.05, 100.16, volume=10, delta=4, ts=24000))
    barras = enchimento() + janela
    g = GatilhoFluxo()
    assert g.avaliar(barras, contexto(), preco=100.05, imbalance=0.3)["acao"] == "buy"
    assert g.avaliar(barras, contexto(), preco=100.05, imbalance=-0.5)["acao"] == "hold"


def test_parametros_incoerentes_sao_recusados_na_criacao():
    with pytest.raises(ValueError):
        ParametrosFluxo(barras_janela=1)
    with pytest.raises(ValueError):
        ParametrosFluxo(barras_janela=10, barras_minimas=5)
    with pytest.raises(ValueError):
        ParametrosFluxo(limiar_delta=1.5)
    with pytest.raises(ValueError):
        ParametrosFluxo(folga_nivel=0.01, tolerancia_nivel=0.001)


def absorcao(delta_ultima=-2.0, ultima=(100.00, 100.10, 99.97, 100.06), por_preco=None):
    """Janela de absorção num suporte em 100,00, com a última barra parametrizável."""
    pp = por_preco or {100.0: 6.0, 100.2: 4.0}
    j = [barra(100.10, 100.15, 99.96, 100.02, volume=10, delta=-4, por_preco=pp, ts=(20 + i) * 1000)
         for i in range(4)]
    o, h, l, c = ultima
    j.append(barra(o, h, l, c, volume=10, delta=delta_ultima, por_preco=pp, ts=24000))
    return enchimento() + j


def test_absorcao_exige_que_a_agressao_esteja_secando():
    """
    Regressão do backtest: sem esta condição o motor comprou sete suportes seguidos num dia de queda e
    perdeu em todos. Num mercado que desce, o preço PARA em todo nível por um minuto antes de passar por
    cima — "agressão presente e nível intacto" descreve tanto uma absorção quanto uma faca caindo.
    """
    assert GatilhoFluxo().avaliar(absorcao(delta_ultima=-2.0), contexto(), preco=100.05)["acao"] == "buy"
    # mesma janela, mas a agressão vendedora está ACELERANDO: não é absorção, é rompimento a caminho
    assert GatilhoFluxo().avaliar(absorcao(delta_ultima=-6.0), contexto(), preco=100.05)["acao"] == "hold"


def test_absorcao_exige_que_a_ultima_barra_feche_longe_do_fundo():
    """Fechar colado na mínima é o preço sendo empurrado, não rejeitado."""
    assert GatilhoFluxo().avaliar(
        absorcao(ultima=(100.00, 100.10, 99.97, 99.98)), contexto(), preco=100.05)["acao"] == "hold"


def test_banda_da_absorcao_e_estreita():
    """
    Absorção é briga por UM preço. Com a banda larga (a tolerância de 0,15%) a concentração dava 100% em
    toda entrada e o filtro não filtrava nada: o backtest mostrou isso em oito trades seguidos.
    """
    longe = {100.10: 6.0, 100.2: 4.0}      # 0,1% acima do nível: dentro da tolerância, fora da banda
    assert GatilhoFluxo().avaliar(absorcao(por_preco=longe), contexto(), preco=100.05)["acao"] == "hold"
