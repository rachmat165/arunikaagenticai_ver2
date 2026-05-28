import asyncio
import logging
from telegram.ext import Application
from src.config import settings, ensure_directories
from src.database import init_db
from src.gateway import TelegramGateway

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    ensure_directories()

    await init_db(settings.database_path)
    logger.info(f"Database initialized at {settings.database_path}")

    app = Application.builder().token(settings.telegram_bot_token).build()
    logger.info("Telegram bot application created")

    gateway = TelegramGateway(settings.database_path)
    gateway.setup_handlers(app)
    logger.info("Telegram handlers registered")

    logger.info("Starting bot in polling mode...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])
        logger.info("Bot is running!")
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Bot shutting down...")
            await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
