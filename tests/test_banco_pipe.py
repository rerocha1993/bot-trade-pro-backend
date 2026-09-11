r"""
Quando o nome (localdb)\MSSQLLocalDB para de resolver para processos novos com a instância ainda de pé, a conexão
tem que cair no pipe da instância — antes o servidor novo ficava sem banco e não subia os robôs.
"""
import pyodbc
import pytest

import api.database as db

PIPE = "np:\\.\pipe\LOCALDB#8ADE1CFF\tsql\query"


@pytest.fixture
def cenario(monkeypatch):
    monkeypatch.setenv("DB_SERVER", "(localdb)\MSSQLLocalDB")
    monkeypatch.setattr(db, "_alvo_ok", None)
    monkeypatch.setattr(db, "_pipes_localdb", lambda: [PIPE])
    tentativas = []

    def conectar(cs, timeout):
        srv = cs.split("SERVER=")[1].split(";")[0]
        tentativas.append((srv, timeout))
        if "(localdb)" in srv:
            raise pyodbc.OperationalError("HYT00", "Tempo limite de logon expirado")
        return object()

    monkeypatch.setattr(pyodbc, "connect", conectar)
    return tentativas


def test_localdb_de_pe_conecta_pelo_pipe_sem_pagar_o_timeout_do_nome(cenario):
    assert db._nova_conexao() is not None
    assert [s for s, _ in cenario] == [PIPE], "o nome que não resolve só desiste depois do timeout inteiro"
    assert db._alvo_ok == PIPE


def test_pipe_que_morreu_cai_no_nome(monkeypatch, cenario):
    """Instância reiniciada: o pipe antigo sumiu. O nome (que acorda o LocalDB) é a última tentativa."""
    def conectar(cs, timeout):
        srv = cs.split("SERVER=")[1].split(";")[0]
        cenario.append((srv, timeout))
        if srv == PIPE:
            raise pyodbc.OperationalError("08001", "pipe fechado")
        return object()

    monkeypatch.setattr(pyodbc, "connect", conectar)
    db._nova_conexao()
    assert [s for s, _ in cenario] == [PIPE, "(localdb)\MSSQLLocalDB"]
    assert db._alvo_ok == "(localdb)\MSSQLLocalDB"


def test_sem_pipe_listado_vai_pelo_nome(monkeypatch, cenario):
    monkeypatch.setattr(db, "_pipes_localdb", lambda: [])
    monkeypatch.setattr(pyodbc, "connect", lambda cs, timeout: cenario.append(cs) or object())
    db._nova_conexao()
    assert len(cenario) == 1 and "(localdb)" in cenario[0]


def test_pipe_tem_timeout_curto(cenario):
    db._nova_conexao()
    assert dict(cenario)[PIPE] == db._TIMEOUT_PIPE


def test_servidor_que_nao_e_localdb_nao_procura_pipe(monkeypatch):
    monkeypatch.setenv("DB_SERVER", "meuservidor.local")
    monkeypatch.setattr(db, "_alvo_ok", None)
    monkeypatch.setattr(db, "_pipes_localdb", lambda: [PIPE])
    assert db._alvos() == ["meuservidor.local"]


def test_nada_atende_levanta_o_erro_do_driver(monkeypatch):
    monkeypatch.setenv("DB_SERVER", "(localdb)\MSSQLLocalDB")
    monkeypatch.setattr(db, "_alvo_ok", None)
    monkeypatch.setattr(db, "_pipes_localdb", lambda: [])

    def falha(cs, timeout):
        raise pyodbc.OperationalError("HYT00", "timeout")

    monkeypatch.setattr(pyodbc, "connect", falha)
    with pytest.raises(pyodbc.Error):
        db._nova_conexao()
