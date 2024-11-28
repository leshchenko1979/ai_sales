"""Main application entry point."""

import logging

from api import handlers  # noqa: F401
from core.telegram import app
from core.telegram.session import save_session
from infrastructure.logging import setup_logging
from pyrogram import idle, types

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""

    async with app:  # Automatic session management
        try:
            logger.info("Bot started successfully")

            # Set bot commands for testing mode
            commands = [
                types.BotCommand("test_dialog", "Начать тестовый диалог"),
                types.BotCommand("help", "Справка"),
            ]

            await app.set_bot_commands(commands)
            logger.info("Bot commands set successfully")

            # Log welcome message
            welcome_message = """
            🤖 Бот для тестирования холодных продаж открытого девелопмента запущен!

            Как начать:
            1. Используйте команду /test_dialog чтобы начать диалог
            2. После завершения диалога вы сможете оставить обратную связь
            3. Все диалоги сохраняются для анализа

            Удачного тестирования! 🚀
            """
            logger.info(welcome_message)

            # Wait for stop signal
            await idle()

        except Exception as e:
            logger.error(f"Critical error in main: {e}", exc_info=True)
            raise

        # Save session string
        session_string = await app.export_session_string()
        if save_session(session_string):
            logger.info("Saved session string")
        else:
            logger.warning("Failed to save session string")

    logger.info("Bot stopped successfully")


if __name__ == "__main__":
    # Run main
    try:
        app.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
