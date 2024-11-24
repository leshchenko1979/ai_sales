import logging
import asyncio
from config import LOG_LEVEL, LOG_FILE
from bot.client import client
from utils.logging import setup_logging

# Импортируем обработчики для их регистрации
from bot import commands, dialogs

def main():
    # Настраиваем логирование
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Sales Bot...")

    # Получаем текущий event loop
    loop = asyncio.get_event_loop()

    try:
        # Запускаем клиента
        loop.run_until_complete(client.start())
        logger.info("Bot started successfully")

        # Запускаем бота
        loop.run_until_complete(client.run_until_disconnected())
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        loop.close()

if __name__ == '__main__':
    main()
