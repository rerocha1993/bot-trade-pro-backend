# # --- ARQUIVO 9: core/bot_executor.py ---
# import time
# from core.indicador_loader import IndicadorLoader
# from core.macro_event_checker import evento_importante_agora
# ...
# # (restante mantido)

#     def executar(self):
#         while self.bot.ativo_bot:
#             try:
#                 if evento_importante_agora(pais="united states", relevancia="alta"):
#                     print(f"[{self.bot.nome}] Evento econômico crítico detectado. Aguardando...")
#                     time.sleep(300)
#                     continue
#                 ...  # restante do loop

import requests
try:
    from bs4 import BeautifulSoup
except ImportError:  # opcional
    BeautifulSoup = None
from datetime import datetime, timedelta
import os

INVESTING_URL = "https://www.investing.com/economic-calendar/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

IMPACTOS = {
    "alta": "High",
    "média": "Medium",
    "baixa": "Low"
}

PAISES = {
    "united states": "United States",
    "brazil": "Brazil",
    "eurozone": "Euro Zone"
}

_DERIV = None


def evento_importante_agora(pais="united states", relevancia="alta", usar_api=False, minutos=30):
    """Fonte principal: calendário Forex Factory (gratuito). Fallbacks: TradingEconomics (chave) e scraping."""
    global _DERIV
    try:
        if _DERIV is None:
            from core.dados_derivativos import DadosDerivativos
            _DERIV = DadosDerivativos()
        ev = _DERIV.evento_proximo(minutos, paises=("USD",), impactos=("High",) if relevancia == "alta" else ("High", "Medium"))
        if ev is not None or _DERIV.calendario():
            return ev is not None
    except Exception:
        pass
    if usar_api:
        return evento_via_api(pais=pais, relevancia=relevancia)
    return evento_via_scraping(pais=pais, relevancia=relevancia)

def evento_via_scraping(pais="united states", relevancia="alta"):
    if BeautifulSoup is None:
        return False
    try:
        response = requests.get(INVESTING_URL, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        linhas = soup.select("tr.js-event-item")
        agora = datetime.utcnow()

        for linha in linhas:
            pais_elem = linha.select_one(".flagCur.noCur")
            impacto_elem = linha.select_one(".sentiment")
            hora_elem = linha.select_one(".first.left.time")

            if not pais_elem or not impacto_elem or not hora_elem:
                continue

            pais_nome = pais_elem.get("title", "").strip()
            impacto = impacto_elem.get("title", "").strip()
            hora_str = hora_elem.text.strip()

            if pais_nome != PAISES.get(pais.lower()):
                continue

            if impacto != IMPACTOS.get(relevancia.lower()):
                continue

            hora_evento = datetime.strptime(hora_str, "%H:%M")
            hora_evento = agora.replace(hour=hora_evento.hour, minute=hora_evento.minute, second=0, microsecond=0)

            if abs((hora_evento - agora).total_seconds()) <= 300:
                return True

        return False
    except Exception as e:
        print(f"[macro_event_checker] Erro no scraping: {e}")
        return False

def evento_via_api(pais="united states", relevancia="alta"):
    try:
        API_KEY = os.getenv("TRADING_ECONOMICS_KEY")  # Defina a chave como variável de ambiente
        if not API_KEY:
            print("[macro_event_checker] API KEY não definida para TradingEconomics.")
            return False

        url = f"https://api.tradingeconomics.com/calendar/country/{pais.replace(' ', '%20')}?c={API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        agora = datetime.utcnow()

        for evento in data:
            if evento.get("Importance") != 3:
                continue

            data_evento = evento.get("Date")
            if not data_evento:
                continue

            data_evento = datetime.strptime(data_evento[:16], "%Y-%m-%dT%H:%M")
            if abs((data_evento - agora).total_seconds()) <= 300:
                return True

        return False
    except Exception as e:
        print(f"[macro_event_checker] Erro na API TradingEconomics: {e}")
        return False
