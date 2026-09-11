"""
Scalp por indicadores em 5m: só os indicadores do usuário, sem Elliott, sem nada novo.

O que estes testes protegem:
    - nada olha o futuro (o contexto do candle t não muda quando chegam candles depois dele)
    - as variações usam a MESMA conta dos indicadores do projeto (VWAP da sessão, value area do VP e do TPO)
    - o stop respeita o piso de ruído e o risco:retorno é líquido de custo
    - o backtest executa como o robô: ordem limitada, stop antes do alvo, limites do dia
"""
import math
import random

import pytest

from core.backtest_scalp import BacktestScalp, avaliar_criterio
from core.scalp_indicadores import (
    DIA_MS, RISCO_MINIMO_PCT, SETUPS, Ctx, Sinal, montar_contextos, montar_sinal, risco_minimo,
)
from core.tpo import TPOProfile
from core.volume_profile_pro import VolumeProfilePRO
from core.vwap import VWAPCalculator

T0 = 1_780_000_000_000 - (1_780_000_000_000 % DIA_MS)     # meia-noite UTC
M5 = 300_000


def passeio(n, preco=78000.0, semente=7, t0=T0):
    random.seed(semente)
    out, p = [], preco
    for i in range(n):
        o = p
        c = o * (1 + random.gauss(0, 0.0015))
        h, l = max(o, c) * (1 + abs(random.gauss(0, 0.0007))), min(o, c) * (1 - abs(random.gauss(0, 0.0007)))
        out.append([t0 + i * M5, o, h, l, c, random.uniform(5, 50)])
        p = c
    return out


# ------------------------------------------------------------------ contexto
def test_nada_olha_o_futuro():
    velas = passeio(900)
    curto = montar_contextos(velas[:600])
    longo = montar_contextos(velas)
    for campo in ("vwap", "sigma", "va_vp", "va_tpo", "regime", "eficiencia", "atr", "maxima_sessao", "minima_sessao"):
        assert getattr(curto[599], campo) == getattr(longo[599], campo), f"{campo} mudou quando chegaram candles futuros"


