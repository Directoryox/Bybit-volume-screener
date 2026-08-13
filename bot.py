import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    BOT_TOKEN,
    CHAT_ID,
    MIN_K,
    MIN_VOLUME,
    MIN_PRICE_CHANGE,
    MIN_OI_CHANGE,
)

from bybit_api import (
    get_symbols,
    get_klines,
    get_open_interest,
    get_futures_price,
)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

KYIV_TZ = ZoneInfo("Europe/Kyiv")
BYBIT_URL = "https://api.bybit.com"

def get_kyiv_now():
    return datetime.now(KYIV_TZ)

def get_history_keyboard():
    now = get_kyiv_now()

    buttons = []

    for days_ago in range(7):
        date = now.date() - timedelta(days=days_ago)

        text = date.strftime("%d.%m.%y")

        if days_ago == 0:
            text += " • сегодня"

        elif days_ago == 1:
            text += " • вчера"

        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"history_{date.isoformat()}",
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
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
            first_impulse_close = float(
                candles[6][4]
            )

            last_impulse_close = float(
                candles[8][4]
            )

        except (ValueError, IndexError):
            return None

        if first_impulse_close <= 0:
            return None

        price_change = (
            (
                last_impulse_close
                - first_impulse_close
            )
            / first_impulse_close
        ) * 100

        oi_data = await get_open_interest(symbol)

        if oi_data is None or len(oi_data) < 10:
            return None

        oi_data = oi_data[:-1]

        if len(oi_data) != 9:
            return None

        try:
            oi_start = float(
                oi_data[6]["openInterest"]
            )

            oi_end = float(
                oi_data[8]["openInterest"]
            )

        except (
            ValueError,
            KeyError,
            IndexError,
        ):
            return None

        if oi_start <= 0:
            return None

        oi_change = (
            (
                oi_end
                - oi_start
            )
            / oi_start
        ) * 100

        if not (
            price_change <= -MIN_PRICE_CHANGE
            and
            oi_change <= -MIN_OI_CHANGE
        ):
            return None

        futures_price = await get_futures_price(
            symbol
        )

        if futures_price is None:
            return None

        daily_candles = await get_klines(
            symbol,
            interval="D",
            limit=2,
        )

        if daily_candles is None or len(daily_candles) < 1:
            return None

        daily_candle = daily_candles[-1]

        try:
            daily_open = float(
                daily_candle[1]
            )

            daily_high = float(
                daily_candle[2]
            )

        except (ValueError, IndexError):
            return None

        if daily_open <= 0 or daily_high <= 0:
            return None

        current_24h_change = (
            (
                futures_price
                - daily_open
            )
            / daily_open
        ) * 100

        max_24h_change = (
            (
                daily_high
                - daily_open
            )
            / daily_open
        ) * 100

        distance_from_high = (
            (
                futures_price
                - daily_high
            )
            / daily_high
        ) * 100

        return {
            "symbol": symbol,
            "signal": "SHORT",

            "k": round(k, 2),

            "avg_base": round(
                avg_base,
                2,
            ),

            "avg_impulse": round(
                avg_impulse,
                2,
            ),

            "price_change": round(
                price_change,
                2,
            ),

            "oi_change": round(
                oi_change,
                2,
            ),

            "futures_price": futures_price,

            "max_24h_change": round(
                max_24h_change,
                2,
            ),

            "current_24h_change": round(
                current_24h_change,
                2,
            ),

            "distance_from_high": round(
                distance_from_high,
                2,
            ),
        }

    except Exception:
        return None


async def scan_market():
    symbols = await get_symbols()

    if not symbols:
        return []

    semaphore = asyncio.Semaphore(30)

    async def limited_scan(symbol):
        async with semaphore:
            return await scan_symbol(symbol)

    tasks = [
        limited_scan(symbol)
        for symbol in symbols
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    passed = []

    for result in results:

        if isinstance(
            result,
            Exception,
        ):
            continue

        if result is not None:
            passed.append(result)

    passed.sort(
        key=lambda x: x["k"],
        reverse=True,
    )

    return passed

def format_scan_results(results):

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

    text.append(
        "🚨 СИЛЬНЫЕ SHORT СИГНАЛЫ\n"
    )

    text.append(
        f"Всего: {len(results)}\n"
    )

    for i, coin in enumerate(
        results,
        start=1,
    ):

        text.append(
            f"\n{i}. {coin['symbol']}\n"
            "🔴 SHORT\n\n"

            f"💰 Futures Price: "
            f"{coin['futures_price']:.10g}\n"

            f"📊 K: "
            f"{coin['k']:.2f}\n"

            f"📉 Price 3H: "
            f"{coin['price_change']:+.2f}%\n"

            f"📊 OI 3H: "
            f"{coin['oi_change']:+.2f}%\n"

            f"📊 Base Volume: "
            f"{coin['avg_base']:,.0f} USDT\n"

            f"⚡ Impulse Volume: "
            f"{coin['avg_impulse']:,.0f} USDT\n"

            f"📈 24H MAX: "
            f"{coin['max_24h_change']:+.2f}%\n"

            f"💰 24H NOW: "
            f"{coin['current_24h_change']:+.2f}%\n"

            f"📉 FROM MAX: "
            f"{coin['distance_from_high']:+.2f}%\n"
        )

    return "".join(text)

async def get_historical_klines(
    symbol: str,
    target_date,
):
    start_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        tzinfo=KYIV_TZ,
    )

    end_dt = (
        start_dt
        + timedelta(days=1)
    )

    start_ms = int(
        start_dt
        .astimezone(timezone.utc)
        .timestamp()
        * 1000
    )

    end_ms = int(
        end_dt
        .astimezone(timezone.utc)
        .timestamp()
        * 1000
    )

    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": "60",
        "start": start_ms,
        "end": end_ms,
        "limit": 1000,
    }

    url = (
        f"{BYBIT_URL}"
        "/v5/market/kline"
    )

    try:
        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                params=params,
            ) as response:

                data = await response.json()

                if data.get(
                    "retCode"
                ) != 0:
                    return []

                candles = (
                    data["result"]["list"]
                )

                candles.reverse()

                return candles

    except Exception:
        return []

