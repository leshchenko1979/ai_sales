"""Account management command handlers."""

from core.accounts import AccountManager, AccountMonitor
from core.accounts.queries import AccountQueries
from core.db import with_queries
from core.telegram.client import app
from infrastructure.config import ERROR_MSG
from pyrogram import Client
from pyrogram.filters import command
from pyrogram.types import Message
from utils.phone import normalize_phone

from .common import STATUS_EMOJIS, admin, logger


@app.on_message(command(["account_add", "addacc"]))
@admin
async def cmd_add_account(client: Client, message: Message):
    """Add new Telegram account."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /account_add phone\n"
                "Пример: /account_add +79991234567"
            )
            return

        phone = normalize_phone(args[1])
        manager = AccountManager()
        account = await manager.get_or_create_account(phone)

        if not account:
            await message.reply("Не удалось создать аккаунт.")
            return

        await message.reply(f"Аккаунт {phone} создан.")

    except Exception as e:
        logger.error(
            f"Error in cmd_add_account: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_auth", "auth"]))
@admin
async def cmd_authorize(client: Client, message: Message):
    """Authorize Telegram account."""
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.reply(
                "Использование: /account_auth phone code\n"
                "Пример: /account_auth +79991234567 12345"
            )
            return

        phone = normalize_phone(args[1])
        code = args[2]

        manager = AccountManager()
        if await manager.authorize_account(phone, code):
            await message.reply(f"Аккаунт {phone} успешно авторизован.")
        else:
            await message.reply(f"Не удалось авторизовать аккаунт {phone}.")

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
async def cmd_list_accounts(client: Client, message: Message, queries: AccountQueries):
    """List all registered accounts and their status."""
    try:
        accounts = await queries.get_all_accounts()
        if not accounts:
            await message.reply("Нет зарегистрированных аккаунтов.")
            return

        monitor = AccountMonitor()
        stats = await monitor.check_accounts()

        response = ["*Список аккаунтов:*\n"]
        for account in accounts:
            status = stats.get(account.phone, "unknown")
            emoji = STATUS_EMOJIS.get(status, "❓")
            response.append(
                f"{emoji} `{account.phone}` - {status}\n"
                f"├ Сообщений: {account.daily_messages}\n"
                f"└ ID: {account.id}"
            )

        await message.reply("\n".join(response))

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
async def cmd_check_account(client: Client, message: Message, queries: AccountQueries):
    """Check specific account status."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /account_check phone\n"
                "Пример: /account_check +79991234567"
            )
            return

        phone = normalize_phone(args[1])
        account = await queries.get_account_by_phone(phone)
        if not account:
            await message.reply(f"Аккаунт {phone} не найден.")
            return

        monitor = AccountMonitor()
        status = await monitor.check_account(account)
        emoji = STATUS_EMOJIS.get(status, "❓")

        response = [
            f"*Статус аккаунта {phone}:*\n",
            f"{emoji} {status}\n",
            f"├ ID: {account.id}",
            f"├ Сообщений: {account.daily_messages}",
            f"└ Доступен: {'да' if account.is_available else 'нет'}",
        ]

        await message.reply("\n".join(response))

    except Exception as e:
        logger.error(
            f"Error in cmd_check_account: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_checkall", "checkall"]))
@admin
async def cmd_check_all_accounts(client: Client, message: Message):
    """Check status of all accounts."""
    try:
        monitor = AccountMonitor()
        stats = await monitor.check_accounts()

        if not stats:
            await message.reply("Нет аккаунтов для проверки.")
            return

        response = ["*Статус всех аккаунтов:*\n"]
        for phone, status in stats.items():
            emoji = STATUS_EMOJIS.get(status, "❓")
            response.append(f"{emoji} `{phone}` - {status}")

        await message.reply("\n".join(response))

    except Exception as e:
        logger.error(
            f"Error in cmd_check_all_accounts: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["account_resend", "resend"]))
@admin
async def cmd_resend_code(client: Client, message: Message):
    """Resend authorization code for account."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /account_resend phone\n"
                "Пример: /account_resend +79991234567"
            )
            return

        phone = normalize_phone(args[1])
        manager = AccountManager()

        if await manager.request_code(phone):
            await message.reply(f"Код авторизации отправлен на номер {phone}.")
        else:
            await message.reply(f"Не удалось отправить код на номер {phone}.")

    except Exception as e:
        logger.error(
            f"Error in cmd_resend_code: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)
