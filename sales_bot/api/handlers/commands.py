"""Bot command handlers."""

import logging
from functools import wraps
from typing import Callable, TypeVar

from core.accounts import AccountManager, AccountMonitor
from core.db import AccountQueries, DialogQueries, get_db, with_queries
from core.telegram.client import app
from infrastructure.config import ADMIN_TELEGRAM_ID
from pyrogram import Client
from pyrogram.filters import command
from pyrogram.types import Message as PyrogramMessage
from utils.export import export_all_dialogs, export_dialog

logger = logging.getLogger(__name__)

# Constants
ERROR_MSG = "Произошла ошибка. Попробуйте позже."
STATUS_EMOJIS = {
    "active": "✅",
    "disabled": "🔴",
    "blocked": "⛔",
    "unknown": "❓",
}

T = TypeVar("T")


def admin(func: Callable[..., T]) -> Callable[..., T]:
    """Admin-only command decorator."""

    @wraps(func)
    async def wrapper(client: Client, message: PyrogramMessage, *args, **kwargs) -> T:
        if message.from_user.id != ADMIN_TELEGRAM_ID:
            await message.reply("Недостаточно прав для выполнения команды.")
            return
        return await func(client, message, *args, **kwargs)

    return wrapper


def _normalize_phone(phone: str) -> str:
    """Normalize phone number to standard format."""
    return phone.strip().replace("+", "")


# Account Management Commands
@app.on_message(command(["account_add", "addacc"]))  # Added alias for convenience
@admin
async def cmd_add_account(client: Client, message: PyrogramMessage):
    """Add new Telegram account."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /account_add phone\n" "Пример: /account_add 79001234567"
            )
            return

        phone = _normalize_phone(args[1])

        # Create account
        manager = AccountManager()
        account = await manager.get_or_create_account(phone)

        if not account:
            await message.reply("Не удалось добавить аккаунт.")
            return

        # Request authorization code
        if await manager.request_code(phone):
            await message.reply(
                "Аккаунт добавлен. Введите код подтверждения командой:\n"
                f"/account_auth {phone} код"
            )
        else:
            await message.reply("Не удалось запросить код авторизации.")

    except Exception as e:
        logger.error(
            f"Error in cmd_add_account: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_auth", "auth"]))  # Shorter alias
@admin
async def cmd_authorize(client: Client, message: PyrogramMessage):
    """Authorize Telegram account."""
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.reply(
                "Использование: /account_auth phone code\n"
                "Пример: /account_auth 79001234567 12345"
            )
            return

        phone = _normalize_phone(args[1])
        code = args[2]

        # Authorize account
        manager = AccountManager()
        success = await manager.authorize_account(phone, code)

        if success:
            await message.reply("Аккаунт успешно авторизован.")
        else:
            await message.reply(
                "Не удалось авторизовать аккаунт. Проверьте код и попробуйте снова."
            )

    except Exception as e:
        logger.error(
            f"Error in cmd_authorize: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_list", "accounts"]))
@admin
@with_queries(AccountQueries)
async def cmd_list_accounts(
    client: Client, message: PyrogramMessage, queries: AccountQueries
):
    """List all registered accounts and their status."""
    try:
        # Get all accounts
        accounts = await queries.get_all_accounts()
        if not accounts:
            await message.reply("Нет добавленных аккаунтов.")
            return

        # Prepare statistics
        stats = {
            "total": len(accounts),
            "active": 0,
            "disabled": 0,
            "blocked": 0,
            "flood_wait": 0,
        }

        # Prepare account list
        account_list = []
        for account in accounts:
            # Update statistics
            stats[account.status.value] += 1
            if account.is_flood_wait:
                stats["flood_wait"] += 1

            # Add to list
            status_emoji = STATUS_EMOJIS.get(
                account.status.value, STATUS_EMOJIS["unknown"]
            )
            account_list.append(
                f"{status_emoji} {account.phone} - {account.status.value}"
                + (" (flood wait)" if account.is_flood_wait else "")
            )

        # Prepare message
        message_text = "Список аккаунтов:\n\n"
        message_text += "\n".join(account_list)
        message_text += f"\n\nВсего: {stats['total']}"
        message_text += f"\nАктивных: {stats['active']}"
        message_text += f"\nОтключенных: {stats['disabled']}"
        message_text += f"\nЗаблокированных: {stats['blocked']}"
        message_text += f"\nВ флуд-контроле: {stats['flood_wait']}"

        await message.reply(message_text)

    except Exception as e:
        logger.error(
            f"Error in cmd_list_accounts: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_check", "check"]))
@admin
@with_queries(AccountQueries)
async def cmd_check_account(
    client: Client, message: PyrogramMessage, queries: AccountQueries
):
    """Check specific account status."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /account_check phone\n"
                "Пример: /account_check 79001234567"
            )
            return

        phone = _normalize_phone(args[1])

        # Get account
        account = await queries.get_account_by_phone(phone)
        if not account:
            await message.reply("Аккаунт не найден.")
            return

        # Check status
        monitor = AccountMonitor()
        if await monitor.check_account(account):
            await message.reply(
                f"Аккаунт {phone} в порядке.\n"
                f"Статус: {account.status.value}\n"
                f"Последнее использование: {account.last_used_at}"
            )
        else:
            await message.reply(
                f"Аккаунт {phone} недоступен.\n"
                f"Статус: {account.status.value}"
                + (" (flood wait)" if account.is_flood_wait else "")
            )

    except Exception as e:
        logger.error(
            f"Error in cmd_check_account: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_checkall", "checkall"]))
