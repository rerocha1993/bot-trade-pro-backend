import threading
from core.bot_executor import BotExecutor

class BotManager:
    def __init__(self, bots_configs, db):
        self.bots_configs = bots_configs  # Lista de dicts, cada um com a config de um bot
        self.db = db
        self.executores = {}  # {nome_do_bot: BotExecutor}
        self.threads = {}     # {nome_do_bot: Thread}

    def start_all(self):
        for config in self.bots_configs:
            self.start_bot(config.nome, config)

    def start_bot(self, nome, config=None):
        # Se já existe e está rodando, ignora
        if nome in self.executores and self.threads[nome].is_alive():
            print(f"[BotManager] Bot {nome} já está rodando.")
            return False

        # Procura config se não veio na chamada
        if config is None:
            config = next((c for c in self.bots_configs if c['nome'] == nome), None)
            if config is None:
                print(f"[BotManager] Config do bot {nome} não encontrada.")
                return False

        # Instancia o BotExecutor — espera dict com dados do bot!

        executor = BotExecutor(config, self.db)
        thread = threading.Thread(target=executor.executar, daemon=True)
        thread.start()
        self.executores[nome] = executor
        self.threads[nome] = thread
        print(f"[BotManager] Bot {nome} iniciado.")
        return True

    def stop_bot(self, nome):
        if nome in self.executores:
            self.executores[nome].bot.ativo_bot = False  # O loop vai parar no executor
            print(f"[BotManager] Parando bot {nome}...")
            return True
        print(f"[BotManager] Bot {nome} não está rodando.")
        return False

    def stop_all(self):
        for nome in list(self.executores.keys()):
            self.stop_bot(nome)
