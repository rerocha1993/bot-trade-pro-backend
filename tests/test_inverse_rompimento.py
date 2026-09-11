"""
Rompimento do range no modo inverse — as regras do usuário, num range de 57k a 82k:

    - rompeu o TOPO de verdade  -> fecha todo o short e deixa subir
    - rompeu o topo em FALSO    -> não fecha; deixa voltar
    - rompeu o FUNDO de verdade -> espera o respiro e, no reteste, vende quase 100%
    - rompeu o fundo em FALSO   -> não vende nada; deixa subir

Mais a regressão que motivou tudo: aprovar um range com o preço no meio dele vendia 60% da carteira de uma vez.
"""
import time
from types import SimpleNamespace

import pytest

from core.inverse_grade import GradeInversa
from core.inverse_rompimento import (
    AGUARDANDO_RETESTE, CONCLUIDO, ENCERRADO, RANGE, ROMPENDO_FUNDO, ROMPENDO_TOPO, SHORT_RETESTE,
    MaquinaRompimento, ParametrosRompimento, pesos_inverse, validar_aprovacao,
)

L, H = 57647.3, 82799.9        # o range que o robô mostrava ao vivo


def vela(m, close, high=None, low=None, equity=1.0, alvos=None, ja=0.0, ts=0):
    return m.avaliar(ts, close if high is None else high, close if low is None else low, close,
                     equity, L, H, alvos, ja)


# ------------------------------------------------------------------ topo
def test_dentro_do_range_nao_faz_nada():
    m = MaquinaRompimento()
    r = vela(m, 70000.0)
    assert r["estado"] == RANGE and not r["fechar_grade"] and not r["execs"]


def test_topo_rompido_de_verdade_fecha_tudo():
    m = MaquinaRompimento()
    r1 = vela(m, 83700.0)                       # acima de 82.800 + 1%
    assert r1["estado"] == ROMPENDO_TOPO and not r1["fechar_grade"], "fechou no primeiro fechamento acima"
    r2 = vela(m, 84000.0)
    assert r2["fechar_grade"] and r2["estado"] == ENCERRADO


def test_topo_rompido_sem_duvida_fecha_no_primeiro_fechamento():
    m = MaquinaRompimento()
    r = vela(m, 86000.0)                        # além de 3% do topo
    assert r["fechar_grade"] and r["estado"] == ENCERRADO


def test_topo_falso_nao_fecha():
    """A regra que o usuário pediu explicitamente: rompeu e voltou, o short fica."""
    m = MaquinaRompimento()
    vela(m, 83700.0)
    r = vela(m, 82000.0)                        # voltou para dentro do range
    assert r["estado"] == RANGE and not r["fechar_grade"]
    assert r["evento"] == "topo_falso"


def test_colado_no_topo_nao_confirma_sozinho():
    """Ficar em cima da borda sem a folga não é rompimento: a contagem recomeça."""
    m = MaquinaRompimento()
    vela(m, 83700.0)                            # 1/2
    r = vela(m, 83000.0)                        # acima do topo, mas dentro da folga
    assert r["estado"] == ROMPENDO_TOPO and m.contagem == 0 and not r["fechar_grade"]
    assert not vela(m, 83700.0)["fechar_grade"]  # 1/2 de novo
    assert vela(m, 84000.0)["fechar_grade"]      # 2/2


def test_contagem_de_elliott_de_alta_nao_confirma_rompimento_sozinha():
    """A regra antiga fechava no 1º fechamento acima do topo se a contagem estivesse de alta. Aqui não entra Elliott."""
    m = MaquinaRompimento()
    r = vela(m, 83700.0, alvos=[100000.0, 126000.0])
    assert not r["fechar_grade"]


# ------------------------------------------------------------------ fundo
def _fundo_rompido(m, alvos=None):
    vela(m, 56900.0, alvos=alvos)               # abaixo de 57.647 - 1%: 1/2
    r = vela(m, 56500.0, alvos=alvos)           # 2/2
    assert r["estado"] == AGUARDANDO_RETESTE, r["motivo"]
    return r


def test_fundo_falso_nao_vende():
    m = MaquinaRompimento()
    vela(m, 56900.0)
    r = vela(m, 57800.0)                        # voltou acima do fundo
    assert r["estado"] == RANGE and not r["execs"] and r["evento"] == "fundo_falso"


