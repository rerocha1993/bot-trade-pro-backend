"""Os 4 robôs em simulação: motor vela a vela, estratégias e o serviço (estado, banca, trades)."""
from types import SimpleNamespace

from conselho import robos as R
from conselho.servico_robos import ServicoRobos

T = 1_792_000_800                      # múltiplo de 1800 s


def plano(lado=1, fatias=((100.0, 0.2), (99.0, 0.3), (98.0, 0.5)), stop=97.0, alvo=104.0, valido=600, teto=3600):
    return R.Plano("cauda_borda", lado, list(fatias), stop, alvo, T, T + valido, teto, "teste")


# ================================================================== motor
def test_fatias_1r_e_alvo():
    pos = R.Posicao(plano())
    assert R.passo(pos, T, 100.2, 100.3, 98.9, 99.2) == ["preencheu"]            # 100 e 99 preenchem
    assert pos.medio == (100 * 0.2 + 99 * 0.3) / 0.5                               # 99,4
    assert R.passo(pos, T + 60, 99.5, 102.0, 99.5, 101.9) == ["1r"]                # 1R = 101,8; stop vai a 99,4
    assert pos.stop_cur == pos.medio and pos.tomou_1r and pos.pend == []
    assert R.passo(pos, T + 120, 102.0, 104.5, 101.0, 104.2) == ["alvo"]
    assert pos.status == "fechada" and pos.tipo_saida == "alvo"
    assert 1.40 < pos.resultado_r < 1.46            # metade em 1R e metade no alvo (+1,92R), menos as taxas


def test_stop_e_favor_no_mesmo_candle_conta_o_stop():
    pos = R.Posicao(plano())
    R.passo(pos, T, 100.2, 100.3, 99.9, 100.0)
    assert R.passo(pos, T + 60, 100.0, 105.0, 96.0, 100.0) == ["preencheu", "stop"]   # as fatias de baixo entram e o stop bate
    assert pos.resultado_r < -1.0                                                  # perde 1R mais as taxas


def test_no_candle_da_entrada_so_o_stop_conta():
    pos = R.Posicao(plano(fatias=((100.0, 1.0),)))
    assert R.passo(pos, T, 100.5, 110.0, 99.0, 109.0) == ["preencheu"]             # bateu 1R e alvo, mas entrou agora
    assert not pos.tomou_1r and pos.status == "aberta"


def test_expira_sem_preencher_e_ignora_candle_repetido():
    pos = R.Posicao(plano(valido=120))
    assert R.passo(pos, T, 101.0, 101.5, 100.5, 101.0) == []
    assert R.passo(pos, T, 101.0, 101.5, 90.0, 101.0) == []                        # mesmo ts: ignorado
    assert R.passo(pos, T + 120, 101.0, 101.5, 100.5, 101.0) == ["expirou"] and pos.status == "expirada"


def test_venda_espelhada_e_tempo():
    pos = R.Posicao(plano(lado=-1, fatias=((100.0, 1.0),), stop=101.0, alvo=95.0, teto=180))
    R.passo(pos, T, 99.8, 100.2, 99.7, 100.0)
    R.passo(pos, T + 60, 100.0, 100.1, 99.6, 99.7)
    assert R.passo(pos, T + 120, 99.7, 99.9, 99.5, 99.6) == ["tempo"]
    assert pos.tipo_saida == "tempo" and pos.resultado_r > 0


def test_posicao_ida_e_volta_em_dicionario():
    pos = R.Posicao(plano())
    R.passo(pos, T, 100.2, 100.3, 98.9, 99.2)
    de_novo = R.Posicao.de_dict(pos.as_dict())
    assert de_novo.medio == pos.medio and de_novo.pend == pos.pend and de_novo.plano.fatias == pos.plano.fatias


# ================================================================== estratégias
COMP = {"val": 80_000.0, "poc": 81_500.0, "vah": 82_000.0}


def mapa(naked=()):
    return SimpleNamespace(composto=dict(COMP), ontem={}, naked_pocs=[{"preco": x} for x in naked])


def velas_cauda(lado=1):
    """4 h acima do VAL e um bloco de 30 min (10:00–10:30 UTC de uma segunda) com cauda compradora no VAL."""
    seg = 1_792_368_000_000                      # segunda-feira 00:00 UTC
    ini = seg + 10 * 3_600_000
    velas = [[ini - 3_600_000 * 4 + k * 300_000, 80_600, 80_700, 80_500, 80_600, 1] for k in range(48)]
    if lado == 1:   # mínima atravessa o VAL (80.000), fecha no terço de cima
        bloco = [[80_450, 80_480, 79_700, 79_800], [79_800, 79_900, 79_690, 79_850], [79_850, 80_100, 79_800, 80_050],
                 [80_050, 80_300, 80_000, 80_250], [80_250, 80_400, 80_200, 80_380], [80_380, 80_480, 80_350, 80_470]]
    velas += [[ini + k * 300_000] + b + [1] for k, b in enumerate(bloco)]
    return velas, (ini + 1_800_000) // 1000


def test_cauda_borda_monta_o_plano_da_regra_do_estudo():
    velas, agora = velas_cauda()
    ctx = R.Contexto(agora_s=agora, velas5=velas, mapa=mapa())
    p = R.cauda_borda(ctx)
    assert p and p.lado == 1 and p.robo == "cauda_borda"
    assert p.stop == round(79_690 * 0.999, 2) and p.alvo == COMP["poc"]
    assert [w for _, w in p.fatias] == [0.2, 0.3, 0.5] and p.fatias[0][0] == 80_470
    assert R.cauda_calco(ctx) is None                                               # sem livro, sem calço
    parede = {"celulas": [[79_760.0, 79_840.0, 0, 60.0, 7.0]]}                     # compra 7x entre o pavio e o VAL
    p2 = R.cauda_calco(R.Contexto(agora_s=agora, velas5=velas, mapa=mapa(), calor_ultimo=parede))
    assert p2 and p2.robo == "cauda_calco" and "calço" in p2.motivo


