import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

"""Global pytest fixtures."""


@pytest.fixture(scope="session", autouse=True)
def load_env() -> Generator[None, None, None]:
    """Load environment variables from .env file.

    This fixture is automatically used in all tests.
    It loads environment variables from .env file and validates required variables.
    """
    from dotenv import load_dotenv

    # Check .env file exists
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_path = os.path.join(base_dir, ".env")
    assert os.path.exists(env_path), ".env file not found"

    # Load environment variables
    load_dotenv(env_path)

    # Check required environment variables
    required_vars = [
        "BOT_TOKEN",
        "API_ID",
        "API_HASH",
        "OPENROUTER_API_KEY",
        "DATABASE_URL",
        "REMOTE_HOST",
        "REMOTE_USER",
    ]

    missing_vars = [var for var in required_vars if os.getenv(var) is None]
    if missing_vars:
        pytest.fail(f"Missing environment variables: {', '.join(missing_vars)}")

    # Check database URL format
    db_url = os.getenv("DATABASE_URL")
    if not db_url.startswith("postgresql+asyncpg://"):
        pytest.fail("DATABASE_URL should use asyncpg driver")

    yield

    # Cleanup if needed
    # Note: Environment variables persist after tests, which is usually what we want
