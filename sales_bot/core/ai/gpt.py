"""GPT integration module."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import aiohttp
import yaml
from infrastructure.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

API_BASE = "https://openrouter.ai/api/v1"
DIRECTION_MAPPING = {"in": "Клиент", "out": "Бот"}

# Load prompts from YAML
PROMPTS_PATH = Path(__file__).parent / "prompts" / "sales.yaml"
logger.info(f"Loading prompts from: {PROMPTS_PATH}")
try:
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        PROMPTS = yaml.safe_load(f)
    logger.info(f"Available top-level keys: {list(PROMPTS.keys())}")
except Exception as e:
    logger.error(f"Error loading prompts: {e}", exc_info=True)
    PROMPTS = {}


class OpenRouterClient:
    """Base client for OpenRouter API interactions."""

    def __init__(self):
        """Initialize OpenRouter client."""
        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

    async def make_request(self, messages: List[dict]) -> Optional[str]:
        """Make request to OpenRouter API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{API_BASE}/chat/completions",
                    headers=self.headers,
                    json={"model": OPENROUTER_MODEL, "messages": messages},
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"API error: {error}")
                        return None

                    data = await response.json()
                    return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Error making request: {e}", exc_info=True)
            return None


class PromptFormatter:
    """Handles prompt formatting and management."""

    def __init__(self):
        """Initialize prompt formatter with system prompts."""
        self.advisor_prompt = self.format_system_prompt(
            PROMPTS["roles"]["advisor"]["prompts"]["system"]
        )
        self.manager_prompt = self.format_system_prompt(
            PROMPTS["roles"]["manager"]["prompts"]["system"]
        )

    def format_system_prompt(self, template: str) -> str:
        """Format system prompt with variables."""
        return template.format(
            company_name=PROMPTS["company"]["name"],
            company_description=PROMPTS["company"]["description"],
            company_history=PROMPTS["company"]["history"],
            product_description=PROMPTS["product"]["description"],
            product_benefits=PROMPTS["product"]["benefits"],
            qualification_criteria=PROMPTS["product"]["qualification_criteria"],
            cold_messaging_techniques=PROMPTS["cold_messaging_techniques"],
            conversation_plan=PROMPTS["conversation_plan"],
            human_like_behavior=PROMPTS["human_like_behavior"],
            style_adjustment=PROMPTS["style_adjustment"],
        )

    def format_dialog_history(self, dialog_history: List[dict]) -> str:
        """Format dialog history into a readable string.

        Args:
            dialog_history: List of message dictionaries
            with 'direction' and 'text' keys

        Returns:
            Formatted dialog history as string
        """
        if not dialog_history:
            return "История диалога пуста"

        formatted_messages = []
        for msg in dialog_history:
            role = DIRECTION_MAPPING.get(msg["direction"], "Unknown")
            text = msg["text"].strip()
            formatted_messages.append(f"{role}: {text}")

        return "\n".join(formatted_messages)

    def format_manager_prompt(
        self,
        dialog_history: List[dict],
        last_message: str,
        stage: int,
        warmth: int,
        advice: str,
    ) -> str:
        """Format manager user prompt."""
        return PROMPTS["roles"]["manager"]["prompts"]["user"].format(
            dialog_history=self.format_dialog_history(dialog_history),
            last_message=last_message,
            stage=f"Этап {stage}",
            warmth=f"Уровень {warmth}",
            advisor_tip=f"Совет: {advice}",
        )


