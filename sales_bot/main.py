import logging

from bot.client import app

# Import commands after client is defined
from bot.commands import *  # noqa: F403 F401
from pyrogram import idle
from pyrogram.types import BotCommand
from scheduler import AccountScheduler
from utils.logging import setup_logging

logger = logging.getLogger(__name__)

COMMANDS = [
    ("start", "Начать диалог с пользователем"),
    ("stop", "Остановить диалог"),
    ("list", "Показать активные диалоги"),
    ("view", "Просмотреть диалог"),
    ("export", "Выгрузить диалог"),
    ("export_all", "Выгрузить все диалоги"),
    ("add_account", "Добавить аккаунт"),
    ("authorize", "Авторизовать аккаунт"),
    ("list_accounts", "Список аккаунтов"),
    ("disable_account", "Отключить аккаунт"),
    ("check_account", "Проверить аккаунт"),
    ("check_all_accounts", "Проверить все аккаунты"),
    ("help", "Показать справку"),
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
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        app.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
