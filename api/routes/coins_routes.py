import requests
from fastapi import APIRouter

router = APIRouter()

@router.get("/moedas-disponiveis")
def listar_pares_binance():
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {"category": "linear"}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        symbols = data.get("result", {}).get("list", [])
        return [s["symbol"] for s in symbols if s.get("status") == "Trading"]
    except Exception as e:
        return {"error": str(e)}
