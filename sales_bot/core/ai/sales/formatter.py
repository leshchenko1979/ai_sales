"""Prompt formatting and management."""

import logging
from typing import Any, Dict, List

import yaml
from infrastructure.config import PROMPTS_PATH

logger = logging.getLogger(__name__)


class PromptFormatError(Exception):
    """Raised when prompts cannot be formatted correctly."""


class PromptFormatter:
    """Handles prompt formatting and management."""

    def __init__(self):
        """Initialize prompt formatter with system prompts."""
        try:
            self.prompts = self._load_prompts()
            self.advisor_prompt = self.format_system_prompt(
                self.prompts["roles"]["advisor"]["prompts"]["system"]
            )
            self.manager_prompt = self.format_system_prompt(
                self.prompts["roles"]["manager"]["prompts"]["system"]
            )
        except Exception as e:
            raise PromptFormatError(f"Failed to format system prompts: {e}") from e

    def _load_prompts(self) -> Dict[str, Any]:
        """Load and validate prompts from YAML file."""
        try:
            with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
                prompts = yaml.safe_load(f)
        except Exception as e:
            raise PromptFormatError(
                f"Failed to load prompts from {PROMPTS_PATH}: {str(e)}"
            )

        # Validate required sections
        required_sections = ["company", "product", "market_context", "roles"]
        missing_sections = [s for s in required_sections if s not in prompts]
        if missing_sections:
            raise PromptFormatError(
                f"Missing required sections in prompts: {missing_sections}"
            )

        return prompts

    def format_system_prompt(self, template: str) -> str:
        """
        Format system prompt with variables.

        Args:
            template: Prompt template string

        Returns:
            Formatted prompt

        Raises:
            PromptFormatError: If required fields are missing or formatting fails
        """
        try:
            return template.format(
                company_name=self.prompts["company"]["name"],
                company_description=self.prompts["company"]["description"],
                company_history=self.prompts["company"]["history"],
                market_context=self.prompts["market_context"],
                product_description=self.prompts["product"]["description"],
                product_benefits=self.prompts["product"]["benefits"],
                qualification_criteria=self.prompts["product"][
                    "qualification_criteria"
                ],
                conversation_plan=self.prompts["conversation_plan"],
                cold_messaging_techniques=self.prompts["cold_messaging_techniques"],
                style_adjustment=self.prompts["style_adjustment"],
                human_like_behavior=self.prompts["human_like_behavior"],
            )
        except KeyError as e:
            raise PromptFormatError(f"Missing required field in prompt template: {e}")
        except Exception as e:
            raise PromptFormatError(f"Failed to format prompt: {e}")

    def format_initial_prompt(self) -> str:
        """
        Format prompt for initial message.

        Returns:
            Formatted initial prompt

        Raises:
            PromptFormatError: If formatting fails
        """
        try:
            template = self.prompts["roles"]["manager"]["prompts"]["initial"]
            return self.format_system_prompt(template)
        except KeyError:
            # Fallback to manager prompt if specific initial prompt not found
            return self.manager_prompt
        except Exception as e:
            raise PromptFormatError(f"Failed to format initial prompt: {e}")

    def format_farewell_prompt(self, dialog_history: str) -> str:
        """
        Format prompt for farewell message.

        Args:
            dialog_history: Formatted dialog history string

        Returns:
            Formatted farewell prompt

        Raises:
            PromptFormatError: If formatting fails
        """
        try:
            template = self.prompts["roles"]["manager"]["prompts"].get(
                "farewell", "{manager_prompt}"
            )
            prompt = template.format(
                manager_prompt=self.manager_prompt, dialog_history=dialog_history
            )
            return (
                f"{prompt}\n\n"
                f"Dialog history:\n{dialog_history}\n\n"
                "Generate a warm farewell message that summarizes the conversation "
                "and leaves the door open for future communication."
            )
        except Exception as e:
            raise PromptFormatError(f"Failed to format farewell prompt: {e}")

    def format_manager_prompt(
        self,
        dialog_history: List[Dict[str, str]],
        last_message: str,
        stage: int,
        warmth: int,
        advice: str,
    ) -> str:
        """
        Format prompt for manager with context and latest message.

        Args:
            dialog_history: Complete dialog history
            last_message: Last message from client
            stage: Current dialog stage
            warmth: Current warmth level
            advice: Advice from advisor

        Returns:
            Formatted prompt for manager

        Raises:
            PromptFormatError: If dialog history formatting fails
        """
        try:
            formatted_history = self.format_dialog_history(dialog_history)
            return (
                f"{self.manager_prompt}\n\n"
                f"Dialog history:\n{formatted_history}\n\n"
                f"Last message: {last_message}\n"
                f"Current stage: {stage}\n"
                f"Warmth level: {warmth}\n"
                f"Advisor tip: {advice}"
            )
        except Exception as e:
            raise PromptFormatError(f"Failed to format manager prompt: {e}")

    def format_dialog_history(self, dialog_history: List[Dict[str, str]]) -> str:
        """
        Format dialog history into a readable string.

        Args:
            dialog_history: List of message dictionaries with 'direction' and 'text' keys

        Returns:
            Formatted dialog history as string

        Raises:
            ValueError: If dialog history messages are malformed
        """
        DIRECTION_MAPPING = {"in": "Client", "out": "Bot"}
        formatted_messages = []

        for message in dialog_history:
            try:
                direction = message["direction"]
                text = message["text"]
                speaker = DIRECTION_MAPPING[direction]
                formatted_messages.append(f"{speaker}: {text}")
            except KeyError as e:
                raise ValueError(f"Malformed message in dialog history: {e}")
            except Exception as e:
                raise ValueError(f"Failed to format dialog history: {e}")

        return "\n".join(formatted_messages)
