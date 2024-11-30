"""Tests for message delivery interruption."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class MockDialogConductor:
    """Mock conductor for testing message interruption."""

    def __init__(self, send_func):
        """Initialize with mocked dependencies."""
        self._send_func = send_func
        self._history = []

        # Mock dependencies
        self.sales = MagicMock()
        self.sales.get_response = AsyncMock(return_value="Test response")
        self.advisor = MagicMock()
        self.advisor.get_tip = AsyncMock(
            return_value=("active", "reason", 0.5, "stage", "advice")
        )
        self.message_delivery = MagicMock()
        self.message_delivery.split_messages = MagicMock(return_value=["Test response"])
        self.message_delivery.deliver_messages = AsyncMock(
            return_value=MagicMock(success=True)
        )

    def get_history(self):
        """Get message history."""
        return self._history.copy()

    async def handle_message(self, text: str):
        """Handle incoming message."""
        # Add message to history
        self._history.append({"direction": "in", "text": text})

        # Get AI response
        await self.advisor.get_tip(self._history)
        response = await self.sales.get_response()

        # Try to deliver response
        try:
            messages = self.message_delivery.split_messages(response)
            for msg in messages:
                result = await self.message_delivery.deliver_messages(
                    dialog_id=1, messages=[msg], send_func=self._send_func
                )
                if not result.success:
                    if isinstance(result.error, DeliveryInterrupted):
                        return False, None
                    return False, result.error

                self._history.append(
                    {"direction": "out", "text": msg, "status": "active"}
                )

            return False, None

        except DeliveryInterrupted:
            return False, None


class DeliveryInterrupted(Exception):
    """Raised when message delivery is interrupted."""


@pytest.fixture
def send_func():
    """Mock send function."""
    return AsyncMock()


@pytest.fixture
def conductor(send_func):
    """Create conductor with mocked dependencies."""
    return MockDialogConductor(send_func)


@pytest.mark.asyncio
async def test_message_delivery_interruption(conductor):
    """Test that message delivery interruption is handled gracefully."""
    # Setup message delivery to be interrupted
    conductor.message_delivery.deliver_messages = AsyncMock(
        side_effect=DeliveryInterrupted()
    )
    conductor.message_delivery.split_messages = MagicMock(
        return_value=["Test response"]
    )

    # Send first message
    is_completed, error = await conductor.handle_message("message 1")

    # Verify first message handling
    assert is_completed is False  # Dialog not completed
    assert error is None  # No error reported

    # Send second message quickly
    is_completed, error = await conductor.handle_message("message 2")

    # Verify second message handling
    assert is_completed is False
    assert error is None

    # Verify history contains only input messages (since delivery was interrupted)
    history = conductor.get_history()
    assert len(history) == 2
    assert history[0] == {"direction": "in", "text": "message 1"}
    assert history[1] == {"direction": "in", "text": "message 2"}

    # Verify advisor was called for both messages
    assert conductor.advisor.get_tip.call_count == 2

    # Verify sales response was generated for both messages
    assert conductor.sales.get_response.call_count == 2
