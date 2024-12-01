""" OpenAI adapter """

from typing import Any, Dict, List

import openai
from infrastructure.config import OPENAI_MODEL

from .base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self):
        self.client = openai.OpenAI()

    async def generate_response(self, messages: List[Dict[str, Any]]) -> str:
        response = self.client.chat.completions.create(
            model=OPENAI_MODEL,  # You can change this to your desired model
            messages=messages,
        )
        return response.choices[0].message.content
