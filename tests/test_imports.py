# noqa

"""Test imports."""
# ruff: noqa: F401


import pytest  # noqa: F401


# @pytest.mark.skip("Что-то с петлёй асинкио")
@pytest.mark.asyncio
async def test_imports():
    """Test that all modules can be imported."""
    # Core modules
    from core.accounts import AccountManager, AccountMonitor  # noqa: F401
    from core.accounts.models.account import Account, AccountStatus  # noqa: F401
    from core.accounts.models.profile import (  # noqa: F401
        AccountProfile,
        ProfileTemplate,
    )
    from core.accounts.queries import AccountQueries  # noqa: F401
    from core.db import Base, BaseQueries, get_db  # noqa: F401
    from core.messaging import (  # noqa: F401
        BaseDialogConductor,
        DeliveryOptions,
        DeliveryResult,
        DialogConductorFactory,
        DialogQueries,
        DialogStatus,
        MessageDelivery,
        MessageDirection,
        MessageQueries,
    )
    from core.telegram.client import app  # noqa: F401

    # Prevent unused import warnings while still testing imports
    all_imports = [
        Account,
        AccountStatus,
        AccountProfile,
        ProfileTemplate,
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
        BaseDialogConductor,
        DialogConductorFactory,
        MessageQueries,
        DialogQueries,
        app,
    ]
    assert all(x is not None for x in all_imports), "All imports should be available"


def test_account_models():
    """Test account models imports."""
    from core.accounts.models.account import Account, AccountStatus  # noqa: F401
    from core.accounts.models.profile import (  # noqa: F401
        AccountProfile,
        ProfileHistory,
        ProfileTemplate,
    )


def test_message_models():
    """Test message models imports."""
    from core.messaging.enums import DialogStatus, MessageDirection  # noqa: F401
    from core.messaging.models import Dialog, Message  # noqa: F401


def test_message_delivery():
    """Test message delivery imports."""
    from core.messaging.delivery import MessageDelivery  # noqa: F401


def test_dialog_conductor():
    """Test dialog conductor imports."""
    from core.ai.strategies.cold_meeting.conductor import (  # noqa: F401
        ColdMeetingConductor,
    )
    from core.messaging import (  # noqa: F401
        BaseDialogConductor,
        DialogConductorFactory,
        DialogStrategyType,
    )


def test_dialog_models():
    """Test dialog models imports."""
    from core.messaging.enums import DialogStatus  # noqa: F401
    from core.messaging.models import Dialog  # noqa: F401


def test_queries():
    """Test queries imports."""
    from core.accounts.queries.account import AccountQueries  # noqa: F401
    from core.accounts.queries.profile import ProfileQueries  # noqa: F401
    from core.messaging.queries import DialogQueries, MessageQueries  # noqa: F401


if __name__ == "__main__":
    pytest.main([__file__])
