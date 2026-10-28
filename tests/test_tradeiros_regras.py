"""Portal Tradeiros — regras R1–R38 e perfis Shaka × Maroja."""
import pytest

from conselho.tradeiros.leitura import Leitura, posicao_no_range, zona_do_range
from conselho.tradeiros.regras import MAROJA, SHAKA, contexto_fluxo, hedge_alvo, medio_das_fatias, pesos_crescentes, planejar

RANGE = {"val": 76000.0, "poc": 78000.0, "vah": 80000.0, "minima": 75000.0, "maxima": 81000.0, "dias": 10,
         "valido": True, "dias_de_lateral": 8}


def _lt(preco, estado="intermediario", do_topo=-0.20, estrutura=None, sentimento=50, derivativos=None, range_=RANGE,
        semanal=None):
    p = posicao_no_range(preco, range_["val"], range_["vah"]) if range_ else None
    return Leitura(ts=0, preco=preco, range=range_, p=p, zona=zona_do_range(p), ciclo={"estado": estado, "do_topo": do_topo},
                   estrutura=estrutura or {"tendencia": "lateral", "quebra": None}, sentimento=sentimento,
                   derivativos=derivativos or {}, estrutura_semanal=semanal or {})


MAPA_NEUTRO = {"prob_bull": 0.4, "prob_bear": 0.4, "inclinacao": 0.0, "veto_onda_4": False}
BAIXA = {"tendencia": "baixa", "quebra": "baixa"}


def _tipos(plano):
    return [d.tipo for d in plano.decisoes]


def _uma(plano, tipo):
    return next(d for d in plano.decisoes if d.tipo == tipo)


def test_pesos_crescentes_somam_um_e_a_ultima_fatia_e_a_maior():
    w = pesos_crescentes(5)
    assert sum(w) == pytest.approx(1) and w[-1] > w[0]
    # compra: a fatia maior é a mais baixa, então o médio fica abaixo do meio da zona
    assert medio_das_fatias((100, 110), w, "compra") < 105 < medio_das_fatias((100, 110), w, "venda_direcional")


@pytest.mark.parametrize("perfil", [SHAKA, MAROJA])
def test_r1_no_meio_nada_a_mercado_mas_ordens_esperando_nas_duas_bordas(perfil):
    plano = planejar(_lt(78000), MAPA_NEUTRO, perfil)
    assert plano.decisoes[0].tipo == "ficar_fora" and plano.decisoes[0].regras == ["R1"]
    compra = _uma(plano, "compra")
    assert compra.zona[1] < RANGE["val"] + 0.25 * 4000, "a compra fica na VAL, não no preço"
    assert _uma(plano, "hedge_aumentar").zona[0] >= RANGE["vah"] - 400
    assert _uma(plano, "hedge_realizar").zona[1] <= RANGE["val"] + 400


@pytest.mark.parametrize("perfil", [SHAKA, MAROJA])
def test_fundo_do_range_compra_em_fatias_com_stop_abaixo_do_fundo_e_alvo_na_vah(perfil):
    plano = planejar(_lt(76300), MAPA_NEUTRO, perfil)
    compra = _uma(plano, "compra")
    assert compra.stop < RANGE["minima"] and compra.alvo == RANGE["vah"]
    assert len(compra.pesos_fatias) == perfil.fatias and "R2" in compra.regras
    assert compra.rr >= 3
    assert "venda_direcional" not in _tipos(plano), "R4: no VAL não se vende"


def test_shaka_arrisca_mais_e_o_maroja_usa_stop_mais_largo():
    s = _uma(planejar(_lt(76300), MAPA_NEUTRO, SHAKA), "compra")
    m = _uma(planejar(_lt(76300), MAPA_NEUTRO, MAROJA), "compra")
    assert s.risco > m.risco and m.stop < s.stop


def test_topo_sobe_o_hedge_em_escada_e_so_o_shaka_vende_direcional():
    s = planejar(_lt(79800), MAPA_NEUTRO, SHAKA, hedge_atual=0.20)
    m = planejar(_lt(79800), MAPA_NEUTRO, MAROJA, hedge_atual=0.20)
    esc = _uma(m, "hedge_aumentar")
    assert esc.stop > RANGE["maxima"] and esc.fracao_hedge == pytest.approx(m.hedge_alvo - 0.20)
    assert "hedge_aumentar" in _tipos(s)
    assert any(d.tipo == "venda_direcional" or "R19" in d.regras for d in s.decisoes)
    assert "venda_direcional" not in _tipos(m)
    assert _uma(m, "compra").zona[1] < RANGE["val"] + 1000, "no topo, a compra espera na VAL"


def test_hedge_respeita_as_faixas_de_cada_perfil():
    euforia = _lt(80500, estado="esticado", do_topo=-0.02, sentimento=90)
    mapa_bear = {"prob_bull": 0.1, "prob_bear": 0.8, "inclinacao": -0.7}
    assert hedge_alvo(euforia, mapa_bear, contexto_fluxo(euforia), SHAKA)[0] == SHAKA.hedge_max
    assert hedge_alvo(euforia, mapa_bear, contexto_fluxo(euforia), MAROJA)[0] == MAROJA.hedge_max


def test_no_mesmo_dia_o_maroja_protege_mais_que_o_shaka():
    lt = _lt(79800)
    assert hedge_alvo(lt, MAPA_NEUTRO, contexto_fluxo(lt), MAROJA)[0] > hedge_alvo(lt, MAPA_NEUTRO, contexto_fluxo(lt), SHAKA)[0]


