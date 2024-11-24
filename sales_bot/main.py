import logging
from config import LOG_LEVEL, LOG_FILE
from bot.client import client
from utils.logging import setup_logging

# Импортируем обработчики для их регистрации
from bot import commands, dialogs

async def main():
    # Настраиваем логирование
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Sales Bot...")

    # Запускаем клиента
    await client.start()
    logger.info("Bot started successfully")

    # Запускаем бота
    await client.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
