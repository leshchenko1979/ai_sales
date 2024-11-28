"""Main application entry point."""

import logging

from api import handlers  # noqa: F401
from core.scheduler import Scheduler
from core.telegram import app
from infrastructure.config import ADMIN_TELEGRAM_ID, SCHEDULER_ON
from infrastructure.logging import setup_logging
from pyrogram import idle, types

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""

    async with app:  # Automatical session management
        try:
            logger.info("Bot started successfully")

            # Start scheduler
            if SCHEDULER_ON:
                scheduler = Scheduler()
                await scheduler.start()
                logger.info("Scheduler started successfully")

            # Set bot commands
            commands = [
                types.BotCommand("account_add", "Добавить аккаунт"),
                types.BotCommand("account_auth", "Авторизовать"),
                types.BotCommand("account_list", "Список аккаунтов"),
                types.BotCommand("account_check", "Проверить статус"),
                types.BotCommand("account_checkall", "Проверить все"),
                types.BotCommand("account_resend", "Повторный код"),
                types.BotCommand("dialog_start", "Начать диалог"),
                types.BotCommand("dialog_export", "Экспорт диалога"),
                types.BotCommand("dialog_exportall", "Экспорт всех"),
                types.BotCommand("help", "Справка по командам"),
            ]

            await app.set_bot_commands(commands)
            logger.info("Bot commands set successfully")

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
            logger.info(commands_info.format(ADMIN_TELEGRAM_ID=ADMIN_TELEGRAM_ID))

            # Wait for stop signal
            await idle()

        except Exception as e:
            logger.error(f"Critical error in main: {e}", exc_info=True)
            raise

        finally:
            # Stop services
            if SCHEDULER_ON:
                try:
                    await scheduler.stop()
                    logger.info("Scheduler stopped successfully")
                except Exception as e:
                    logger.error(f"Error stopping scheduler: {e}", exc_info=True)

    logger.info("Bot stopped successfully")


if __name__ == "__main__":
    # Run main
    try:
        app.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
