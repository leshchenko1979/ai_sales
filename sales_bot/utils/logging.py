import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config import LOG_FILE, LOG_LEVEL


def setup_logging():
    """Настройка логирования"""
    # Создаем директорию для логов если её нет
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Настраиваем формат с миллисекундами
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Настраиваем файловый обработчик с ротацией
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # В файл пишем все логи

    # Настраиваем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)  # В консоль только INFO и выше

    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log application startup with precise timestamp
    logger = logging.getLogger(__name__)
    startup_msg = (
        f"Application starting at {datetime.now().isoformat(timespec='microseconds')}"
    )
    logger.error(startup_msg)  # Log at ERROR level as requested

    # Add separator line for better log readability
    logger.error("-" * 80)
