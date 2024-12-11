"""Main application entry point."""

import logging

from api import handlers  # noqa: F401
from core.accounts.client_manager import ClientManager
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
            logger.trace("Bot commands set successfully, starting idle loop")

            # Wait for stop signal
            await idle()

        except Exception as e:
            logger.error(f"Critical error in main: {e}", exc_info=True)
            raise

        finally:
            # Cleanup all clients
            try:
                client_manager = ClientManager()
                await client_manager.stop_all()
                logger.trace("All clients stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping clients: {e}", exc_info=True)

            # Save session string
            try:
                session_string = await app.export_session_string()
                if save_session(session_string):
                    logger.trace("Saved session string")
                else:
                    logger.warning("Failed to save session string")
            except Exception as e:
                logger.error(f"Error saving session: {e}", exc_info=True)

    logger.trace("Bot stopped successfully")


if __name__ == "__main__":
    # Run main
    try:
        app.run(main())
    except KeyboardInterrupt:
        logger.trace("Bot shutdown requested by user")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
