from conselho import posicionamento as pos


def _linha(ts, preco, compra, venda, oi, contas=0.6):
    return {"ts": ts, "fechamento": preco, "perp_binance": [compra, venda], "perp_bybit": None,
            "spot_binance": [compra, venda], "spot_coinbase": None,
            "oi": {"binance": oi, "bybit": oi / 2, "okx": None}, "contas_long": contas}


def _serie(precos, compras, vendas, ois, contas=None):
    contas = contas or [0.6] * len(precos)
    return [_linha(i * 300, p, c, v, o, k) for i, (p, c, v, o, k) in enumerate(zip(precos, compras, vendas, ois, contas))]


def test_variacao_oi_usa_so_as_corretoras_com_as_duas_pontas():
    a = {"oi": {"binance": 100.0, "bybit": 50.0, "okx": None}}
    b = {"oi": {"binance": 110.0, "bybit": 50.0, "okx": 30.0}}
    assert abs(pos.variacao_oi(a, b) - 10 / 150) < 1e-12


def test_alta_com_perpetuo_vendendo_e_oi_subindo_e_distorcao_de_alta():
    n = 30
    # base: preço e agressão andando juntos (sobe com compra, cai com venda), OI parado
    precos = [100 + (i % 2) for i in range(n)]
    compras = [10.0 if i % 2 else 5.0 for i in range(n)]
    vendas = [5.0 if i % 2 else 10.0 for i in range(n)]
    ois = [1000.0] * n
    # fim: o preço sobe 3% em 6 velas, o perpétuo vende no saldo e o OI sobe (gente abrindo short contra a alta)
    for k, i in enumerate(range(n - 6, n)):
        precos[i] = 101 + 0.5 * (k + 1)
        compras[i], vendas[i] = 4.0, 9.0
        ois[i] = 1000.0 + 10 * (k + 1)
    d = pos.distorcao(_serie(precos, compras, vendas, ois))
    ult = d[-1]
    assert ult["lado"] == "alta"
    assert "agressao" in ult["por"]
    assert ult["perp_pct"] < 0 and ult["oi_pct"] > 0 and ult["preco_pct"] > 0


def test_queda_com_contas_virando_compradas_e_distorcao_de_baixa():
    n = 30
    precos = [100 - (i % 2) for i in range(n)]
    compras = [5.0 if i % 2 else 10.0 for i in range(n)]
    vendas = [10.0 if i % 2 else 5.0 for i in range(n)]
    ois = [1000.0] * n
    contas = [0.6 + (0.001 if i % 2 else -0.001) for i in range(n)]
    for k, i in enumerate(range(n - 6, n)):
        precos[i] = 99 - 0.5 * (k + 1)
        ois[i] = 1000.0 + 10 * (k + 1)
        contas[i] = 0.6 + 0.01 * (k + 1)            # cada vez mais contas compradas na queda
    d = pos.distorcao(_serie(precos, compras, vendas, ois, contas))
    assert d[-1]["lado"] == "baixa"
    assert "contas" in d[-1]["por"]


def test_sem_oi_subindo_nao_acende():
    n = 30
    precos = [100 + (i % 2) for i in range(n)]
    compras = [10.0 if i % 2 else 5.0 for i in range(n)]
    vendas = [5.0 if i % 2 else 10.0 for i in range(n)]
    ois = [1000.0] * n
    for k, i in enumerate(range(n - 6, n)):
        precos[i] = 101 + 0.5 * (k + 1)
        compras[i], vendas[i] = 4.0, 9.0
        ois[i] = 1000.0 - 10 * (k + 1)            # OI caindo: é gente fechando, não abrindo short
    assert pos.distorcao(_serie(precos, compras, vendas, ois))[-1]["lado"] is None


def test_soma_na_grade_so_quando_todas_as_corretoras_tem_valor():
    a = {0: 10.0, 300: 11.0, 600: 12.0}
    b = {300: 5.0, 600: 6.0}
    assert pos.somar_na_grade([a, b], 300, 0, 600) == {300: 16.0, 600: 18.0}
    # uma série parada há mais de 2 pontos deixa de valer
    assert pos.somar_na_grade([a, {0: 1.0}], 300, 0, 1200) == {0: 11.0, 300: 12.0, 600: 13.0}


def test_vela_do_oi_abre_no_comeco_fecha_no_fim_e_pega_maxima_e_minima_de_dentro():
    pontos = {0: 100.0, 300: 104.0, 600: 98.0, 900: 101.0, 1200: 103.0}
    velas = pos.velas_oi(pontos, 900, [0, 900])
    assert velas[0] == [100.0, 104.0, 98.0, 101.0]
    assert velas[900] == [101.0, 103.0, 101.0, 103.0]     # a vela de agora fecha no último ponto que existe
    assert pos.velas_oi(pontos, 900, [5400])[5400] is None


def test_net_positioning_manda_o_oi_para_o_lado_que_agrediu():
    assert pos.posicionamento_liquido(10, 3) == (10, 0)      # OI subiu e compraram: longs abrindo
    assert pos.posicionamento_liquido(10, -3) == (0, 10)     # OI subiu e venderam: shorts abrindo
    assert pos.posicionamento_liquido(-10, 3) == (0, -10)    # OI caiu e compraram: shorts fechando
    assert pos.posicionamento_liquido(-10, -3) == (-10, 0)   # OI caiu e venderam: longs fechando
    assert pos.posicionamento_liquido(0, 5) == (0, 0)
