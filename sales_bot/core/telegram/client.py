"""Telegram client initialization."""

import logging
import os
from typing import Optional

from infrastructure.config import API_HASH, API_ID, BOT_TOKEN
from pyrogram import Client

logger = logging.getLogger(__name__)


def create_client(session_string: Optional[str] = None) -> Client:
    """Create Telegram client."""
    return Client(
        "sales_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN if not session_string else None,
        session_string=session_string,
        in_memory=True,  # Prevent session file issues
    )


# Initialize the bot client only if not in testing environment
app = create_client() if not os.getenv("TESTING") else None
