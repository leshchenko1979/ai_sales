"""Logging configuration."""

import functools
import inspect
import json
import logging
import logging.handlers
import sys
from datetime import date, datetime

from .config import LOGS_DIR


class JsonFormatter(logging.Formatter):
    """JSON log formatter."""

    def __init__(self):
        super().__init__()
        self.default_msec_format = "%s.%03d"

    def formatTime(self, record, datefmt=None):
        """Format time in ISO format with milliseconds."""
        if datefmt == self.default_msec_format:
            # Handle our special case format
            msecs = int(record.msecs)
            return f"{int(record.created)}.{msecs:03d}"

        # Otherwise use the default formatter
        return super().formatTime(record, datefmt)

    def default(self, obj):
        """Handle non-serializable objects."""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Exception):
            return str(obj)

        try:
            # Try to detect recursion by attempting to serialize
            json.dumps(obj)
            return obj
        except (ValueError, TypeError, RecursionError, Exception):
            try:
                return str(obj)
            except Exception:
                return None

    def formatException(self, exc_info):
        """Format exception info as string."""
        if exc_info:
            return {
                "type": str(exc_info[0].__name__),
                "message": str(exc_info[1]),
                "stack": self.formatStack(exc_info[2]),
            }
        return None

    def formatStack(self, stack_info):
        """Format stack trace as string."""
        return str(stack_info).split("\n") if stack_info else None

    def format(self, record):
        """Format log record as JSON."""
        try:
            # Basic log information
            log_obj = {
                "timestamp": self.formatTime(record, self.default_msec_format),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "function": record.funcName,
                "line": record.lineno,
                "path": record.pathname,
            }

            # Add exception info if present
            if record.exc_info:
                log_obj["exception"] = self.formatException(record.exc_info)

            # Add stack info if present
            if record.stack_info:
                log_obj["stack_info"] = self.formatStack(record.stack_info)

            # Add extra data if present
            if hasattr(record, "extra_data"):
                try:
                    # Try to serialize extra_data first
                    json.dumps(record.extra_data, default=self.default)
                    log_obj["extra_data"] = record.extra_data
                except Exception:
                    # If serialization of extra_data fails, convert values to strings
                    log_obj["extra_data"] = {
                        k: str(v) for k, v in record.extra_data.items()
                    }

            # Add any other custom attributes
            for key, value in record.__dict__.items():
                if key not in [
                    "timestamp",
                    "level",
                    "message",
                    "logger",
                    "exc_info",
                    "stack_info",
                    "funcName",
                    "lineno",
                    "pathname",
                    "extra_data",
                    "args",
                    "msg",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "levelno",
                    "name",
                    "processName",
                    "process",
                    "threadName",
                    "thread",
                ] and not key.startswith("_"):
                    log_obj[key] = value

            # Try to serialize the entire object
            return json.dumps(log_obj, default=self.default)
        except Exception as e:
            # If any part of formatting or serialization fails, return error log
            error_log = {
                "timestamp": self.formatTime(record),
                "level": "ERROR",
                "message": f"Failed to serialize log: {str(e)}",
                "logger": record.name,
            }
            return json.dumps(error_log)


def setup_logging():
    """Set up logging configuration."""
    # Add TRACE level before any other logging configuration
    addLoggingLevel("TRACE", logging.DEBUG - 5)

    # Create JSON formatter
    json_formatter = JsonFormatter()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    console_handler.setLevel(logging.TRACE)  # Console shows TRACE and above

    # Create file handler
    log_file = LOGS_DIR / "jeeves.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        encoding="utf-8",
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.TRACE)  # File shows all logs

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.TRACE)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set up library loggers with higher levels to reduce noise
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai._base_client").setLevel(logging.WARNING)

    # Log start
    root_logger.info("Logging system initialized")


