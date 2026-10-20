"""Coletor de negócios (leitura e agregação por minuto) e as leituras de fluxo: velas, presos e absorção."""
from conselho import fluxo
from conselho.coletor_negocios import AgregadorMinuto, ler_binance, ler_bybit, ler_coinbase

T0 = 1_792_000_200          # múltiplo de 300 s


# ----------------------------------------------------------------- leitura das mensagens
def test_lado_do_agressor_em_cada_corretora():
    assert ler_bybit({"topic": "publicTrade.BTCUSDT", "data": [{"T": 1000, "p": "100", "v": "2", "S": "Buy"}]}) == [(1.0, 100.0, 2.0, True)]
    assert ler_bybit({"op": "pong"}) == []
    # Binance: m = o comprador era maker -> o agressor vendeu
    assert ler_binance({"e": "aggTrade", "T": 2000, "p": "100", "q": "1", "m": True}) == [(2.0, 100.0, 1.0, False)]
    # Coinbase: side é a ordem maker; maker vendendo = agressor comprando
    (n,) = ler_coinbase({"type": "match", "time": "1970-01-01T00:00:03Z", "price": "100", "size": "0.5", "side": "sell"})
    assert n == (3.0, 100.0, 0.5, True)


def test_agregador_fecha_o_minuto_so_depois_do_atraso():
    ag = AgregadorMinuto("bybit", passo_usd=20.0)
    ag.adicionar([(T0 + 1, 100_005.0, 2.0, True), (T0 + 30, 100_030.0, 1.0, False), (T0 + 59, 99_990.0, 0.5, True),
                  (T0 + 61, 100_000.0, 9.0, True)])
    assert ag.fechados(T0 + 62) == []                 # o minuto T0 ainda está no atraso
    (r,) = ag.fechados(T0 + 66)
    assert r["ts"] == T0 and r["compra"] == 2.5 and r["venda"] == 1.0 and r["delta"] == 1.5 and r["n"] == 3
    assert (r["abertura"], r["maxima"], r["minima"], r["fechamento"]) == (100_005.0, 100_030.0, 99_990.0, 99_990.0)
    assert r["niveis"] == [[99_980.0, 0.5, 0.0], [100_000.0, 2.0, 0.0], [100_020.0, 0.0, 1.0]]
    assert list(ag.minutos) == [T0 + 60]


# ----------------------------------------------------------------- velas e presos
def minuto(ts, ab, mx, mn, fe, niveis, compra=None, venda=None):
    c = sum(n[1] for n in niveis) if compra is None else compra
    v = sum(n[2] for n in niveis) if venda is None else venda
    return {"ts": ts, "abertura": ab, "maxima": mx, "minima": mn, "fechamento": fe, "compra": c, "venda": v, "niveis": niveis}


def test_barras_somam_exchanges_e_pegam_ohlc_de_uma_so():
    m = {"bybit": [minuto(T0, 100, 110, 95, 105, [[100.0, 1, 0]]), minuto(T0 + 60, 105, 120, 104, 118, [[100.0, 2, 1]])],
         "coinbase": [minuto(T0, 90, 999, 1, 91, [[100.0, 4, 0]])]}
    (b,) = fluxo.barras(m, 300, preco_de="bybit")
    assert (b["abertura"], b["maxima"], b["minima"], b["fechamento"]) == (100, 120, 95, 118)
    assert b["compra"] == 7 and b["venda"] == 1 and b["delta"] == 6 and b["niveis"][100.0] == [7.0, 1.0]


def vela(ts, ab, mx, mn, fe, niveis):
    return {"ts": ts, "abertura": ab, "maxima": mx, "minima": mn, "fechamento": fe,
            "compra": sum(c for c, _ in niveis.values()), "venda": sum(v for _, v in niveis.values()),
            "delta": 0.0, "niveis": niveis}


def test_compradores_presos_no_topo_confirmados_pelo_abandono():
    base = {f: [1.0, 1.0] for f in (99_900.0, 99_920.0, 99_940.0, 99_960.0)}
    topo = {**base, 100_080.0: [30.0, 1.0]}          # nó comprador no terço de cima, a vela fecha abaixo
    velas = [vela(T0, 99_950, 100_100, 99_900, 99_960, topo),
             vela(T0 + 300, 99_960, 99_970, 99_700, 99_750, base),
             vela(T0 + 600, 99_750, 99_800, 99_600, 99_650, base)]
    (e,) = fluxo.presos(velas, abandono_pct=0.002)
    assert e["lado"] == "compradores" and e["preco"] == 100_090.0 and e["btc"] == 30.0 and e["confirmado"] is True
    # sem as velas seguintes, a marca fica em formação
    (e2,) = fluxo.presos(velas[:1])
    assert e2["confirmado"] is None


def test_no_comprador_que_rompe_para_cima_nao_e_preso():
    topo = {99_900.0: [1.0, 1.0], 99_920.0: [1.0, 1.0], 99_940.0: [1.0, 1.0], 100_080.0: [30.0, 1.0]}
    assert fluxo.presos([vela(T0, 99_950, 100_100, 99_900, 100_095, topo)]) == []


# ----------------------------------------------------------------- absorção
def test_absorcao_exige_parede_agressao_oi_e_preco_travado():
    velas = []
    for k in range(30):                                # 2 h e meia de delta normal (-2..+2)
        b = vela(T0 + 300 * k, 100_000, 100_050, 99_950, 100_000, {})
        b["delta"] = float((k % 5) - 2)
        velas.append(b)
    alvo = vela(T0 + 300 * 30, 100_000, 100_380, 99_990, 100_200, {})
    alvo["delta"] = 40.0                               # agressão compradora fora do normal
    velas.append(alvo)
    parede = [100_400.0, 100_500.0, 1, 80.0, 9.0]      # venda 9x o normal, logo acima da máxima
    calor = {"colunas": [{"ts": alvo["ts"], "mid": 100_200, "celulas": [parede]},
                         {"ts": alvo["ts"] + 300, "mid": 100_150, "celulas": [parede]}]}
    velas.append(vela(alvo["ts"] + 300, 100_200, 100_250, 100_100, 100_150, {}))
    oi_sobe = [[(alvo["ts"] - 900) * 1000, 50_000.0], [(alvo["ts"] + 300) * 1000, 50_400.0]]
    (e,) = fluxo.absorcao(velas, calor, oi_sobe)
    assert e["tipo"] == "venda" and e["baixo"] == 100_400.0 and e["delta_z"] > 2 and e["oi_var_pct"] > 0
    assert e["ate_ts"] == alvo["ts"] + 600             # a parede seguiu de pé na vela seguinte
    # sem alavancagem entrando, não é a distorção
    oi_cai = [[p[0], 50_000.0 - i] for i, p in enumerate(oi_sobe)]
    assert fluxo.absorcao(velas, calor, oi_cai) == []
    # se o preço atravessou a parede, não houve absorção
    alvo["fechamento"] = 100_450
    assert fluxo.absorcao(velas, calor, oi_sobe) == []


def test_presos_com_buraco_na_coleta_logo_depois_nao_marca():
    base = {f: [1.0, 1.0] for f in (99_900.0, 99_920.0, 99_940.0, 99_960.0)}
    topo = {**base, 100_080.0: [30.0, 1.0]}
    velas = [vela(T0, 99_950, 100_100, 99_900, 99_960, topo),
             vela(T0 + 300 * 50, 99_960, 99_970, 99_700, 99_750, base),       # horas depois
             vela(T0 + 300 * 51, 99_750, 99_800, 99_600, 99_650, base)]
    assert fluxo.presos(velas, passo_s=300) == []
