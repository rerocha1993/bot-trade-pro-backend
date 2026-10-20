"""Avisos do conselho (conselho/avisos.py) e o serviço (services/avisos_service.py): só informação, um por nível por dia."""
import json
import os
from types import SimpleNamespace

from conselho.avisos import HORAS_MAPA, JANELA_MAPA_MIN, PROXIMIDADE_PCT, RESSALVA, Estado, avaliar
from conselho.mapa_do_dia import CANDLE_MS, DIA_MS, Mapa, Nivel, mapa
from services.avisos_service import AvisosService
from tests.test_mapa_do_dia import T0, candles_base, dia_flat

H = 3_600_000


def _mapa(ts, preco=80_000.0, niveis=None):
    niveis = niveis if niveis is not None else [
        Nivel("composto.vah", "composto", "VAH do composto (10d)", 81_000.0, 1.25),
        Nivel("composto.poc", "composto", "POC do composto (10d)", 80_100.0, 0.125),
        Nivel("composto.val", "composto", "VAL do composto (10d)", 79_000.0, -1.25),
        Nivel("naked.123", "naked", "Naked POC de 01/05", 80_050.0, 0.0625, 123),
        Nivel("abertura.semana", "abertura", "Abertura da semana", 79_950.0, -0.0625),
        Nivel("abertura.dia", "abertura", "Abertura do dia", 80_020.0, 0.025),
        Nivel("ontem.poc", "ontem", "POC de ontem (28/05)", 80_010.0, 0.0125),
        Nivel("sessao.ontem.asia.poc", "sessao", "Ásia de ontem POC", 80_030.0, 0.0375),
        Nivel("pivo.acima", "pivo", "Pivô virgem acima", 80_040.0, 0.05),
    ]
    return Mapa(ts=ts, preco=preco, posicao="meio", p=0.5, dias_no_composto=10, niveis=niveis)


# ------------------------------------------------------------------ proximidade
def test_proximidade_so_para_composto_naked_e_abertura_semanal():
    e = Estado()
    av = avaliar(_mapa(T0 + 10 * H), 80_000.0, e)
    chaves = {a.chave for a in av}
    assert chaves == {"composto.poc", "naked.123", "abertura.semana"}, \
        "ontem, sessão, pivô e abertura do dia estão a < 0,2% mas não geram aviso de proximidade"
    assert all(a.tipo == "proximidade" for a in av)


def test_limite_de_0_2_por_cento_inclusive():
    m = _mapa(T0 + 10 * H, niveis=[Nivel("composto.val", "composto", "VAL", 80_000.0 * (1 - PROXIMIDADE_PCT / 100), -0.2),
                                   Nivel("composto.vah", "composto", "VAH", 80_000.0 * (1 + 0.21 / 100), 0.21)])
    av = avaliar(m, 80_000.0, Estado())
    assert [a.chave for a in av] == ["composto.val"]


def test_um_aviso_por_nivel_por_dia_e_volta_no_dia_seguinte():
    e = Estado()
    m = _mapa(T0 + 10 * H)
    assert len(avaliar(m, 80_000.0, e)) == 3
    assert avaliar(m, 80_000.0, e) == [], "mesmo instante: nada novo"
    assert avaliar(_mapa(T0 + 15 * H), 80_000.0, e) == [], "mesmo dia, horas depois: o nível já avisou"
    assert avaliar(_mapa(T0 + 20 * H), 80_100.0, e) == [], "preço em cima do POC: continua o mesmo nível, mesmo dia"
    de_novo = avaliar(_mapa(T0 + DIA_MS + 10 * H), 80_000.0, e)
    assert {a.chave for a in de_novo} == {"composto.poc", "naked.123", "abertura.semana"}, "dia seguinte: pode avisar de novo"


def test_distancia_do_aviso_usa_o_preco_ao_vivo_nao_o_do_mapa():
    e = Estado()
    m = _mapa(T0 + 10 * H, preco=80_000.0)
    av = avaliar(m, 81_000.0, e)                         # preço ao vivo em cima do VAH
    assert [a.chave for a in av] == ["composto.vah"] and av[0].nivel["distancia_pct"] == 0.0
    assert "VAH do composto" in av[0].texto and "81.000" in av[0].texto


