import logging

from bot.client import app

# Import commands after client is defined
from bot.commands import *  # noqa: F403 F401
from db.queries import engine
from pyrogram import idle
from pyrogram.types import BotCommand
from scheduler import AccountScheduler
from utils.logging import setup_logging

logger = logging.getLogger(__name__)

COMMANDS = [
    # Диалоги
    ("start", "Начать диалог с пользователем"),
    ("stop", "Остановить диалог"),
    ("list", "Показать активные диалоги"),
    ("view", "Просмотреть диалог"),
    ("export", "Выгрузить диалог"),
    ("export_all", "Выгрузить все диалоги"),
    # Управление аккаунтами
    ("add_account", "Добавить новый аккаунт"),
    ("authorize", "Авторизовать аккаунт"),
    ("resend_code", "Повторно отправить код авторизации"),
    ("list_accounts", "Список всех аккаунтов"),
    ("disable_account", "Отключить аккаунт"),
    ("check_account", "Проверить состояние аккаунта"),
    ("check_all_accounts", "Проверить все аккаунты"),
    # Помощь
    ("help", "Показать справку по командам"),
]


async def register_commands(app):
    """Register bot commands in Telegram"""
    try:
        # Register new commands
        await app.set_bot_commands(
            [BotCommand(command, description) for command, description in COMMANDS]
        )
        logger.info("Bot commands registered successfully")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}", exc_info=True)
        raise


async def main():
    """Main application entry point"""
    try:
        setup_logging()
        logger.info("Starting bot application...")

        async with app:
            logger.info("Bot started successfully")

            # Register commands
            await register_commands(app)

            # Start scheduler
            scheduler = AccountScheduler()
            await scheduler.start()
            logger.info("Scheduler started successfully")

            # Log ready state
            logger.info("Bot is ready to handle commands")

            # Wait for bot
            await idle()

    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise

    finally:
        try:
            if "scheduler" in locals():
                await scheduler.stop()
            # Close database connection pool
            await engine.dispose()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        app.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
