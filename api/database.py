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

E quando o nome `(localdb)\\...` deixa de resolver com a instância ainda de pé, a conexão cai no pipe dela
(`_pipes_localdb`), em vez de o servidor novo não subir.
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


def _url_explicita() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    # só aceita uma URL de verdade: um valor solto (ex.: o próprio nome da variável) é ignorado
    return url if url and "://" in url else ""


def _odbc(servidor: str) -> str:
    partes = [
        f"DRIVER={{{os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')}}}",
        f"SERVER={servidor}",
        f"DATABASE={os.getenv('DB_NAME', 'dbo_trading_bot')}",
    ]
    if (os.getenv("DB_TRUSTED", "yes") or "yes").lower() in ("yes", "true", "1"):
        partes.append("Trusted_Connection=yes")
    else:
        partes.append(f"UID={os.getenv('DB_USER', '')}")
        partes.append(f"PWD={os.getenv('DB_PASSWORD', '')}")
    partes.append(f"Encrypt={os.getenv('DB_ENCRYPT', 'no')}")
    return ";".join(partes) + ";"


def _url() -> str:
    return _url_explicita() or f"mssql+pyodbc:///?odbc_connect={urlparse.quote_plus(_odbc(_servidor()))}"


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


def _conecta() -> bool:
    """A única prova que vale: o banco atende ou não atende."""
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _matar_localdb_orfao() -> bool:
    """
    Encerra o sqlservr do LocalDB quando ele fica pendurado: a instância aparece como parada e o 'start' falha
    com "SQL Server process failed to start".

    DESLIGADO POR PADRÃO. Ligue com DB_LIMPAR_ORFAO=1, ciente de que pode derrubar robôs em operação.

    ANTES DE MATAR, TENTA CONECTAR. Um sqlservr do LocalDB é compartilhado por todos os processos deste usuário:
    se o banco atende, ele não está órfão, está EM USO — e derrubá-lo arranca o banco de baixo de quem já estava
    rodando. Foi o que aconteceu ao abrir uma segunda janela do servidor: a primeira perdeu a conexão no meio da
    operação ("o pipe está sendo fechado").
    """
    if _conecta():
        logger.info("o LocalDB atende: não há processo órfão para encerrar")
        return False
    # Não dá para distinguir com segurança um processo órfão de um banco EM USO: já vimos o `sqllocaldb info`
    # dizer "Stopped" e o `start` falhar enquanto o sqlservr seguia servindo os robôs em execução — só conexões
    # NOVAS falhavam. Matar ali arranca o banco de baixo de uma operação em andamento. Por isso é opt-in.
    if (os.getenv("DB_LIMPAR_ORFAO", "0") or "0").lower() not in ("1", "true", "yes"):
        logger.error(
            "O LocalDB não aceita conexões novas e a instância não sobe. Pode haver um sqlservr pendurado — ou um "
            "que ainda esteja servindo robôs em execução. NÃO vou encerrar processo nenhum por conta própria. "
            "Feche o servidor, rode 'sqllocaldb stop MSSQLLocalDB -k' e depois 'sqllocaldb start MSSQLLocalDB'. "
            "Para autorizar a limpeza automática, defina DB_LIMPAR_ORFAO=1.")
        return False
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
        # o estado leva alguns segundos para assentar; concluir cedo demais leva a matar um banco que ia subir
        for _ in range(6):
            if _rodando(inst) or _conecta():
                logger.info("LocalDB %s pronto", inst)
                return True
            time.sleep(1)
        logger.warning("LocalDB %s continua parado depois do start: limpando processo órfão", inst)
        if not _matar_localdb_orfao():
            return _conecta()        # não era órfão: ou o banco atende, ou o problema é outro
        time.sleep(2)
        _start_localdb(inst)
        if _rodando(inst) or _conecta():
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
_TIMEOUT_PIPE = 5


def _pipes_localdb() -> list:
    r"""
    Pipes das instâncias LocalDB de pé nesta máquina (np:\\.\pipe\LOCALDB#XXXX\tsql\query).

    Já aconteceu de o `(localdb)\MSSQLLocalDB` parar de resolver para processos NOVOS — o `sqllocaldb info` diz
    "Stopped", o `start` falha — enquanto o sqlservr segue de pé servindo quem já estava conectado. Nesse estado
    o pipe continua listado e atende; o nome é que não chega nele.
    """
    if os.name != "nt":
        return []
    try:
        nomes = os.listdir("\\\\.\\pipe\\")
    except OSError:
        return []
    return ["np:\\\\.\\pipe\\" + n for n in sorted(nomes) if n.upper().startswith("LOCALDB#")]


_alvo_ok = None                 # servidor que conectou por último: é tentado primeiro
_trava_alvo = threading.Lock()


def _alvos() -> list:
    """
    Ordem de tentativa: o último que funcionou; se for LocalDB, os pipes de pé; por fim o nome configurado.

    O pipe vem antes do nome porque, com a instância de pé, os dois levam ao mesmo lugar — e quando o nome não
    resolve ele só desiste depois do timeout inteiro de logon (35 s medidos). Sem pipe listado (instância
    dormindo por ociosidade) sobra o nome, que é quem acorda o LocalDB.
    """
    pipes = _pipes_localdb() if _instancia_localdb() else []
    candidatos = [_alvo_ok] + pipes + [_servidor()]
    vistos, out = set(), []
    for c in candidatos:
        if c and c not in vistos:
            vistos.add(c)
            out.append(c)
    return out


def _nova_conexao():
    """Conexão DBAPI para o pool: o nome configurado, ou o pipe da instância quando o nome não resolve."""
    global _alvo_ok
    import pyodbc
    ultimo = None
    for srv in _alvos():
        try:
            con = pyodbc.connect(_odbc(srv), timeout=_TIMEOUT_PIPE if srv.startswith("np:") else _TIMEOUT)
        except pyodbc.Error as e:
            ultimo = e
            continue
        with _trava_alvo:
            if srv != _alvo_ok:
                logger.info("banco conectado por %s", srv)
                _alvo_ok = srv
        return con
    raise ultimo or RuntimeError("nenhum servidor de banco para tentar")


if _url_explicita():
    engine = create_engine(_url_explicita(), pool_pre_ping=True, pool_recycle=1800, future=True,
                           connect_args={"timeout": _TIMEOUT})
else:
    engine = create_engine("mssql+pyodbc://", creator=_nova_conexao, pool_pre_ping=True, pool_recycle=1800,
                           future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def aguardar_banco(tentativas: int = None, espera_inicial: float = 1.0) -> bool:
    """
    Espera o banco responder, acordando o LocalDB antes. Devolve True se conectou.
    Não levanta: quem chama decide o que fazer, e derrubar a subida por causa disso é pior que avisar.
    """
    tentativas = int(tentativas or os.getenv("DB_TENTATIVAS", "6"))
    if _conecta():
        return True              # banco de pé: não encosta na instância (e nunca chega perto do matar órfão)
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
