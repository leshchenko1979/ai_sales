"""OpenRouter AI provider implementation."""

import logging
from typing import Any, Dict, List

import aiohttp
from infrastructure.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

from .base import AIProvider

logger = logging.getLogger(__name__)

API_BASE = "https://openrouter.ai/api/v1"


class OpenRouterProvider(AIProvider):
    """OpenRouter implementation."""

    def __init__(self):
        """Initialize OpenRouter client."""
        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

    async def generate_response(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate response using OpenRouter API.

        Args:
            messages: List of message dictionaries with role and content

        Returns:
            Generated response text

        Raises:
            RuntimeError: If API request fails
        """
        try:
            response = await self.make_request(messages)
            if "error" in response:
                raise RuntimeError(f"API returned error: {response['error']}")
            if "choices" not in response:
                logger.error(f"Unexpected API response format: {response}")
                raise RuntimeError("API response missing 'choices' field")
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise RuntimeError(f"Failed to generate response: {e}")

    async def make_request(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make request to OpenRouter API.

        Args:
            messages: List of message dictionaries with role and content

        Returns:
            Raw response from OpenRouter API

        Raises:
            RuntimeError: If API request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{API_BASE}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": messages,
                    },
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"API request failed with status {response.status}: {error_text}"
                        )
                    response_json = await response.json()
                    logger.debug(f"OpenRouter API response: {response_json}")
                    return response_json
        except Exception as e:
            logger.error(f"Failed to make API request: {e}")
            raise RuntimeError(f"Failed to make API request: {e}")
