import asyncio

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

        price_change = (
            (last_impulse_close - first_impulse_close)
            / first_impulse_close
        ) * 100

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

        oi_change = (
            (oi_end - oi_start)
            / oi_start
        ) * 100

        signal = None

        if (
            price_change >= MIN_PRICE_CHANGE
            and oi_change >= MIN_OI_CHANGE
        ):
            signal = "LONG"

        elif (
            price_change <= -MIN_PRICE_CHANGE
            and oi_change <= -MIN_OI_CHANGE
        ):
            signal = "SHORT"

        if signal is None:
            return None

        futures_price = await get_futures_price(symbol)

        if futures_price is None:
            return None

        return {
            "symbol": symbol,
            "signal": signal,

            "k": round(k, 2),

            "avg_base": round(avg_base, 2),
            "avg_impulse": round(avg_impulse, 2),

            "price_change": round(price_change, 2),
            "oi_change": round(oi_change, 2),

            "futures_price": futures_price,
        }

    except Exception:
        return None


async def scan_market():
    symbols = await get_symbols()

    if not symbols:
        return []

    tasks = [
        scan_symbol(symbol)
        for symbol in symbols
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    passed = []

    for result in results:

        if isinstance(result, Exception):
            continue

        if result is not None:
            passed.append(result)

    passed.sort(
        key=lambda x: x["k"],
        reverse=True
    )

    return passed


def format_results(results: list) -> str:
    if not results:
        return (
            "❌ Сильных сигналов не найдено.\n\n"
            "Условия:\n"
            f"• Base Volume ≥ {MIN_VOLUME:,} USDT\n"
            f"• K ≥ {MIN_K}\n"
            f"• Price 3H ≥ ±{MIN_PRICE_CHANGE}%\n"
            f"• OI 3H ≥ ±{MIN_OI_CHANGE}%"
        )

    text = []

    text.append("🚨 СИЛЬНЫЕ СИГНАЛЫ\n")
    text.append(f"Всего: {len(results)}\n")

    for i, coin in enumerate(results, start=1):

        if coin["signal"] == "LONG":
            direction = "🟢 LONG"
        else:
            direction = "🔴 SHORT"

        text.append(
            f"\n{i}. {coin['symbol']}\n"
            f"{direction}\n\n"
            f"💰 Futures Price: "
            f"{coin['futures_price']:.10g}\n"
            f"📊 K: {coin['k']:.2f}\n"
            f"📈 Price 3H: "
            f"{coin['price_change']:+.2f}%\n"
            f"📊 OI 3H: "
            f"{coin['oi_change']:+.2f}%\n"
            f"📊 Base Volume: "
            f"{coin['avg_base']:,.0f} USDT\n"
            f"⚡ Impulse Volume: "
            f"{coin['avg_impulse']:,.0f} USDT\n"
        )

    return "".join(text)