import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.telegram_alert_service import TelegramAlertService  # noqa: E402

if __name__ == "__main__":
    t = TelegramAlertService()
    print("ativo:", t.ativo, "| enviado:", t.info("Bot Trade Pro: alerta de teste"))
