import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database import Database
from handlers import business, owner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main():
    Config.validate()

    db = Database()
    await db.init()
    log.info("✅ База данных инициализирована")

    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(business.router)  # ← business ПЕРВЫМ
    dp.include_router(owner.router)

    log.info("🚀 Бот запущен. Владелец ID: %s", Config.OWNER_ID)
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "callback_query",
            "business_connection",
            "business_message",  # ← явно разрешаем business апдейты
        ]
    )


if __name__ == "__main__":
    asyncio.run(main())
