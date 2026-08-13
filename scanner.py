import asyncio
import aiohttp

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import (
    MIN_K,
    MIN_VOLUME,
    MIN_PRICE_CHANGE,
    MIN_OI_CHANGE,
)

from bybit_api import (
    get_klines,
    get_open_interest,
    get_futures_price,
    get_symbols,
)

KYIV = ZoneInfo("Europe/Kyiv")
MAX_CONCURRENT_REQUESTS = 30

async def scan_symbol(symbol: str):
    try:
        candles = await get_klines(symbol)
        if candles is None or len(candles) < 10:
            return None
        candles = candles[:-1]
        if len(candles) != 9:
            return None

        volumes = []
        for candle in candles:
            try:
                turnover = float(candle[6])
            except (ValueError, IndexError):
                return None
            volumes.append(turnover)

        base = volumes[:6]
        impulse = volumes[6:]
        avg_base = sum(base) / 6
        avg_impulse = sum(impulse) / 3

        if avg_base < MIN_VOLUME:
            return None
        if avg_base <= 0:
            return None

        k = avg_impulse / avg_base
        if k < MIN_K:
            return None

        try:
            first_impulse_close = float(candles[6][4])
            last_impulse_close = float(candles[8][4])
        except (ValueError, IndexError):
            return None

        if first_impulse_close <= 0:
            return None

        price_change = ((last_impulse_close - first_impulse_close) / first_impulse_close) * 100

        oi_data = await get_open_interest(symbol)
        if oi_data is None or len(oi_data) < 10:
            return None
        oi_data = oi_data[:-1]
        if len(oi_data) != 9:
            return None

        try:
            oi_start = float(oi_data[6]["openInterest"])
            oi_end = float(oi_data[8]["openInterest"])
        except (ValueError, KeyError, IndexError):
            return None

        if oi_start <= 0:
            return None

        oi_change = ((oi_end - oi_start) / oi_start) * 100

        if not (price_change <= -MIN_PRICE_CHANGE and oi_change <= -MIN_OI_CHANGE):
            return None

        futures_price = await get_futures_price(symbol)
        if futures_price is None:
            return None

        daily_candles = await get_klines(symbol, interval="D", limit=2)
        if daily_candles is None or len(daily_candles) < 1:
            return None
        daily_candle = daily_candles[-1]

        try:
            daily_open = float(daily_candle[1])
            daily_high = float(daily_candle[2])
        except (ValueError, IndexError):
            return None

        if daily_open <= 0 or daily_high <= 0:
            return None

        current_24h_change = ((futures_price - daily_open) / daily_open) * 100
        max_24h_change = ((daily_high - daily_open) / daily_open) * 100
        distance_from_high = ((futures_price - daily_high) / daily_high) * 100

        return {
            "symbol": symbol,
            "signal": "SHORT",
            "k": round(k, 2),
            "avg_base": round(avg_base, 2),
            "avg_impulse": round(avg_impulse, 2),
            "price_change": round(price_change, 2),
            "oi_change": round(oi_change, 2),
            "futures_price": futures_price,
            "max_24h_change": round(max_24h_change, 2),
            "current_24h_change": round(current_24h_change, 2),
            "distance_from_high": round(distance_from_high, 2),
        }

    except Exception:
        return None

async def scan_market():
    symbols = await get_symbols()
    if not symbols:
        return []

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def limited_scan(symbol):
        async with semaphore:
            return await scan_symbol(symbol)

    tasks = [limited_scan(symbol) for symbol in symbols]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    passed = []
    for result in results:
        if isinstance(result, Exception):
            continue
        if result is not None:
            passed.append(result)

    passed.sort(key=lambda x: x["k"], reverse=True)
    return passed

def format_results(results: list) -> str:
    if not results:
        return (
            "❌ Сильных SHORT сигналов не найдено.\n\n"
            "Условия:\n"
            f"• Base Volume ≥ {MIN_VOLUME:,} USDT\n"
            f"• K ≥ {MIN_K}\n"
            f"• Price 3H ≤ -{MIN_PRICE_CHANGE}%\n"
            f"• OI 3H ≤ -{MIN_OI_CHANGE}%"
        )

    text = []
    text.append("🚨 СИЛЬНЫЕ SHORT СИГНАЛЫ\n")
    text.append(f"Всего: {len(results)}\n")

    for i, coin in enumerate(results, start=1):
        text.append(
            f"\n{i}. {coin['symbol']}\n"
            "🔴 SHORT\n\n"
            f"💰 Futures Price: {coin['futures_price']:.10g}\n"
            f"📊 K: {coin['k']:.2f}\n"
            f"📉 Price 3H: {coin['price_change']:+.2f}%\n"
            f"📊 OI 3H: {coin['oi_change']:+.2f}%\n"
            f"📊 Base Volume: {coin['avg_base']:,.0f} USDT\n"
            f"⚡ Impulse Volume: {coin['avg_impulse']:,.0f} USDT\n"
            f"📈 24H MAX: {coin['max_24h_change']:+.2f}%\n"
            f"💰 24H NOW: {coin['current_24h_change']:+.2f}%\n"
            f"📉 FROM MAX: {coin['distance_from_high']:+.2f}%\n"
        )

    return "".join(text)

