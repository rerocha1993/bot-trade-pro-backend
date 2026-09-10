"""Barras de fluxo: fechar por quantidade negociada, e não por relógio, é o que sustenta o motor do scalp."""
import pytest

from core.barras_fluxo import AgregadorBarras, Barra


def negocios(qtds, preco=100.0, t0=0, passo_ms=100, side="buy"):
    return [{"price": preco, "qty": q, "side": side, "timestamp": t0 + i * passo_ms}
            for i, q in enumerate(qtds)]


def test_fecha_a_barra_no_tamanho_exato():
    ag = AgregadorBarras(tipo="volume", tamanho=1.0)
    fechadas = ag.ingerir(negocios([0.5] * 10))
    assert len(fechadas) == 5
    assert all(abs(b.volume - 1.0) < 1e-9 for b in fechadas)


def test_negocio_grande_e_partido_para_a_barra_nao_passar_do_tamanho():
    """Uma baleia de 2,5 BTC não pode virar uma barra de 2,5 quando a régua é 1: o delta deixaria de ser comparável."""
    ag = AgregadorBarras(tipo="volume", tamanho=1.0)
    fechadas = ag.ingerir(negocios([2.5]))
    assert len(fechadas) == 2
    assert all(abs(b.volume - 1.0) < 1e-9 for b in fechadas)
    assert abs(ag.parcial.volume - 0.5) < 1e-9


def test_delta_separa_agressao_compradora_de_vendedora():
    ag = AgregadorBarras(tipo="volume", tamanho=1.0)
    trades = negocios([0.3, 0.3], side="buy") + negocios([0.4], side="sell", t0=1000)
    fechadas = ag.ingerir(trades)
    assert len(fechadas) == 1
    assert abs(fechadas[0].delta - (0.6 - 0.4)) < 1e-9
    assert abs(fechadas[0].razao_delta - 0.2) < 1e-9


def test_barra_por_tick_nao_parte_negocio():
    """Na contagem por tick um negócio é indivisível: partir seria contar duas vezes o mesmo evento."""
    ag = AgregadorBarras(tipo="tick", tamanho=3)
    fechadas = ag.ingerir(negocios([0.1, 5.0, 0.1, 0.2]))
    assert len(fechadas) == 1
    assert fechadas[0].negocios == 3
    assert abs(fechadas[0].volume - 5.2) < 1e-9


def test_barra_por_dolar_usa_preco_vezes_quantidade():
    ag = AgregadorBarras(tipo="dolar", tamanho=1000.0)
    fechadas = ag.ingerir([{"price": 100.0, "qty": 5.0, "side": "buy", "timestamp": 0},
                           {"price": 100.0, "qty": 6.0, "side": "buy", "timestamp": 100}])
    assert len(fechadas) == 1
    assert abs(fechadas[0].volume - 10.0) < 1e-9      # 10 x 100 = 1000 dólares


def test_ohlc_da_barra_acompanha_os_precos():
    ag = AgregadorBarras(tipo="volume", tamanho=1.0)
    trades = [{"price": p, "qty": 0.25, "side": "buy", "timestamp": i * 100}
              for i, p in enumerate([100.0, 103.0, 98.0, 101.0])]
    b = ag.ingerir(trades)[0]
    assert (b.abertura, b.maxima, b.minima, b.fechamento) == (100.0, 103.0, 98.0, 101.0)
    assert b.as_ohlcv()[1:5] == [100.0, 103.0, 98.0, 101.0]


def test_sem_regua_calibrada_nao_sai_barra_nenhuma():
    """Melhor não decidir nada do que decidir em cima de barras de tamanho arbitrário."""
    ag = AgregadorBarras(tipo="volume", tamanho=0.0, segundos_alvo=30.0)
    assert ag.ingerir(negocios([0.5] * 10, passo_ms=100)) == []
    assert not ag.calibrado


def test_regua_se_calibra_sozinha_pelo_fluxo_observado():
    # 1 BTC por segundo durante 300 segundos, mirando barra a cada 30s -> régua perto de 30 BTC
    trades = [{"price": 100.0, "qty": 0.1, "side": "buy", "timestamp": i * 100} for i in range(3000)]
    ag = AgregadorBarras(tipo="volume", tamanho=0.0, segundos_alvo=30.0)
    ag.ingerir(trades)
    assert ag.calibrado
    assert 25.0 <= ag.tamanho <= 35.0


