"""Dialog conductor module."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.ai import SalesAdvisor, SalesManager
from core.messaging.delivery import MessageDelivery
from core.messaging.models import DeliveryResult

from .models import DialogStatus

logger = logging.getLogger(__name__)

# Constants
MESSAGE_BATCH_DELAY = 5  # seconds to wait after last message before processing


class DialogConductor:
    """Orchestrates sales dialogs."""

    def __init__(
        self, send_func: Callable[[str], Any], dialog_id: Optional[int] = None
    ):
        """
        Initialize conductor.

        Args:
            send_func: Function to send messages
            dialog_id: Optional dialog ID for message persistence
        """
        self.sales = SalesManager()
        self.advisor = SalesAdvisor(self.sales.provider)
        self.message_delivery = MessageDelivery()
        self._history: List[Dict[str, str]] = []
        self._send_func = send_func
        self._dialog_id = dialog_id or 0  # Use 0 as default for non-persistent dialogs

        # Message batching state
        self._pending_messages: List[str] = []
        self._processing_task: Optional[asyncio.Task] = None
        self._last_message_time: Optional[datetime] = None

    async def _deliver_messages(
        self, messages: List[str], error_context: str
    ) -> DeliveryResult:
        """
        Deliver messages and update history.

        Args:
            messages: List of messages to deliver
            error_context: Context for error logging

        Returns:
            DeliveryResult: Result of message delivery
        """
        try:
            task = asyncio.create_task(
                self.message_delivery.deliver_messages(
                    dialog_id=self._dialog_id,
                    messages=messages,
                    send_func=self._send_func,
                )
            )
            delivery_result = await task

            if delivery_result.success:
                # Add messages to history on success
                for msg in messages:
                    self._history.append({"direction": "out", "text": msg})
            else:
                logger.error(
                    f"Failed to deliver {error_context}: {delivery_result.error}"
                )

            return delivery_result
        except Exception as e:
            logger.error(f"Error in message delivery: {e}", exc_info=True)
            return DeliveryResult(success=False, error=str(e))

    async def _process_message_batch(self) -> Tuple[bool, Optional[str]]:
        """Process accumulated messages after delay."""
        try:
            # Wait for the batch delay
            await asyncio.sleep(MESSAGE_BATCH_DELAY)

            # Get all pending messages
            messages = self._pending_messages.copy()
            if not messages:
                return False, None

            # Clear pending messages before processing to avoid duplicates
            self._pending_messages.clear()

            # Process each message in order
            for message in messages:
                # Get advice from advisor
                status, reason, warmth, stage, advice = await self.advisor.get_tip(
                    self._history
                )

                # Generate response
                response = await self.sales.get_response(
                    dialog_history=self._history,
                    status=status,
                    warmth=warmth,
                    reason=reason,
                    advice=advice,
                    stage=stage,
                )

                # Split and deliver response
                split_messages = self.message_delivery.split_messages(response)
                delivery_result = await self._deliver_messages(
                    split_messages, "response messages"
                )

                if not delivery_result.success:
                    return False, delivery_result.error

                if status == DialogStatus.closed:
                    # Send farewell message if dialog ended
                    farewell = await self.sales.generate_farewell_message(self._history)
                    farewell_result = await self._deliver_messages(
                        [farewell], "farewell message"
                    )
                    if not farewell_result.success:
                        return (
                            True,
                            f"Failed to deliver farewell: {farewell_result.error}",
                        )
                    return (
                        True,
                        None,
                    )  # Return None as error since this is normal completion

            return False, None

        except asyncio.CancelledError:
            # Let the cancellation propagate up to handle_message
            raise

        except Exception as e:
            logger.error(f"Error processing message batch: {e}", exc_info=True)
            return False, str(e)

    async def handle_message(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Handle an incoming message, adding it to the current batch for delayed processing.

        The message will be accumulated with other recent messages and processed together
        after a short delay. This creates a more natural conversation flow by allowing
        the bot to "read" multiple messages before responding.

        When a new message arrives, any ongoing message delivery is interrupted to maintain
        natural conversation flow.

        Args:
            message: User message to handle

        Returns:
            Tuple[bool, Optional[str]]: (is_completed, error_message)
                - is_completed: True if dialog is complete
                - error_message: Error message if any
        """
        try:
            # Add message to history
            self._history.append({"direction": "in", "text": message})

            # Add to pending messages
            self._pending_messages.append(message)
            self._last_message_time = datetime.now()

            # Cancel any existing processing
            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling task

            # Create and await new processing task
            self._processing_task = asyncio.create_task(self._process_message_batch())
            result = await self._processing_task

            # Clear task reference after completion
            self._processing_task = None
            return result

        except asyncio.CancelledError:
            # Only log shutdown message if task was cancelled externally
            if self._processing_task is not None:
                logger.info("Message processing cancelled - likely due to shutdown")
                return (
                    False,
                    "Обработка сообщения прервана из-за завершения работы бота",
                )
            raise  # Re-raise if it's an internal cancellation

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return False, str(e)

    async def start_dialog(self) -> None:
        """Start new dialog and send initial message."""
        self._history = []
        self._pending_messages = []
        initial_message = await self.sales.generate_initial_message()

        # Split and deliver initial message
        messages = self.message_delivery.split_messages(initial_message)
        await self._deliver_messages(messages, "initial messages")

    def get_history(self) -> List[Dict[str, str]]:
        """Get current dialog history."""
        return self._history.copy()

    async def clear_history(self) -> None:
        """Clear dialog history and cancel any ongoing tasks."""
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        self._history.clear()
        self._pending_messages.clear()
        self._last_message_time = None
        self.message_delivery.interrupt_delivery()
