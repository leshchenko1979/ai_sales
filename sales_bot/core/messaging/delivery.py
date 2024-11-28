"""Message delivery module."""

import asyncio
import logging
from typing import Any, Callable, List, Optional

from core.db.decorators import with_queries
from core.messaging.models import DeliveryOptions, DeliveryResult, MessageDirection
from core.messaging.queries import MessageQueries

logger = logging.getLogger(__name__)

# Constants
DEFAULT_TYPING_DELAY = 3  # seconds
DEFAULT_MESSAGE_DELAY = 1  # seconds


class MessageDelivery:
    """Handles message delivery and formatting."""

    def __init__(self, options: Optional[DeliveryOptions] = None):
        """
        Initialize delivery manager.

        Args:
            options: Optional delivery options
        """
        self.options = options or DeliveryOptions()
        self._current_delivery_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def split_messages(self, text: str) -> List[str]:
        """
        Split message into deliverable chunks.

        Args:
            text: Text to split

        Returns:
            List of message chunks
        """
        # Split by double newline
        chunks = text.split("\n\n")

        # Filter out empty chunks and strip whitespace
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def interrupt_delivery(self) -> None:
        """Interrupt current message delivery if any."""
        if self._current_delivery_task and not self._current_delivery_task.done():
            self._current_delivery_task.cancel()

    async def _deliver_messages_impl(
        self,
        messages: List[str],
        send_func: Callable[[str], Any],
        options: DeliveryOptions,
    ) -> DeliveryResult:
        """
        Internal implementation of message delivery.

        Args:
            messages: Messages to deliver
            send_func: Function to send message
            options: Delivery options

        Returns:
            DeliveryResult with delivery status
        """
        try:
            for i, message in enumerate(messages):
                if options.simulate_typing:
                    # Simulate typing delay proportional to message length
                    typing_time = min(
                        len(message) * 0.05, options.typing_delay  # 50ms per character
                    )
                    await asyncio.sleep(typing_time)

                # Send message
                await send_func(message)

                # Add delay between messages if not the last one
                if i < len(messages) - 1:
                    await asyncio.sleep(options.message_delay)

            return DeliveryResult(success=True)

        except asyncio.CancelledError:
            logger.info("Message delivery interrupted")
            return DeliveryResult(
                success=False, error="Message delivery interrupted by user"
            )
        except Exception as e:
            logger.error(f"Message delivery failed: {e}", exc_info=True)
            return DeliveryResult(success=False, error=str(e))

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

                # Store messages in DB if dialog is persistent
                if dialog_id > 0:
                    for message in messages:
                        await queries.add_message(
                            dialog_id=dialog_id,
                            text=message,
                            direction=MessageDirection.OUT,
                        )

                # Start new delivery
                delivery_result = await self._deliver_messages_impl(
                    messages=messages,
                    send_func=send_func,
                    options=self.options,
                )

                return delivery_result

        except Exception as e:
            logger.error(f"Message delivery failed: {e}", exc_info=True)
            return DeliveryResult(success=False, error=str(e))
