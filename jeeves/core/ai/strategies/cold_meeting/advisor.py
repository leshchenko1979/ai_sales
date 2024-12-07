"""Sales conversation advisor."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from infrastructure.config import DEFAULT_AI_PROVIDER

from ...formatter import PromptFormatter
from ...providers.base import AIProvider

logger = logging.getLogger(__name__)


class SalesAdvisor:
    """Provides conversation analysis and advice."""

    def __init__(
        self, provider: Optional[AIProvider] = None, prompts_path: Optional[Path] = None
    ):
        """Initialize advisor."""
        self.provider = provider or AIProvider.create(DEFAULT_AI_PROVIDER)
        self.prompt_formatter = PromptFormatter(prompts_path=prompts_path)

    async def get_tip(
        self, dialog_history: List[Dict[str, str]]
    ) -> Tuple[str, str, int, int]:
        """
        Get advice for the current conversation state.

        Args:
            dialog_history: List of message dictionaries

        Returns:
            Tuple of (status, reason, warmth level, stage, advice)

        Raises:
            ValueError: If dialog history is malformed
            PromptError: If there are issues with prompt formatting
        """
        try:
            # Format dialog history for advisor
            formatted_history = self.prompt_formatter.format_dialog_history(
                dialog_history
            )
            messages = [
                {"role": "system", "content": self.prompt_formatter.advisor_prompt},
                {"role": "user", "content": formatted_history},
            ]

            # Get advice from AI
            response = await self.provider.generate_response(messages)
            return self._parse_advisor_response(response)

        except Exception as e:
            logger.error(f"Failed to get advisor tip: {e}")
            # Return default values if advice generation fails
            return "neutral", "Failed to analyze conversation", 5, 1

    def _parse_advisor_response(self, response: str) -> Tuple[str, str, int, int]:
        """
        Parse advisor response into components.

        Args:
            response: Raw response from advisor

        Returns:
            Tuple of (status, reason, warmth level, stage, advice)

        Raises:
            ValueError: If response format is invalid
        """
        try:
            # Split response into lines and extract components
            lines = [line.strip() for line in response.split("\n") if line.strip()]

            logger.debug(f"Raw advisor response:\n{response}")

            # Initialize default values
            status = ""
            reason = ""
            warmth = 5  # Default values
            stage = 1
            advice = ""
            current_section = None

            for line in lines:
                # Remove markdown formatting
                line = line.replace("**", "").strip()

                if line.startswith("STATUS:"):
                    status = line.replace("STATUS:", "").strip().lower()
                elif line.startswith("STAGE:"):
                    try:
                        stage = int(
                            line.replace("STAGE:", "").strip().split()[0]
                        )  # Take first number
                    except ValueError:
                        stage = 1
                elif line.startswith("WARMTH:"):
                    try:
                        # Extract first number from string like "WARMTH: 2 (Прохладный)"
                        warmth_text = line.replace("WARMTH:", "").strip()
                        warmth = int(
                            next(num for num in warmth_text.split() if num.isdigit())
                        )
                    except (ValueError, StopIteration):
                        warmth = 5
                elif line.startswith("REASON:"):
                    current_section = "reason"
                    reason_line = line.replace("REASON:", "").strip()
                    if reason_line:  # If there's text on the same line
                        reason = reason_line
                elif line.startswith("ADVICE:"):
                    current_section = "advice"
                    advice_line = line.replace("ADVICE:", "").strip()
                    if advice_line:  # If there's text on the same line
                        advice = advice_line
                elif line.startswith("-") and current_section:  # Process bullet points
                    line_content = line.replace("-", "").strip()
                    if current_section == "reason" and not reason:
                        reason = line_content
                    elif current_section == "advice" and not advice:
                        advice = line_content

            if not all([status, reason, advice]):
                logger.error(
                    f"Invalid advisor response format. Missing fields:\nStatus: {status}\nReason: {reason}\nAdvice: {advice}\nResponse:\n{response}"
                )
                raise ValueError("Missing required fields in advisor response")

            logger.debug(
                f"Parsed advisor response - Status: {status}, Stage: {stage}, Warmth: {warmth}, Reason: {reason}, Advice: {advice}"
            )
            return status, reason, warmth, stage, advice

        except Exception as e:
            logger.error(
                f"Failed to parse advisor response: {e}\nFull response:\n{response}"
            )
            return "neutral", str(e), 5, 1, ""
