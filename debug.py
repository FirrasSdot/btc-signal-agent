import requests
import os

key = os.getenv("CRYPTOQUANT_API_KEY")
print("Key exists:", key is not None)
print("Key length:", len(key) if key else 0)

# Try the endpoint
headers = {"Authorization": "Bearer " + key}

endpoints = [
    "https://api.cryptoquant.com/v1/btc/network-indicator/funding-rates?window=day&limit=1",
    "https://api.cryptoquant.com/v1/btc/market-indicator/funding-rates?window=day&limit=1",
    "https://api.cryptoquant.com/v1/btc/exchange/aggregated-funding-rates?window=day&limit=1",
]

for url in endpoints:
    print("\nTrying:", url)
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print("Status:", r.status_code)
        print("Response:", r.text[:500])
    except Exception as e:
        print("Error:", str(e))