def test_cauda_fora_do_horario_ou_no_meio_do_range_nao_sai():
    velas, agora = velas_cauda()
    assert R.cauda_borda(R.Contexto(agora_s=agora + 86400 * 5, velas5=velas, mapa=mapa())) is None   # sábado
    meio = SimpleNamespace(composto={"val": 79_000.0, "poc": 81_500.0, "vah": 81_000.0}, ontem={}, naked_pocs=[])
    assert R.cauda_borda(R.Contexto(agora_s=agora, velas5=velas, mapa=meio)) is None                 # VAL no meio


def evento(tipo="venda", fe=81_950.0):
    if tipo == "venda":
        return {"ts": T, "tipo": "venda", "baixo": 82_100.0, "alto": 82_180.0, "intensidade": 9.0, "parede_btc": 80.0,
                "delta_btc": 40.0, "delta_z": 3.0, "oi_var_pct": 0.4, "fechamento": fe}
    return {"ts": T, "tipo": "compra", "baixo": 79_820.0, "alto": 79_900.0, "intensidade": 9.0, "parede_btc": 80.0,
            "delta_btc": -40.0, "delta_z": -3.0, "oi_var_pct": 0.4, "fechamento": fe}


def test_absorcao_so_na_borda_com_alvo_no_poc():
    p = R.absorcao_borda(R.Contexto(agora_s=T, velas5=[], mapa=mapa(), absorcoes=[evento()]))
    assert p and p.lado == -1 and p.alvo == COMP["poc"] and p.stop == round(82_180 * 1.001, 2)
    longe = evento(fe=81_400.0)                                                      # no meio do range
    assert R.absorcao_borda(R.Contexto(agora_s=T, velas5=[], mapa=mapa(), absorcoes=[longe])) is None
    c = R.absorcao_borda(R.Contexto(agora_s=T, velas5=[], mapa=mapa(), absorcoes=[evento("compra", 80_050.0)]))
    assert c and c.lado == 1


def test_esticado_exige_funding_extremo_e_oi_subindo():
    base = dict(agora_s=T, velas5=[], mapa=mapa(), absorcoes=[evento(fe=81_000.0)])
    assert R.esticado_absorcao(R.Contexto(**base, funding_pct=0.89, oi_24h_pct=5.0)) is None     # funding neutro
    assert R.esticado_absorcao(R.Contexto(**base, funding_pct=1.0, oi_24h_pct=1.0)) is None      # OI não subiu 2%
    p = R.esticado_absorcao(R.Contexto(**base, funding_pct=1.0, oi_24h_pct=3.0))
    medio = sum(x * w for x, w in p.fatias)
    assert p.lado == -1 and p.alvo < medio and abs((medio - p.alvo) - 2 * (p.stop - medio)) < 0.02


# ================================================================== serviço
def test_servico_abre_simula_registra_e_sobrevive_a_reinicio(tmp_path):
    relogio = [T + 300]
    velas1 = []

    def candles(tf, desde_ms):
        if tf == "5m":
            return [[(T - 12 * 86400) * 1000 + k * 300_000, 1, 1, 1, 1, 1] for k in range(12 * 288 + 1)]
        return [v for v in velas1 if v[0] >= desde_ms]

    def contexto(agora_s, velas5):
        return SimpleNamespace(marca=agora_s)

    tg = SimpleNamespace(ativo=True, enviados=[], info=lambda t: tg.enviados.append(t) or True)
    s = ServicoRobos(pasta=str(tmp_path), telegram=tg, relogio=lambda: relogio[0], candles=candles, contexto=contexto)
    pl = plano(fatias=((100.0, 1.0),), stop=99.0, alvo=103.0)
    pl.criado_s, pl.valido_ate_s = T + 300, T + 3000
    s_orig = dict(R.ESTRATEGIAS)
    try:
        R.ESTRATEGIAS["cauda_borda"] = lambda ctx: pl
        for k in ("absorcao_borda", "cauda_calco", "esticado_absorcao"):
            R.ESTRATEGIAS[k] = lambda ctx: None
        assert s.ciclo() == ["cauda_borda:plano"]
        assert "Limitadas" in tg.enviados[-1] and "[simulação]" in tg.enviados[-1]
        velas1 += [[(T + 300) * 1000, 100.5, 100.6, 99.8, 100.2, 1], [(T + 360) * 1000, 100.2, 103.5, 100.1, 103.2, 1]]
        relogio[0] = T + 480
        ev = s.ciclo()
        assert ev == ["cauda_borda:preencheu", "cauda_borda:1r", "cauda_borda:alvo"]
        (t,) = s.trades()
        assert t["saida"] == "alvo" and t["resultado_r"] > 1.5 and t["banca"] > R.BANCA_INICIAL
        st = s.status()
        cb = next(r for r in st["robos"] if r["robo"] == "cauda_borda")
        assert cb["trades"] == 1 and cb["ganhos"] == 1 and cb["posicao"] is None and st["simulacao"] is True
        # reinício: a banca vem do disco
        s2 = ServicoRobos(pasta=str(tmp_path), relogio=lambda: relogio[0], candles=candles, contexto=contexto)
        assert s2.estado["cauda_borda"]["banca"] == t["banca"]
    finally:
        R.ESTRATEGIAS.clear()
        R.ESTRATEGIAS.update(s_orig)
