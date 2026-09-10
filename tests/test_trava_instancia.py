"""
Dois servidores não podem subir os mesmos robôs.

O `uvicorn` roda o startup da aplicação ANTES de reservar a porta. Numa segunda janela aberta por engano, os
quatro robôs sobem, falam com a corretora, e só então a porta falha com Errno 10048 e tudo é desmontado —
aconteceu, e a tela mostrava "bot 4 iniciado ... BotManager iniciou 4 bot(s)" antes do erro. Por um instante
existem dois executores por subconta, e a Bybit tem UMA posição por símbolo por conta: com posição aberta,
os dois disputariam a mesma posição e poderiam mandar ordem em cima de ordem.

A porta era o sintoma. O perigo é o segundo BotManager, e ele existe mesmo com a porta livre (basta subir a
segunda janela em 8001) — por isso a trava é de arquivo, não de porta.
"""
import os

from core.trava_instancia import TravaInstancia


def test_a_segunda_instancia_nao_leva_os_robos(tmp_path):
    caminho = str(tmp_path / "robos.lock")
    primeira = TravaInstancia(caminho)
    segunda = TravaInstancia(caminho)
    try:
        assert primeira.adquirir() is True
        assert segunda.adquirir() is False, "duas instâncias subiriam os mesmos robôs"
    finally:
        primeira.liberar()
        segunda.liberar()


def test_liberar_devolve_a_vez_para_a_proxima(tmp_path):
    caminho = str(tmp_path / "robos.lock")
    primeira = TravaInstancia(caminho)
    assert primeira.adquirir() is True
    primeira.liberar()
    segunda = TravaInstancia(caminho)
    try:
        assert segunda.adquirir() is True, "o servidor legítimo não conseguiu subir depois de um reinício"
    finally:
        segunda.liberar()


def test_o_pid_do_dono_fica_gravado_para_a_mensagem_de_erro(tmp_path):
    caminho = str(tmp_path / "robos.lock")
    dono = TravaInstancia(caminho)
    try:
        dono.adquirir()
        assert TravaInstancia(caminho).dono_anterior() == str(os.getpid())
    finally:
        dono.liberar()


def test_adquirir_duas_vezes_no_mesmo_processo_e_inofensivo(tmp_path):
    caminho = str(tmp_path / "robos.lock")
    t = TravaInstancia(caminho)
    try:
        assert t.adquirir() is True
        assert t.adquirir() is True
    finally:
        t.liberar()


def test_trava_impossivel_nao_impede_o_sistema_de_subir(tmp_path):
    """A trava é uma proteção, não um motivo para o robô não existir: caminho inválido não pode barrar tudo."""
    impossivel = TravaInstancia(str(tmp_path / "nao" / "existe" / "robos.lock"))
    assert impossivel.adquirir() is True
    impossivel.liberar()