# ------------------------------------------------------------------ mapa nas aberturas de sessão
def test_mapa_as_0_8_e_13h30_utc_uma_vez_por_sessao():
    e = Estado()
    m_longe = lambda ts: _mapa(ts, niveis=[Nivel("composto.poc", "composto", "POC", 90_000.0, 12.5)])  # noqa: E731
    assert avaliar(m_longe(T0 + 5 * H), 80_000.0, e) == [], "05:00 não é hora de mapa"
    for sessao, h, mi in HORAS_MAPA:
        ts = T0 + h * H + mi * 60_000
        av = avaliar(m_longe(ts + 60_000), 80_000.0, e)                   # 1 min depois da hora
        assert len(av) == 1 and av[0].tipo == "mapa" and av[0].chave == f"mapa.{sessao}", sessao
        assert "POC: 90.000 (+12.50%)" in av[0].texto and "Preço 80.000" in av[0].texto
        assert avaliar(m_longe(ts + 5 * 60_000), 80_000.0, e) == [], "5 min depois: já saiu"
    assert avaliar(m_longe(T0 + 8 * H + JANELA_MAPA_MIN * 60_000), 80_000.0, Estado()) == [], \
        "passada a janela de 30 min, o mapa daquela sessão não sai mais"
    av = avaliar(m_longe(T0 + DIA_MS + 10 * 60_000), 80_000.0, e)
    assert len(av) == 1 and av[0].chave == "mapa.asia", "dia seguinte, 00:10: mapa da Ásia de novo"


def test_mapa_traz_todos_os_niveis_e_a_posicao():
    av = avaliar(_mapa(T0 + 13 * H + 31 * 60_000, niveis=[Nivel("composto.poc", "composto", "POC do composto (10d)", 90_000.0, 12.5),
                                                          Nivel("naked.5", "naked", "Naked POC de 01/05", 70_000.0, -12.5, 5)]),
                 80_000.0, Estado())
    assert len(av) == 1 and av[0].titulo == "Mapa do dia · América"
    linhas = av[0].texto.split("\n")
    assert linhas[1] == "Preço 80.000 · meio do composto"
    assert linhas[2].startswith("POC do composto") and linhas[3].startswith("Naked POC"), "do mais alto ao mais baixo"
    assert linhas[-1] == RESSALVA


# ------------------------------------------------------------------ todo aviso
def test_todo_aviso_tem_a_ressalva_e_nenhum_tem_stop_alvo_ou_pct():
    e = Estado()
    av = avaliar(_mapa(T0 + 8 * H + 60_000), 80_000.0, e)
    assert len(av) == 4                                  # mapa da Europa + 3 proximidades
    for a in av:
        assert a.ressalva == RESSALVA and RESSALVA in a.texto
        d = a.as_dict()
        assert not any(k in d for k in ("stop", "alvo", "prob", "probabilidade", "lado", "rr"))
        assert "%" not in a.titulo and "acerto" not in a.texto.lower()
        json.dumps(d)


def test_estado_reconstruido_dos_registros_nao_repete():
    e1 = Estado()
    av = avaliar(_mapa(T0 + 10 * H), 80_000.0, e1)
    e2 = Estado.de_registros([a.as_dict() for a in av])
    assert e2.enviados == e1.enviados
    assert avaliar(_mapa(T0 + 11 * H), 80_000.0, e2) == []


# ------------------------------------------------------------------ o serviço
class _Telegram:
    def __init__(self, ativo=True):
        self.ativo = ativo
        self.enviados = []

    def info(self, texto):
        self.enviados.append(texto)
        return True


def _servico(tmp_path, candles, preco, telegram=None, relogio_ms=None):
    chamadas = []

    def obter_candles(desde):
        chamadas.append(desde)
        return [c for c in candles if c[0] >= desde]

    s = AvisosService(obter_candles, lambda: preco, telegram=telegram, caminho=str(tmp_path / "avisos.jsonl"),
                      relogio=lambda: (relogio_ms or 0) / 1000)
    s.chamadas = chamadas
    return s


