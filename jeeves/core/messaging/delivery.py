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


class DeliveryInterrupted(RuntimeError):
    """Raised when message delivery is interrupted."""


class MessageDelivery:
    """Handles message delivery with realistic typing delays."""

    def __init__(self):
        """Initialize delivery options and state."""
        self._lock = asyncio.Lock()
        self._outgoing_queue = asyncio.Queue(maxsize=MAX_OUTGOING_QUEUE_SIZE)
        self._current_delivery_task: Optional[asyncio.Task] = None

    @with_queries(MessageQueries)
    async def deliver_messages(
        self,
        dialog_id: Optional[int],
        messages: List[str],
        send_func: Callable[[str], Any],
        queries: MessageQueries,
    ) -> DeliveryResult:
        """Deliver messages with proper delays and persistence."""
        try:
            async with self._lock:
                await self._cancel_current_delivery()
                await self._clear_outgoing_queue()
                await self._queue_new_messages(messages)

                success = await self._process_message_queue(
                    dialog_id=dialog_id or 0, send_func=send_func, queries=queries
                )
                return DeliveryResult(success=success)

        except asyncio.CancelledError:
            logger.info("Message delivery interrupted")
            raise DeliveryInterrupted()
        except Exception as e:
            logger.error(f"Message delivery failed: {e}", exc_info=True)
            await self._cancel_current_delivery()
            return DeliveryResult(success=False, error=str(e))

    async def _cancel_current_delivery(self) -> None:
        """Cancel current delivery task if exists."""
        if self._current_delivery_task and not self._current_delivery_task.done():
            self._current_delivery_task.cancel()
            try:
                await self._current_delivery_task
            except asyncio.CancelledError:
                pass
            self._current_delivery_task = None

    async def _queue_new_messages(self, messages: List[str]) -> None:
        """Add new messages to the outgoing queue."""
        for message in messages:
            try:
                self._outgoing_queue.put_nowait(message)
            except asyncio.QueueFull:
                await self._handle_queue_full(message)

    async def _handle_queue_full(self, message: str) -> None:
        """Handle case when queue is full by removing oldest message."""
        try:
            self._outgoing_queue.get_nowait()
            self._outgoing_queue.task_done()
            self._outgoing_queue.put_nowait(message)
        except asyncio.QueueEmpty:
            pass

    async def _process_message_queue(
        self,
        dialog_id: int,
        send_func: Callable[[str], Any],
        queries: MessageQueries,
    ) -> bool:
        """Process all messages in the queue."""

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
        return success

    def interrupt_delivery(self) -> None:
        """Interrupt current message delivery."""
        if self._current_delivery_task and not self._current_delivery_task.done():
            self._current_delivery_task.cancel()

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

    async def _clear_outgoing_queue(self) -> None:
        """Clear all pending outgoing messages."""
        try:
            while True:
                self._outgoing_queue.get_nowait()
                self._outgoing_queue.task_done()
        except asyncio.QueueEmpty:
            pass

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
