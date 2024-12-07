"""Base classes for dialog conductors."""

import asyncio
import contextlib
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.db.decorators import with_queries
from core.messaging.delivery import MessageDelivery
from core.messaging.models import DialogStatus
from core.messaging.queries import DialogQueries, MessageQueries
from infrastructure.posthog import PosthogClient

logger = logging.getLogger(__name__)

# Constants
MAX_QUEUE_SIZE = 10  # maximum number of pending messages


class DialogStrategyType(str, Enum):
    """Types of dialog strategies."""

    COLD_MEETING = "cold_meeting"  # Cold outreach for meeting
    SURVEY = "survey"  # Customer surveys
    SALES = "sales"  # Product/service sales
    SUPPORT = "support"  # Customer support
    FOLLOW_UP = "follow_up"  # Follow-up after meeting/demo


class BaseDialogConductor:
    """Base class for dialog conductors that implement specific strategies."""

    strategy_type: DialogStrategyType
    prompts_path: Path

    def __init__(
        self,
        send_func: Callable[[str], Any],
        dialog_id: Optional[int] = None,
        dialog_queries: Optional[DialogQueries] = None,
        message_queries: Optional[MessageQueries] = None,
        prompts_path: Optional[Path] = None,
        telegram_id: Optional[int] = None,
    ):
        """Initialize conductor."""
        self.send_func = send_func
        self.dialog_id = dialog_id or 0  # Set default to 0 if None
        self.telegram_id = telegram_id
        self.prompts_path = prompts_path
        self.message_delivery = MessageDelivery()
        self._history: List[Dict[str, Union[str, DialogStatus]]] = []
        self.posthog = PosthogClient()

        # Message queue state
        self._message_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self._processing_task: Optional[asyncio.Task] = None
        self._is_processing = False

    @with_queries((DialogQueries, MessageQueries))
    async def start_dialog(
        self, dialog_queries: DialogQueries, message_queries: MessageQueries
    ) -> None:
        """Start new dialog and send initial message."""
        raise NotImplementedError

    @with_queries((DialogQueries, MessageQueries))
    async def handle_message(
        self,
        message: str,
        dialog_queries: DialogQueries,
        message_queries: MessageQueries,
    ) -> Tuple[bool, Optional[str]]:
        """Handle incoming message."""
        raise NotImplementedError

    def get_history(self) -> List[Dict[str, Union[str, DialogStatus]]]:
        """Get current dialog history."""
        return self._history.copy()

    def get_current_status(self) -> DialogStatus:
        """Get current dialog status from history."""
        if not self._history:
            return DialogStatus.active

        return next(
            (
                msg["status"]
                for msg in reversed(self._history)
                if msg.get("direction") == "out" and "status" in msg
            ),
            DialogStatus.active,
        )

    def clear_history(self) -> None:
        """Clear dialog history."""
        self._history.clear()
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()

    def set_status(self, status: DialogStatus) -> None:
        """Set dialog status manually."""
        if self._history:
            if self._history[-1]["direction"] == "out":
                self._history[-1]["status"] = status
            else:
                self._history.append(
                    {"direction": "out", "text": "Диалог остановлен", "status": status}
                )

    async def _add_to_message_queue(self, message: str):
        """Add message to queue, removing oldest if full."""
        try:
            self._message_queue.put_nowait(message)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self._message_queue.get_nowait()
                self._message_queue.task_done()
                self._message_queue.put_nowait(message)

    def _is_dialog_complete(self, status: DialogStatus) -> bool:
        """Check if dialog is complete based on status."""
        return status in [
            DialogStatus.success,
            DialogStatus.rejected,
            DialogStatus.not_qualified,
            DialogStatus.blocked,
            DialogStatus.expired,
            DialogStatus.stopped,
        ]
