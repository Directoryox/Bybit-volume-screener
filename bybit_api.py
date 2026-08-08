import aiohttp
from config import BYBIT_BASE_URL


async def get_symbols():
    url = f"{BYBIT_BASE_URL}/v5/market/instruments-info"

    params = {
        "category": "linear"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()

            if data["retCode"] != 0:
                return []

            symbols = []

            for item in data["result"]["list"]:
                symbol = item["symbol"]

                if symbol.endswith("USDT"):
                    symbols.append(symbol)

            return symbols


async def get_klines(symbol: str):
    url = f"{BYBIT_BASE_URL}/v5/market/kline"

    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": "60",
        "limit": 10
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()

            if data["retCode"] != 0:
                return None

            candles = data["result"]["list"]
            candles.reverse()

            return candles