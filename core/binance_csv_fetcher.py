import os
import requests
from datetime import datetime, timedelta
from zipfile import ZipFile

symbol = "BTCUSDT"
interval = "1h"
start_date = datetime(2023, 5, 1)
end_date = datetime(2025, 5, 14)
output_dir = "binance_csv"

os.makedirs(output_dir, exist_ok=True)

current_date = start_date
while current_date <= end_date:
    date_str = current_date.strftime("%Y-%m-%d")
    file_name = f"{symbol}-{interval}-{date_str}.zip"
    url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/{file_name}"
    local_zip = os.path.join(output_dir, file_name)

    try:
        print(f"🔽 Baixando {file_name}...")
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(local_zip, "wb") as f:
                f.write(r.content)
            with ZipFile(local_zip, 'r') as zip_ref:
                zip_ref.extractall(output_dir)
            os.remove(local_zip)  # opcional: remove o zip depois de extrair
        else:
            print(f"⚠️ Não encontrado: {url}")
    except Exception as e:
        print(f"❌ Erro ao baixar {file_name}: {e}")
    
    current_date += timedelta(days=1)

print("✅ Download completo.")