def test_fundo_rompido_de_verdade_espera_o_respiro_e_vende_no_reteste():
    m = MaquinaRompimento()
    _fundo_rompido(m)
    assert not vela(m, 55500.0)["execs"], "vendeu antes do reteste"
    # o respiro: a máxima volta até o fundo rompido e o candle fecha abaixo dele (rejeição)
    r = vela(m, 57200.0, high=57500.0, low=56800.0)
    assert r["estado"] == SHORT_RETESTE
    (venda,) = r["execs"]
    assert venda["tipo"] == "venda" and venda["contratos"] == pytest.approx(0.9 * 1.0 * 57200.0)
    # e realiza no alvo
    r2 = vela(m, 44000.0, high=45000.0, low=m.alvo - 1)
    (recompra,) = r2["execs"]
    assert recompra["tipo"] == "recompra" and recompra["pnl_btc"] > 0
    assert r2["concluido"] and r2["estado"] == CONCLUIDO


def test_short_de_reteste_tem_stop():
    """O único lugar do inverse que vende grande de uma vez precisa de saída se o rompimento falhar."""
    m = MaquinaRompimento()
    _fundo_rompido(m)
    vela(m, 57200.0, high=57500.0, low=56800.0)
    r = vela(m, 58400.0)                        # fechou acima de 57.647 + 1%
    (recompra,) = r["execs"]
    assert recompra["pnl_btc"] < 0
    assert r["estado"] == RANGE and not r["concluido"]


def test_toque_sem_rejeicao_nao_vende():
    """Encostar no fundo rompido e fechar ACIMA dele não é rejeição: ainda está sendo testado."""
    m = MaquinaRompimento()
    _fundo_rompido(m)
    r = vela(m, 57900.0, high=58000.0, low=57300.0)
    assert r["estado"] == AGUARDANDO_RETESTE and not r["execs"]


def test_fundo_retomado_depois_de_confirmado_volta_ao_range_sem_vender():
    m = MaquinaRompimento()
    _fundo_rompido(m)
    r = vela(m, 58400.0)
    assert r["estado"] == RANGE and not r["execs"] and r["evento"] == "fundo_retomado"


def test_sem_reteste_ate_o_alvo_conclui_sem_vender():
    m = MaquinaRompimento()
    _fundo_rompido(m)
    r = vela(m, m.alvo - 100)
    assert r["concluido"] and not r["execs"] and r["evento"] == "alvo_sem_reteste"


def test_reteste_que_nao_vem_expira():
    m = MaquinaRompimento(ParametrosRompimento(espera_max_reteste=3))
    _fundo_rompido(m)
    vela(m, 55000.0)
    vela(m, 55000.0)
    r = vela(m, 55000.0)
    assert r["concluido"] and r["evento"] == "reteste_expirou"


def test_alvo_de_elliott_tem_preferencia_sobre_a_projecao():
    m = MaquinaRompimento()
    _fundo_rompido(m, alvos=[50000.0, 45000.0, 60000.0])     # 60k fica acima do fundo e não serve
    assert m.alvo == 50000.0 and m.fonte_alvo == "Elliott"
    m2 = MaquinaRompimento()
    _fundo_rompido(m2)
    assert m2.alvo == pytest.approx(L - 0.618 * (H - L)) and "61,8%" in m2.fonte_alvo


def test_quase_100_e_o_short_total_somando_as_fatias_de_base():
    m = MaquinaRompimento()
    _fundo_rompido(m)
    r = vela(m, 57200.0, high=57500.0, ja=0.3)                 # 30% já vendidos pelas fatias de base
    (venda,) = r["execs"]
    assert venda["contratos"] == pytest.approx(0.6 * 1.0 * 57200.0)


def test_estado_sobrevive_ao_reinicio_do_servidor():
    m = MaquinaRompimento()
    _fundo_rompido(m)
    vela(m, 57200.0, high=57500.0, low=56800.0)
    volta = MaquinaRompimento.from_dict(m.as_dict())
    assert volta.estado == SHORT_RETESTE and volta.reteste == m.reteste
    r = vela(volta, 44000.0, low=volta.alvo - 1)
    assert r["concluido"] and r["execs"][0]["pnl_btc"] > 0


def test_estado_corrompido_volta_ao_range_em_vez_de_quebrar():
    assert MaquinaRompimento.from_dict({"estado": "nao_existe"}).estado == RANGE
    assert MaquinaRompimento.from_dict(None).estado == RANGE


def test_parametros_incoerentes_sao_recusados():
    for kw in ({"folga": 0.0}, {"fechamentos_confirmacao": 0}, {"multiplo_rompimento_claro": 1.0},
               {"fracao_reteste": 1.5}, {"espera_max_reteste": 0}):
        with pytest.raises(ValueError):
            ParametrosRompimento(**kw)


# ------------------------------------------------------------------ grade
def test_grade_do_inverse_chega_a_100_no_topo_e_nao_vende_acima():
    p = pesos_inverse()
    assert sum(p.values()) == pytest.approx(1.0)
    assert max(p) == 1.0, "sobrou nível acima do topo"


