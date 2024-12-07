"""Telegram client initialization.

Network architecture:
- Jeeves uses Pyrogram library to interact with Telegram API
- Connection is established via long polling (not webhooks)
- No web server or open ports are required
- Outbound internet access is needed for:
  * Telegram API (api.telegram.org)
  * Telegram MTProto servers (DC1-DC5)
  * Media downloads/uploads if used

Container configuration:
- No port exposure needed in Dockerfile or docker-compose
- No reverse proxy (Traefik/Nginx) integration needed
- Only outbound internet access required
- No special network configuration needed besides basic outbound connectivity
"""

import logging
import os
from typing import Optional

from infrastructure.config import API_HASH, API_ID, BOT_TOKEN
from pyrogram import Client

from .session import load_session

logger = logging.getLogger(__name__)


def create_client(session_string: Optional[str] = None) -> Client:
    """Create Telegram client."""
    # Try to load saved session if none provided
    if not session_string:
        session_string = load_session()
        if session_string:
            logger.info("Loaded existing session")

    return Client(
        "jeeves",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=None if session_string else BOT_TOKEN,
        session_string=session_string,
        in_memory=True,  # We'll handle session persistence ourselves
    )


# Initialize the bot client only if not in testing environment
app = None if os.getenv("TESTING") else create_client()
