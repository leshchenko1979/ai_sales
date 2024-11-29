"""Dialog conductor module."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.ai import SalesAdvisor, SalesManager
from core.messaging.delivery import MessageDelivery
from core.messaging.models import DialogStatus

logger = logging.getLogger(__name__)

# Constants
MAX_QUEUE_SIZE = 10  # maximum number of pending messages


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
        self._history: List[Dict[str, Union[str, DialogStatus]]] = []
        self._responded_messages: Set[str] = (
            set()
        )  # Track which messages have been responded to
        self._send_func = send_func
        self._dialog_id = dialog_id or 0  # Use 0 as default for non-persistent dialogs

        # Message queue state
        self._message_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self._processing_task: Optional[asyncio.Task] = None
        self._ai_task: Optional[asyncio.Task] = None
        self._is_processing = False

    async def _process_message_queue(self):
        """Process messages from the queue."""
        try:
            # Collect all messages from queue
            messages = []
            while True:
                try:
                    message = self._message_queue.get_nowait()
                    messages.append(message)
                    self._message_queue.task_done()
                except asyncio.QueueEmpty:
                    break

            if not messages:
                return False, None
            # Get AI response
            try:
                self._ai_task = asyncio.create_task(self.advisor.get_tip(self._history))
                status, reason, warmth, stage, advice = await self._ai_task

                # Generate response for combined message
                response = await self.sales.get_response(
                    dialog_history=self._history,
                    status=status,
                    warmth=warmth,
                    reason=reason,
                    advice=advice,
                    stage=stage,
                )

            except asyncio.CancelledError:
                raise

            finally:
                self._ai_task = None

            # Split response into chunks if needed
            split_messages = self.message_delivery.split_messages(response)

            # Deliver each chunk with proper delays
            for chunk in split_messages:
                delivery_result = await self.message_delivery.deliver_messages(
                    dialog_id=self._dialog_id,
                    messages=[chunk],  # Send one chunk at a time
                    send_func=self._send_func,
                )

                if delivery_result.success:
                    # Add the chunk to history with status
                    self._history.append(
                        {
                            "direction": "out",
                            "text": chunk,
                            "status": status,  # Add status to history
                        }
                    )
                else:
                    return False, delivery_result.error

            if status in [
                DialogStatus.closed,
                DialogStatus.rejected,
                DialogStatus.not_qualified,
                DialogStatus.meeting_scheduled,
            ]:
                # Dialog is complete
                return True, None

            return False, None

        except asyncio.CancelledError:
            # Let the cancellation propagate up
            raise
        except Exception as e:
            logger.error(f"Error processing message queue: {e}", exc_info=True)
            return False, str(e)

    async def handle_message(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Handle an incoming message by adding it to the message queue.

        Messages are processed in batches. If the queue is full, older messages are
        discarded to make room for new ones. Any ongoing AI response generation is
        cancelled when a new message arrives.

        Args:
            message: User message to handle

        Returns:
            Tuple[bool, Optional[str]]: (is_completed, error_message)
                - is_completed: True if dialog is complete
                - error_message: Error message if any
        """
        try:
            # Add message to history immediately
            self._history.append({"direction": "in", "text": message})

            # Cancel any ongoing AI task
            if self._ai_task and not self._ai_task.done():
                self._ai_task.cancel()
                try:
                    await self._ai_task
                except asyncio.CancelledError:
                    pass
                self._ai_task = None

            # Cancel any ongoing processing task
            if self._processing_task and not self._processing_task.done():
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
                self._processing_task = None

            # Try to add message to queue, removing oldest if full
            try:
                self._message_queue.put_nowait(message)
            except asyncio.QueueFull:
                try:
                    # Remove oldest message if queue is full
                    self._message_queue.get_nowait()
                    self._message_queue.task_done()
                    # Add new message
                    self._message_queue.put_nowait(message)
                except asyncio.QueueEmpty:
                    pass

            # Process this message
            self._is_processing = True
            self._processing_task = asyncio.create_task(self._process_message_queue())
            try:
                result = await self._processing_task
            finally:
                self._is_processing = False
                self._processing_task = None
            return result

        except asyncio.CancelledError:
            # Check if dialog was already completed
            if len(self._history) >= 2 and self._history[-1]["direction"] == "out":
                logger.info("Dialog completed before shutdown")
                return True, None
            logger.info("Message processing cancelled - likely due to shutdown")
            return False, "Обработка сообщения прервана из-за завершения работы бота"

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return False, str(e)

    async def start_dialog(self) -> None:
        """Start new dialog and send initial message."""
        try:
            # Get initial message
            response = await self.sales.generate_initial_message()

            # Split and deliver
            split_messages = self.message_delivery.split_messages(response)
            delivery_result = await self.message_delivery.deliver_messages(
                dialog_id=self._dialog_id,
                messages=split_messages,
                send_func=self._send_func,
            )

            # Only add to history if delivery was successful
            if delivery_result.success:
                for msg in split_messages:
                    self._history.append(
                        {
                            "direction": "out",
                            "text": msg,
                            "status": DialogStatus.active,  # Add initial active status
                        }
                    )
            else:
                logger.error(
                    f"Failed to deliver initial message: {delivery_result.error}"
                )
                raise RuntimeError("Failed to start dialog")

        except Exception as e:
            logger.error(f"Error starting dialog: {e}", exc_info=True)
            raise

    def get_history(self) -> List[Dict[str, Union[str, DialogStatus]]]:
        """Get current dialog history."""
        return self._history.copy()

    def get_current_status(self) -> DialogStatus:
        """Get current dialog status from history."""
        if not self._history:
            return DialogStatus.active

        # Look for the last AI response with status
        for msg in reversed(self._history):
            if msg.get("direction") == "out" and "status" in msg:
                return msg["status"]

        return DialogStatus.active

    def clear_history(self) -> None:
        """Clear dialog history and cancel any ongoing tasks."""
        self._history.clear()
        self._responded_messages.clear()
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
