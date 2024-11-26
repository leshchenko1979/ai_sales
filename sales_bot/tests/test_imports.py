# noqa

"""Test imports."""
# ruff: noqa: F401

import os

import pytest  # noqa: F401


def test_core_structure():
    """Test core module structure."""
    base_dir = os.path.dirname(os.path.dirname(__file__))

    # Check core structure
    assert os.path.exists(os.path.join(base_dir, "core"))
    assert os.path.exists(os.path.join(base_dir, "core", "accounts"))
    assert os.path.exists(os.path.join(base_dir, "core", "ai"))
    assert os.path.exists(os.path.join(base_dir, "core", "messages"))
    assert os.path.exists(os.path.join(base_dir, "core", "telegram"))
    assert os.path.exists(os.path.join(base_dir, "core", "db"))


def test_account_files():
    """Test account module files."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    accounts_dir = os.path.join(base_dir, "core", "accounts")

    assert os.path.exists(os.path.join(accounts_dir, "__init__.py"))
    assert os.path.exists(os.path.join(accounts_dir, "client.py"))
    assert os.path.exists(os.path.join(accounts_dir, "manager.py"))
    assert os.path.exists(os.path.join(accounts_dir, "models.py"))
    assert os.path.exists(os.path.join(accounts_dir, "monitoring.py"))
    assert os.path.exists(os.path.join(accounts_dir, "notifications.py"))
    assert os.path.exists(os.path.join(accounts_dir, "rotation.py"))
    assert os.path.exists(os.path.join(accounts_dir, "warmup.py"))


def test_message_files():
    """Test message module files."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    messages_dir = os.path.join(base_dir, "core", "messages")

    assert os.path.exists(os.path.join(messages_dir, "__init__.py"))
    assert os.path.exists(os.path.join(messages_dir, "models.py"))
    assert os.path.exists(os.path.join(messages_dir, "service.py"))


def test_telegram_files():
    """Test telegram module files."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    telegram_dir = os.path.join(base_dir, "core", "telegram")

    assert os.path.exists(os.path.join(telegram_dir, "__init__.py"))
    assert os.path.exists(os.path.join(telegram_dir, "client.py"))


def test_api_files():
    """Test API module files."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    api_dir = os.path.join(base_dir, "api")

    assert os.path.exists(os.path.join(api_dir, "__init__.py"))
    assert os.path.exists(os.path.join(api_dir, "handlers", "__init__.py"))
    assert os.path.exists(os.path.join(api_dir, "handlers", "commands.py"))
    assert os.path.exists(os.path.join(api_dir, "handlers", "messages.py"))


def test_infrastructure_files():
    """Test infrastructure module files."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    infra_dir = os.path.join(base_dir, "infrastructure")

    assert os.path.exists(os.path.join(infra_dir, "__init__.py"))


def test_imports():
    """Test that all modules can be imported."""
    # Core modules
    # API modules
    from api.handlers.commands import app as commands_app  # noqa: F401
    from api.handlers.messages import MessageHandler  # noqa: F401
    from core.accounts import AccountManager, AccountMonitor  # noqa: F401
    from core.ai.gpt import GPTClient  # noqa: F401
    from core.db import AccountQueries, DialogQueries, get_db  # noqa: F401
    from core.messages.service import MessageService  # noqa: F401
    from core.telegram.client import app  # noqa: F401

    # Infrastructure
    from infrastructure.config import ADMIN_TELEGRAM_ID  # noqa: F401
    from infrastructure.logging import setup_logging  # noqa: F401

    # Prevent unused import warnings while still testing imports
    all_imports = [
        AccountManager,
        AccountMonitor,
        GPTClient,
        AccountQueries,
        DialogQueries,
        get_db,
        MessageService,
        app,
        commands_app,
        MessageHandler,
        ADMIN_TELEGRAM_ID,
        setup_logging,
    ]
    assert all(x is not None for x in all_imports), "All imports should be available"


if __name__ == "__main__":
    pytest.main([__file__])
