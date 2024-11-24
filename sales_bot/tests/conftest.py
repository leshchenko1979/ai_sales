import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables required for the application"""
    with patch.dict(
        os.environ,
        {
            "TESTING": "1",
            # Pyrogram settings
            "API_ID": "12345",
            "API_HASH": "fake_hash",
            "BOT_TOKEN": "fake_token",
            # Bot settings
            "ADMIN_TELEGRAM_ID": "123456789",
            # OpenRouter settings
            "OPENROUTER_API_KEY": "fake_openrouter_key",
            # Database settings (необязательные, есть значения по умолчанию)
            "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/test_db",
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE": "test.log",
        },
    ):
        yield
