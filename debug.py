import os

print("Checking environment variables...")
print("TELEGRAM_BOT_TOKEN exists:", os.getenv("TELEGRAM_BOT_TOKEN") is not None)
print("TELEGRAM_CHAT_ID exists:", os.getenv("TELEGRAM_CHAT_ID") is not None)
print("FRED_API_KEY exists:", os.getenv("FRED_API_KEY") is not None)
print("CRYPTOQUANT_API_KEY exists:", os.getenv("CRYPTOQUANT_API_KEY") is not None)
