"""Tests for DialogConductor."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.messaging.conductor import DialogConductor
from core.messaging.delivery import MessageDelivery
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
    conductor.sales.get_initial_message = AsyncMock(return_value="Welcome")
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

    # Verify history contains both messages
    history = conductor.get_history()
    assert len(history) == 2
    assert history[0] == {"direction": "in", "text": "test message"}
    assert history[1] == {"direction": "out", "text": "Test response"}


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

    # Verify history contains both messages
    history = conductor.get_history()
    assert len(history) == 2
    assert history[0] == {"direction": "in", "text": "test message"}
    assert history[1] == {"direction": "out", "text": "Test response"}


@pytest.mark.asyncio
async def test_delivery_error_handling(conductor):
    """Test error handling when message delivery fails."""
    # Setup advisor to return active status
    conductor.advisor.get_tip = AsyncMock(
        return_value=(DialogStatus.active, "reason", 0.5, "stage", "advice")
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

    # Verify only input message is in history
    history = conductor.get_history()
    assert len(history) == 1
    assert history[0] == {"direction": "in", "text": "test message"}


@pytest.mark.asyncio
async def test_history_with_failed_delivery(conductor):
    """Test that failed message delivery doesn't add to history."""
    # First message succeeds
    conductor.advisor.get_tip = AsyncMock(
        return_value=(DialogStatus.active, "reason", 0.5, "stage", "advice")
    )
    conductor.message_delivery.deliver_messages = AsyncMock(
        return_value=DeliveryResult(success=True)
    )
    await conductor.handle_message("message 1")

    # Second message delivery fails
    conductor.message_delivery.deliver_messages = AsyncMock(
        return_value=DeliveryResult(success=False, error="Test error")
    )
    await conductor.handle_message("message 2")

    # Verify history only contains successful messages
    history = conductor.get_history()
    assert len(history) == 3  # message 1 + response 1 + message 2
    assert history[0] == {"direction": "in", "text": "message 1"}
    assert history[1] == {"direction": "out", "text": "Test response"}
    assert history[2] == {"direction": "in", "text": "message 2"}


@pytest.mark.asyncio
async def test_history_with_rapid_messages(conductor):
    """Test history consistency with rapid message delivery."""

    # Setup slow message delivery
    async def slow_delivery(*args, **kwargs):
        await asyncio.sleep(0.1)
        return DeliveryResult(success=True)

    # Setup message delivery to succeed but take time
    conductor.message_delivery.deliver_messages = AsyncMock(side_effect=slow_delivery)
    conductor.message_delivery.split_messages = MagicMock(side_effect=lambda x: [x])
    conductor.advisor.get_tip = AsyncMock(
        return_value=(DialogStatus.active, "reason", 0.5, "stage", "advice")
    )

    # Setup response generation with proper signature
    async def get_response(
        dialog_history=None,
        status=None,
        warmth=None,
        reason=None,
        advice=None,
        stage=None,
    ):
        # Get all unresponded messages
        messages = []
        for entry in dialog_history:
            if entry["direction"] == "in":
                messages.append(entry["text"])
        return f"Response to combined messages: {', '.join(messages)}"

    conductor.sales.get_response = AsyncMock(side_effect=get_response)

    # Clear history before starting
    conductor.clear_history()

    # Send messages rapidly
    task1 = asyncio.create_task(conductor.handle_message("message 1"))
    await asyncio.sleep(0.01)  # Small delay to ensure order
    task2 = asyncio.create_task(conductor.handle_message("message 2"))

    # Wait for both tasks
    await asyncio.gather(task1, task2)

    # Verify history maintains correct order of messages as they were sent/received
    history = conductor.get_history()
    assert len(history) == 3  # Two messages and one combined response
    assert history[0] == {"direction": "in", "text": "message 1"}
    assert history[1] == {"direction": "in", "text": "message 2"}
    assert history[2] == {
        "direction": "out",
        "text": "Response to combined messages: message 1, message 2",
    }


