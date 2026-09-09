# api/database.py
"""
Conexão com o banco.

A string vem do ambiente, com os valores atuais como padrão para não quebrar quem já roda local:

    DATABASE_URL   = URL completa do SQLAlchemy (tem prioridade; ignorada se não parecer uma URL)
    DB_DRIVER      = ODBC Driver 17 for SQL Server
    DB_SERVER      = (localdb)\\MSSQLLocalDB
    DB_NAME        = dbo_trading_bot
    DB_TRUSTED     = yes            (autenticação do Windows; com 'no' usa DB_USER/DB_PASSWORD)
    DB_USER        / DB_PASSWORD
    DB_ENCRYPT     = no             (essencial para LocalDB)
    DB_TIMEOUT     = 30             segundos de espera no logon
    DB_TENTATIVAS  = 6              tentativas de conexão na subida

O LocalDB desliga sozinho por ociosidade e leva alguns segundos para subir. A primeira conexão depois de um tempo
parado falha com "o tempo limite do logon expirou", e antes isso derrubava a subida inteira do sistema. Agora
`aguardar_banco()` acorda a instância e tenta de novo com espera crescente.
"""
import logging
import os
import subprocess
import threading
import time
import urllib.parse as urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
logger = logging.getLogger(__name__)

Base = declarative_base()


def _servidor() -> str:
    return os.getenv("DB_SERVER", "(localdb)\\MSSQLLocalDB")


def _url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    # só aceita uma URL de verdade: um valor solto (ex.: o próprio nome da variável) é ignorado
    if url and "://" in url:
        return url
    partes = [
        f"DRIVER={{{os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')}}}",
        f"SERVER={_servidor()}",
        f"DATABASE={os.getenv('DB_NAME', 'dbo_trading_bot')}",
    ]
    if (os.getenv("DB_TRUSTED", "yes") or "yes").lower() in ("yes", "true", "1"):
        partes.append("Trusted_Connection=yes")
    else:
        partes.append(f"UID={os.getenv('DB_USER', '')}")
        partes.append(f"PWD={os.getenv('DB_PASSWORD', '')}")
    partes.append(f"Encrypt={os.getenv('DB_ENCRYPT', 'no')}")
    return f"mssql+pyodbc:///?odbc_connect={urlparse.quote_plus(';'.join(partes) + ';')}"


def _instancia_localdb() -> str:
    """Nome da instância se o servidor for LocalDB, senão string vazia."""
    srv = _servidor()
    if "(localdb)" not in srv.lower():
        return ""
    return srv.split("\\")[-1] if "\\" in srv else "MSSQLLocalDB"


# só encerra processos do LocalDB (pasta LocalDB\Binn). Um SQL Server de verdade jamais é tocado.
_PS_MATAR_ORFAO = (
    "Get-CimInstance Win32_Process -Filter \"Name='sqlservr.exe'\" | "
    r"Where-Object { $_.ExecutablePath -like '*\LocalDB\Binn\*' } | "
    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
)


def _matar_localdb_orfao() -> bool:
    """
    Quando um sqlservr.exe do LocalDB fica órfão, a instância aparece como parada mas o 'start' falha com
    "SQL Server process failed to start". Encerrar o processo pendurado é a saída documentada.
    """
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", _PS_MATAR_ORFAO],
                       capture_output=True, text=True, timeout=60)
        logger.warning("processo órfão do LocalDB encerrado")
        return True
    except Exception as e:
        logger.debug("não foi possível encerrar o processo órfão: %s", e)
        return False


def _start_localdb(inst: str):
    return subprocess.run(["sqllocaldb", "start", inst], capture_output=True, text=True, timeout=90)


def _rodando(inst: str) -> bool:
    """
    O 'sqllocaldb start' devolve sucesso mesmo quando a instância NÃO subiu (acontece com um sqlservr órfão
    pendurado). Por isso o estado é conferido de verdade, em vez de confiar no código de retorno.
    """
    try:
        r = subprocess.run(["sqllocaldb", "info", inst], capture_output=True, text=True, timeout=30)
        for linha in (r.stdout or "").splitlines():
            if linha.strip().lower().startswith("state"):
                return "running" in linha.split(":", 1)[-1].strip().lower()
    except Exception:
        pass
    return False