def test_vwap_da_sessao_e_a_mesma_conta_do_indicador_do_projeto():
    velas = passeio(400)
    ctxs = montar_contextos(velas)
    x = ctxs[350]
    sessao = [v for v in velas[:351] if v[0] // DIA_MS == x.dia]
    ref = VWAPCalculator(sessao).vwap_bandas()
    assert x.vwap == pytest.approx(ref["vwap"], rel=1e-9)
    assert x.sigma == pytest.approx(ref["stddev"], rel=1e-6)


def test_vwap_reinicia_a_meia_noite_utc():
    ctxs = montar_contextos(passeio(400))
    primeiro_do_dia = next(x for x in ctxs if x.k == 0 and x.i > 0)
    assert primeiro_do_dia.vwap == pytest.approx((primeiro_do_dia.h + primeiro_do_dia.l + primeiro_do_dia.c) / 3)


def test_value_area_e_da_sessao_anterior_pelos_dois_indicadores():
    velas = passeio(600)
    ctxs = montar_contextos(velas)
    x = next(c for c in ctxs if c.dia == velas[0][0] // DIA_MS + 1)
    anterior = [v for v in velas if v[0] // DIA_MS == x.dia - 1]
    vp = VolumeProfilePRO(anterior, num_bins=40).poc_va()
    tpo = TPOProfile(anterior, bins=30).calculate_poc_val_vah()
    assert x.va_vp == {"VAL": vp["VAL"], "POC": vp["POC"], "VAH": vp["VAH"]}
    assert x.va_tpo["POC"] == pytest.approx(tpo["POC"])


def test_primeira_sessao_nao_tem_value_area_inventada():
    assert montar_contextos(passeio(100))[50].va_vp is None


def test_nenhum_setup_usa_indicador_de_fora():
    """A regra do usuário: só os indicadores que ele programou. Nada de EMA, RSI, MACD..."""
    import ast
    import inspect
    import core.scalp_indicadores as mod
    arvore = ast.parse(inspect.getsource(mod))
    nomes = set()
    for no in ast.walk(arvore):          # só o código: nomes, atributos e imports (a docstring pode citar a regra)
        if isinstance(no, ast.Name):
            nomes.add(no.id.lower())
        elif isinstance(no, ast.Attribute):
            nomes.add(no.attr.lower())
        elif isinstance(no, (ast.Import, ast.ImportFrom)):
            nomes.update(a.name.lower() for a in no.names)
            nomes.add((getattr(no, "module", "") or "").lower())
    for proibido in ("ema", "rsi", "macd", "stoch", "bollinger", "media_movel", "sma"):
        assert not any(proibido == n or n.startswith(proibido + "_") or n.endswith("_" + proibido) for n in nomes), \
            f"{proibido} apareceu no scalp"


# ------------------------------------------------------------------ sinal
def _ctx(c=78000.0, h=78100.0, l=77900.0, atr_=40.0, vwap=78000.0, sigma=100.0, **kw):
    base = dict(i=0, ts=T0, o=c, h=h, l=l, c=c, v=10.0, dia=T0 // DIA_MS, k=30, vwap=vwap, sigma=sigma,
                va_vp=None, va_tpo=None, abertura_sessao=c, maxima_sessao=h, minima_sessao=l, ts_max_sessao=T0,
                ts_min_sessao=T0, regime="tendencia", eficiencia=0.5, atr=atr_, blocos_bull=[], blocos_bear=[])
    base.update(kw)
    return Ctx(**base)


def test_stop_colado_vai_para_o_piso():
    x = _ctx()
    s = montar_sinal("t", "buy", x, sl_estrutural=77990.0)            # 10 dólares: dentro do ruído
    assert x.c - s.sl == pytest.approx(risco_minimo(x))
    assert risco_minimo(x) >= x.c * RISCO_MINIMO_PCT


def test_risco_retorno_liquido_de_custo_recusa_alvo_perto():
    x = _ctx()
    assert montar_sinal("t", "buy", x, 77800.0, tp=78050.0) is None  # ganha 50 arriscando 200


def test_alvo_padrao_e_2r():
    x = _ctx()
    s = montar_sinal("t", "buy", x, 77800.0)
    assert (s.tp - s.entrada) == pytest.approx(2 * (s.entrada - s.sl))


def test_regra_dos_80_por_cento_do_value_area():
    va = {"VAL": 77500.0, "POC": 77800.0, "VAH": 78200.0}
    comum = dict(va_vp=va, abertura_sessao=77300.0)
    ctxs = [_ctx(i=0, c=77400.0, h=77450.0, l=77350.0, k=5, **comum),
            _ctx(i=1, c=77600.0, h=77620.0, l=77380.0, k=6, **comum),
            _ctx(i=2, c=77650.0, h=77700.0, l=77550.0, k=7, **comum)]
    est = {}
    assert SETUPS["va_vp"](ctxs, 1, est) is None                     # só um fechamento dentro
    s = SETUPS["va_vp"](ctxs, 2, est)
    assert s is not None and s.acao == "buy" and s.tp == 78200.0
    assert SETUPS["va_vp"](ctxs, 2, est) is None                     # uma vez por sessão


# ------------------------------------------------------------------ backtest
def _sempre(acao="buy", distancia=0.004):
    """Setup de teste: sinal em todo candle, com stop e alvo simétricos."""
    def f(ctxs, i, est):
        x = ctxs[i]
        s = 1 if acao == "buy" else -1
        return Sinal("sempre", acao, x.c, x.c * (1 - s * distancia), x.c * (1 + s * distancia), "teste")
    return f


def _velas(precos, t0=T0):
    out, ant = [], precos[0]
    for i, c in enumerate(precos):
        out.append([t0 + i * M5, ant, max(ant, c) + 1, min(ant, c) - 1, c, 10.0])
        ant = c
    return out


def test_ordem_limitada_executa_so_quando_o_preco_encosta():
    ctxs = montar_contextos(_velas([100.0] * 40 + [101.0, 102.0, 103.0, 104.0]))
    bt = BacktestScalp(ctxs, {"s": _sempre()}, espera_limite=2)
    r = bt.executar(inicio_ms=ctxs[39].ts)
    assert r["sinais"] >= 1


def test_stop_e_alvo_no_mesmo_candle_conta_o_stop():
    precos = [100.0] * 40
    # candle gigante que passa pelo stop e pelo alvo depois da execução
    velas = _velas(precos + [100.0, 100.0])
    velas[-1] = [velas[-1][0], 100.0, 110.0, 90.0, 100.0, 10.0]
    ctxs = montar_contextos(velas)
    r = BacktestScalp(ctxs, {"s": _sempre(distancia=0.02)}).executar(inicio_ms=ctxs[39].ts)
    assert r["trades"] >= 1 and r["lista"][0]["motivo_saida"] == "SL"


def test_limite_de_perda_do_dia_para_o_robo():
    precos = [100.0 - 0.5 * i for i in range(60)]
    ctxs = montar_contextos(_velas(precos))
    r = BacktestScalp(ctxs, {"s": _sempre(distancia=0.002)}, max_perda_dia_pct=0.0001).executar(inicio_ms=ctxs[30].ts)
    assert r["trades"] <= 2


def test_taxas_entram_em_todo_trade():
    precos = [100.0] * 40 + [100.0 + 0.2 * i for i in range(40)]
    ctxs = montar_contextos(_velas(precos))
    r = BacktestScalp(ctxs, {"s": _sempre(distancia=0.003)}).executar(inicio_ms=ctxs[39].ts)
    assert r["trades"] > 0 and all(t["taxas"] > 0 for t in r["lista"])


def test_criterio_reprova_quem_so_vai_bem_no_treino():
    treino = {"trades": 150, "bruto_pct_medio": 0.002, "custo_pct_medio": 0.0005, "pnl_liquido": 500.0}
    validacao = {"trades": 60, "bruto_pct_medio": 0.0001, "custo_pct_medio": 0.0005, "pnl_liquido": -80.0}
    ok, falhas = avaliar_criterio(treino, validacao)
    assert not ok and any("validação" in f for f in falhas)
    ok2, _ = avaliar_criterio(treino, {**validacao, "pnl_liquido": 120.0})
    assert ok2