def test_medo_extremo_descontado_derruba_o_hedge_e_bear_declarado_sobe_para_90():
    medo = _lt(76300, estado="descontado", do_topo=-0.30, sentimento=12, derivativos={"oi_vs_max_30d": -0.4})
    h, regras = hedge_alvo(medo, MAPA_NEUTRO, contexto_fluxo(medo), MAROJA)
    assert h == pytest.approx(0.25, abs=0.011) and "P11" in regras
    assert "R30" not in regras, "com o cenário baixista neutro não re-hedgeia"
    assert hedge_alvo(medo, {"prob_bear": 0.6, "inclinacao": 0.0}, contexto_fluxo(medo), MAROJA)[0] == 0.40
    bear = _lt(70000, estado="descontado", do_topo=-0.40, estrutura=BAIXA, semanal=BAIXA)
    assert hedge_alvo(bear, {"inclinacao": -0.6, "prob_bear": 0.8}, contexto_fluxo(bear), MAROJA)[0] == 0.90
    assert hedge_alvo(bear, MAPA_NEUTRO, contexto_fluxo(bear), MAROJA)[0] < 0.90, "o Maroja pede o mapa de baixa"


def test_bear_de_2022_o_shaka_fica_90_por_cento_vendido_sem_depender_de_elliott():
    bear = _lt(75500, estado="descontado", do_topo=-0.75, estrutura=BAIXA, semanal=BAIXA)
    assert hedge_alvo(bear, MAPA_NEUTRO, contexto_fluxo(bear), SHAKA)[0] == 0.90
    # 2023: ainda ~57% abaixo do topo, mas a estrutura semanal já era de alta — correção, não bear
    correcao = _lt(75500, estado="descontado", do_topo=-0.57, estrutura=BAIXA, semanal={"tendencia": "alta", "quebra": None})
    assert hedge_alvo(correcao, MAPA_NEUTRO, contexto_fluxo(correcao), SHAKA)[0] < 0.5


def test_quebra_da_estrutura_semanal_para_cima_leva_o_hedge_ao_minimo():
    lt = _lt(79800, semanal={"tendencia": "lateral", "quebra": "alta"})
    assert hedge_alvo(lt, MAPA_NEUTRO, contexto_fluxo(lt), MAROJA)[0] == pytest.approx(MAROJA.hedge_min)


def test_stop_da_escada_do_hedge_tem_a_folga_de_pedagio_deles():
    esc = _uma(planejar(_lt(79800), MAPA_NEUTRO, MAROJA, hedge_atual=0.20), "hedge_aumentar")
    assert esc.stop == pytest.approx(max(esc.zona[1], RANGE["maxima"]) * 1.02)


def test_sem_hedge_informado_parte_do_hedge_do_poc_e_sobe_na_vah():
    plano = planejar(_lt(79800), MAPA_NEUTRO, SHAKA)
    assert "hedge_aumentar" in _tipos(plano)


def test_na_alta_a_compra_do_reteste_mira_alem_do_topo():
    c = _uma(planejar(_lt(79800, estrutura={"tendencia": "alta", "quebra": None}), MAPA_NEUTRO, MAROJA), "compra")
    assert c.alvo == RANGE["maxima"] + 4000 and "P8" in c.regras


def test_veto_de_onda_4_trava_o_maroja_e_nao_o_shaka():
    mapa = dict(MAPA_NEUTRO, veto_onda_4=True)
    assert "compra" not in _tipos(planejar(_lt(76300), mapa, MAROJA))
    assert "compra" in _tipos(planejar(_lt(76300), mapa, SHAKA))


def test_r16_minima_renovada_trava_o_maroja_mas_o_panico_libera_camadas_p12():
    sem_limpeza = _lt(76300, estrutura=BAIXA)
    assert "compra" not in _tipos(planejar(sem_limpeza, MAPA_NEUTRO, MAROJA))
    panico = _lt(76300, estrutura=BAIXA, sentimento=15)
    c = _uma(planejar(panico, MAPA_NEUTRO, MAROJA), "compra")
    assert "P12" in c.regras and c.risco == pytest.approx(MAROJA.risco_extremo * 0.5)


def test_abaixo_do_valor_o_maroja_espera_reacao_e_o_shaka_entra_pequeno():
    lt = _lt(75500)
    for d in planejar(lt, MAPA_NEUTRO, MAROJA).decisoes:
        if d.tipo == "compra":
            assert d.exige_reacao
    for d in planejar(lt, MAPA_NEUTRO, SHAKA).decisoes:
        if d.tipo == "compra":
            assert not d.exige_reacao and "R38" in d.regras and d.risco < SHAKA.risco_extremo


def test_r19_recusa_trade_com_menos_de_3r():
    estreito = dict(RANGE, vah=76600.0, poc=76300.0)          # alvo colado na entrada
    plano = planejar(_lt(76050, range_=estreito), MAPA_NEUTRO, MAROJA)
    assert "compra" not in _tipos(plano)
    assert any("R19" in d.regras for d in plano.decisoes if d.tipo == "ficar_fora")


def test_sem_range_fica_fora():
    plano = planejar(_lt(76000, range_=None), MAPA_NEUTRO, SHAKA)
    assert _tipos(plano) == ["ficar_fora"]
    assert plano.as_dict()["decisoes"][0]["rr"] is None
