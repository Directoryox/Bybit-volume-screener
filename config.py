from dotenv import load_dotenv
import os

load_dotenv()
if not os.getenv("BOT_TOKEN") and os.path.exists("env.txt"):
    load_dotenv("env.txt")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if BOT_TOKEN is None:
    raise EnvironmentError(
        "BOT_TOKEN is not set. Create a .env or env.txt file with BOT_TOKEN=..."
    )

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

TIMEFRAME = "60"
MIN_VOLUME = 20_000
MIN_K = 4.8

BYBIT_BASE_URL = "https://api.bybit.com"