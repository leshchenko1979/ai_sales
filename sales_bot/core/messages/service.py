"""Message service."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from core.ai.gpt import GPTClient
from core.db import with_queries
from pyrogram.types import Message as PyrogramMessage

from .models import Dialog, DialogStatus, Message, MessageDirection

logger = logging.getLogger(__name__)


class MessageService:
    """Message service."""

    def __init__(self):
        """Initialize service."""
        self.gpt_client = GPTClient()

    @with_queries
    async def start_dialog(self, username: str, queries=None) -> Optional[Dialog]:
        """
        Start dialog with user.

        :param username: Username to start dialog with
        :param queries: Dialog queries executor
        :return: Created dialog or None if failed
        """
        from core.accounts import AccountManager
        from core.db import DialogQueries  # Import inside method

        try:
            # Check if user already has active dialog
            existing_dialog = await queries.get(DialogQueries).get_active_dialog(
                username
            )
            if existing_dialog:
                logger.warning(f"User {username} already has active dialog")
                return existing_dialog

            # Get available account
            account_manager = AccountManager()
            account = await account_manager.get_available_account()
            if not account:
                logger.error("No available accounts")
                return None

            # Create dialog
            dialog = await queries.get(DialogQueries).create_dialog(
                username, account.id
            )
            if not dialog:
                logger.error(f"Failed to create dialog for {username}")
                return None

            # Generate and send initial message
            initial_message = await self.gpt_client.generate_initial_message()
            if await self.send_message(dialog.id, initial_message, queries):
                return dialog
            else:
                logger.error(f"Failed to send initial message to {username}")
                await queries.get(DialogQueries).update_dialog_status(
                    dialog.id, DialogStatus.failed
                )
                return None

        except Exception as e:
            logger.error(f"Error starting dialog with {username}: {e}", exc_info=True)
            return None

    @with_queries
    async def get_or_create_dialog(
        self, username: str, queries=None
    ) -> Optional[Dialog]:
        """Get or create dialog."""
        from core.db import DialogQueries  # Import inside method

        try:
            # Check for existing active dialog
            dialog = await queries.get(DialogQueries).get_active_dialog(username)
            if dialog:
                return dialog

            # Start new dialog
            return await self.start_dialog(username, queries)

        except Exception as e:
            logger.error(
                f"Error getting or creating dialog for {username}: {e}", exc_info=True
            )
            return None

    @with_queries
    async def send_message(
        self, dialog_id: int, content: str, queries=None
    ) -> Optional[Message]:
        """Send message."""
        from core.accounts import AccountManager
        from core.db import DialogQueries  # Import inside method

        try:
            # Get dialog
            dialog = await queries.get(DialogQueries).get_dialog_by_id(dialog_id)
            if not dialog:
                logger.error(f"Dialog {dialog_id} not found")
                return None

            # Check if account can send message
            account_manager = AccountManager()
            if not dialog.account.can_be_used:
                logger.warning(f"Account {dialog.account.phone} cannot be used")
                return None

            # Send message
            if not await dialog.account.send_message(dialog.username, content):
                return None

            # Save message
            message = await queries.get(DialogQueries).save_message(
                dialog_id=dialog_id,
                content=content,
                direction=MessageDirection.out,
            )

            # Update dialog
            dialog.last_message_at = datetime.utcnow()
            queries.session.add(dialog)

            # Update account
            await account_manager.increment_messages(dialog.account.id)

            return message

        except Exception as e:
            logger.error(
                f"Error sending message to dialog {dialog_id}: {e}", exc_info=True
            )
            return None

    @with_queries
    async def process_incoming_message(
        self, message: PyrogramMessage, queries=None
    ) -> Optional[Tuple[str, bool]]:
        """Process incoming message and generate response."""
        from core.db import DialogQueries  # Import inside method

        try:
            username = message.from_user.username
            if not username:
                return None

            # Get or create dialog
            dialog = await self.get_or_create_dialog(username, queries)
            if not dialog:
                return None

            # Save incoming message
            await self.save_incoming_message(dialog.id, message.text, queries)

            # Get dialog history
            messages = await self.get_dialog_messages(dialog.id, queries)
            history = [
                {"direction": msg.direction, "content": msg.content} for msg in messages
            ]

            # Check qualification
            qualified, reason = await self.gpt_client.check_qualification(history)

            # Generate response
            if qualified:
                response = (
                    "Отлично! Вы соответствуете нашим критериям. "
                    "Давайте организуем звонок с менеджером для обсуждения деталей. "
                    "В какое время вам удобно пообщаться?"
                )
                await queries.get(DialogQueries).update_dialog_status(
                    dialog.id, DialogStatus.qualified
                )
            else:
                response = await self.gpt_client.generate_response(
                    history, message.text
                )

            return response, qualified

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return None

    @with_queries
    async def save_incoming_message(
        self, dialog_id: int, content: str, queries=None
    ) -> Optional[Message]:
        """Save incoming message."""
        from core.db import DialogQueries  # Import inside method

        try:
            # Save message
            message = await queries.get(DialogQueries).save_message(
                dialog_id=dialog_id,
                content=content,
                direction=MessageDirection.in_,
            )

            # Update dialog
            dialog = await queries.get(DialogQueries).get_dialog_by_id(dialog_id)
            if dialog:
                dialog.last_message_at = datetime.utcnow()
                queries.session.add(dialog)

            return message

        except Exception as e:
            logger.error(
                f"Error saving incoming message to dialog {dialog_id}: {e}",
                exc_info=True,
            )
            return None

    @with_queries
    async def get_dialog_messages(self, dialog_id: int, queries=None) -> List[Message]:
        """Get dialog messages."""
        from core.db import DialogQueries  # Import inside method

        try:
            dialog = await queries.get(DialogQueries).get_dialog_by_id(dialog_id)
            return dialog.messages if dialog else []

        except Exception as e:
            logger.error(
                f"Error getting messages for dialog {dialog_id}: {e}", exc_info=True
            )
            return []

    @with_queries
    async def get_all_dialogs(self, queries=None) -> List[Dialog]:
        """Get all dialogs."""
        from core.db import DialogQueries  # Import inside method

        try:
            return await queries.get(DialogQueries).get_all_dialogs()
        except Exception as e:
            logger.error(f"Error getting all dialogs: {e}", exc_info=True)
            return []
