import requests
import time

now = int(time.time() * 1000)
print("Local timestamp:", now)

resp = requests.get("https://api-testnet.bybit.com/v5/market/time")
print("Bybit server time:", resp.json())