class Advisor(OpenRouterClient):
    """Sales advisor that analyzes conversations and provides guidance."""

    def __init__(self):
        """Initialize advisor."""
        super().__init__()
        self.prompt_formatter = PromptFormatter()

    async def get_tip(
        self, dialog_history: List[dict]
    ) -> Tuple[str, int, str, str, int]:
        """Get advice for the current conversation state."""
        try:
            formatted_history = self.prompt_formatter.format_dialog_history(
                dialog_history
            )
            messages = [
                {"role": "system", "content": self.prompt_formatter.advisor_prompt},
                {"role": "user", "content": f"История диалога:\n{formatted_history}"},
            ]

            response = await self.make_request(messages)
            if not response:
                return "IN_PROGRESS", 3, "Ошибка API", "Продолжай диалог", 0

            return self._parse_advisor_response(response)

        except Exception as e:
            logger.error(f"Error getting advisor tip: {e}", exc_info=True)
            return "IN_PROGRESS", 3, "Ошибка", "Продолжай диалог", 0

    def _parse_advisor_response(self, response: str) -> Tuple[str, int, str, str, int]:
        """Parse advisor response into components."""
        status = "IN_PROGRESS"
        warmth = 3
        stage = 0
        reason = ""
        advice = ""

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("STATUS:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("WARMTH:"):
                try:
                    warmth = int(line.split(":", 1)[1].strip())
                except ValueError:
                    warmth = 3
            elif line.startswith("STAGE:"):
                try:
                    stage = int(line.split(":", 1)[1].strip())
                except ValueError:
                    stage = 0
            elif line.startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()
            elif line.startswith("ADVICE:"):
                advice = line.split(":", 1)[1].strip()

        return status, warmth, reason, advice, stage


class SalesManager(OpenRouterClient):
    """Sales manager that conducts conversations with clients."""

    def __init__(self):
        """Initialize sales manager."""
        super().__init__()
        self.prompt_formatter = PromptFormatter()

    async def get_response(
        self,
        dialog_history: List[dict],
        status: str,
        warmth: int,
        reason: str,
        advice: str,
        stage: int,
    ) -> str:
        """Generate response to client message."""
        try:
            last_message = dialog_history[-1]["text"] if dialog_history else ""
            messages = [
                {"role": "system", "content": self.prompt_formatter.manager_prompt},
                {
                    "role": "user",
                    "content": self.prompt_formatter.format_manager_prompt(
                        dialog_history=dialog_history,
                        last_message=last_message,
                        stage=stage,
                        warmth=warmth,
                        advice=advice,
                    ),
                },
            ]

            response = await self.make_request(messages)
            if not response:
                return "Извините, произошла ошибка. Попробуйте позже."

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            return "Извините, произошла ошибка. Попробуйте позже."

    async def generate_initial_message(self) -> str:
        """Generate first message of the conversation."""
        try:
            messages = [
                {"role": "system", "content": self.prompt_formatter.manager_prompt},
                {
                    "role": "user",
                    "content": "Сгенерируй первое сообщение для холодного контакта.",
                },
            ]
            return await self.make_request(messages)

        except Exception as e:
            logger.error(f"Error generating initial message: {e}", exc_info=True)
            return (
                "Здравствуйте! Я представляю компанию, которая помогает в инвестициях."
            )


class GPTClient:
    """Main client that orchestrates the sales conversation."""

    def __init__(self):
        """Initialize GPT client with advisor and manager."""
        self.advisor = Advisor()
        self.manager = SalesManager()

    async def get_advisor_tip(
        self, dialog_history: List[dict]
    ) -> Tuple[str, int, str, str, int]:
        """Get tip from advisor."""
        return await self.advisor.get_tip(dialog_history)

    async def get_manager_response(
        self,
        dialog_history: List[dict],
        status: str,
        warmth: int,
        reason: str,
        advice: str,
        stage: int,
    ) -> str:
        """Get response from manager."""
        return await self.manager.get_response(
            dialog_history, status, warmth, reason, advice, stage
        )

    async def generate_initial_message(self) -> str:
        """Generate first message."""
        return await self.manager.generate_initial_message()

    async def generate_farewell_message(self, dialog_history: List[dict]) -> str:
        """Generate farewell message based on conversation context."""
        try:
            history_text = self.prompt_formatter.format_dialog_history(dialog_history)

            prompt = """Сгенерируй короткое прощальное сообщение для завершения диалога.

История диалога:
{history_text}
"""
            messages = [
                {"role": "system", "content": self.prompt_formatter.manager_prompt},
                {"role": "user", "text": prompt.format(history_text=history_text)},
            ]

            response = await self.manager.make_request(messages)
            if not response:
                return "Всего доброго! Если у вас появятся вопросы, обращайтесь."

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating farewell message: {e}", exc_info=True)
            return "Всего доброго! Если у вас появятся вопросы, обращайтесь."
