"""Main application entry point."""

import asyncio
import logging

from core.scheduler import Scheduler
from core.telegram import app
from infrastructure.logging import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""
    try:
        # Start scheduler
        scheduler = Scheduler()
        await scheduler.start()
        logger.info("Scheduler started successfully")

        # Start bot
        await app.start()

        # Log available commands
        commands_info = """
        Бот запущен. Доступные команды администратора:

        Управление аккаунтами:
        /account_add (или /addacc) - Добавить аккаунт
        /account_auth (или /auth) - Авторизовать
        /account_list (или /accounts) - Список аккаунтов
        /account_check (или /check) - Проверить статус
        /account_checkall (или /checkall) - Проверить все
        /account_resend (или /resend) - Повторный код

        Управление диалогами:
        /dialog_start (или /start_chat) - Начать диалог
        /dialog_export (или /export) - Экспорт диалога
        /dialog_exportall (или /exportall) - Экспорт всех

        /help - Справка по командам

        ID администратора: {ADMIN_TELEGRAM_ID}
        """
        logger.info(commands_info)
        logger.info("Bot started successfully")

        # Wait for stop signal
        await app.idle()

    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        raise

    finally:
        # Stop services
        try:
            await scheduler.stop()
            logger.info("Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)

        try:
            await app.stop()
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}", exc_info=True)


if __name__ == "__main__":
    # Run main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
