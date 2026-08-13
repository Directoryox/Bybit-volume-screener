import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import aiohttp

from config import (
    MIN_K,
    MIN_VOLUME,
    MIN_PRICE_CHANGE,
    MIN_OI_CHANGE,
)

from bybit_api import (
    get_klines,
    get_open_interest,
    get_symbols,
)


KYIV = ZoneInfo("Europe/Kyiv")


async def get_daily_boundaries():
    now_ms = int(
        datetime.now(timezone.utc).timestamp() * 1000
    )

    daily = await get_klines(
        "BTCUSDT",
        interval="D",
        limit=2,
        end=now_ms,
    )

    if daily is None or len(daily) < 2:
        return None

    today_candle = daily[-1]
    yesterday_candle = daily[-2]

    today_start = int(today_candle[0])

    yesterday_start = int(yesterday_candle[0])

    today_end = now_ms
    yesterday_end = today_start

    return {
        "today": (
            today_start,
            today_end,
        ),
        "yesterday": (
            yesterday_start,
            yesterday_end,
        ),
    }


async def get_history_for_symbol(
    session,
    symbol: str,
    start_ms: int,
    end_ms: int,
):
    candles = await get_klines(
        session,
        symbol,
        interval="60",
        limit=1000,
        start=start_ms - 9 * 60 * 60 * 1000,
        end=end_ms,
    )

    if candles is None or len(candles) < 10:
        return []

    oi_data = await get_open_interest(
        session,
        symbol,
        limit=1000,
        start=start_ms - 9 * 60 * 60 * 1000,
        end=end_ms,
    )

    if oi_data is None or len(oi_data) < 10:
        return []

    candles_map = {
        int(candle[0]): candle
        for candle in candles
    }

    oi_map = {
        int(item["timestamp"]): item
        for item in oi_data
    }

    timestamps = sorted(candles_map.keys())

    results = []

    for timestamp in timestamps:
        if timestamp < start_ms:
            continue

        if timestamp >= end_ms:
            continue

        required_timestamps = [
            timestamp - i * 60 * 60 * 1000
            for i in range(8, -1, -1)
        ]

        if any(
            ts not in candles_map
            for ts in required_timestamps
        ):
            continue

        if any(
            ts not in oi_map
            for ts in required_timestamps
        ):
            continue

        historical_candles = [
            candles_map[ts]
            for ts in required_timestamps
        ]

        historical_oi = [
            oi_map[ts]
            for ts in required_timestamps
        ]

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

        if avg_base < MIN_VOLUME:
            continue

        if avg_base <= 0:
            continue

        k = avg_impulse / avg_base

        if k < MIN_K:
            continue

        try:
            first_impulse_close = float(
                historical_candles[6][4]
            )

            last_impulse_close = float(
                historical_candles[8][4]
            )
        except (ValueError, IndexError):
            continue

        if first_impulse_close <= 0:
            continue

        price_change = (
            (
                last_impulse_close
                - first_impulse_close
            )
            / first_impulse_close
        ) * 100

        try:
            oi_start = float(
                historical_oi[6]["openInterest"]
            )

            oi_end = float(
                historical_oi[8]["openInterest"]
            )
        except (
            ValueError,
            KeyError,
            IndexError,
        ):
            continue

        if oi_start <= 0:
            continue

        oi_change = (
            (oi_end - oi_start)
            / oi_start
        ) * 100

        if not (
            price_change <= -MIN_PRICE_CHANGE
            and oi_change <= -MIN_OI_CHANGE
        ):
            continue

        signal_time = datetime.fromtimestamp(
            timestamp / 1000,
            tz=timezone.utc,
        ).astimezone(KYIV)

        results.append({
            "symbol": symbol,
            "time": signal_time,
            "k": round(k, 2),
            "price_change": round(
                price_change,
                2,
            ),
            "oi_change": round(
                oi_change,
                2,
            ),
            "avg_base": round(
                avg_base,
                2,
            ),
            "avg_impulse": round(
                avg_impulse,
                2,
            ),
        })

    return results


async def scan_history(
    start_ms: int,
    end_ms: int,
):
    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=60)

    symbols = await get_symbols()

    if not symbols:
        return []

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:

        tasks = [
            get_history_for_symbol(
                session,
                symbol,
                start_ms,
                end_ms,
            )
            for symbol in symbols
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

    signals = []

    for result in results:
        if isinstance(
            result,
            Exception,
        ):
            continue

        if result:
            signals.extend(result)

    signals.sort(
        key=lambda x: x["time"]
    )

    return signals


def format_history(
    signals: list,
    title: str,
):
    if not signals:
        return (
            f"📜 ИСТОРИЯ — {title}\n\n"
            "❌ SHORT сигналов не найдено.\n\n"
            "Условия:\n"
            f"• Base Volume ≥ "
            f"{MIN_VOLUME:,} USDT\n"
            f"• K ≥ {MIN_K}\n"
            f"• Price 3H ≤ "
            f"-{MIN_PRICE_CHANGE}%\n"
            f"• OI 3H ≤ "
            f"-{MIN_OI_CHANGE}%"
        )

    text = [
        f"📜 ИСТОРИЯ — {title}\n",
        f"Найдено: {len(signals)}\n",
    ]

    for i, signal in enumerate(
        signals,
        start=1,
    ):
        text.append(
            f"\n{i}. {signal['symbol']}\n"
            f"🔴 SHORT\n"
            f"⏰ "
            f"{signal['time'].strftime('%d.%m.%Y %H:%M')}"
            f" Киев\n\n"
            f"📊 K: "
            f"{signal['k']:.2f}\n"
            f"📉 Price 3H: "
            f"{signal['price_change']:+.2f}%\n"
            f"📊 OI 3H: "
            f"{signal['oi_change']:+.2f}%\n"
            f"📊 Base Volume: "
            f"{signal['avg_base']:,.0f} USDT\n"
            f"⚡ Impulse Volume: "
            f"{signal['avg_impulse']:,.0f} USDT\n"
        )

    return "".join(text)