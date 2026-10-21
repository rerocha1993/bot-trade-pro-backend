"""
Manda uma mensagem de teste pelo Telegram com o token e o chat do .env (TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID).

    .venv\\Scripts\\python.exe scripts\\testar_telegram.py

Se chegar no celular, os avisos do conselho também chegam (reinicie a API depois de mexer no .env).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from conselho.telegram import TelegramAlertService  # noqa: E402


def main() -> int:
    t = TelegramAlertService()
    if not t.ativo:
        print("Telegram desligado: preencha TELEGRAM_BOT_TOKEN (tem ':' no meio) e TELEGRAM_CHAT_ID (só números) no .env")
        return 1
    ok = t.info("Conselho BTC: teste de aviso. Se você leu isto, os avisos de absorção e de presos vão chegar aqui.")
    print("mensagem enviada" if ok else "o Telegram recusou: confira se você mandou uma mensagem para o seu bot antes")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
