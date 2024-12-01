"""Base AI provider interface."""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from infrastructure.config import OPENAI_API_KEY, OPENROUTER_API_KEY

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Available AI provider types."""

    OPENAI = "openai"
    OPENROUTER = "openrouter"


class AIProvider:
    """Base class for AI providers."""

    @staticmethod
    def create(provider_type: Optional[str] = None) -> "AIProvider":
        """
        Create an AI provider instance based on configuration.

        Args:
            provider_type: Optional provider type string. If not provided, will use available
                configuration to determine the provider.

        Returns:
            AIProvider instance
        """
        # Import here to avoid circular imports
        from .openai import OpenAIProvider
        from .openrouter import OpenRouterProvider

        if provider_type:
            provider_type = provider_type.lower()

        # If no specific provider requested, choose based on available config
        if not provider_type:
            if OPENAI_API_KEY:
                provider_type = ProviderType.OPENAI.value
            elif OPENROUTER_API_KEY:
                provider_type = ProviderType.OPENROUTER.value
            else:
                raise ValueError("No AI provider configuration found")

        if provider_type == ProviderType.OPENAI.value:
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
            return OpenAIProvider()
        elif provider_type == ProviderType.OPENROUTER.value:
            if not OPENROUTER_API_KEY:
                raise ValueError("OpenRouter API key not configured")
            return OpenRouterProvider()
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    async def generate_response(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate response from AI provider.

        Args:
            messages: List of message dictionaries with role and content

        Returns:
            Generated response text

        Raises:
            NotImplementedError: Must be implemented by provider
        """
        raise NotImplementedError

    async def make_request(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make request to AI provider.

        Args:
            messages: List of message dictionaries with role and content

        Returns:
            Response data from provider

        Raises:
            NotImplementedError: Must be implemented by provider
        """
        raise NotImplementedError
