import io
import json
import logging
import sys
from datetime import datetime

import pytest
from infrastructure.logging import JsonFormatter, addLoggingLevel, trace


# Add this setup before running tests
def setup_module(module):
    """Setup TRACE level for tests if not already defined"""
    if not hasattr(logging, "TRACE"):
        addLoggingLevel("TRACE", logging.DEBUG - 5)


@pytest.fixture
def test_class():
    class TestClass:
        logger = logging.getLogger("test_class_logger")

        @trace
        def method(self):
            return "method_result"

        @trace
        async def async_method(self):
            return "async_method_result"

    return TestClass()


# Helper functions
@trace
def sample_function():
    return "function_result"


@trace
async def sample_async_function():
    return "async_function_result"


# Test with explicit logger
explicit_logger = logging.getLogger("explicit_logger")


@trace(explicit_logger)
def function_with_explicit_logger():
    return "explicit_logger_result"


@pytest.fixture
def capture_logs(caplog):
    caplog.set_level(logging.TRACE)
    return caplog


def test_class_method_logging(test_class, capture_logs):
    # Act
    result = test_class.method()

    # Assert
    assert result == "method_result"
    assert any(record.name == "test_class_logger" for record in capture_logs.records)
    assert any("Calling method" in record.message for record in capture_logs.records)
    assert any(
        "method completed successfully" in record.message
        for record in capture_logs.records
    )


def test_function_logging(capture_logs):
    # Act
    result = sample_function()

    # Assert
    assert result == "function_result"
    assert any(
        record.name == "tests.infrastructure.test_logging"
        for record in capture_logs.records
    )
    assert any(
        "Calling sample_function" in record.message for record in capture_logs.records
    )
    assert any(
        "sample_function completed successfully" in record.message
        for record in capture_logs.records
    )


@pytest.mark.asyncio
async def test_async_function_logging(capture_logs):
    # Act
    result = await sample_async_function()

    # Assert
    assert result == "async_function_result"
    assert any(
        record.name == "tests.infrastructure.test_logging"
        for record in capture_logs.records
    )
    assert any(
        "Calling sample_async_function" in record.message
        for record in capture_logs.records
    )
    assert any(
        "sample_async_function completed successfully" in record.message
        for record in capture_logs.records
    )


def test_exception_logging(capture_logs):
    # Arrange
    @trace
    def failing_function():
        raise ValueError("Test error")

    # Act & Assert
    with pytest.raises(ValueError):
        failing_function()

    assert any(record.levelname == "ERROR" for record in capture_logs.records)
    assert any(
        "failing_function failed: Test error" in record.message
        for record in capture_logs.records
    )


def test_json_formatter_basic():
    # Arrange
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert log_dict["logger"] == "test_logger"
    assert log_dict["level"] == "INFO"
    assert log_dict["message"] == "Test message"
    assert log_dict["line"] == 42
    assert log_dict["path"] == "test.py"


def test_json_formatter_with_exception():
    # Arrange
    formatter = JsonFormatter()
    try:
        raise ValueError("Test error")
    except ValueError:
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=sys.exc_info(),
        )

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert log_dict["level"] == "ERROR"
    assert log_dict["message"] == "Error occurred"
    assert "exception" in log_dict
    assert log_dict["exception"]["type"] == "ValueError"
    assert log_dict["exception"]["message"] == "Test error"
    assert isinstance(log_dict["exception"]["stack"], list)


def test_json_formatter_with_extra_data():
    # Arrange
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = {"user_id": 123, "action": "test"}

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert log_dict["extra_data"]["user_id"] == 123
    assert log_dict["extra_data"]["action"] == "test"


def test_json_formatter_with_datetime():
    # Arrange
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = {"timestamp": datetime(2024, 1, 1, 12, 0, 0)}

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert log_dict["extra_data"]["timestamp"] == "2024-01-01T12:00:00"