async def get_historical_oi(
    symbol: str,
    target_date,
):
    start_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        tzinfo=KYIV_TZ,
    )

    end_dt = (
        start_dt
        + timedelta(days=1)
    )

    start_ms = int(
        start_dt
        .astimezone(timezone.utc)
        .timestamp()
        * 1000
    )

    end_ms = int(
        end_dt
        .astimezone(timezone.utc)
        .timestamp()
        * 1000
    )

    params = {
        "category": "linear",
        "symbol": symbol,
        "intervalTime": "1h",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": 200,
    }

    url = (
        f"{BYBIT_URL}"
        "/v5/market/open-interest"
    )

    try:
        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                params=params,
            ) as response:

                data = await response.json()

                if data.get(
                    "retCode"
                ) != 0:
                    return []

                oi_list = (
                    data["result"]["list"]
                )

                oi_list.reverse()

                return oi_list

    except Exception:
        return []

async def analyze_historical_signal(
    symbol: str,
    target_date,
    hour_index: int,
):
    try:

        candles = await get_historical_klines(
            symbol,
            target_date,
        )

        if len(candles) < 9:
            return None

        if hour_index < 8:
            return None

        current_candle = (
            candles[hour_index]
        )

        current_timestamp = int(
            current_candle[0]
        )

        used_candles = candles[
            hour_index - 8:
            hour_index + 1
        ]

        if len(used_candles) != 9:
            return None

        volumes = []

        for candle in used_candles:

            try:
                turnover = float(
                    candle[6]
                )

            except (
                ValueError,
                IndexError,
            ):
                return None

            volumes.append(turnover)

        base = volumes[:6]
        impulse = volumes[6:]

        avg_base = (
            sum(base) / 6
        )

        avg_impulse = (
            sum(impulse) / 3
        )

        if avg_base < MIN_VOLUME:
            return None

        if avg_base <= 0:
            return None

        k = (
            avg_impulse
            / avg_base
        )

        if k < MIN_K:
            return None

        first_impulse_close = float(
            used_candles[6][4]
        )

        last_impulse_close = float(
            used_candles[8][4]
        )

        if first_impulse_close <= 0:
            return None

        price_change = (
            (
                last_impulse_close
                - first_impulse_close
            )
            / first_impulse_close
        ) * 100

        oi_data = await get_historical_oi(
            symbol,
            target_date,
        )

        if len(oi_data) < 9:
            return None

        if hour_index >= len(oi_data):
            return None

        oi_used = oi_data[
            hour_index - 8:
            hour_index + 1
        ]

        if len(oi_used) != 9:
            return None

        oi_start = float(
            oi_used[6][
                "openInterest"
            ]
        )

        oi_end = float(
            oi_used[8][
                "openInterest"
            ]
        )

        if oi_start <= 0:
            return None

        oi_change = (
            (
                oi_end
                - oi_start
            )
            / oi_start
        ) * 100

        if not (
            price_change
            <= -MIN_PRICE_CHANGE
            and
            oi_change
            <= -MIN_OI_CHANGE
        ):
            return None

        dt = datetime.fromtimestamp(
            current_timestamp / 1000,
            tz=timezone.utc,
        ).astimezone(
            KYIV_TZ
        )

        return {
            "symbol": symbol,

            "time": dt,

            "price": last_impulse_close,

            "k": round(
                k,
                2,
            ),

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
        }

    except Exception:
        return None

async def scan_history_date(
    target_date,
):
    symbols = await get_symbols()

    if not symbols:
        return []

    results = []

    semaphore = asyncio.Semaphore(10)

    async def scan_symbol_history(
        symbol,
    ):

        async with semaphore:

            candles = (
                await get_historical_klines(
                    symbol,
                    target_date,
                )
            )

            if len(candles) < 9:
                return []

            symbol_results = []

            for hour_index in range(
                8,
                len(candles),
            ):

                signal = (
                    await analyze_historical_signal(
                        symbol,
                        target_date,
                        hour_index,
                    )
                )

                if signal is not None:
                    symbol_results.append(
                        signal
                    )

            return symbol_results

    tasks = [
        scan_symbol_history(symbol)
        for symbol in symbols
    ]

    all_results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    for result in all_results:

        if isinstance(
            result,
            Exception,
        ):
            continue

        if result:
            results.extend(result)

    results.sort(
        key=lambda x: x["time"]
    )

    return results