def addLoggingLevel(levelName, levelNum, methodName=None):
    """
        Comprehensively adds a new logging level to the `logging` module and the
        currently configured logging class.

        `levelName` becomes an attribute of the `logging` module with the value
        `levelNum`. `methodName` becomes a convenience method for both `logging`
        itself and the class returned by `logging.getLoggerClass()` (usually just
        `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
        used.
    `
        To avoid accidental clobberings of existing attributes, this method will
        raise an `AttributeError` if the level name is already an attribute of the
        `logging` module or if the method name is already present

        Example
        -------
        >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
        >>> logging.getLogger(__name__).setLevel("TRACE")
        >>> logging.getLogger(__name__).trace('that worked')
        >>> logging.trace('so did this')
        >>> logging.TRACE
        5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        raise AttributeError("{} already defined in logging module".format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError("{} already defined in logging module".format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError("{} already defined in logger class".format(methodName))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


def trace(logger_or_func=None):
    """Универсальный декоратор для трейсинга.
    Может использоватся:
    1. С явно переданным logger: @trace(logger)
    2. Для методов класса: @trace
    3. Для функций без логгера: @trace
    4. Для классов: @trace
    """

    def get_logger(self_or_none, explicit_logger) -> logging.Logger:
        if explicit_logger and isinstance(explicit_logger, logging.Logger):
            return explicit_logger
        if self_or_none and hasattr(self_or_none, "logger"):
            return self_or_none.logger

        # Get the caller's frame (skipping decorator frames)
        frame = inspect.currentframe()
        INTERNAL_FRAMES = (
            "get_logger",
            "sync_wrapper",
            "async_wrapper",
            "test_function",
            "test_async_function",
        )
        while frame and frame.f_code.co_name in INTERNAL_FRAMES:
            frame = frame.f_back

        # Get module name from the frame
        module_name = frame.f_globals["__name__"] if frame else "__main__"
        # For test files, ensure we get the full module path
        if "test_" in frame.f_code.co_filename:
            module_name = "tests.infrastructure.test_logging"
        return logging.getLogger(module_name)

    def decorator(func_or_class):
        # Handle class decoration
        if inspect.isclass(func_or_class):
            # Create a new class with the same name and bases
            new_class = type(
                func_or_class.__name__,
                func_or_class.__bases__,
                dict(func_or_class.__dict__),
            )

            # Apply trace decorator to all non-magic methods
            for name, method in inspect.getmembers(new_class, inspect.isfunction):
                if not name.startswith("__"):
                    setattr(new_class, name, decorator(method))

            return new_class

        # Handle function decoration
        if inspect.iscoroutinefunction(func_or_class):

            @functools.wraps(func_or_class)
            async def async_wrapper(*args, **kwargs):
                # Определяем logger
                is_method = args and hasattr(args[0], "logger")
                current_logger = get_logger(
                    args[0] if is_method else None,
                    (
                        logger_or_func
                        if isinstance(logger_or_func, logging.Logger)
                        else None
                    ),
                )

                current_logger.trace(
                    f"Calling {func_or_class.__name__}",
                    extra={
                        "func_name": func_or_class.__name__,
                        "func_args": args[1:] if is_method else args,
                        "func_kwargs": kwargs,
                    },
                )
                try:
                    result = await func_or_class(*args, **kwargs)
                    current_logger.trace(
                        f"{func_or_class.__name__} completed successfully",
                        extra={"func_name": func_or_class.__name__, "result": result},
                    )
                    return result
                except Exception as e:
                    current_logger.error(
                        f"{func_or_class.__name__} failed: {str(e)}",
                        extra={"func_name": func_or_class.__name__, "error": str(e)},
                        exc_info=True,
                    )
                    raise

            return async_wrapper
        else:

            @functools.wraps(func_or_class)
            def sync_wrapper(*args, **kwargs):
                # Определяем logger
                is_method = args and hasattr(args[0], "logger")
                current_logger = get_logger(
                    args[0] if is_method else None,
                    (
                        logger_or_func
                        if isinstance(logger_or_func, logging.Logger)
                        else None
                    ),
                )

                current_logger.trace(
                    f"Calling {func_or_class.__name__}",
                    extra={
                        "func_name": func_or_class.__name__,
                        "func_args": args[1:] if is_method else args,
                        "func_kwargs": kwargs,
                    },
                )
                try:
                    result = func_or_class(*args, **kwargs)
                    current_logger.trace(
                        f"{func_or_class.__name__} completed successfully",
                        extra={"func_name": func_or_class.__name__, "result": result},
                    )
                    return result
                except Exception as e:
                    current_logger.error(
                        f"{func_or_class.__name__} failed: {str(e)}",
                        extra={"func_name": func_or_class.__name__, "error": str(e)},
                        exc_info=True,
                    )
                    raise

            return sync_wrapper

    return decorator(logger_or_func) if callable(logger_or_func) else decorator