@pytest.mark.asyncio
async def test_ai_task_cancellation_history(conductor):
    """Test history consistency when AI tasks are cancelled."""

    # Setup slow AI response
    async def slow_ai_response(*args, **kwargs):
        await asyncio.sleep(0.2)
        return DialogStatus.active, "reason", 0.5, "stage", "advice"

    # Setup mocks with proper delays
    conductor.advisor.get_tip = AsyncMock(side_effect=slow_ai_response)
    conductor.message_delivery.split_messages = MagicMock(side_effect=lambda x: [x])

    # Setup response generation with proper signature
    async def get_response(
        dialog_history=None,
        status=None,
        warmth=None,
        reason=None,
        advice=None,
        stage=None,
    ):
        message = dialog_history[-1]["text"] if dialog_history else "unknown"
        return f"Response to {message}"

    conductor.sales.get_response = AsyncMock(side_effect=get_response)

    async def slow_delivery(*args, **kwargs):
        await asyncio.sleep(0.1)
        return DeliveryResult(success=True)

    conductor.message_delivery.deliver_messages = AsyncMock(side_effect=slow_delivery)

    # Clear history before starting
    conductor.clear_history()

    # Start first message processing
    task1 = asyncio.create_task(conductor.handle_message("message 1"))
    await asyncio.sleep(0.1)  # Let AI start processing

    # Send second message to cancel first
    task2 = asyncio.create_task(conductor.handle_message("message 2"))

    # Wait for both tasks
    await asyncio.gather(task2, task1)

    # Verify history contains all messages in order of arrival/delivery
    history = conductor.get_history()
    assert len(history) == 3  # Both messages + response to message 2
    assert history[0] == {"direction": "in", "text": "message 1"}
    assert history[1] == {"direction": "in", "text": "message 2"}
    assert history[2] == {"direction": "out", "text": "Response to message 2"}


@pytest.mark.asyncio
async def test_start_dialog_history(conductor):
    """Test history consistency when starting dialog."""
    # Setup initial message
    conductor.message_delivery.split_messages = MagicMock(side_effect=lambda x: [x])
    conductor.sales.generate_initial_message = AsyncMock(return_value="Initial message")

    # Test successful start
    await conductor.start_dialog()

    # Check history
    history = conductor.get_history()
    assert len(history) == 1
    assert history[0] == {"direction": "out", "text": "Initial message"}

    # Test failed start
    conductor.message_delivery.deliver_messages = AsyncMock(
        return_value=DeliveryResult(success=False, error="Test error")
    )
    conductor.clear_history()

    with pytest.raises(RuntimeError):
        await conductor.start_dialog()

    # Verify history is empty after failed start
    history = conductor.get_history()
    assert len(history) == 0


@pytest.mark.asyncio
async def test_message_splitting_by_newlines(conductor):
    """Test splitting messages by double newlines."""
    # Create a message with multiple paragraphs
    response = (
        "First paragraph with some text.\n\n"
        "Second paragraph that continues.\n"
        "Still the second paragraph.\n\n"
        "Third paragraph here.\n\n"
        "Final paragraph."
    )

    # Use actual MessageDelivery split_messages implementation
    conductor.message_delivery.split_messages = MessageDelivery().split_messages

    conductor.message_delivery.deliver_messages = AsyncMock(
        return_value=DeliveryResult(success=True)
    )
    conductor.advisor.get_tip = AsyncMock(
        return_value=(DialogStatus.active, "reason", 0.5, "stage", "advice")
    )
    conductor.sales.get_response = AsyncMock(return_value=response)

    # Send a message
    await conductor.handle_message("Test message")

    # Verify history contains all paragraphs
    history = conductor.get_history()
    assert len(history) == 5  # Input message + 4 paragraphs
    assert history[0] == {"direction": "in", "text": "Test message"}
    assert history[1] == {"direction": "out", "text": "First paragraph with some text."}
    assert history[2] == {
        "direction": "out",
        "text": "Second paragraph that continues.\nStill the second paragraph.",
    }
    assert history[3] == {"direction": "out", "text": "Third paragraph here."}
    assert history[4] == {"direction": "out", "text": "Final paragraph."}

    # Verify each paragraph was delivered separately
    assert conductor.message_delivery.deliver_messages.call_count == 4
    for i, call in enumerate(
        conductor.message_delivery.deliver_messages.call_args_list
    ):
        _, kwargs = call
        assert len(kwargs["messages"]) == 1
