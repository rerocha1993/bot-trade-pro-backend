"""
O log não pode derrubar o que o robô fez.

Um log que não cabia na coluna fez uma realização parcial sair TRÊS vezes na corretora: a ordem foi enviada, o
INSERT do log estourou, o rollback apagou o registro da fatia realizada, e o ciclo seguinte achou que ela ainda
estava pendente. Estes testes prendem as duas pontas: a sessão do log é separada, e os valores escritos cabem.
"""
import re

import pytest

from core.bot_executor import BotExecutor


class _Sessao:
    """Sessão que aceita tudo e anota o que foi chamado."""
    def __init__(self, falhar=False):
        self.falhar, self.commits, self.rollbacks, self.fechada = falhar, 0, 0, False

    def add(self, *a):
        if self.falhar:
            raise RuntimeError("String or binary data would be truncated")

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.fechada = True


def _executor(monkeypatch, sessao_log):
    ex = BotExecutor.__new__(BotExecutor)
    ex.bot = type("B", (), {"id": 1})()
    ex.db = _Sessao()
    monkeypatch.setattr("core.bot_executor.SessionLocal", lambda: sessao_log)
    return ex


def test_log_que_falha_nao_desfaz_o_estado_do_robo(monkeypatch):
    log = _Sessao(falhar=True)
    ex = _executor(monkeypatch, log)
    ex._log(acao="parcial", tipo_operacao="saida_parcial", preco=1.0)
    assert ex.db.commits == 1, "o que o robô fez tem que ser gravado antes do log"
    assert ex.db.rollbacks == 0, "a falha do log não pode desfazer a realização parcial"
    assert log.rollbacks == 1 and log.fechada, "quem falha é a sessão do log, e ela é fechada"


def test_log_normal_grava_nas_duas_sessoes(monkeypatch):
    log = _Sessao()
    ex = _executor(monkeypatch, log)
    ex._log(acao="parcial", tipo_operacao="saida_parcial", preco=1.0)
    assert ex.db.commits == 1 and log.commits == 1
    assert ex.db.rollbacks == 0 and log.rollbacks == 0


def test_valores_gravados_cabem_nas_colunas():
    """Todo acao=/tipo_operacao= escrito no executor precisa caber na largura que o setup_db garante."""
    from scripts.setup_db import LARGURAS_MINIMAS

    minimo = {(t, c): n for t, c, n in LARGURAS_MINIMAS}
    fonte = open("core/bot_executor.py", encoding="utf-8").read()
    achou = False
    for campo in ("acao", "tipo_operacao"):
        largura = minimo[("LogExecucaoBot", campo)]
        for valor in re.findall(rf'{campo}="([a-z_]+)"', fonte):
            achou = True
            assert len(valor) <= largura, f"{campo}={valor!r} ({len(valor)}) não cabe em varchar({largura})"
    assert achou, "nenhum valor encontrado: o teste precisa ser revisto"


@pytest.mark.parametrize("tabela,coluna", [("LogExecucaoBot", "tipo_operacao"), ("LogExecucaoBot", "acao")])
def test_colunas_do_incidente_estao_na_lista(tabela, coluna):
    from scripts.setup_db import LARGURAS_MINIMAS

    assert any(t == tabela and c == coluna for t, c, _ in LARGURAS_MINIMAS)
