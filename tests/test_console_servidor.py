"""
Um clique na janela do rodar.bat pausava a saída do console e, com ela, toda thread que escrevia log: os robôs
paravam no meio do ciclo. O modo de edição rápida sai desta janela, e o log vai também para arquivo.
"""
import logging
import os

import pytest

import core.console_servidor as cs


class _Kernel32:
    def __init__(self, modo, tem_console=True):
        self.modo, self.tem_console, self.definido = modo, tem_console, None

    def GetStdHandle(self, n):
        return 7

    def GetConsoleMode(self, h, ponteiro):
        if not self.tem_console:
            return 0
        ponteiro.contents.value = self.modo
        return 1

    def SetConsoleMode(self, h, modo):
        self.definido = modo
        return 1


@pytest.mark.skipif(os.name != "nt", reason="console do Windows")
def test_tira_so_a_edicao_rapida_e_mantem_o_resto():
    k = _Kernel32(modo=0x01F7)               # padrão do conhost com edição rápida ligada
    assert cs.desligar_edicao_rapida(k) is True
    assert not k.definido & cs.ENABLE_QUICK_EDIT_MODE
    assert k.definido & cs.ENABLE_EXTENDED_FLAGS, "sem EXTENDED_FLAGS o Windows ignora a mudança"
    assert k.definido & 0x0001 and k.definido & 0x0004, "os outros modos (processed input, echo) ficam"


@pytest.mark.skipif(os.name != "nt", reason="console do Windows")
def test_ja_desligado_ou_sem_console_nao_mexe():
    k = _Kernel32(modo=0x0087)
    assert cs.desligar_edicao_rapida(k) is False and k.definido is None
    k2 = _Kernel32(modo=0x01F7, tem_console=False)
    assert cs.desligar_edicao_rapida(k2) is False and k2.definido is None


def test_log_em_arquivo_rotativo_uma_vez_so(tmp_path):
    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    try:
        c1 = cs.log_em_arquivo(str(tmp_path))
        c2 = cs.log_em_arquivo(str(tmp_path))
        novos = [h for h in raiz.handlers if h not in antes]
        assert c1 == c2 and len(novos) == 1
        raiz.setLevel(logging.INFO)
        logging.getLogger("teste").warning("ciclo do robô")
        novos[0].flush()
        assert "ciclo do robô" in open(c1, encoding="utf-8").read()
    finally:
        for h in list(raiz.handlers):
            if h not in antes:
                raiz.removeHandler(h)
                h.close()