def test_json_formatter_with_non_serializable():
    # Arrange
    class NonSerializable:
        def __str__(self):
            return "non_serializable_object"

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = {"object": NonSerializable()}

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert log_dict["extra_data"]["object"] == "non_serializable_object"


def test_json_formatter_serialization_failure():
    # Arrange
    class FailingSerializable:
        def __str__(self):
            return "FailingSerializable"

        def __repr__(self):
            return "FailingSerializable"

        def __json__(self):
            raise Exception("Serialization error")

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = {"failing_object": FailingSerializable()}

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert (
        log_dict["level"] == "INFO"
    )  # Level remains INFO since we handle serialization gracefully
    assert (
        log_dict["extra_data"]["failing_object"] == "FailingSerializable"
    )  # Converted to string


import threading
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_json_formatter_with_complex_objects():
    # Arrange
    formatter = JsonFormatter()

    # Создаем сложный объект с разными типами данных
    complex_data = {
        "file": io.StringIO("test"),
        "thread": threading.Thread(),
        "mock": MagicMock(),
        "namespace": SimpleNamespace(a=1, b="test"),
        "bytes": b"binary data",
        "set": {1, 2, 3},
        "function": lambda x: x,
    }

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = complex_data

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert isinstance(log_dict["extra_data"]["file"], str)
    assert isinstance(log_dict["extra_data"]["thread"], str)
    assert isinstance(log_dict["extra_data"]["mock"], str)
    assert isinstance(log_dict["extra_data"]["namespace"], str)
    assert isinstance(log_dict["extra_data"]["bytes"], str)
    assert isinstance(log_dict["extra_data"]["set"], str)
    assert isinstance(log_dict["extra_data"]["function"], str)


def test_json_formatter_with_recursive_structures():
    # Arrange
    formatter = JsonFormatter()

    # Создаем рекурсивную структуру
    recursive_dict = {}
    recursive_dict["self"] = recursive_dict

    recursive_list = []
    recursive_list.append(recursive_list)

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = {
        "recursive_dict": recursive_dict,
        "recursive_list": recursive_list,
    }

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert isinstance(log_dict["extra_data"]["recursive_dict"], str)
    assert isinstance(log_dict["extra_data"]["recursive_list"], str)


def test_json_formatter_with_custom_objects():
    # Arrange
    class CustomObject:
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return f"CustomObject({self.value})"

    class FailingObject:
        def __str__(self):
            raise ValueError("Failed to stringify")

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = {"custom": CustomObject("test"), "failing": FailingObject()}

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert log_dict["extra_data"]["custom"] == "CustomObject(test)"
    assert log_dict["extra_data"]["failing"] is None


def test_json_formatter_with_large_objects():
    # Arrange
    formatter = JsonFormatter()

    # Создаем большой вложенный объект
    large_data = {
        "level1": {
            "level2": {
                "level3": {
                    "data": "x" * 1000,
                    "list": list(range(1000)),
                    "dict": {str(i): i for i in range(100)},
                }
            }
        }
    }

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.extra_data = large_data

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert isinstance(log_dict["extra_data"], dict)
    assert isinstance(log_dict["extra_data"]["level1"], dict)
    assert isinstance(log_dict["extra_data"]["level1"]["level2"], dict)
    assert isinstance(log_dict["extra_data"]["level1"]["level2"]["level3"], dict)


def test_trace_level_setup():
    """Test that TRACE level is properly set up"""
    assert hasattr(logging, "TRACE")
    assert logging.TRACE == logging.DEBUG - 5

    logger = logging.getLogger("test_trace")
    logger.setLevel(logging.TRACE)

    # Create a memory stream to capture log output
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.TRACE)
    logger.addHandler(handler)

    logger.log(logging.TRACE, "Test trace message")
    output = stream.getvalue()
    assert "Test trace message" in output


