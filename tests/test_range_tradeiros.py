"""O jogo do range do Tradeiros: merge, bordas, nada no meio, desvio, aceitação, fatias e tirar o risco."""
import math

import pytest

from core.range_tradeiros import (
    BacktestRange, Contexto, ParametrosRange, abrir, aceitacao, contexto, passo_posicao, plano_borda, plano_reteste,
)
from core.tpo_sessao import BLOCO_MS, DIA_MS, Perfil

T0 = 1_780_000_000_000 - (1_780_000_000_000 % DIA_MS)
P = ParametrosRange()


def _dia_oscilando(d, lo=100.0, hi=110.0, fase=0.0):
    """48 blocos oscilando entre lo e hi (range)."""
    out = []
    for i in range(48):
        meio = (lo + hi) / 2 + (hi - lo) / 2 * 0.9 * math.sin(i / 48 * 2 * math.pi * 2 + fase)
        out.append((T0 + d * DIA_MS + i * BLOCO_MS, meio, meio + 0.6, meio - 0.6, meio, 10.0))
    return out


def _ctx():
    return Contexto(val=102.0, vah=108.0, poc=105.0, minima=101.0, maxima=109.0, valido=True, pocs_diarios=[105.0] * 10)


def test_merge_de_dias_lateralizados_e_um_range_valido():
    perfis = [Perfil(_dia_oscilando(d), tick=0.5) for d in range(10)]
    ctx = contexto(perfis, P)
    assert ctx.valido and 99 < ctx.val < ctx.poc < ctx.vah < 111


def test_tendencia_nao_e_range():
    perfis = [Perfil(_dia_oscilando(d, 100 + 8 * d, 110 + 8 * d), tick=0.5) for d in range(10)]
    assert not contexto(perfis, P).valido, "POCs diários fora do valor composto: é tendência, não range"


def test_escada_de_compra_fica_na_borda_de_baixo_e_stop_abaixo_do_fundo():
    pl = plano_borda(_ctx(), 1, "borda", P)
    assert pl is not None
    assert max(pl.niveis) == pytest.approx(102.0 + 0.15 * 6) and min(pl.niveis) == pytest.approx(102.0 - 0.10 * 6)
    assert pl.stop < 102.0 - 0.25 * 6 and pl.alvo1 == 105.0 and pl.alvo2 == 108.0


def test_rr_ruim_nao_opera():
    ctx = Contexto(val=102.0, vah=103.0, poc=102.5, minima=90.0, maxima=111.0, valido=True, pocs_diarios=[])
    assert plano_borda(ctx, 1, "borda", P) is None, "stop longe (fundo em 90) e alvo perto: não compensa"


def test_realiza_metade_no_poc_e_o_stop_vai_para_o_zero_a_zero():
    pl = plano_borda(_ctx(), 1, "borda", P)
    pos = abrir(pl)
    assert passo_posicao(pos, (0, 103, 103.5, 102.8, 103, 1), "tradeiros", P) is None      # executa a 1ª fatia
    assert len(pos.exec_) == 1
    assert passo_posicao(pos, (0, 103, 105.5, 102.8, 105, 1), "tradeiros", P) is None      # chega no POC
    assert pos.parcial_feita and pos.stop == pytest.approx(pos.medio)
    r = passo_posicao(pos, (0, 105, 105, 101, 101, 1), "tradeiros", P)                     # volta: zero a zero
    assert r["motivo"] == "zero_a_zero" and r["bruto_r"] > 0


def test_sem_gestao_segura_ate_o_alvo_ou_o_stop():
    pos = abrir(plano_borda(_ctx(), 1, "borda", P))
    passo_posicao(pos, (0, 102, 103, 101.9, 102.5, 1), "sem", P)
    passo_posicao(pos, (0, 103, 105.5, 102.8, 105, 1), "sem", P)
    assert not pos.parcial_feita
    r = passo_posicao(pos, (0, 105, 108.5, 104, 108, 1), "sem", P)
    assert r["motivo"] == "alvo" and r["liquido_r"] > 0


def test_aceitacao_acima_do_valor():
    ctx = _ctx()
    fora = [(T0 + i * BLOCO_MS, 109, 110, 108.6, 109.5, 1) for i in range(10)]
    assert aceitacao(fora, ctx, P) == 1
    assert aceitacao(fora[:4], ctx, P) == 0, "menos de 4 h fora ainda não é aceitação"


def test_reteste_compra_a_borda_rompida_com_stop_de_volta_dentro():
    pl = plano_reteste(_ctx(), 1, P, 108.5)
    assert pl is not None and pl.stop < 108.0 - 0.3 * 6 and pl.alvo2 == pytest.approx(114.0)


def test_backtest_em_range_compra_embaixo_e_vende_em_cima():
    blocos = [b for d in range(40) for b in _dia_oscilando(d, fase=d * 0.7)]
    r = BacktestRange(blocos, "borda", "tradeiros").executar()
    assert r["trades"] > 0 and r["n_compra"] > 0 and r["n_venda"] > 0


def test_range_adaptativo_para_onde_o_valor_deixou_de_se_sobrepor():
    """O merge é o período lateral: dias de tendência antes dele não entram."""
    tendencia = [Perfil(_dia_oscilando(d, 60 + 8 * d, 70 + 8 * d), tick=0.5) for d in range(5)]
    lateral = [Perfil(_dia_oscilando(5 + d, 100, 110, fase=d), tick=0.5) for d in range(6)]
    ctx = contexto(tendencia + lateral, P)
    assert ctx.valido and ctx.dias == 6 and ctx.minima >= 99


def test_range_de_um_dia_so_nao_vale():
    tendencia = [Perfil(_dia_oscilando(d, 60 + 12 * d, 70 + 12 * d), tick=0.5) for d in range(6)]
    assert not contexto(tendencia, P).valido
