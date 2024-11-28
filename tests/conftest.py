"""Test configuration."""

import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent / "sales_bot"
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file
load_dotenv()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment."""
    # Set up any test environment variables here