def test_json_formatter_all_attributes():
    """Test that JsonFormatter handles all record attributes correctly"""
    # Arrange
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # Add custom attributes
    record.custom_attr = "custom_value"
    record.extra_data = {"test_key": "test_value"}

    # Act
    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    # Assert
    assert log_dict["logger"] == "test_logger"
    assert log_dict["level"] == "INFO"
    assert log_dict["message"] == "Test message"
    assert log_dict["path"] == "test.py"
    assert log_dict["line"] == 42
    assert log_dict["custom_attr"] == "custom_value"
    assert log_dict["extra_data"]["test_key"] == "test_value"


@pytest.mark.asyncio
async def test_class_async_method_logging(test_class, capture_logs):
    # Act
    result = await test_class.async_method()

    # Assert
    assert result == "async_method_result"
    assert any(record.name == "test_class_logger" for record in capture_logs.records)
    assert any(
        "Calling async_method" in record.message for record in capture_logs.records
    )
    assert any(
        "async_method completed successfully" in record.message
        for record in capture_logs.records
    )


def test_explicit_logger(capture_logs):
    # Act
    result = function_with_explicit_logger()

    # Assert
    assert result == "explicit_logger_result"
    assert any(record.name == "explicit_logger" for record in capture_logs.records)
    assert any(
        "Calling function_with_explicit_logger" in record.message
        for record in capture_logs.records
    )
    assert any(
        "function_with_explicit_logger completed successfully" in record.message
        for record in capture_logs.records
    )


def test_class_decoration(capture_logs):
    # Arrange
    @trace
    class DecoratedClass:
        logger = logging.getLogger("decorated_class_logger")

        def method1(self):
            return "method1_result"

        def method2(self):
            return "method2_result"

        def __special__(self):
            return "special_result"

    # Act
    instance = DecoratedClass()
    result1 = instance.method1()
    result2 = instance.method2()
    special_result = instance.__special__()

    # Assert
    assert result1 == "method1_result"
    assert result2 == "method2_result"
    assert special_result == "special_result"

    # Check that normal methods are traced
    assert any("Calling method1" in record.message for record in capture_logs.records)
    assert any(
        "method1 completed successfully" in record.message
        for record in capture_logs.records
    )
    assert any("Calling method2" in record.message for record in capture_logs.records)
    assert any(
        "method2 completed successfully" in record.message
        for record in capture_logs.records
    )

    # Check that magic methods are not traced
    assert not any(
        "Calling __special__" in record.message for record in capture_logs.records
    )
    assert not any(
        "__special__ completed successfully" in record.message
        for record in capture_logs.records
    )


@pytest.mark.asyncio
async def test_class_decoration_with_async(capture_logs):
    # Arrange
    @trace
    class AsyncDecoratedClass:
        logger = logging.getLogger("async_decorated_class_logger")

        async def async_method1(self):
            return "async_method1_result"

        def sync_method(self):
            return "sync_method_result"

    # Act
    instance = AsyncDecoratedClass()
    async_result = await instance.async_method1()
    sync_result = instance.sync_method()

    # Assert
    assert async_result == "async_method1_result"
    assert sync_result == "sync_method_result"

    # Check that both async and sync methods are traced
    assert any(
        "Calling async_method1" in record.message for record in capture_logs.records
    )
    assert any(
        "async_method1 completed successfully" in record.message
        for record in capture_logs.records
    )
    assert any(
        "Calling sync_method" in record.message for record in capture_logs.records
    )
    assert any(
        "sync_method completed successfully" in record.message
        for record in capture_logs.records
    )


def test_class_decoration_with_explicit_logger(capture_logs):
    # Arrange
    explicit_class_logger = logging.getLogger("explicit_class_logger")

    @trace(explicit_class_logger)
    class ExplicitLoggerClass:
        def method(self):
            return "explicit_result"

    # Act
    instance = ExplicitLoggerClass()
    result = instance.method()

    # Assert
    assert result == "explicit_result"
    assert any(
        record.name == "explicit_class_logger" for record in capture_logs.records
    )
    assert any("Calling method" in record.message for record in capture_logs.records)
    assert any(
        "method completed successfully" in record.message
        for record in capture_logs.records
    )
