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
async def cmd_help(client: Client, message: Message):
    """Show help message with available commands."""
    help_text = """
*Бот для тестирования холодных продаж*

Доступные команды:
/test_dialog - Начать тестовый диалог
/help - Показать это сообщение

После завершения диалога вы сможете:
- Оценить сообщения бота 👍/👎
- Оставить комментарии к конкретным сообщениям
- Записать общее впечатление (текстом или голосом)
"""
    await message.reply(help_text)


@app.on_message(filters.command("start"))
async def cmd_start(client: Client, message: Message):
    """Welcome message for new users."""
    welcome_text = """
👋 Здравствуйте! Я бот для тестирования холодных продаж для компании "Открытый девелопмент".

🎯 Как это работает:
1. Используйте команду /test_dialog чтобы начать тестовый диалог
2. Я буду играть роль менеджера по продажам
3. Вы можете отвечать как реальный клиент
4. После завершения диалога вы сможете оценить его качество

✨ Ваша обратная связь поможет улучшить скрипты продаж и сделать общение более естественным.

🚀 Готовы начать? Используйте /test_dialog!

ℹ️ Если нужна помощь, используйте /help
"""
    await message.reply(welcome_text)
