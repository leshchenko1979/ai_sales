"""PostHog integration module."""

import logging
import os
from typing import Any, Dict, Optional

from posthog import Posthog

logger = logging.getLogger(__name__)


class PosthogClient:
    """PostHog client for event tracking."""

    def __init__(self) -> None:
        """Initialize PostHog client."""
        api_key = os.getenv("POSTHOG_PROJECT_API_KEY")
        host = os.getenv("POSTHOG_HOST", "https://eu.i.posthog.com")

        if not api_key:
            raise ValueError("POSTHOG_PROJECT_API_KEY environment variable is not set")

        self.client = Posthog(project_api_key=api_key, host=host)

    def track_message(
        self,
        dialog_id: int = -1,
        campaign_id: int = -1,
        company_id: int = -1,
        account_id: int = -1,
        direction: str = "",
        content: str = "",
        dialog_stage: str = "",
        dialog_status: str = "",
        account_data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        telegram_id: Optional[int] = None,
    ) -> None:
        """Track message event in PostHog.

        Args:
            dialog_id: Dialog ID, defaults to -1 for test dialogs
            campaign_id: Campaign ID, defaults to -1 for test campaigns
            company_id: Company ID, defaults to -1 for test companies
            account_id: Account ID, defaults to -1 for test accounts
            direction: Message direction (inbound/outbound)
            content: Full message content
            dialog_stage: Current dialog stage
            dialog_status: Current dialog status
            account_data: Account metadata like username, names, bio, photo
            timestamp: Message timestamp
            telegram_id: Telegram user ID
        """
        try:
            event_data = {
                "dialog_id": dialog_id,
                "campaign_id": campaign_id,
                "company_id": company_id,
                "account_id": account_id,
                "direction": direction,
                "content": content,
                "dialog_stage": dialog_stage,
                "dialog_status": dialog_status,
                "telegram_id": telegram_id,
            }

            if account_data:
                event_data.update(account_data)

            self.client.capture(
                distinct_id=str(dialog_id),
                event="message",
                properties=event_data,
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"Failed to track message in PostHog: {e}", exc_info=True)
