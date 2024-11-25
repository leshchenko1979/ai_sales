import asyncio
import logging
from pathlib import Path

from bot.client import app
from bot.commands import *  # noqa: F403 F401
from db.migrate import create_tables
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
        await app.set_bot_commands(
            [BotCommand(command, description) for command, description in COMMANDS]
        )
        logger.info("Bot commands registered successfully")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}", exc_info=True)


async def main():
    """Main application entry point"""
    try:
        setup_logging()
        await create_tables()

        # Delete potentially corrupt session file
        session_file = Path("admin_bot.session")
        if session_file.exists():
            try:
                session_file.unlink()  # Delete the file
                logger.info("Deleted existing session file")
            except OSError as e:
                logger.error(f"Failed to delete session file: {e}")

        try:
            await app.start()
            scheduler = AccountScheduler()
            await scheduler.start()

            await register_commands(app)

            await idle()

        finally:
            await scheduler.stop()
            await app.stop()

    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