def test_baleia_isolada_engorda_a_regua_e_a_regua_volta_sozinha():
    """
    Uma ordem gigante infla a régua enquanto está na janela de calibragem. Isso é aceito de propósito: régua
    grande demais deixa o robô QUIETO, que é o erro barato. O caro seria o contrário — régua pequena demais
    manda o robô decidir em cima de ruído. O que não se aceita é o exagero ficar de pé para sempre.
    """
    ag = AgregadorBarras(tipo="volume", tamanho=0.0, segundos_alvo=30.0, recalibrar_a_cada_s=1)
    ag.ingerir(fluxo_constante(1.0, 300))
    regua = ag.tamanho
    assert 25.0 <= regua <= 35.0

    # a baleia entra na janela recente e a próxima recalibragem a enxerga
    ag.ingerir([{"price": 100.0, "qty": 5000.0, "side": "buy", "timestamp": 320_000},
                {"price": 100.0, "qty": 0.1, "side": "buy", "timestamp": 320_100}])
    assert ag.tamanho > regua                      # inflou, e para o lado quieto

    # passado o tempo, a baleia sai da janela recente e a régua volta ao ritmo do mercado
    ag.ingerir(fluxo_constante(1.0, 300, t0=700_000))
    assert 25.0 <= ag.tamanho <= 35.0


def test_tipo_invalido_e_tamanho_negativo_sao_recusados():
    with pytest.raises(ValueError):
        AgregadorBarras(tipo="minuto")
    with pytest.raises(ValueError):
        AgregadorBarras(tipo="volume", tamanho=-1)
    with pytest.raises(ValueError):
        AgregadorBarras(tipo="volume", segundos_alvo=0)


def test_status_conta_o_que_passou():
    ag = AgregadorBarras(tipo="volume", tamanho=1.0)
    ag.ingerir(negocios([0.5] * 10))
    s = ag.status()
    assert s["barras"] == 5 and s["negocios_vistos"] == 10 and s["calibrado"] is True


def test_barra_guarda_volume_por_preco_para_achar_absorcao():
    ag = AgregadorBarras(tipo="volume", tamanho=1.0)
    trades = [{"price": 100.0, "qty": 0.8, "side": "sell", "timestamp": 0},
              {"price": 100.5, "qty": 0.2, "side": "buy", "timestamp": 100}]
    b = ag.ingerir(trades)[0]
    assert abs(sum(b.por_preco.values()) - 1.0) < 1e-9
    assert max(b.por_preco, key=b.por_preco.get) == pytest.approx(100.0, abs=0.1)


def test_barra_avulsa_sem_volume_nao_divide_por_zero():
    b = Barra(inicio_ms=0, fim_ms=0, abertura=1, maxima=1, minima=1, fechamento=1)
    assert b.razao_delta == 0.0


def fluxo_constante(qty_por_s, segundos, t0=0, por_s=10):
    """`por_s` negócios por segundo, somando `qty_por_s` de volume a cada segundo."""
    passo = 1000 // por_s
    return [{"price": 100.0, "qty": qty_por_s / por_s, "side": "buy", "timestamp": t0 + i * passo}
            for i in range(segundos * por_s)]


def test_recalibragem_nao_derruba_a_regua_com_amostra_velha():
    """
    Regressão: a recalibração misturava negócios de horas atrás com os de agora. O meio da amostra virava
    um deserto de segundos vazios, a mediana dava zero e a régua caía para 0,1 BTC — um dia inteiro rendeu
    275 mil barras de nada, e cada uma delas era uma chance de o robô mandar ordem em cima de ruído.
    """
    ag = AgregadorBarras(tipo="volume", tamanho=0.0, segundos_alvo=30.0, recalibrar_a_cada_s=1)
    ag.ingerir(fluxo_constante(6.0, 300))
    regua = ag.tamanho
    assert 150.0 <= regua <= 210.0                      # 6 BTC/s x 30s
    # muito tempo depois, um negócio solto: não há amostra recente, então a régua tem que ficar de pé
    ag.ingerir([{"price": 100.0, "qty": 0.1, "side": "buy", "timestamp": 6 * 3600 * 1000}])
    assert ag.tamanho == regua


