from config import MIN_K, MIN_VOLUME
from bybit_api import get_klines
import asyncio
from bybit_api import get_symbols

async def scan_symbol(symbol: str):
    """
    Проверяет одну монету по алгоритму VolRatio.
    Возвращает словарь с результатом либо None.
    """

    candles = await get_klines(symbol)

    if candles is None:
        return None

    if len(candles) < 10:
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

    for vol in base:
        if vol < MIN_VOLUME:
            return None

    avg_base = sum(base) / 6
    avg_impulse = sum(impulse) / 3

    if avg_base == 0:
        return None

    k = avg_impulse / avg_base

    if k < MIN_K:
        return None

    return {
        "symbol": symbol,
        "k": round(k, 2),
        "avg_base": round(avg_base, 2),
        "avg_impulse": round(avg_impulse, 2),
    }

async def scan_market():
    """
    Сканирует все USDT-пары Bybit.
    Возвращает список монет, прошедших фильтр.
    """

    symbols = await get_symbols()

    if not symbols:
        return []

    tasks = [scan_symbol(symbol) for symbol in symbols]
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
    """
    Формирует красивое сообщение для Telegram.
    """

    if not results:
        return (
            "❌ Монет по фильтру не найдено.\n\n"
            f"Условия:\n"
            f"• Объем базы ≥ {MIN_VOLUME:,} USDT\n"
            f"• K ≥ {MIN_K}"
        )

    text = []

    text.append("🚀 Найдены монеты\n")
    text.append(f"Всего: {len(results)}\n")

    for i, coin in enumerate(results, start=1):

        text.append(
            f"\n{i}. {coin['symbol']}\n"
            f"📈 K = {coin['k']:.2f}\n"
            f"📊 Base = {coin['avg_base']:,.0f}\n"
            f"⚡ Impulse = {coin['avg_impulse']:,.0f}\n"
        )

    return "".join(text)