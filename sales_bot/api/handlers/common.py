"""Common utilities and constants for command handlers."""

import logging
from functools import wraps
from typing import Callable, TypeVar

from core.telegram.client import app
from infrastructure.config import (
    ACCESS_DENIED_MSG,
    ADMIN_TELEGRAM_ID,
    TESTER_TELEGRAM_IDS,
)
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# Constants
STATUS_EMOJIS = {
    "active": "✅",
    "disabled": "🔴",
    "blocked": "⛔",
    "unknown": "❓",
    "new": "🆕",
    "code_requested": "📱",
    "password_requested": "🔑",
    "warming": "🔥",
}

T = TypeVar("T")


def admin(func: Callable[..., T]) -> Callable[..., T]:
    """Admin-only command decorator."""

    @wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs) -> T:
        if message.from_user.id != ADMIN_TELEGRAM_ID:
            await message.reply(ACCESS_DENIED_MSG)
            return
        return await func(client, message, *args, **kwargs)

    return wrapper


def tester(func: Callable[..., T]) -> Callable[..., T]:
    """Tester command decorator. Allows both admin and testers to use the command."""

    @wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs) -> T:
        user_id = message.from_user.id
        if user_id != ADMIN_TELEGRAM_ID and user_id not in TESTER_TELEGRAM_IDS:
            await message.reply(ACCESS_DENIED_MSG)
            return
        return await func(client, message, *args, **kwargs)

    return wrapper


@app.on_message(filters.command("help"))
@admin
async def cmd_help(client: Client, message: Message):
    """Show help message with available commands."""
    help_text = """
*Команды администратора:*

Управление аккаунтами:
/accounts - Список аккаунтов
/add_account - Добавить аккаунт
/edit_account - Редактировать аккаунт
/delete_account - Удалить аккаунт
/export_accounts - Экспорт аккаунтов в CSV

Мониторинг:
/status - Статус системы
/logs - Последние логи
/errors - Последние ошибки

Тестирование:
/test_dialog - Тестировать диалог с ботом
"""
    await message.reply(help_text)
