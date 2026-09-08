"""Teste rápido: análise de Elliott multi-grau com dados públicos da Bybit."""
import json

from services.elliott_service import ElliottService

if __name__ == "__main__":
    r = ElliottService().analisar_multi_grau("BTCUSDT", "daytrade", "15m", "conservador")
    print(json.dumps(r["alinhamento"], indent=2, ensure_ascii=False))
    for grau, g in r["graus"].items():
        print(grau, g["timeframe"], g["fase"], "bull", g["prob_bull"], "bear", g["prob_bear"], "|", (g.get("primario") or {}).get("nome"))
