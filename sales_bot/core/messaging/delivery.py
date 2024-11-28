"""Message delivery module."""

import asyncio
import logging
from typing import Any, Callable, List, Optional

from core.db.decorators import with_queries
from core.messaging.models import DeliveryResult, MessageDirection

from .queries.message import MessageQueries

logger = logging.getLogger(__name__)

# Constants
MAX_OUTGOING_QUEUE_SIZE = 10
TYPING_DELAY = 1.5  # seconds
CHAR_DELAY = 0.05  # seconds per character


class MessageDelivery:
    """Handles message delivery with realistic typing delays."""

    def __init__(self):
        """Initialize delivery options and state."""
        self._lock = asyncio.Lock()
        self._outgoing_queue = asyncio.Queue(maxsize=MAX_OUTGOING_QUEUE_SIZE)
        self._current_delivery_task: Optional[asyncio.Task] = None

    def split_messages(self, text: str) -> List[str]:
        """
        Split message on double newlines to preserve paragraph breaks.

        Args:
            text: Message text to split

        Returns:
            List of message chunks
        """
        # Split on double newlines
        messages = [p.strip() for p in text.split("\n\n")]
        # Filter out empty messages
        return [m for m in messages if m]

    async def _clear_outgoing_queue(self) -> None:
        """Clear all pending outgoing messages."""
        try:
            while True:
                self._outgoing_queue.get_nowait()
                self._outgoing_queue.task_done()
        except asyncio.QueueEmpty:
            pass

    async def _deliver_message(
        self,
        message: str,
        dialog_id: int,
        send_func: Callable[[str], Any],
        queries: MessageQueries,
    ) -> bool:
        """
        Deliver single message with typing simulation and persistence.

        Args:
            message: Message text
            dialog_id: Dialog ID for persistence
            send_func: Function to send message
            queries: Message queries instance (injected)

        Returns:
            True if successful
        """
        try:
            # Add typing delay based on message length
            await asyncio.sleep(TYPING_DELAY + len(message) * CHAR_DELAY)

            # Send message
            await send_func(message)

            # Only store in DB after successful delivery
            if dialog_id > 0:
                await queries.add_message(
                    dialog_id=dialog_id,
                    text=message,
                    direction=MessageDirection.OUT,
                )
            return True

        except asyncio.CancelledError:
            logger.info("Message delivery interrupted")
            return False
        except Exception as e:
            logger.error(f"Failed to deliver message: {e}")
            return False

    @with_queries(MessageQueries)
    async def deliver_messages(
        self,
        dialog_id: int,
        messages: List[str],
        send_func: Callable[[str], Any],
        queries: MessageQueries,
    ) -> DeliveryResult:
        """
        Deliver messages with proper delays and persistence.

        Args:
            dialog_id: Dialog ID
            messages: Messages to deliver
            send_func: Function to send message
            queries: Message queries instance (injected)

        Returns:
            DeliveryResult with delivery status
        """
        try:
            async with self._lock:
                # Cancel any ongoing delivery
                if (
                    self._current_delivery_task
                    and not self._current_delivery_task.done()
                ):
                    self._current_delivery_task.cancel()
                    try:
                        await self._current_delivery_task
                    except asyncio.CancelledError:
                        pass
                    self._current_delivery_task = None

                # Clear any pending outgoing messages
                await self._clear_outgoing_queue()

                # Add new messages to queue
                for message in messages:
                    try:
                        self._outgoing_queue.put_nowait(message)
                    except asyncio.QueueFull:
                        # Remove oldest message if queue is full
                        try:
                            self._outgoing_queue.get_nowait()
                            self._outgoing_queue.task_done()
                            self._outgoing_queue.put_nowait(message)
                        except asyncio.QueueEmpty:
                            pass

                # Create new delivery task
                async def delivery_task():
                    success = True
                    while not self._outgoing_queue.empty():
                        try:
                            message = self._outgoing_queue.get_nowait()
                            if not await self._deliver_message(
                                message=message,
                                dialog_id=dialog_id,
                                send_func=send_func,
                                queries=queries,
                            ):
                                success = False
                            self._outgoing_queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                    return success

                self._current_delivery_task = asyncio.create_task(delivery_task())
                success = await self._current_delivery_task
                self._current_delivery_task = None

                return DeliveryResult(success=success)

        except Exception as e:
            logger.error(f"Message delivery failed: {e}", exc_info=True)
            if self._current_delivery_task:
                self._current_delivery_task.cancel()
                self._current_delivery_task = None
            return DeliveryResult(success=False, error=str(e))

    def interrupt_delivery(self) -> None:
        """Interrupt current message delivery."""
        if self._current_delivery_task and not self._current_delivery_task.done():
            self._current_delivery_task.cancel()
