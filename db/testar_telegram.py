import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pathlib import Path
from dotenv import load_dotenv

# ✅ Carrega variáveis do .env automaticamente
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from services.telegram_alert_service import TelegramAlertService

if __name__ == "__main__":
    try:
        telegram = TelegramAlertService()
        telegram.enviar_alerta("🚀 *Alerta de Teste:* Bot está funcionando corretamente!")
        print("✅ Alerta enviado com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao enviar alerta: {e}")
