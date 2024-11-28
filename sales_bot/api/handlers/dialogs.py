"""Dialog management command handlers."""

from core.accounts import AccountManager
from core.db import get_db
from core.messaging.queries import DialogQueries
from core.telegram.client import app
from infrastructure.config import ERROR_MSG
from pyrogram import Client
from pyrogram.filters import command
from pyrogram.types import Message
from utils.export import export_all_dialogs, export_dialog

from .common import admin, logger


@app.on_message(command(["dialog_start", "start_chat"]))
@admin
async def cmd_start_dialog(client: Client, message: Message):
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


@app.on_message(command(["dialog_export", "export"]))
@admin
async def cmd_export_dialog(client: Client, message: Message):
    """Export specific dialog history."""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /dialog_export dialog_id\n" "Пример: /dialog_export 123"
            )
            return

        dialog_id = int(args[1])
        file_path = await export_dialog(dialog_id)

        if not file_path:
            await message.reply(f"Диалог {dialog_id} не найден.")
            return

        # Send file
        await message.reply_document(
            file_path,
            caption=f"Экспорт диалога {dialog_id}",
        )

    except ValueError:
        await message.reply("Некорректный ID диалога.")
    except Exception as e:
        logger.error(
            f"Error in cmd_export_dialog: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command(["dialog_exportall", "exportall"]))
@admin
async def cmd_export_all_dialogs(client: Client, message: Message):
    """Export all dialog histories."""
    try:
        # Export dialogs
        file_path = await export_all_dialogs()

        if not file_path:
            await message.reply("Нет диалогов для экспорта.")
            return

        # Send file
        await message.reply_document(
            file_path,
            caption="Экспорт всех диалогов",
        )

    except Exception as e:
        logger.error(
            f"Error in cmd_export_all_dialogs: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)
