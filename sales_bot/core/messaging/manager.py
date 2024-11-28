"""Message manager module."""

import asyncio
import logging
from typing import List, Optional

from core.db.decorators import with_queries
from core.messaging.delivery import MessageDelivery
from core.messaging.models import DeliveryOptions, MessageDirection
from core.messaging.queries import MessageQueries

logger = logging.getLogger(__name__)

# Constants
DEFAULT_INCOMING_TIMEOUT = 3  # seconds
DELAY_OUTGOING_MESSAGES = 3  # seconds


class MessageManager:
    """Message manager."""

    def __init__(self, delivery_options: Optional[DeliveryOptions] = None):
        """
        Initialize manager.

        Args:
            delivery_options: Optional delivery options
        """
        self._delivery = MessageDelivery(options=delivery_options)
        self._incoming_messages: List[str] = []
        self._incoming_task: Optional[asyncio.Task] = None

    @with_queries(MessageQueries)
    async def receive(
        self,
        dialog_id: int,
        message: str,
        queries: MessageQueries,
    ) -> Optional[str]:
        """
        Add client message to the queue.

        If there is an ongoing message aggregation, add to it.
        Otherwise start a new aggregation with timeout.

        Args:
            dialog_id: Dialog ID
            message: Message to add
            queries: Message queries instance (injected)

        Returns:
            Aggregated message if timeout reached, None if still waiting
        """
        # Cancel any ongoing bot message sending
        if self._outgoing_task and not self._outgoing_task.done():
            self._outgoing_task.cancel()
            try:
                await self._outgoing_task
            except asyncio.CancelledError:
                pass

        # Add message to queue
        self._incoming_messages.append(message)

        # Store message in database
        await queries.create_message(
            dialog_id=dialog_id, content=message, direction=MessageDirection.IN
        )

        return None

    async def _wait_for_more_messages(self) -> Optional[str]:
        """
        Wait for more messages with timeout.

        Returns:
            Aggregated message if timeout reached, None otherwise
        """
        try:
            await asyncio.sleep(DEFAULT_INCOMING_TIMEOUT)
            if self._incoming_messages:
                result = " ".join(self._incoming_messages)
                self._incoming_messages.clear()
                return result
            return None
        except asyncio.CancelledError:
            return None

    async def send(
        self,
        dialog_id: int,
        messages: List[str],
        send_func: callable,
    ) -> None:
        """
        Send bot messages with delay.

        Args:
            dialog_id: Dialog ID
            messages: List of messages to send
            send_func: Function to send message
        """
        # Split long messages if needed
        split_messages = []
        for message in messages:
            split_messages.extend(self._delivery.split_messages(message))

        # Deliver messages
        await self._delivery.deliver_messages(
            dialog_id=dialog_id,
            messages=split_messages,
            send_func=send_func,
        )
