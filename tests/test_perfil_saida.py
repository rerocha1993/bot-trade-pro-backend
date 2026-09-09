"""Perfil de saída por estilo: o trailing tem que caber no ruído do timeframe."""
import pytest

from core.perfil_saida import PADRAO, PERFIS, PerfilSaida, perfil
from core.saida_escalonada import PLANO_PADRAO, ler_plano


def test_trailing_nunca_trava_prejuizo():
    """Ao ligar, o stop já tem que estar do lado do lucro: ativador > distância nos três estilos."""
    for estilo, p in PERFIS.items():
        assert p.ativador_trailing > p.distancia_trailing, f"{estilo} liga o trailing travando prejuízo"


def test_perfil_invalido_e_recusado_na_criacao():
    with pytest.raises(ValueError):
        PerfilSaida(0.003, 0.005, "50/30")


def test_distancia_cresce_com_o_timeframe():
    assert (PERFIS["scalping"].distancia_trailing
            < PERFIS["daytrade"].distancia_trailing
            < PERFIS["swing"].distancia_trailing), "o pavio de 4h é muito maior que o de 1m"


def test_swing_ficou_bem_mais_folgado_que_o_valor_antigo():
    """O valor único de 0,30% tirava o swing no primeiro pavio: era a queixa."""
    assert PERFIS["swing"].distancia_trailing >= 0.015


def test_estilo_desconhecido_cai_no_daytrade():
    assert perfil("") is PADRAO
    assert perfil(None) is PADRAO
    assert perfil("outro") is PADRAO
    assert perfil("SWING") is PERFIS["swing"], "o estilo não pode depender de caixa alta"


def test_todo_perfil_traz_um_plano_de_saida_valido():
    for estilo, p in PERFIS.items():
        plano = ler_plano(p.saida_escalonada)
        assert plano != PLANO_PADRAO or estilo == "daytrade", f"o plano do {estilo} não foi entendido"
        assert sum(f for _, f in plano) < 1.0, "tem que sobrar posição para o alvo"


def test_scalp_garante_mais_cedo_que_o_swing():
    """No alvo curto vale realizar mais; no swing vale deixar correr."""
    primeira = lambda e: ler_plano(PERFIS[e].saida_escalonada)[0][1]  # noqa: E731
    assert primeira("scalping") > primeira("swing")
