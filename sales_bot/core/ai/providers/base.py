"""Base AI provider interface."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AIProvider:
    """Base class for AI providers."""

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
            Raw response from provider

        Raises:
            NotImplementedError: Must be implemented by provider
        """
        raise NotImplementedError
