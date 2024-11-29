# noqa

"""Test imports."""
# ruff: noqa: F401


import pytest  # noqa: F401


@pytest.mark.skip("Что-то с петлёй асинкио")
@pytest.mark.asyncio
async def test_imports():
    """Test that all modules can be imported."""
    # Core modules
    # API modules
    from api.handlers.messages import MessageHandler  # noqa: F401
    from core.accounts import AccountManager, AccountMonitor  # noqa: F401
    from core.accounts.queries import AccountQueries  # noqa: F401
    from core.db import Base, BaseQueries, get_db  # noqa: F401
    from core.messaging import (  # noqa: F401
        DeliveryOptions,
        DeliveryResult,
        DialogConductor,
        DialogQueries,
        DialogStatus,
        MessageDelivery,
        MessageDirection,
        MessageQueries,
    )
    from core.telegram.client import app  # noqa: F401

    # Prevent unused import warnings while still testing imports
    all_imports = [
        AccountManager,
        AccountMonitor,
        AccountQueries,
        Base,
        BaseQueries,
        get_db,
        MessageDirection,
        DialogStatus,
        DeliveryOptions,
        DeliveryResult,
        MessageDelivery,
        DialogConductor,
        MessageQueries,
        DialogQueries,
        app,
        MessageHandler,
    ]
    assert all(x is not None for x in all_imports), "All imports should be available"


def test_message_models():
    """Test message models imports."""
    from core.messaging.enums import DialogStatus, MessageDirection  # noqa: F401
    from core.messaging.models import Dialog, Message  # noqa: F401


def test_message_delivery():
    """Test message delivery imports."""
    from core.messaging.delivery import MessageDelivery  # noqa: F401


def test_dialog_conductor():
    """Test dialog conductor imports."""
    from core.messaging.conductor import DialogConductor  # noqa: F401


def test_dialog_models():
    """Test dialog models imports."""
    from core.messaging.enums import DialogStatus  # noqa: F401
    from core.messaging.models import Dialog  # noqa: F401


def test_queries():
    """Test queries imports."""
    from core.messaging.queries import DialogQueries, MessageQueries  # noqa: F401


if __name__ == "__main__":
    pytest.main([__file__])