def test_regua_acompanha_o_mercado_acelerando():
    ag = AgregadorBarras(tipo="volume", tamanho=0.0, segundos_alvo=30.0, recalibrar_a_cada_s=1)
    ag.ingerir(fluxo_constante(1.0, 300))
    devagar = ag.tamanho
    ag.ingerir(fluxo_constante(10.0, 300, t0=300_000))
    assert ag.tamanho > devagar * 3


def test_regua_entrega_o_ritmo_pedido_mesmo_com_fluxo_torto():
    """
    Regressão: o que importa não é a régua ser "robusta", é a barra sair no ritmo pedido.

    Em BTC o volume por segundo é muito torto — a maioria dos segundos é fraca e alguns são violentos. Uma
    régua calibrada pela mediana enchia muito antes dos 30 segundos combinados: num dia real saíram 41 mil
    barras em vez de 2.880, o que é uma decisão a cada 2 segundos, exatamente o ruído que o motor existe
    para não olhar.
    """
    import random
    random.seed(7)
    trades, ts = [], 0
    for segundo in range(1200):
        volume = 5.0 if segundo % 20 == 0 else 0.1      # um segundo violento a cada vinte
        for i in range(10):
            trades.append({"price": 100.0, "qty": volume / 10, "side": "buy", "timestamp": ts + i * 100})
        ts += 1000
    ag = AgregadorBarras(tipo="volume", tamanho=0.0, segundos_alvo=30.0, recalibrar_a_cada_s=0)
    ag.ingerir(trades)
    ritmo = ag.status()["ritmo_s"]
    assert 15.0 <= ritmo <= 60.0, f"ritmo de {ritmo}s por barra, longe dos 30s pedidos"


def test_regua_nova_so_vale_a_partir_da_proxima_barra():
    """
    Regressão: trocar a régua com barra aberta recortava a barra retroativamente. Uma barra que já tinha
    90 BTC fechava declarando 10, e o resto do laço cuspia oito barras sintéticas no MESMO milissegundo e
    no MESMO preço — a janela de 5 barras do gatilho ficava inteiramente fantasma, com delta e concentração
    inventados. E a régua encolhe toda vez que o mercado desacelera, então isso acontecia de verdade.
    """
    ag = AgregadorBarras(tipo="volume", tamanho=100.0, recalibrar_a_cada_s=0)
    ag.ingerir([{"price": 100.0, "qty": 90.0, "side": "buy", "timestamp": 0}])
    assert ag.parcial.volume == 90.0

    ag._tamanho_pendente = 10.0        # é o que a recalibragem faz agora com uma barra aberta
    fechadas = ag.ingerir([{"price": 100.0, "qty": 10.0, "side": "buy", "timestamp": 100}])
    assert len(fechadas) == 1, f"{len(fechadas)} barras de uma vez: voltaram as barras fantasma"
    assert fechadas[0].volume == 100.0, "a barra aberta foi recortada pela régua nova"
    assert fechadas[0].delta == 100.0
    assert ag.tamanho == 100.0, "a régua trocou antes de a barra fechar"

    # a régua nova entra em vigor ao ABRIR a próxima barra, não antes
    seguintes = ag.ingerir([{"price": 100.0, "qty": 10.0, "side": "buy", "timestamp": 200}])
    assert ag.tamanho == 10.0
    assert ag._tamanho_pendente == 0.0
    assert len(seguintes) == 1 and seguintes[0].volume == 10.0


def test_recalibragem_com_barra_aberta_nao_muda_a_regua_na_hora():
    ag = AgregadorBarras(tipo="volume", tamanho=0.0, segundos_alvo=30.0, recalibrar_a_cada_s=1)
    ag.ingerir(fluxo_constante(1.0, 300))
    regua = ag.tamanho
    ag.ingerir([{"price": 100.0, "qty": regua / 2, "side": "buy", "timestamp": 300_000}])
    assert ag.parcial is not None                       # há barra aberta
    ag.ingerir(fluxo_constante(10.0, 300, t0=301_000))   # mercado acelera: a régua deveria crescer
    assert ag.tamanho > regua                            # e cresceu
    # o que não pode é ter acontecido no meio: nenhuma barra pode ter saído menor que a régua antiga
    for b in ag.ultimas(50):
        assert b.volume >= regua * 0.99, f"barra de {b.volume} com régua de {regua}"
