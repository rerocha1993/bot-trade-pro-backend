r"""
Subir um segundo servidor não pode derrubar o banco do primeiro.

O sqlservr do LocalDB é compartilhado por todos os processos do usuário. A rotina que limpa "processo órfão"
matava qualquer sqlservr sob LocalDB\Binn, e ao abrir uma segunda janela do servidor a primeira perdeu a conexão
no meio da operação. A regra agora é simples: se o banco atende, ninguém encosta nele.
"""
import api.database as bd


def _sem_efeito(monkeypatch):
    """Anota o que a rotina tentou fazer, sem executar nada de verdade."""
    feito = {"matou": 0, "start": 0}
    monkeypatch.setattr(bd.subprocess, "run", lambda *a, **k: feito.__setitem__("matou", feito["matou"] + 1))
    monkeypatch.setattr(bd, "_start_localdb", lambda inst: feito.__setitem__("start", feito["start"] + 1))
    return feito


def test_banco_de_pe_nao_e_derrubado(monkeypatch):
    feito = _sem_efeito(monkeypatch)
    monkeypatch.setattr(bd, "_conecta", lambda: True)
    assert bd._matar_localdb_orfao() is False
    assert feito["matou"] == 0, "o banco atende: matar seria arrancar o banco de quem está usando"


def test_so_mata_quando_o_banco_nao_atende(monkeypatch):
    feito = _sem_efeito(monkeypatch)
    monkeypatch.setattr(bd, "_conecta", lambda: False)
    assert bd._matar_localdb_orfao() is True
    assert feito["matou"] == 1


def test_aguardar_nem_encosta_na_instancia_com_banco_de_pe(monkeypatch):
    feito = _sem_efeito(monkeypatch)
    monkeypatch.setattr(bd, "_conecta", lambda: True)
    monkeypatch.setattr(bd, "acordar_localdb", lambda: (_ for _ in ()).throw(AssertionError("não devia acordar")))
    assert bd.aguardar_banco() is True
    assert feito == {"matou": 0, "start": 0}


def test_instancia_que_demora_a_subir_nao_e_morta(monkeypatch):
    """O estado leva segundos para assentar: concluir cedo demais mataria um banco que ia subir sozinho."""
    feito = _sem_efeito(monkeypatch)
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd, "_conecta", lambda: False)
    estados = iter([False, False, True])
    monkeypatch.setattr(bd, "_rodando", lambda inst: next(estados, True))
    monkeypatch.setattr(bd, "_instancia_localdb", lambda: "MSSQLLocalDB")
    assert bd.acordar_localdb() is True
    assert feito["matou"] == 0


def test_instancia_realmente_travada_e_limpa(monkeypatch):
    feito = _sem_efeito(monkeypatch)
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd, "_conecta", lambda: False)
    monkeypatch.setattr(bd, "_rodando", lambda inst: False)
    monkeypatch.setattr(bd, "_instancia_localdb", lambda: "MSSQLLocalDB")
    assert bd.acordar_localdb() is False
    assert feito["matou"] == 1, "aí sim: não atende e não sobe"
