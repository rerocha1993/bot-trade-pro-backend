from api import cache_dias


def test_dias_corta_no_utc_e_termina_no_fim():
    d0 = 1792540800                       # 22/10/2026 00:00 UTC
    assert cache_dias.dias(d0 - 3600, d0 + 7200) == [(d0 - 86400, d0 - 1), (d0, d0 + 7200)]


def test_dia_fechado_vem_do_cache_e_hoje_sempre_recalcula():
    cache_dias.limpar()
    d0 = 1792540800
    chamadas = []

    def calcular(a, b):
        chamadas.append((a, b))
        return {"a": a, "b": b}

    agora = d0 + 5 * 3600
    p1 = cache_dias.por_dia("teste", d0 - 3600, agora, calcular, agora_s=agora)
    p2 = cache_dias.por_dia("teste", d0 - 1800, agora + 300, calcular, agora_s=agora + 300)
    # o dia de ontem é calculado inteiro uma vez só, mesmo com o início andando; hoje é recalculado nas duas
    assert chamadas == [(d0 - 86400, d0 - 1), (d0, agora), (d0, agora + 300)]
    assert p1[0] is p2[0] and p2[1] == {"a": d0, "b": agora + 300}
    cache_dias.limpar()


def test_dia_recem_fechado_espera_a_folga():
    cache_dias.limpar()
    d0 = 1792540800
    chamadas = []
    calcular = lambda a, b: chamadas.append((a, b)) or {}
    agora = d0 + 60                        # ontem acabou há 1 min: ainda pode chegar gravação atrasada
    cache_dias.por_dia("teste", d0 - 3600, agora, calcular, agora_s=agora)
    cache_dias.por_dia("teste", d0 - 3600, agora + 10, calcular, agora_s=agora + 10)    # dentro dos 50 s: reaproveita
    assert chamadas.count((d0 - 86400, d0 - 1)) == 1
    cache_dias.por_dia("teste", d0 - 3600, agora + 60, calcular, agora_s=agora + 60)    # passou: recalcula
    assert chamadas.count((d0 - 86400, d0 - 1)) == 2
    cache_dias.limpar()