async def get_history_for_symbol(session, symbol: str, start_ms: int, end_ms: int):
    history_start = start_ms - 9 * 60 * 60 * 1000
    candles = await get_klines(session, symbol, interval="60", limit=1000, start=history_start, end=end_ms)

    if candles is None or len(candles) < 10:
        return []

    oi_data = await get_open_interest(session, symbol, limit=1000, start=history_start, end=end_ms)
    if oi_data is None or len(oi_data) < 10:
        return []

    candles_map = {int(candle[0]): candle for candle in candles}
    oi_map = {int(item["timestamp"]): item for item in oi_data}
    timestamps = sorted(candles_map.keys())

    results = []
    for timestamp in timestamps:
        if timestamp < start_ms or timestamp >= end_ms:
            continue

        required_timestamps = [timestamp - i * 60 * 60 * 1000 for i in range(8, -1, -1)]
        if any(ts not in candles_map for ts in required_timestamps):
            continue
        if any(ts not in oi_map for ts in required_timestamps):
            continue

        historical_candles = [candles_map[ts] for ts in required_timestamps]
        historical_oi = [oi_map[ts] for ts in required_timestamps]

        volumes = []
        valid = True
        for candle in historical_candles:
            try:
                turnover = float(candle[6])
            except (ValueError, IndexError):
                valid = False
                break
            volumes.append(turnover)

        if not valid:
            continue

        base = volumes[:6]
        impulse = volumes[6:]
        avg_base = sum(base) / 6
        avg_impulse = sum(impulse) / 3

        if avg_base < MIN_VOLUME or avg_base <= 0:
            continue

        k = avg_impulse / avg_base
        if k < MIN_K:
            continue

        try:
            first_impulse_close = float(historical_candles[6][4])
            last_impulse_close = float(historical_candles[8][4])
        except (ValueError, IndexError):
            continue

        if first_impulse_close <= 0:
            continue

        price_change = ((last_impulse_close - first_impulse_close) / first_impulse_close) * 100

        try:
            oi_start = float(historical_oi[6]["openInterest"])
            oi_end = float(historical_oi[8]["openInterest"])
        except (ValueError, KeyError, IndexError):
            continue

        if oi_start <= 0:
            continue

        oi_change = ((oi_end - oi_start) / oi_start) * 100
        if not (price_change <= -MIN_PRICE_CHANGE and oi_change <= -MIN_OI_CHANGE):
            continue

        signal_time = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).astimezone(KYIV)

        results.append({
            "symbol": symbol,
            "time": signal_time,
            "k": round(k, 2),
            "price_change": round(price_change, 2),
            "oi_change": round(oi_change, 2),
            "avg_base": round(avg_base, 2),
            "avg_impulse": round(avg_impulse, 2),
        })

    return results

async def scan_history(start_ms: int, end_ms: int):
    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=60)

    symbols = await get_symbols()
    if not symbols:
        return []

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [get_history_for_symbol(session, symbol, start_ms, end_ms) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    signals = []
    for result in results:
        if isinstance(result, Exception):
            continue
        if result:
            signals.extend(result)

    signals.sort(key=lambda x: x["time"])
    return signals

def format_history(signals: list, title: str):
    if not signals:
        return (
            f"📜 ИСТОРИЯ — {title}\n\n"
            "❌ SHORT сигналов не найдено.\n\n"
            "Условия:\n"
            f"• Base Volume ≥ {MIN_VOLUME:,} USDT\n"
            f"• K ≥ {MIN_K}\n"
            f"• Price 3H ≤ -{MIN_PRICE_CHANGE}%\n"
            f"• OI 3H ≤ -{MIN_OI_CHANGE}%"
        )

    text = [
        f"📜 ИСТОРИЯ — {title}\n",
        f"🔴 SHORT сигналов: {len(signals)}\n",
    ]

    for i, signal in enumerate(signals, start=1):
        text.append(
            f"\n{i}. {signal['symbol']}\n"
            "🔴 SHORT\n"
            f"⏰ {signal['time'].strftime('%H:%M')} Киев\n\n"
            f"💰 Price: {signal['price']:.10g}\n"
            f"📊 K: {signal['k']:.2f}\n"
            f"📉 Price 3H: {signal['price_change']:+.2f}%\n"
            f"📊 OI 3H: {signal['oi_change']:+.2f}%\n"
            f"📊 Base Volume: {signal['avg_base']:,.0f} USDT\n"
            f"⚡ Impulse Volume: {signal['avg_impulse']:,.0f} USDT\n"
        )

    return "".join(text)