def format_history(
    results,
    target_date,
):

    date_text = (
        target_date.strftime(
            "%d.%m.%Y"
        )
    )

    if not results:
        return (
            f"📜 ИСТОРИЯ — "
            f"{date_text}\n\n"

            "❌ SHORT сигналов "
            "не найдено.\n\n"

            "Условия:\n"

            f"• Base Volume ≥ "
            f"{MIN_VOLUME:,} USDT\n"

            f"• K ≥ {MIN_K}\n"

            f"• Price 3H ≤ "
            f"-{MIN_PRICE_CHANGE}%\n"

            f"• OI 3H ≤ "
            f"-{MIN_OI_CHANGE}%"
        )

    text = []

    text.append(
        f"📜 ИСТОРИЯ — "
        f"{date_text}\n\n"
    )

    text.append(
        f"🔴 SHORT сигналов: "
        f"{len(results)}\n"
    )

    for i, coin in enumerate(
        results,
        start=1,
    ):

        text.append(
            f"\n{i}. "
            f"{coin['symbol']}\n"

            "🔴 SHORT\n"

            f"⏰ "
            f"{coin['time'].strftime('%H:%M')}"
            f" Киев\n\n"

            f"💰 Price: "
            f"{coin['price']:.10g}\n"

            f"📊 K: "
            f"{coin['k']:.2f}\n"

            f"📉 Price 3H: "
            f"{coin['price_change']:+.2f}%\n"

            f"📊 OI 3H: "
            f"{coin['oi_change']:+.2f}%\n"

            f"📊 Base Volume: "
            f"{coin['avg_base']:,.0f} USDT\n"

            f"⚡ Impulse Volume: "
            f"{coin['avg_impulse']:,.0f} USDT\n"
        )

    return "".join(text)

@dp.message(
    Command("start")
)
async def start_command(
    message: Message,
):

    await message.answer(
        "🤖 VolRatio Scanner\n\n"

        "/history — "
        "исторические SHORT сигналы\n"

        "/scan — "
        "запустить сканирование"
    )

@dp.message(
    Command("scan")
)
async def scan_command(
    message: Message,
):

    await message.answer(
        "🔎 Сканирую рынок..."
    )

    try:

        results = (
            await scan_market()
        )

        text = (
            format_scan_results(
                results
            )
        )

        await message.answer(
            text
        )

    except Exception as exc:

        print(
            "Scan error:",
            type(exc).__name__,
            str(exc),
        )

        await message.answer(
            "❌ Ошибка при сканировании."
        )

@dp.message(
    Command("history")
)
async def history_command(
    message: Message,
):

    await message.answer(
        "📜 ИСТОРИЯ\n\n"
        "Выбери день:",
        reply_markup=(
            get_history_keyboard()
        ),
    )

@dp.callback_query(
    F.data.startswith("history_")
)
async def history_callback(
    callback: CallbackQuery,
):

    data = callback.data

    if data is None:
        return

    date_string = data.replace(
        "history_",
        "",
        1,
    )

    try:

        target_date = (
            datetime.strptime(
                date_string,
                "%Y-%m-%d",
            ).date()
        )

    except ValueError:

        await callback.answer(
            "❌ Неверная дата."
        )

        return

    today = (
        get_kyiv_now().date()
    )

    oldest = (
        today
        - timedelta(days=6)
    )

    if (
        target_date < oldest
        or target_date > today
    ):

        await callback.answer(
            "❌ Эта дата больше недоступна."
        )

        return

    await callback.answer()

    await callback.message.answer(
        f"⏳ Сканирую "
        f"{target_date.strftime('%d.%m.%Y')}...\n\n"

        "📊 Таймфрейм анализа: 1H\n"
        "📅 Границы дня: 1D Bybit\n"
        "🇺🇦 Время: Киев"
    )

    try:

        results = (
            await scan_history_date(
                target_date
            )
        )

        text = format_history(
            results,
            target_date,
        )

        await callback.message.answer(
            text
        )

    except Exception as exc:

        print(
            "History error:",
            type(exc).__name__,
            str(exc),
        )

        await callback.message.answer(
            "❌ Ошибка при получении "
            "исторических данных."
        )

async def auto_scan():

    print(
        "Automatic scan started"
    )

    try:

        results = (
            await scan_market()
        )

        if results:

            text = (
                format_scan_results(
                    results
                )
            )

            await bot.send_message(
                chat_id=CHAT_ID,
                text=text,
            )

    except Exception as exc:

        print(
            "Automatic scan error:",
            exc,
        )

async def main():

    scheduler = (
        AsyncIOScheduler()
    )

    scheduler.add_job(
        auto_scan,
        "interval",
        minutes=30,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    await auto_scan()

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    asyncio.run(main())