def test_aprovar_com_o_preco_no_meio_do_range_nao_vende_de_uma_vez():
    """
    Regressão medida: com o range 57.647–82.800 e o preço em 76.810, a grade nascia com todos os níveis ativos
    e, no primeiro candle de 4h, vendia 14 fatias — 60% da carteira de uma vez, a mercado. O guarda que evita
    isso (`desativar_abaixo`) existia e o hedge dial usava; o executor do inverse nunca chamava.
    """
    from core.inverse_executor import InverseRangeExecutor
    inv = InverseRangeExecutor.__new__(InverseRangeExecutor)
    inv.bot = SimpleNamespace(range_low=L, range_high=H, escada_json=None, folga_stop=0.01, grade_json=None)
    inv.db = SimpleNamespace(commit=lambda: None)
    inv.maquina = MaquinaRompimento()
    g = inv._nova_grade(76810.0)
    execs = g.processar_candle(0, 76810.0 * 1.006, 76810.0 * 0.994, 76810.0, 1.0)
    assert not [e for e in execs if e["tipo"] == "venda"], "vendeu de uma vez os níveis abaixo do preço"


# ------------------------------------------------------------------ aprovação
def test_aprovacao_limpa_nao_tem_aviso():
    assert validar_aprovacao(L, H, 70000.0, "proposto", 0.0) == ([], [])


def test_aprovacao_bloqueia_range_impossivel_e_grade_com_short_aberto():
    bloq, _ = validar_aprovacao(H, L, 70000.0, "proposto", 0.0)
    assert bloq
    bloq2, _ = validar_aprovacao(L, H, 70000.0, "proposto", 50000.0)
    assert bloq2 and "sem gestão" in bloq2[0]


def test_aprovacao_avisa_sem_proposta_valida_e_preco_fora():
    """A rota antiga aceitava calada até a proposta que o próprio robô marcava como inválida."""
    _, avisos = validar_aprovacao(L, H, 90000.0, None, 0.0)
    assert any("fora do range" in a for a in avisos)
    assert any("proposta válida" in a for a in avisos)


# ------------------------------------------------------------------ no ciclo do executor
class _Db:
    def add(self, o):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass


def _executor():
    from core.inverse_executor import InverseRangeExecutor
    bot = SimpleNamespace(id=8, nome="Hedge Inverso", range_low=L, range_high=H, range_status="aprovado",
                          escada_json=None, folga_stop=0.01, grade_json=None, banca=1.0, range_motivo=None)
    ex = SimpleNamespace(bot=bot, db=_Db(), par="BTCUSD", modo="simulador", timeframe="4h", con=None,
                         ordens=SimpleNamespace(simulado=True), estado={"pnl_dia": 0.0, "preco": 0.0}, logs=[],
                         alertas=SimpleNamespace(info=lambda *a, **k: None))
    ex._log = lambda **kw: ex.logs.append(kw)
    inv = InverseRangeExecutor(ex)
    inv._mestre_cache, inv._mestre_ts = {"guia": None, "primario": None}, time.time()
    return inv, ex


def _candle(inv, ts, close, high, low):
    inv.ciclo([[ts, close, high, low, close, 1.0]], close, True)


def test_no_ciclo_rompimento_real_do_topo_fecha_toda_a_grade():
    inv, ex = _executor()
    _candle(inv, 1, 76810.0, 77200.0, 76400.0)
    assert inv.grade.fracao_aberta() == 0.0, "vendeu no primeiro candle"
    _candle(inv, 2, 80000.0, 80200.0, 79500.0)
    assert inv.grade.fracao_aberta() > 0, "não vendeu subindo no range"
    _candle(inv, 3, 83700.0, 84000.0, 82500.0)
    assert inv.grade is not None and inv.grade.fracao_aberta() > 0, "fechou antes de confirmar"
    _candle(inv, 4, 84100.0, 84300.0, 83500.0)
    assert ex.bot.range_status == "encerrado" and inv.grade is None
    assert any(l.get("tipo_operacao") == "saida" for l in ex.logs), "não recomprou o short"


def test_no_ciclo_rompimento_falso_do_topo_mantem_o_short():
    inv, ex = _executor()
    _candle(inv, 1, 76810.0, 77200.0, 76400.0)
    _candle(inv, 2, 80000.0, 80200.0, 79500.0)
    _candle(inv, 3, 83700.0, 84000.0, 82500.0)
    _candle(inv, 4, 82000.0, 83000.0, 81800.0)             # voltou para dentro
    assert ex.bot.range_status == "aprovado"
    assert inv.maquina.estado == RANGE and inv.grade.fracao_aberta() > 0
