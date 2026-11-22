import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from api.routes import setup_app
from bot.handlers import router as bot_router
from config import BOT_TOKEN, HOST, PORT, WEBAPP_URL
from database import init_db
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("main")


async def main():
    if not BOT_TOKEN:
        logger.error("9177803777:AAF87QC5CwW_rEh9A6608hKAzURWnDc_eNw")
        print("\nОШИБКА: BOT_TOKEN не задан. Создайте файл .env и укажите BOT_TOKEN=ваш_токен\n")
        return

    logger.info("Инициализация базы данных...")
    await init_db()

    logger.info("Инициализация бота aiogram 3...")
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bot_router)

    logger.info("Запуск планировщика APScheduler...")
    scheduler = setup_scheduler(bot)
    scheduler.start()

    logger.info(f"Запуск HTTP-сервера для Mini App на http://{HOST}:{PORT}...")
    logger.info(f"Публичный WebApp URL: {WEBAPP_URL}")
    app = setup_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=HOST, port=PORT)
    await site.start()

    print("\n-----------------------------------------------------------")
    print(f"Сервер успешно запущен на http://{HOST}:{PORT}")
    print(f"Telegram Mini App доступен по адресу: {WEBAPP_URL}")
    print("Бот готов к приему сообщений. Нажмите Ctrl+C для остановки.")
    print("-----------------------------------------------------------\n")

    try:
        # Удаляем предыдущие обновления и запускаем поллинг
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал завершения работы...")
    finally:
        logger.info("Остановка планировщика и очистка ресурсов...")
        scheduler.shutdown(wait=False)
        await runner.cleanup()
        await bot.session.close()
        logger.info("Работа завершена.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
