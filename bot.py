import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CHAT_ID
from scanner import scan_market, format_results

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "🚀 VolRatio Scanner запущен\n\n"
        "Команды:\n"
        "/scan - ручной поиск монет\n"
        "/start - информация"
    )

@dp.message(Command("scan"))
async def scan_handler(message: Message):
    await message.answer(
        "🔎 Начинаю сканирование рынка..."
    )

    results = await scan_market()
    text = format_results(results)
    await message.answer(text)

async def auto_scan():
    print("Запуск автоматического сканирования")
    results = await scan_market()

    if results:
        text = format_results(results)

        await bot.send_message(
            chat_id=CHAT_ID,
            text=text
        )

    else:
        print("Сигналов нет")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        auto_scan,
        "interval",
        hours=1
    )

    scheduler.start()
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())