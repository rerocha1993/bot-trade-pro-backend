"""Contexto de order flow: long/short de contas contra a mediana de 30 dias, sem olhar o futuro."""
from core.contexto_derivativos import HORA_MS, ContextoLSR

T0 = 1_700_000_000_000 - (1_700_000_000_000 % HORA_MS)


def _serie(n_horas, valor=1.5):
    return {T0 + i * HORA_MS: valor for i in range(n_horas)}


def test_so_usa_a_hora_que_ja_fechou():
    s = _serie(24 * 10)
    s[T0 + 240 * HORA_MS] = 0.5                     # hora nova, ainda aberta
    c = ContextoLSR(s)
    assert c.atual(T0 + 240 * HORA_MS + 10) == 1.5
    assert c.atual(T0 + 241 * HORA_MS) == 0.5


def test_presos_do_lado_certo_da_borda():
    s = _serie(24 * 10)
    s[T0 + 239 * HORA_MS] = 1.0                     # menos contas compradas que o normal
    c = ContextoLSR(s)
    agora = T0 + 240 * HORA_MS
    assert c.presos_contra(agora, 1) is True        # no VAL: multidão vendida
    assert c.presos_contra(agora, -1) is False      # no VAH: não há comprados sobrando


def test_sem_uma_semana_de_dado_nao_decide():
    c = ContextoLSR(_serie(24 * 3))
    assert c.presos_contra(T0 + 72 * HORA_MS, 1) is None
    assert c.filtro()(T0 + 60 * HORA_MS, 1) is False
    assert c.filtro(sem_dado=True)(T0 + 60 * HORA_MS, 1) is True
