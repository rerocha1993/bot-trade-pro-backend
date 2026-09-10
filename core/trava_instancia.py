# core/trava_instancia.py
"""
TRAVA DE INSTÂNCIA ÚNICA: impede que dois servidores subam os mesmos robôs.

O `uvicorn` roda o startup da aplicação ANTES de reservar a porta. Numa segunda janela aberta por engano,
isso significa que os quatro robôs sobem, falam com a corretora, e só então a porta falha com Errno 10048 e
tudo é desmontado. Por um instante existem dois executores por subconta — e a Bybit tem UMA posição por
símbolo por conta, então dois executores disputando a mesma posição podem mandar ordem em cima de ordem.

A porta era só o sintoma. O perigo de verdade é o segundo BotManager, e ele existe mesmo quando a porta
está livre (basta subir a segunda janela em 8001). Por isso a trava é um arquivo com lock do sistema
operacional, e não uma checagem de porta: ela vale para qualquer porta.

Quando não dá para travar, os robôs NÃO sobem — mas a API e o painel sobem, para você enxergar o problema.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

PADRAO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".robos.lock")


class TravaInstancia:
    """Lock exclusivo de arquivo. `adquirir()` devolve False quando outro processo já tem os robôs."""

    def __init__(self, caminho: str = PADRAO):
        self.caminho = caminho
        self._fh = None

    def _travar(self) -> bool:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def dono_anterior(self) -> Optional[str]:
        """
        PID de quem está com a trava, só para a mensagem de erro fazer sentido.

        Fica num arquivo À PARTE porque no Windows o `msvcrt.locking` bloqueia até a LEITURA do byte
        travado: ler o PID de dentro do próprio arquivo da trava devolvia sempre vazio.
        """
        try:
            with open(self.caminho + ".pid", "r", encoding="utf-8") as f:
                return (f.read() or "").strip() or None
        except Exception:
            return None

    def adquirir(self) -> bool:
        if self._fh is not None:
            return True
        anterior = self.dono_anterior()
        try:
            # 'r+' se existir, senão cria: abrir com 'w' apagaria o PID do dono antes de saber se dá para travar
            self._fh = open(self.caminho, "r+" if os.path.exists(self.caminho) else "w+", encoding="utf-8")
        except Exception as e:
            logger.warning("não foi possível abrir a trava de instância (%s): seguindo sem ela", e)
            return True          # a trava é uma proteção, não um motivo para o sistema não subir
        self._fh.seek(0)
        if not self._travar():
            self._fh.close()
            self._fh = None
            logger.error(
                "JÁ HÁ UM SERVIDOR COM OS ROBÔS RODANDO%s. Esta instância sobe só a API e o painel: dois "
                "executores na mesma subconta disputariam a MESMA posição na Bybit e poderiam mandar ordem "
                "em cima de ordem. Feche o outro servidor antes de subir este.",
                f" (PID {anterior})" if anterior else "")
            return False
        try:
            with open(self.caminho + ".pid", "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
        except Exception as e:
            logger.debug("não foi possível registrar o PID da trava: %s", e)
        return True

    def liberar(self):
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            logger.debug("falha ao liberar a trava: %s", e)
        finally:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None

    def __enter__(self):
        self.adquirir()
        return self

    def __exit__(self, *_):
        self.liberar()
