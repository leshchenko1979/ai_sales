"""Dialog conductor module."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from core.ai import SalesAdvisor, SalesManager
from core.messaging.delivery import DeliveryInterrupted, MessageDelivery
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

    # 1. Основные публичные методы для управления диалогом

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

    async def handle_message(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Handle an incoming message by adding it to the message queue.
        """
        # Add message to history immediately
        self._history.append({"direction": "in", "text": message})

        try:
            await self._cancel_ongoing_tasks()
            await self._add_to_message_queue(message)

            self._is_processing = True
            self._processing_task = asyncio.create_task(self._process_message_queue())
            result = await self._processing_task

            return result

        except asyncio.CancelledError:
            return self._handle_cancellation()
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return False, str(e)
        finally:
            self._is_processing = False
            self._processing_task = None

    async def _cancel_ongoing_tasks(self):
        """Cancel any ongoing AI and processing tasks."""
        for task in [self._ai_task, self._processing_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._ai_task = None
        self._processing_task = None

    async def _add_to_message_queue(self, message: str):
        """Add message to queue, removing oldest if full."""
        try:
            self._message_queue.put_nowait(message)
        except asyncio.QueueFull:
            try:
                self._message_queue.get_nowait()
                self._message_queue.task_done()
                self._message_queue.put_nowait(message)
            except asyncio.QueueEmpty:
                pass

    async def _process_message_queue(self):
        """Process messages from the queue."""
        messages = await self._collect_queue_messages()
        if not messages:
            return False, None

        try:
            response_data = await self._get_ai_response()
            await self._deliver_response(response_data)

            status = response_data[0]  # First element is status
            if self._is_dialog_complete(status):
                return True, None

            return False, None

        except asyncio.CancelledError:
            raise
        except DeliveryInterrupted:
            # Silently handle interruption due to new message
            logger.info("Message delivery interrupted by new message")
            return False, None
        except Exception as e:
            logger.error(f"Error processing message queue: {e}", exc_info=True)
            return False, str(e)

    async def _collect_queue_messages(self) -> List[str]:
        """Collect all messages from queue."""
        messages = []
        while True:
            try:
                message = self._message_queue.get_nowait()
                messages.append(message)
                self._message_queue.task_done()
            except asyncio.QueueEmpty:
                break
        return messages

    async def _get_ai_response(self):
        """Get response from AI."""
        self._ai_task = asyncio.create_task(self.advisor.get_tip(self._history))
        try:
            status, reason, warmth, stage, advice = await self._ai_task
            response = await self.sales.get_response(
                dialog_history=self._history,
                status=status,
                warmth=warmth,
                reason=reason,
                advice=advice,
                stage=stage,
            )
            return status, response
        finally:
            self._ai_task = None

    async def _deliver_response(self, response_data):
        """Deliver response messages."""
        status, response = response_data
        split_messages = self.message_delivery.split_messages(response)

        try:
            for chunk in split_messages:
                delivery_result = await self.message_delivery.deliver_messages(
                    dialog_id=self._dialog_id,
                    messages=[chunk],
                    send_func=self._send_func,
                )

                if not delivery_result.success:
                    if delivery_result.error:
                        raise RuntimeError(
                            f"Message delivery failed: {delivery_result.error}"
                        )
                    return  # Silent return on interruption

                self._history.append(
                    {
                        "direction": "out",
                        "text": chunk,
                        "status": status,
                    }
                )
        except DeliveryInterrupted:
            logger.info("Message delivery interrupted by new message")
            return

    def _is_dialog_complete(self, status: DialogStatus) -> bool:
        """Check if dialog is complete based on status."""
        return status in [
            DialogStatus.closed,
            DialogStatus.rejected,
            DialogStatus.not_qualified,
            DialogStatus.meeting_scheduled,
        ]

    def _handle_cancellation(self) -> Tuple[bool, Optional[str]]:
        """Handle cancellation of message processing."""
        if len(self._history) >= 2 and self._history[-1]["direction"] == "out":
            logger.info("Dialog completed before shutdown")
            return True, None
        logger.info("Message processing cancelled - likely due to shutdown")
        return False, "Обработка сообщения прервана из-за завершения работы бота"

    # 2. Публичные методы для получения информации о диалоге

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

    # 3. Приватные вспомогательные методы

    def set_status(self, status: DialogStatus) -> None:
        """Set dialog status manually."""
        if self._history:
            # Add status to the last message if it's outbound
            if self._history[-1]["direction"] == "out":
                self._history[-1]["status"] = status
            else:
                # Add a system message with the new status
                self._history.append(
                    {"direction": "out", "text": "Диалог остановлен", "status": status}
                )
