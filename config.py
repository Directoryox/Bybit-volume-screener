import os
from pathlib import Path
from dotenv import load_dotenv

env_file = Path(".env")
if not env_file.exists():
    env_file = Path("env.txt")
load_dotenv(env_file)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_STR = os.getenv("CHAT_ID")

if BOT_TOKEN is None:
    raise EnvironmentError("BOT_TOKEN is not set in the environment or env file")
if CHAT_ID_STR is None:
    raise EnvironmentError("CHAT_ID is not set in the environment or env file")

try:
    CHAT_ID = int(CHAT_ID_STR)
except ValueError as exc:
    raise ValueError("CHAT_ID must be an integer") from exc

BYBIT_BASE_URL = "https://api.bybit.com"

MIN_K = 3
MIN_VOLUME = 20_000

MIN_PRICE_CHANGE = 5.0
MIN_OI_CHANGE = 5.0