"""Testing command handlers."""

import logging
from typing import Dict

from core.messaging.conductor import DialogConductor
from core.telegram.client import app
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# Store active test dialogs
test_dialogs: Dict[int, DialogConductor] = {}


@app.on_message(filters.command("test_dialog"))
async def cmd_test_dialog(client: Client, message: Message):
    """Test dialog with sales bot."""
    user_id = message.from_user.id

    # Check if user already has active dialog
    if user_id in test_dialogs:
        await message.reply(
            "⚠️ У вас уже есть активный тестовый диалог. Дождитесь его завершения."
        )
        return

    try:
        # Create conductor for test dialog
        async def send_message(text: str) -> None:
            await message.reply(text)

        conductor = DialogConductor(send_func=send_message)
        test_dialogs[user_id] = conductor

        # Start dialog
        await conductor.start_dialog()
        logger.info(f"Started test dialog for user {user_id}")

    except Exception as e:
        logger.error(f"Error starting test dialog: {e}", exc_info=True)
        await message.reply("⚠️ Не удалось запустить тестовый диалог. Попробуйте позже.")
        if user_id in test_dialogs:
            del test_dialogs[user_id]


@app.on_message(~filters.command("test_dialog") & filters.private)
async def on_test_message(client: Client, message: Message):
    """Handle messages in test dialog."""
    user_id = message.from_user.id

    # Skip if user has no active test dialog
    if user_id not in test_dialogs:
        # If this is not a command, remind user to start new dialog
        if not message.text.startswith("/"):
            await message.reply(
                "Тестовый диалог не активен. Используйте /test_dialog чтобы начать новый."
            )
        return

    try:
        # Handle incoming message
        conductor = test_dialogs[user_id]
        is_completed, error = await conductor.handle_message(message.text)

        if is_completed:
            # Remove dialog first to prevent race conditions
            del test_dialogs[user_id]
            await message.reply(
                "🏁 Тестовый диалог завершен! Спасибо за участие.\n\nЧтобы начать новый диалог, используйте команду /test_dialog"
            )
        elif error:
            # Only show error if dialog wasn't completed normally
            if user_id in test_dialogs:
                del test_dialogs[user_id]
                await message.reply(
                    f"⚠️ Произошла ошибка при обработке сообщения: {error}\nДиалог завершен."
                )

    except Exception as e:
        logger.error(f"Error handling test message: {e}", exc_info=True)
        if user_id in test_dialogs:
            del test_dialogs[user_id]
            await message.reply(
                "⚠️ Произошла ошибка при обработке сообщения. Диалог завершен."
            )
