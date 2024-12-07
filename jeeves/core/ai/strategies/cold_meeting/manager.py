"""AI-powered sales response generation."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from infrastructure.config import DEFAULT_AI_PROVIDER

from ...formatter import PromptFormatter
from ...providers.base import AIProvider

logger = logging.getLogger(__name__)


class SalesManager:
    """Generates AI-powered sales responses."""

    def __init__(
        self, provider: Optional[AIProvider] = None, prompts_path: Optional[Path] = None
    ):
        """
        Initialize sales manager.

        Args:
            provider: Optional AI provider instance. If not provided, uses default provider.
            prompts_path: Optional path to prompts file. If not provided, uses default path.
        """
        self.provider = provider or AIProvider.create(DEFAULT_AI_PROVIDER)
        self.prompt_formatter = PromptFormatter(prompts_path=prompts_path)

    async def get_response(
        self,
        dialog_history: List[Dict[str, str]],
        status: str,
        warmth: int,
        reason: str,
        advice: str,
        stage: int,
    ) -> str:
        """
        Generate sales response based on conversation context.

        Args:
            dialog_history: Complete dialog history
            status: Current conversation status
            warmth: Warmth level (1-10)
            reason: Reason for current status
            advice: Advice from advisor
            stage: Current conversation stage

        Returns:
            Generated sales response text

        Raises:
            ValueError: If dialog history is malformed
            PromptError: If there are issues with prompt formatting
            RuntimeError: If API request fails
        """
        try:
            # Get all client messages after the last bot message
            last_messages = []
            for msg in reversed(dialog_history):
                if msg["direction"] == "out":
                    break
                if msg["direction"] == "in":
                    last_messages.append(msg["text"])
            last_message = "\n".join(reversed(last_messages)) or ""

            # Format prompt for sales response
            prompt = self.prompt_formatter.format_manager_prompt(
                dialog_history=dialog_history,
                last_message=last_message,
                stage=stage,
                warmth=warmth,
                advice=advice,
            )

            # Generate response
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": last_message},
            ]
            return await self.provider.generate_response(messages)

        except Exception as e:
            logger.error(f"Failed to generate response: {e}", exc_info=True)
            raise

    async def generate_initial_message(self) -> str:
        """
        Generate initial sales greeting.

        Returns:
            Initial greeting text

        Raises:
            PromptError: If there are issues with prompt formatting
            RuntimeError: If API request fails
        """
        try:
            prompt = self.prompt_formatter.format_initial_prompt()
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Start conversation"},
            ]
            return await self.provider.generate_response(messages)

        except Exception as e:
            logger.error(f"Failed to generate initial message: {e}", exc_info=True)
            raise

    async def generate_farewell_message(
        self, dialog_history: List[Dict[str, str]]
    ) -> str:
        """
        Generate farewell message with potential next steps.

        Args:
            dialog_history: Complete dialog history

        Returns:
            Farewell message text with next steps

        Raises:
            ValueError: If dialog history is malformed
            PromptError: If there are issues with prompt formatting
            RuntimeError: If API request fails
        """
        try:
            formatted_history = self.prompt_formatter.format_dialog_history(
                dialog_history
            )
            prompt = self.prompt_formatter.format_farewell_prompt(formatted_history)
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate farewell message"},
            ]
            return await self.provider.generate_response(messages)

        except Exception as e:
            logger.error(f"Failed to generate farewell message: {e}", exc_info=True)
            raise