def test_ciclo_grava_jsonl_envia_telegram_e_nao_repete(tmp_path):
    c = candles_base(12)                                 # composto, ontem e sessões em 80.000
    tg = _Telegram()
    agora = T0 + 11 * DIA_MS + 8 * H + 60_000            # 08:01 UTC: mapa da Europa + proximidade do POC composto
    s = _servico(tmp_path, c, 80_000.0, tg, agora)
    av = s.ciclo(agora)
    tipos = sorted(a.tipo for a in av)
    assert tipos[0] == "mapa" and "proximidade" in tipos
    assert any(a.chave == "composto.poc" for a in av)
    linhas = [json.loads(x) for x in open(s.caminho, encoding="utf-8")]
    assert [x["id"] for x in linhas] == [a.id for a in av] and all(x["ressalva"] == RESSALVA for x in linhas)
    assert len(tg.enviados) == len(av) and RESSALVA in tg.enviados[0]
    assert s.ciclo(agora + 60_000) == [] and s.ciclos == 2
    assert s.ultimos(10)[0]["id"] == av[-1].id, "do mais novo para o mais antigo"
    assert s.status()["telegram"] is True and s.status()["ativo"] is False


def test_telegram_inativo_nao_envia_mas_grava(tmp_path):
    tg = _Telegram(ativo=False)
    agora = T0 + 11 * DIA_MS + 8 * H + 60_000
    s = _servico(tmp_path, candles_base(12), 80_000.0, tg, agora)
    av = s.ciclo(agora)
    assert av and tg.enviados == [] and os.path.exists(s.caminho)


def test_candles_sao_buscados_de_forma_incremental(tmp_path):
    c = candles_base(12)
    agora = T0 + 11 * DIA_MS + 3 * H
    s = _servico(tmp_path, c, None, None, agora)
    s.ciclo(agora)
    s.ciclo(agora + 60_000)
    assert s.chamadas[0] < T0 and s.chamadas[1] == s.candles[-1][0], "2º ciclo pede só a partir do último candle guardado"
    assert s.ultimo_mapa.preco == 80_000.0, "sem preço ao vivo, vale o último fechamento"


def test_ao_iniciar_relê_o_arquivo_e_nao_repete_o_que_ja_saiu(tmp_path):
    agora = T0 + 11 * DIA_MS + 8 * H + 60_000
    s1 = _servico(tmp_path, candles_base(12), 80_000.0, None, agora)
    n = len(s1.ciclo(agora))
    assert n > 0
    s2 = _servico(tmp_path, candles_base(12), 80_000.0, None, agora)
    s2.estado = Estado.de_registros(s2.ultimos(500))     # o que iniciar() faz antes de subir a thread
    assert s2.ciclo(agora + 60_000) == []


def test_mapa_atual_funciona_com_a_thread_desligada(tmp_path):
    agora = T0 + 11 * DIA_MS + 3 * H
    s = _servico(tmp_path, candles_base(12), 80_000.0, None, agora)
    m = s.mapa_atual()
    assert m.dias_no_composto == 10 and s.ciclos == 0 and not s.ativo


def test_rotas_devolvem_json_puro(tmp_path, monkeypatch):
    import api.routes.avisos_routes as ar
    agora = T0 + 11 * DIA_MS + 8 * H + 60_000
    s = _servico(tmp_path, candles_base(12), 80_000.0, None, agora)
    monkeypatch.setattr(ar, "get_avisos_service", lambda: s)
    r = ar.mapa()
    json.dumps(r)
    assert r["ressalva"] == RESSALVA and r["servico"]["ativo"] is False and len(r["niveis"]) > 5
    s.ciclo(agora)
    u = ar.ultimos(10)
    json.dumps(u)
    assert u["avisos"] and u["avisos"][0]["tipo"] in ("mapa", "proximidade")


def test_get_avisos_service_usa_o_conector_publico(monkeypatch):
    import services.avisos_service as sv
    con = SimpleNamespace(obter_ohlcv_historico=lambda par, tf, desde: [], obter_preco_atual=lambda par: 1.0)
    monkeypatch.setattr("services.bot_manager.get_manager",
                        lambda: SimpleNamespace(servicos={"connectors": {"simulador": con}, "telegram": _Telegram(False)}))
    monkeypatch.setattr(sv, "_service", None)
    s = sv.get_avisos_service()
    assert s is sv.get_avisos_service() and s.obter_preco() == 1.0 and s.obter_candles(0) == []
    monkeypatch.setattr(sv, "_service", None)
