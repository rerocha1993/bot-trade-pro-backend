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
