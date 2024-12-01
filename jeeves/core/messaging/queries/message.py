"""Message queries."""

import logging
from datetime import datetime
from typing import List, Optional

from core.db.base import BaseQueries
from core.messaging.models import Message, MessageDirection
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


class MessageQueries(BaseQueries):
    """Queries for working with messages."""

    async def get_message(self, message_id: int) -> Optional[Message]:
        """
        Get message by ID.

        Args:
            message_id: Message ID

        Returns:
            Message if found, None otherwise
        """
        try:
            query = select(Message).where(Message.id == message_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None

    async def get_dialog_messages(
        self, dialog_id: int, limit: Optional[int] = None
    ) -> List[Message]:
        """
        Get all messages for dialog.

        Args:
            dialog_id: Dialog ID
            limit: Optional limit of messages to return

        Returns:
            List of messages
        """
        try:
            query = (
                select(Message)
                .where(Message.dialog_id == dialog_id)
                .order_by(Message.timestamp)
            )
            if limit:
                query = query.limit(limit)

            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get messages for dialog {dialog_id}: {e}")
            return []

    async def create_message(
        self,
        dialog_id: int,
        content: str,
        direction: MessageDirection,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Message]:
        """
        Create new message.

        Args:
            dialog_id: Dialog ID
            content: Message content
            direction: Message direction
            timestamp: Optional message timestamp

        Returns:
            Created message if successful, None otherwise
        """
        try:
            message = Message(
                dialog_id=dialog_id,
                content=content,
                direction=direction,
                timestamp=timestamp or datetime.utcnow(),
            )
            self.session.add(message)
            await self.session.flush()
            return message
        except Exception as e:
            logger.error(f"Failed to create message for dialog {dialog_id}: {e}")
            return None

    async def update_message_content(
        self, message_id: int, content: str
    ) -> Optional[Message]:
        """
        Update message content.

        Args:
            message_id: Message ID
            content: New content

        Returns:
            Updated message if successful, None otherwise
        """
        try:
            query = (
                update(Message)
                .where(Message.id == message_id)
                .values(content=content)
                .returning(Message)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to update message {message_id}: {e}")
            return None

    async def delete_message(self, message_id: int) -> bool:
        """
        Delete message.

        Args:
            message_id: Message ID

        Returns:
            True if successful, False otherwise
        """
        try:
            message = await self.get_message(message_id)
            if message:
                await self.session.delete(message)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
            return False
