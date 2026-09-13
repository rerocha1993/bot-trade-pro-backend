"""Portal Tradeiros — mapa de Elliott: várias contagens, invalidação comum, onda 2 e onda 4."""
import datetime as dt

import pytest

from core.tpo_sessao import DIA_MS
from tradeiros.elliott_mapa import invalidacao_comum, resumir, semanais_ate

SEGUNDA = int(dt.datetime(2026, 9, 7, tzinfo=dt.timezone.utc).timestamp() * 1000)


def test_a_data_base_e_segunda():
    assert dt.datetime.fromtimestamp(SEGUNDA / 1000, dt.timezone.utc).weekday() == 0


def test_semana_so_entra_depois_de_fechada():
    diarios = [[SEGUNDA + i * DIA_MS, 100 + i, 110 + i, 90 + i, 105 + i, 1] for i in range(10)]   # seg a qua da 2ª semana
    fechadas = semanais_ate(diarios, SEGUNDA + 9 * DIA_MS)
    assert len(fechadas) == 1, "a segunda semana ainda não fechou"
    w = fechadas[0]
    assert w[0] == SEGUNDA and w[1] == 100 and w[2] == 116 and w[3] == 90 and w[4] == 111
    assert len(semanais_ate(diarios, SEGUNDA + 14 * DIA_MS)) == 2


def _c(vies, fase, prob, inval, nome="c"):
    return {"nome": nome, "vies": vies, "fase": fase, "probabilidade": prob, "invalidacao": inval, "alvos": []}


def test_invalidacao_comum_derruba_a_maior_parte_das_contagens_de_alta():
    cen = [_c("bull", "onda_2", 0.4, 95), _c("bull", "inicio_onda_3", 0.3, 90), _c("bull", "onda_5", 0.1, 98),
           _c("bear", "onda_4", 0.2, 110)]
    # do mais alto para baixo: 98 (0,1), 95 (0,5 acumulado), 90 (0,8). 60% de 0,8 = 0,48 → cai em 95
    assert invalidacao_comum(cen, preco=100, lado=1) == 95
    assert invalidacao_comum(cen, preco=100, lado=-1) == 110
    assert invalidacao_comum([_c("bear", "onda_4", 0.5, 90)], preco=100, lado=1) is None


def test_resumo_pondera_os_graus_e_marca_onda_2_e_veto_de_onda_4():
    graus = {
        "ciclo": {"prob_bull": 1.0, "prob_bear": 0.0, "cenarios": [_c("bull", "meio_onda_3", 1.0, 15000)]},
        "primario": {"prob_bull": 0.6, "prob_bear": 0.4, "cenarios": [_c("bull", "onda_5", 0.6, 60000)]},
        "intermediario": {"prob_bull": 0.5, "prob_bear": 0.5,
                          "cenarios": [_c("bull", "onda_2", 0.45, 74000), _c("bear", "onda_4", 0.55, 82000)]},
    }
    r = resumir(graus, preco=78000)
    assert r["prob_bull"] == pytest.approx(0.2 * 1.0 + 0.5 * 0.6 + 0.3 * 0.5)
    assert r["grau_operacional"] == "intermediario"
    assert r["veto_onda_4"] is True
    assert r["setup_onda_2"]["vies"] == "bull" and r["setup_onda_2"]["invalidacao"] == 74000
    assert r["invalidacao_compra"] == 74000 and r["invalidacao_venda"] == 82000
    assert -1 <= r["inclinacao"] <= 1


def test_sem_graus_nao_quebra():
    r = resumir({}, preco=100)
    assert r["prob_bull"] == 0 and r["setup_onda_2"] is None and r["veto_onda_4"] is False
