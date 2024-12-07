"""Dialog conductor module."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

from core.messaging.base import BaseDialogConductor, DialogStrategyType
from core.messaging.queries import DialogQueries, MessageQueries

logger = logging.getLogger(__name__)

# Constants
MAX_QUEUE_SIZE = 10  # maximum number of pending messages


class DialogConductorFactory:
    """Factory for creating dialog conductors."""

    _conductors: Dict[DialogStrategyType, Type[BaseDialogConductor]] = {}

    @classmethod
    def register_conductor(
        cls,
        strategy_type: DialogStrategyType,
        conductor_class: Type[BaseDialogConductor],
    ) -> None:
        """Register conductor class for strategy type."""
        cls._conductors[strategy_type] = conductor_class
        logger.debug(
            f"Registered conductor {conductor_class.__name__} for strategy {strategy_type}"
        )

    @classmethod
    def create_conductor(
        cls,
        strategy_type: DialogStrategyType,
        send_func: Callable[[str], Any],
        dialog_id: Optional[int] = None,
        dialog_queries: Optional[DialogQueries] = None,
        message_queries: Optional[MessageQueries] = None,
        telegram_id: Optional[int] = None,
    ) -> BaseDialogConductor:
        """Create conductor for specified strategy type."""
        logger.info(f"Creating conductor for strategy: {strategy_type}")

        # Lazy import to avoid circular dependencies
        from core.ai.strategies.cold_meeting.conductor import ColdMeetingConductor

        # Register conductors if not already registered
        if not cls._conductors:
            logger.debug("No conductors registered, registering defaults")
            cls.register_conductor(
                DialogStrategyType.COLD_MEETING, ColdMeetingConductor
            )

        if strategy_type not in cls._conductors:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        # Get prompts path for strategy
        prompts_path = (
            Path(__file__).parent.parent.parent
            / "core"
            / "ai"
            / "strategies"
            / strategy_type.value
            / "prompts.yaml"
        )
        logger.info(f"Looking for prompts at: {prompts_path}")

        if not prompts_path.exists():
            logger.error(f"Prompts file not found at: {prompts_path}")
            raise ValueError(
                f"Prompts not found for strategy: {strategy_type} at {prompts_path}"
            )

        logger.debug(f"Creating conductor instance with prompts from: {prompts_path}")
        conductor_class = cls._conductors[strategy_type]
        return conductor_class(
            send_func=send_func,
            dialog_id=dialog_id,
            dialog_queries=dialog_queries,
            message_queries=message_queries,
            prompts_path=prompts_path,
            telegram_id=telegram_id,
        )
