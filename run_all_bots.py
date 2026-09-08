"""Roda todos os bots ativos sem a API (um thread por bot). Ctrl+C para parar."""
import logging
import time

from services.bot_manager import get_manager

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    m = get_manager()
    print("bots iniciados:", m.start_all())
    m.iniciar_manutencao(30)
    try:
        while True:
            time.sleep(30)
            for bid, st in m.status().items():
                print(bid, st.get("nome"), "preco", st.get("preco"), "decisao",
                      (st.get("ultima_decisao") or {}).get("acao"), "pnl_dia", st.get("pnl_dia"))
    except KeyboardInterrupt:
        m.stop_all()
