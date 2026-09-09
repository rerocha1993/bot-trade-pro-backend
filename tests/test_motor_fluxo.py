"""
Motor de fluxo do scalp: contexto dos graus maiores + gatilho na fita.

O ponto que estes testes protegem é o motivo de o motor existir: em 1m a contagem de Elliott trocava de
fase em 45% das leituras e era ela que segurava o robô parado. Aqui Elliott decide o LADO (15m/1h) e os
NÍVEIS; a hora vem do fluxo. O que não pode acontecer é o fluxo passar por cima do lado permitido.
"""
import time
from types import SimpleNamespace

from core.barras_fluxo import Barra
from core.contexto_fluxo import Contexto, LeitorContexto, Nivel
from core.motor_fluxo import MotorFluxo


def bot(**kw):
    base = dict(id=1, nome="Scalp Fluxo", ativo="BTCUSDT", timeframe="1m", estilo_trade="scalping",
                confluencia_tipo="conservador", barra_tipo="volume", barra_tamanho=1.0,
                barra_segundos_alvo=30.0, rr_minimo=0)
    base.update(kw)
    return SimpleNamespace(**base)


def barra(o, h, l, c, volume=10.0, delta=0.0, por_preco=None, ts=0):
    return Barra(inicio_ms=ts, fim_ms=ts + 1000, abertura=o, maxima=h, minima=l, fechamento=c,
                 volume=volume, delta=delta, negocios=20, por_preco=por_preco or {round(c, 1): volume})


def enchimento(n=20, preco=100.0):
    return [barra(preco, preco + 0.05, preco - 0.05, preco, ts=i * 1000) for i in range(n)]


def absorcao_no_suporte():
    janela = [barra(100.10, 100.15, 99.96, 100.02, volume=10, delta=-4,
                    por_preco={100.0: 6.0, 100.2: 4.0}, ts=(20 + i) * 1000) for i in range(4)]
    # a última barra fecha longe do fundo e com metade do esforço: a agressão está secando
    janela.append(barra(100.00, 100.10, 99.97, 100.06, volume=10, delta=-2,
                        por_preco={100.0: 6.0, 100.2: 4.0}, ts=24000))
    return enchimento() + janela


def motor_com_contexto(ctx, barras=None, **kw):
    m = MotorFluxo(bot(**kw), lambda tf, n: [])
    m.contexto = ctx
    m._proximo_contexto = time.time() + 3600     # congela: o teste não vai à rede buscar 15m/1h
    for b in (barras or []):
        m.agregador.fechadas.append(b)
    return m


def contexto(direcao="buy", niveis=None, fator=1.0):
    return Contexto(direcao=direcao, motivo="teste", fator_tamanho=fator,
                    niveis=niveis if niveis is not None else
                    [Nivel(100.0, "VP.POC", "suporte", 1.5), Nivel(100.60, "VP.VAH", "resistencia", 1.0)])


# ------------------------------------------------------------------ SL e TP
def test_stop_fica_alem_do_nivel_que_o_preco_defendeu():
    """O stop mora abaixo do que o nível segurou, não abaixo da entrada: se o nível cedeu, a leitura morreu."""
    m = motor_com_contexto(contexto(), absorcao_no_suporte())
    niveis = m._sl_tp("buy", 100.05, Nivel(100.0, "VP.POC", "suporte"), list(m.agregador.fechadas), contexto())
    assert niveis["sl"] < 99.96          # abaixo da mínima da janela
    assert niveis["tp"] < 100.60         # para um pouco antes da resistência, para ser servido
    assert niveis["rr"] > 1.0


def test_alvo_vira_2r_quando_nao_ha_nivel_adiante():
    m = motor_com_contexto(contexto(niveis=[Nivel(100.0, "VP.POC", "suporte", 1.5)]), absorcao_no_suporte())
    ctx = contexto(niveis=[Nivel(100.0, "VP.POC", "suporte", 1.5)])
    niveis = m._sl_tp("buy", 100.05, ctx.niveis[0], list(m.agregador.fechadas), ctx)
    assert "2R" in niveis["fonte_tp"]
    assert niveis["rr"] == 2.0


# ------------------------------------------------------------------ decisão
def test_absorcao_com_espaco_ate_o_alvo_vira_entrada():
    m = motor_com_contexto(contexto(), absorcao_no_suporte())
    d = m.avaliar(preco=100.05)
    assert d["acao"] == "buy"
    assert d["sl"] < 100.0 < d["tp"]
    assert d["motor"] == "fluxo"
    assert d["votos"] == ["fluxo:absorcao"]


def test_sinal_bom_com_alvo_perto_demais_e_recusado():
    """Gatilho certo e alvo a três passos não paga o risco: o scalp perde no custo, não na leitura."""
    ctx = contexto(niveis=[Nivel(100.0, "VP.POC", "suporte", 1.5),
                           Nivel(100.10, "VP.VAH", "resistencia", 1.0)])
    m = motor_com_contexto(ctx, absorcao_no_suporte())
    d = m.avaliar(preco=100.05)
    assert d["acao"] == "hold" and "risco:retorno" in d["motivo"]


def test_contexto_vendedor_descarta_a_compra_do_fluxo():
    m = motor_com_contexto(contexto(direcao="sell"), absorcao_no_suporte())
    assert m.avaliar(preco=100.05)["acao"] == "hold"