@admin
async def cmd_check_all_accounts(client: Client, message: PyrogramMessage):
    """Check status of all accounts."""
    try:
        monitor = AccountMonitor()
        stats = await monitor.check_accounts()

        if not stats:
            await message.reply("Не удалось проверить аккаунты.")
            return

        # Prepare report
        report = "Результаты проверки:\n\n"
        report += f"Всего аккаунтов: {stats['total']}\n"
        report += f"Активных: {stats['active']}\n"
        report += f"Отключенных: {stats['disabled']}\n"
        report += f"Заблокированных: {stats['blocked']}\n"
        report += f"В флуд-контроле: {stats['flood_wait']}"

        await message.reply(report)

    except Exception as e:
        logger.error(
            f"Error in cmd_check_all_accounts: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_resend", "resend"]))
@admin
async def cmd_resend_code(client: Client, message: PyrogramMessage):
    """Resend authorization code for account."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /account_resend phone\n"
                "Пример: /account_resend 79001234567"
            )
            return

        phone = _normalize_phone(args[1])

        # Request code
        manager = AccountManager()
        if await manager.request_code(phone):
            await message.reply(
                "Код отправлен повторно. Введите его командой:\n"
                f"/account_auth {phone} код"
            )
        else:
            await message.reply("Не удалось отправить код повторно.")

    except Exception as e:
        logger.error(
            f"Error in cmd_resend_code: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


# Dialog Management Commands
@app.on_message(command(["dialog_export", "export"]))
@admin
async def cmd_export_dialog(client: Client, message: PyrogramMessage):
    """Export specific dialog history."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /dialog_export username\n"
                "Пример: /dialog_export @username"
            )
            return

        username = args[1].replace("@", "")

        # Export dialog
        file_path = await export_dialog(username)
        if not file_path:
            await message.reply("Не удалось экспортировать диалог.")
            return

        # Send file
        await message.reply_document(
            document=file_path,
            caption=f"Экспорт диалога с {username}",
        )

    except Exception as e:
        logger.error(
            f"Error in cmd_export_dialog: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["dialog_exportall", "exportall"]))
@admin
async def cmd_export_all_dialogs(client: Client, message: PyrogramMessage):
    """Export all dialog histories."""
    try:
        # Export dialogs
        file_path = await export_all_dialogs()
        if not file_path:
            await message.reply("Не удалось экспортировать диалоги.")
            return

        # Send file
        await message.reply_document(
            document=file_path,
            caption="Экспорт всех диалогов",
        )

    except Exception as e:
        logger.error(
            f"Error in cmd_export_all_dialogs: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


# User Commands
@app.on_message(command(["dialog_start", "start_chat"]))
@admin
async def cmd_start_dialog(client: Client, message: PyrogramMessage):
    """Handle dialog start command."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /dialog_start username\n"
                "Пример: /dialog_start @username"
            )
            return

        username = args[1].replace("@", "")

        # Get available account
        manager = AccountManager()
        account = await manager.get_available_account()

        if not account:
            await message.reply("Нет доступных аккаунтов для отправки сообщений.")
            return

        # Create dialog
        async with get_db() as session:
            queries = DialogQueries(session)
            dialog = await queries.create_dialog(username, account.id)

            if not dialog:
                await message.reply("Не удалось создать диалог.")
                return

            await message.reply(
                f"Начат новый диалог с {username}\n"
                f"Используется аккаунт: {account.phone}"
            )

    except Exception as e:
        logger.error(
            f"Error in cmd_start_dialog: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["help", "?"]))
@admin
async def cmd_help(client: Client, message: PyrogramMessage):
    """Show help message with available commands."""
    help_text = """
🤖 *Команды администратора:*

📱 *Управление аккаунтами:*
/account_add (или /addacc) - Добавить новый аккаунт
/account_auth (или /auth) - Авторизовать аккаунт
/account_list (или /accounts) - Список всех аккаунтов
/account_check (или /check) - Проверить статус аккаунта
/account_checkall (или /checkall) - Проверить все аккаунты
/account_resend (или /resend) - Повторно отправить код

💬 *Управление диалогами:*
/dialog_start (или /start_chat) - Начать новый диалог с пользователем
/dialog_export (или /export) - Экспорт диалога
/dialog_exportall (или /exportall) - Экспорт всех диалогов

❓ /help - Показать это сообщение
"""
    await message.reply(help_text, parse_mode="markdown")
