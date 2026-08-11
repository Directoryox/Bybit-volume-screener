import aiohttp
from config import BYBIT_BASE_URL

async def get_symbols():
    url = f"{BYBIT_BASE_URL}/v5/market/instruments-info"

    params = {
        "category": "linear",
        "limit": 1000,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()

            if data.get("retCode") != 0:
                return []

            symbols = []

            for item in data["result"]["list"]:
                symbol = item["symbol"]

                if (
                    symbol.endswith("USDT")
                    and item.get("status") == "Trading"
                ):
                    symbols.append(symbol)
            return symbols


async def get_klines(symbol: str):
    url = f"{BYBIT_BASE_URL}/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": "60",
        "limit": 10,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()
            if data.get("retCode") != 0:
                return None
            candles = data["result"]["list"]
            candles.reverse()
            return candles


async def get_open_interest(symbol: str):
    url = f"{BYBIT_BASE_URL}/v5/market/open-interest"
    params = {
        "category": "linear",
        "symbol": symbol,
        "intervalTime": "1h",
        "limit": 10,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()
            if data.get("retCode") != 0:
                return None
            oi_list = data["result"]["list"]
            oi_list.reverse()
            return oi_list


async def get_futures_price(symbol: str):
    url = f"{BYBIT_BASE_URL}/v5/market/tickers"
    params = {
        "category": "linear",
        "symbol": symbol,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()
            if data.get("retCode") != 0:
                return None

            ticker_list = data["result"]["list"]

            if not ticker_list:
                return None
            return float(ticker_list[0]["lastPrice"])