def acordar_localdb() -> bool:
    """LocalDB dorme por ociosidade. Manda iniciar e CONFERE se subiu; se não subiu, limpa o processo órfão."""
    inst = _instancia_localdb()
    if not inst:
        return False
    try:
        _start_localdb(inst)
        if _rodando(inst):
            logger.info("LocalDB %s pronto", inst)
            return True
        logger.warning("LocalDB %s continua parado depois do start: limpando processo órfão", inst)
        _matar_localdb_orfao()
        time.sleep(2)
        _start_localdb(inst)
        if _rodando(inst):
            logger.info("LocalDB %s pronto (depois de limpar o processo órfão)", inst)
            return True
        logger.error("LocalDB %s não subiu nem depois da limpeza", inst)
    except FileNotFoundError:
        logger.debug("sqllocaldb não encontrado no PATH")
    except Exception as e:
        logger.debug("não foi possível acordar o LocalDB: %s", e)
    return False


# timeout de logon vai pelo pyodbc (SQL_ATTR_LOGIN_TIMEOUT), não como atributo da string ODBC:
# 'Connection Timeout' é palavra do .NET e o driver ODBC reclama dela no diagnóstico.
_TIMEOUT = int(os.getenv("DB_TIMEOUT", "30"))
engine = create_engine(_url(), pool_pre_ping=True, pool_recycle=1800, future=True,
                       connect_args={"timeout": _TIMEOUT})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def aguardar_banco(tentativas: int = None, espera_inicial: float = 1.0) -> bool:
    """
    Espera o banco responder, acordando o LocalDB antes. Devolve True se conectou.
    Não levanta: quem chama decide o que fazer, e derrubar a subida por causa disso é pior que avisar.
    """
    tentativas = int(tentativas or os.getenv("DB_TENTATIVAS", "6"))
    acordar_localdb()
    espera = espera_inicial
    ultimo = None
    for n in range(1, tentativas + 1):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            if n > 1:
                logger.info("banco respondeu na tentativa %d", n)
            return True
        except Exception as e:
            ultimo = str(e).splitlines()[0][:180]
            if n < tentativas:
                logger.warning("banco não respondeu (tentativa %d/%d), nova tentativa em %.0fs: %s",
                               n, tentativas, espera, ultimo)
                time.sleep(espera)
                espera = min(espera * 2, 10)
                acordar_localdb()
    logger.error("banco indisponível depois de %d tentativas: %s", tentativas, ultimo)
    return False


_keepalive_thread = None
_keepalive_parar = threading.Event()


def manter_banco_acordado(intervalo_s: int = None):
    """
    O LocalDB desliga por ociosidade (nesta máquina, em poucos minutos). Com os robôs rodando a noite toda,
    um período sem escrita bastaria para ele dormir e a próxima consulta falhar. Um ping leve mantém de pé.
    """
    global _keepalive_thread
    if _keepalive_thread and _keepalive_thread.is_alive():
        return
    intervalo = int(intervalo_s or os.getenv("DB_KEEPALIVE_S", "120"))
    if intervalo <= 0:
        return

    def loop():
        while not _keepalive_parar.wait(intervalo):
            try:
                with engine.connect() as c:
                    c.execute(text("SELECT 1"))
            except Exception as e:
                logger.warning("keepalive do banco falhou, tentando acordar: %s", str(e).splitlines()[0][:140])
                aguardar_banco(tentativas=3)

    _keepalive_parar.clear()
    _keepalive_thread = threading.Thread(target=loop, name="db-keepalive", daemon=True)
    _keepalive_thread.start()
    logger.info("keepalive do banco a cada %ds", intervalo)


def parar_keepalive():
    _keepalive_parar.set()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
