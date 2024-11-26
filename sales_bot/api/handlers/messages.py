"""Message handlers."""

import logging

from core.messages.service import MessageService
from core.telegram.client import app
from pyrogram import filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handler for processing messages."""

    def __init__(self):
        """Initialize message handler."""
        self.message_service = MessageService()

    async def handle_message(self, client, message: Message):
        """Handle incoming messages."""
        try:
            username = message.from_user.username
            if not username:
                logger.warning("Message from user without username")
                return

            logger.info(f"Processing message from {username}")
            response = await self.message_service.process_incoming_message(message)
            if response:
                await message.reply(response[0])

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await message.reply("Произошла ошибка. Попробуйте позже.")


# Create handler instance
message_handler = MessageHandler()


# Register message handler
@app.on_message(
    filters.private
    & ~filters.command(["start", "stop", "list", "view", "export", "export_all"])
    & ~filters.me
)
async def handle_message(client, message: Message):
    """Handle incoming messages."""
    await message_handler.handle_message(client, message)
