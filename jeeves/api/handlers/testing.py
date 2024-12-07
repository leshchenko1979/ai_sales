"""Testing command handlers."""

import logging
from typing import Dict, List

from core.messaging import DialogConductorFactory, DialogStrategyType
from core.messaging.enums import DialogStatus
from core.telegram import create_forum_topic, forward_messages_to_topic
from core.telegram.client import app
from infrastructure.config import ANALYSIS_GROUP
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# Store active test dialogs
test_dialogs: Dict[int, DialogConductorFactory] = {}
# Store dialog messages for analysis
dialog_messages: Dict[int, List[Message]] = {}

# Status and tag mappings
STATUS_TO_TAG = {
    DialogStatus.active: "#уточнение",  # Dialog is still active
    DialogStatus.success: "#успех",  # Successful outcome
    DialogStatus.blocked: "#заблокировал",  # Blocked
    DialogStatus.rejected: "#отказ",  # Explicit rejection
    DialogStatus.not_qualified: "#неподходит",  # Not qualified
    DialogStatus.expired: "#истек",  # No response/dead
    DialogStatus.stopped: "#остановлен",  # Manually stopped
}

TAG_DESCRIPTIONS = {
    "#уточнение": "Требуется уточнение деталей",
    "#успех": "Успешный результат диалога",
    "#неподходит": "Клиент не соответствует критериям",
    "#отказ": "Отказ от предложения",
    "#тест": "Тестовый диалог с отделом продаж",
    "#заблокировал": "Клиент заблокировал бота",
    "#остановлен": "Диалог остановлен командой /stop",
    "#истек": "Диалог истек без ответа",
}


# Command handlers
@app.on_message(filters.command("test_dialog") & ~filters.private)
async def private_chat_filter(message):
    """Handle test_dialog command in non-private chats."""
    await message.reply(
        "⚠️ Чтобы протестировать диалог с ботом, пожалуйста:\n"
        "1. Перейдите в личный чат с ботом @ai_sales_bot\n"
        "2. Отправьте команду /test_dialog"
    )


@app.on_message(filters.command("test_dialog") & filters.private)
async def cmd_test_dialog(client: Client, message: Message):
    """Test dialog with sales bot."""
    user_id = message.from_user.id

    if user_id in test_dialogs:
        await message.reply(
            "⚠️ У вас уже есть активный тестовый диалог. Дождитесь его завершения."
        )
        return

    async def send_message(text: str) -> None:
        sent_msg = await message.reply(text)
        if user_id in dialog_messages:
            dialog_messages[user_id].append(sent_msg)

    try:
        conductor = DialogConductorFactory.create_conductor(
            strategy_type=DialogStrategyType.COLD_MEETING,
            send_func=send_message,
            telegram_id=user_id,
        )
        test_dialogs[user_id] = conductor
        dialog_messages[user_id] = [message]

        await conductor.start_dialog()
        logger.info(f"Started test dialog for user {user_id}")

    except Exception:
        await handle_error(
            message, "Не удалось запустить тестовый диалог. Попробуйте позже.", user_id
        )


@app.on_message(filters.command("stop") & filters.private)
async def cmd_stop_dialog(client: Client, message: Message):
    """Stop active test dialog."""
    user_id = message.from_user.id

    if user_id not in test_dialogs:
        await message.reply("У вас нет активного тестового диалога.")
        return

    try:
        conductor = test_dialogs[user_id]
        conductor.set_status(DialogStatus.stopped)  # Set status to stopped
        thread_link = await forward_dialog_for_analysis(client, user_id)
        await cleanup_dialog(user_id)
        await send_completion_message(message, thread_link, stopped=True)

    except Exception:
        await handle_error(message, "Произошла ошибка при остановке диалога.", user_id)