def test_fator_de_tamanho_vem_do_contexto():
    m = motor_com_contexto(contexto(fator=0.5), absorcao_no_suporte())
    assert m.avaliar(preco=100.05)["tamanho_fator"] == 0.5


def test_sem_regua_calibrada_o_motor_nao_opera():
    m = motor_com_contexto(contexto(), absorcao_no_suporte(), barra_tamanho=0)
    d = m.avaliar(preco=100.05)
    assert d["acao"] == "hold" and "calibrando" in d["motivo"]


def test_ingerir_monta_barras_a_partir_dos_negocios():
    m = motor_com_contexto(contexto())
    novas = m.ingerir([{"price": 100.0, "qty": 0.5, "side": "buy", "timestamp": i * 100} for i in range(10)])
    assert len(novas) == 5
    assert m.ultima_barra is novas[-1]


def test_contexto_so_e_recalculado_quando_vence():
    """Buscar 15m/1h a cada barra seria pagar rede e banco por um número que muda devagar."""
    m = motor_com_contexto(contexto())
    assert m.contexto_vencido is False
    m._proximo_contexto = time.time() - 1
    assert m.contexto_vencido is True


def test_status_mostra_a_regua_e_o_ultimo_motivo():
    m = motor_com_contexto(contexto(), absorcao_no_suporte())
    m.avaliar(preco=100.05)
    s = m.status()
    assert s["motor"] == "fluxo" and s["barras"]["calibrado"] is True and s["ultimo_motivo"]


# ------------------------------------------------------------------ contexto
def leitor():
    return LeitorContexto(lambda tf, n: [], "BTCUSDT")


def grau(bull=0.0, bear=0.0, fase="onda_3", tf="15m"):
    return {"prob_bull": bull, "prob_bear": bear, "fase": fase, "timeframe": tf, "primario": None}


def test_contexto_e_macro_de_acordo_definem_o_lado():
    d, fator, *_ = leitor()._direcao(grau(bull=0.8), grau(bull=0.7, tf="1h"), None, None, None)
    assert d == "buy" and fator == 1.0


def test_contexto_e_macro_em_desacordo_seguram_o_conservador():
    d, *_ = leitor()._direcao(grau(bull=0.8), grau(bear=0.8, tf="1h"), None, None, None)
    assert d == "hold"


def test_sem_lado_em_nenhum_grau_o_scalp_opera_as_duas_pontas():
    """Ausência de tendência não é motivo para parar um scalp: é range, que é onde ele trabalha melhor."""
    d, fator, *_ = leitor()._direcao(grau(), grau(tf="1h"), None, None, None)
    assert d == "ambos" and fator < 1.0


def test_o_plano_do_par_tem_a_ultima_palavra():
    plano = {"modo": "defensivo", "pode_comprar": False, "pode_vender": True, "risco_permitido": 0.5}
    d, fator, *_ = leitor()._direcao(grau(bull=0.9), grau(bull=0.9, tf="1h"), plano, None, None)
    assert d == "hold"
    plano2 = {"modo": "defensivo", "pode_comprar": False, "pode_vender": True, "risco_permitido": 0.5}
    d2, fator2, *_ = leitor()._direcao(grau(), grau(tf="1h"), plano2, None, None)
    assert d2 == "sell" and fator2 <= 0.5


def test_contagem_mestre_travada_manda_na_leitura_automatica():
    trava = {"vies": "bear", "status": "ativa", "grau": "diario"}
    d, *_ = leitor()._direcao(grau(bull=0.9), grau(bull=0.9, tf="1h"), None, trava, None)
    assert d == "hold"


def test_trader_nao_deixa_vender_fundo_de_ciclo():
    trader = {"superciclo": {"estado": "fundo_terminal"}}
    d, *_ = leitor()._direcao(grau(bear=0.9), grau(bear=0.9, tf="1h"), None, None, trader)
    assert d == "hold"


def test_niveis_sao_classificados_pelo_lado_em_que_estao_agora():
    serie = [[i * 60000, 100.0, 100.5, 99.5, 100.0, 10.0] for i in range(120)]
    niveis = leitor()._niveis(serie, preco=100.0, cenario={"invalidacao": 98.0, "alvos": [104.0]})
    fontes = {n.fonte: n for n in niveis}
    assert any("Elliott.invalidacao" in f for f in fontes)
    for n in niveis:
        assert n.tipo == ("suporte" if n.preco < 100.0 else "resistencia")


def test_niveis_colados_viram_um_so_com_forca_somada():
    """Dois indicadores apontando o mesmo preço é confirmação, não dois níveis para o gatilho tropeçar."""
    serie = [[i * 60000, 100.0, 100.01, 99.99, 100.0, 10.0] for i in range(120)]
    niveis = leitor()._niveis(serie, preco=100.0, cenario=None)
    precos = [n.preco for n in niveis]
    assert len(precos) == len(set(precos))
    assert any("+" in n.fonte for n in niveis)


def test_contexto_acha_o_alvo_na_direcao():
    ctx = contexto()
    assert ctx.alvo_na_direcao(100.05, "buy").preco == 100.60
    assert ctx.alvo_na_direcao(100.05, "sell").preco == 100.0
    assert ctx.permite("buy") and not ctx.permite("sell")
    assert contexto(direcao="ambos").permite("sell")
