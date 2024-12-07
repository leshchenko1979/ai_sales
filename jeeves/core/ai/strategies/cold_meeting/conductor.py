"""Cold meeting dialog conductor."""

import asyncio
import contextlib
import logging
from typing import List, Optional, Set, Tuple

from core.db.decorators import with_queries
from core.messaging.base import BaseDialogConductor, DialogStrategyType
from core.messaging.delivery import DeliveryInterrupted
from core.messaging.models import DialogStatus
from core.messaging.queries import DialogQueries, MessageQueries

from .advisor import SalesAdvisor
from .manager import SalesManager

logger = logging.getLogger(__name__)


class ColdMeetingConductor(BaseDialogConductor):
    """Conductor for cold meeting outreach strategy."""

    strategy_type = DialogStrategyType.COLD_MEETING

    def __init__(self, *args, **kwargs):
        """Initialize cold meeting conductor."""
        super().__init__(*args, **kwargs)

        # Initialize AI components with prompts path
        self.sales = SalesManager(prompts_path=self.prompts_path)
        self.advisor = SalesAdvisor(
            provider=self.sales.provider, prompts_path=self.prompts_path
        )

        self._ai_task: Optional[asyncio.Task] = None
        self._responded_messages: Set[str] = set()

    @with_queries((DialogQueries, MessageQueries))
    async def start_dialog(
        self,
        dialog_queries: DialogQueries,
        message_queries: MessageQueries,
    ) -> None:
        """Start new dialog with cold meeting approach."""
        try:
            response = await self.sales.generate_initial_message()
            split_messages = self.message_delivery.split_messages(response)

            delivery_result = await self.message_delivery.deliver_messages(
                dialog_id=self.dialog_id,
                messages=split_messages,
                send_func=self.send_func,
            )

            if delivery_result.success:
                for msg in split_messages:
                    self._history.append(
                        {
                            "direction": "out",
                            "text": msg,
                            "status": DialogStatus.active,
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

    @with_queries((DialogQueries, MessageQueries))
    async def handle_message(
        self,
        message: str,
        dialog_queries: DialogQueries,
        message_queries: MessageQueries,
    ) -> Tuple[bool, Optional[str]]:
        """Handle message in cold meeting context."""
        self.posthog.track_message(
            dialog_id=self.dialog_id,
            direction="in",
            content=message,
            dialog_stage=getattr(self.advisor, "current_stage", ""),
            dialog_status=self.get_current_status(),
            telegram_id=self.telegram_id,
        )

        self._history.append({"direction": "in", "text": message})

        try:
            await self._cancel_ongoing_tasks()
            await self._add_to_message_queue(message)

            self._is_processing = True
            self._processing_task = asyncio.create_task(self._process_message_queue())
            return await self._processing_task

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
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._ai_task = None
        self._processing_task = None

    async def _process_message_queue(self):
        """Process messages from the queue."""
        messages = await self._collect_queue_messages()
        if not messages:
            return False, None

        try:
            response_data = await self._get_ai_response()
            await self._deliver_response(response_data)

            status = response_data[0]
            return (True, None) if self._is_dialog_complete(status) else (False, None)

        except asyncio.CancelledError:
            raise
        except DeliveryInterrupted:
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
                    dialog_id=self.dialog_id,
                    messages=[chunk],
                    send_func=self.send_func,
                )

                if not delivery_result.success:
                    if delivery_result.error:
                        raise RuntimeError(
                            f"Message delivery failed: {delivery_result.error}"
                        )
                    return

                self.posthog.track_message(
                    dialog_id=self.dialog_id,
                    direction="out",
                    content=chunk,
                    dialog_stage=getattr(self.advisor, "current_stage", ""),
                    dialog_status=status,
                    telegram_id=self.telegram_id,
                )

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

    def _handle_cancellation(self) -> Tuple[bool, Optional[str]]:
        """Handle cancellation of message processing."""
        if len(self._history) >= 2 and self._history[-1]["direction"] == "out":
            logger.info("Dialog completed before shutdown")
            return True, None
        logger.info("Message processing cancelled - likely due to shutdown")
        return False, "Обработка сообщения прервана из-за завершения работы бота"
