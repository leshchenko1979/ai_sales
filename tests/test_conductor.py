"""Tests for DialogConductor."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from core.messaging.conductor import DialogConductor
from core.messaging.models import DeliveryResult, DialogStatus


@pytest.fixture
def send_func():
    """Mock send function."""
    return AsyncMock()


@pytest.fixture
def conductor(send_func):
    """Create conductor with mocked dependencies."""
    conductor = DialogConductor(send_func=send_func)
    # Mock dependencies
    conductor.sales = MagicMock()
    conductor.sales.get_response = AsyncMock(return_value="Test response")
    conductor.sales.generate_farewell_message = AsyncMock(return_value="Goodbye")
    conductor.advisor = MagicMock()
    conductor.message_delivery = MagicMock()
    conductor.message_delivery.split_messages = MagicMock(
        return_value=["Test response"]
    )
    conductor.message_delivery.deliver_messages = AsyncMock(
        return_value=DeliveryResult(success=True)
    )
    return conductor


@pytest.mark.asyncio
async def test_dialog_completion(conductor):
    """Test that dialog is completed when advisor returns closed status."""
    # Setup advisor to return closed status
    conductor.advisor.get_tip = AsyncMock(
        return_value=(DialogStatus.closed, "reason", 0.5, "stage", "advice")
    )

    # Send a message
    is_completed, error = await conductor.handle_message("test message")

    # Verify dialog was completed
    assert is_completed is True
    assert error is None

    # Verify farewell was sent
    conductor.sales.generate_farewell_message.assert_called_once()
    assert len(conductor._history) == 3  # Input message + bot response + farewell


@pytest.mark.asyncio
async def test_dialog_not_completed(conductor):
    """Test that dialog continues when advisor returns active status."""
    # Setup advisor to return active status
    conductor.advisor.get_tip = AsyncMock(
        return_value=(DialogStatus.active, "reason", 0.5, "stage", "advice")
    )

    # Send a message
    is_completed, error = await conductor.handle_message("test message")

    # Verify dialog was not completed
    assert is_completed is False
    assert error is None

    # Verify no farewell was sent
    conductor.sales.generate_farewell_message.assert_not_called()
    assert len(conductor._history) == 2  # Input message + bot response


@pytest.mark.asyncio
async def test_delivery_error_handling(conductor):
    """Test error handling when message delivery fails."""
    # Setup advisor to return closed status
    conductor.advisor.get_tip = AsyncMock(
        return_value=(DialogStatus.closed, "reason", 0.5, "stage", "advice")
    )
    # Setup message delivery to fail
    conductor.message_delivery.deliver_messages = AsyncMock(
        return_value=DeliveryResult(success=False, error="Test error")
    )

    # Send a message
    is_completed, error = await conductor.handle_message("test message")

    # Verify error was returned
    assert is_completed is False
    assert error == "Test error"

    # Verify no farewell was attempted
    conductor.sales.generate_farewell_message.assert_not_called()