@app.on_message(~filters.command("test_dialog") & filters.private)
async def on_test_message(client: Client, message: Message):
    """Handle messages in test dialog."""
    user_id = message.from_user.id

    # Ignore messages from the bot itself
    if message.from_user.is_bot:
        return

    if user_id not in test_dialogs:
        if not message.text.startswith("/"):
            await message.reply(
                "Тестовый диалог не активен. Используйте /test_dialog чтобы начать новый."
            )
        return

    try:
        if user_id in dialog_messages:
            dialog_messages[user_id].append(message)

        conductor = test_dialogs[user_id]
        is_completed, error = await conductor.handle_message(message.text)

        if error:
            await handle_error(
                message,
                f"Произошла ошибка при обработке сообщения: {error}\nДиалог завершен.",
                user_id,
            )
            return

        if not is_completed:
            return

        thread_link = await forward_dialog_for_analysis(client, user_id)
        await cleanup_dialog(user_id)
        await send_completion_message(message, thread_link)

    except Exception:
        await handle_error(
            message,
            "Произошла ошибка при обработке сообщения. Диалог завершен.",
            user_id,
        )


# Dialog management functions
async def cleanup_dialog(user_id: int):
    """Clean up dialog data for user."""
    if user_id in test_dialogs:
        del test_dialogs[user_id]
    if user_id in dialog_messages:
        del dialog_messages[user_id]


async def handle_error(message: Message, error: str, user_id: int):
    """Handle error and cleanup dialog."""
    logger.error(f"Error: {error}", exc_info=True)
    await cleanup_dialog(user_id)
    await message.reply(f"⚠️ {error}")


async def send_completion_message(
    message: Message, thread_link: str, stopped: bool = False
):
    """Send completion message with thread link and feedback instructions."""
    action = "остановлен" if stopped else "завершен"
    await message.reply(
        f"Диалог {action} и переслан в группу анализа {ANALYSIS_GROUP}.\n"
        f"Вот ссылка: {thread_link}\n\n"
        "Пожалуйста, ответьте на сообщения бота, дав ваши комментарии\n"
    )


async def create_thread_message(
    client: Client,
    group_id: int,
    topic_id: int,
    messages: List[Message],
    status: DialogStatus,
) -> Message:
    """Create initial thread message with dialog info."""
    result_tag = STATUS_TO_TAG.get(status, "#тест")
    tag_description = TAG_DESCRIPTIONS.get(result_tag, "")

    return await client.send_message(
        chat_id=group_id,
        reply_to_message_id=topic_id,
        text=f"📊 Информация о диалоге:\n"
        f"- Тестировал: {messages[0].from_user.first_name} "
        f"(@{messages[0].from_user.username})\n"
        f"- Дата: {messages[0].date.strftime('%Y-%m-%d')}\n"
        f"- Итог: {result_tag} - {tag_description}\n\n"
        "Давайте обратную связь на конкретное сообщение, ответив на него, "
        "или на весь диалог, отправляя сообщения в эту тему.",
    )


# Forum topic management functions
async def forward_dialog_for_analysis(client: Client, user_id: int) -> str:
    """Forward dialog to testing group for analysis."""
    try:
        if user_id not in dialog_messages or user_id not in test_dialogs:
            logger.error(f"No messages or dialog found for user {user_id}")
            return ""

        messages = dialog_messages[user_id]
        conductor = test_dialogs[user_id]

        if not messages:
            logger.error("Empty messages list")
            return ""

        group = await client.get_chat(ANALYSIS_GROUP)
        if not group or not group.id:
            logger.error("Failed to get testing group info")
            return ""

        title = f"Диалог с {messages[0].from_user.first_name}"
        topic_id = await create_forum_topic(client, group.id, title)
        if not topic_id:
            return ""

        thread_msg = await create_thread_message(
            client, group.id, topic_id, messages, conductor.get_current_status()
        )

        await forward_messages_to_topic(client, messages, group.id, topic_id)

        thread_link = f"https://t.me/c/{str(group.id)[4:]}/{topic_id}/{thread_msg.id}"
        logger.info(f"Generated thread link: {thread_link}")
        return thread_link

    except Exception as e:
        logger.error(f"Error forwarding dialog: {e}", exc_info=True)
        return ""
