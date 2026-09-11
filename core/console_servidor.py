# core/console_servidor.py
"""
O servidor roda numa janela de console do Windows (rodar.bat) a noite toda. Duas coisas protegem os robôs dela:

1. MODO DE EDIÇÃO RÁPIDA DESLIGADO. Com ele ligado, um clique na janela começa uma seleção de texto e o console
   PAUSA a saída até alguém apertar Esc/Enter. Toda thread que tentar escrever um log fica bloqueada nesse
   meio-tempo — os robôs param no meio do ciclo, com ordem aberta, sem ninguém perceber. Só esta janela é
   alterada (SetConsoleMode no próprio console do processo); a configuração do Windows não é tocada.

2. LOG EM ARQUIVO. logs/servidor.log, rotativo (5 MB x 5), para o histórico não depender da rolagem da janela.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
STD_INPUT_HANDLE = -10


def desligar_edicao_rapida(kernel32=None) -> bool:
    """Tira o modo de edição rápida do console DESTE processo. Devolve True se mudou algo."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        if kernel32 is None:
            kernel32 = ctypes.windll.kernel32
        h = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        modo = wintypes.DWORD()
        if not kernel32.GetConsoleMode(h, ctypes.pointer(modo)):
            return False             # sem console (serviço, redirecionado): nada a fazer
        if not modo.value & ENABLE_QUICK_EDIT_MODE:
            return False
        novo = (modo.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
        return bool(kernel32.SetConsoleMode(h, novo))
    except Exception:
        return False


def log_em_arquivo(pasta: str = "logs", nome: str = "servidor.log", max_bytes: int = 5 * 1024 * 1024,
                   copias: int = 5) -> str:
    """Acrescenta um arquivo rotativo ao logger raiz (uma vez só). Devolve o caminho."""
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.abspath(os.path.join(pasta, nome))
    raiz = logging.getLogger()
    for h in raiz.handlers:
        if isinstance(h, RotatingFileHandler) and os.path.abspath(h.baseFilename) == caminho:
            return caminho
    h = RotatingFileHandler(caminho, maxBytes=max_bytes, backupCount=copias, encoding="utf-8", delay=True)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"))
    raiz.addHandler(h)
    return caminho


def preparar_console_servidor(logger: logging.Logger = None) -> None:
    caminho = log_em_arquivo(os.getenv("LOG_PASTA", "logs"))
    mudou = desligar_edicao_rapida() if sys.stdin is not None and sys.stdin.isatty() else False
    if logger:
        logger.info("log também em %s%s", caminho,
                    "; modo de edição rápida desligado nesta janela (um clique não pausa mais os robôs)" if mudou else "")
