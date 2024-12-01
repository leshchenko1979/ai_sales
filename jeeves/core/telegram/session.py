"""Session management for Telegram client."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Session storage location
SESSION_DIR = Path("sessions")
SESSION_FILE = SESSION_DIR / "bot_session.json"


def ensure_session_dir():
    """Create sessions directory if it doesn't exist."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def load_session() -> Optional[str]:
    """Load session string from file."""
    try:
        if not SESSION_FILE.exists():
            return None

        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            return data.get("session_string")

    except Exception as e:
        logger.error(f"Error loading session: {e}")
        return None


def save_session(session_string: str) -> bool:
    """Save session string to file."""
    try:
        ensure_session_dir()
        with open(SESSION_FILE, "w") as f:
            json.dump({"session_string": session_string}, f)
        return True

    except Exception as e:
        logger.error(f"Error saving session: {e}")
        return False


def clear_session() -> bool:
    """Clear saved session."""
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
        return True

    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return False
