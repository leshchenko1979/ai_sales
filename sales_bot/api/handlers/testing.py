"""Testing command handlers."""

import logging
from typing import Dict, List

from core.messaging.conductor import DialogConductor
from core.messaging.enums import DialogStatus
from core.telegram.client import app
from pyrogram import Client, filters
from pyrogram.raw import functions
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# Store active test dialogs
test_dialogs: Dict[int, DialogConductor] = {}
# Store dialog messages for analysis
dialog_messages: Dict[int, List[Message]] = {}
# Testing group username
TESTING_GROUP = "@sales_bot_analysis"

# Mapping from dialog status to result tag
STATUS_TO_TAG = {
    DialogStatus.active: "#уточнение",  # Dialog is still active
    DialogStatus.closed: "#продажа",  # Successful sale
    DialogStatus.blocked: "#заблокировал",  # Blocked
    DialogStatus.rejected: "#отказ",  # Explicit rejection
    DialogStatus.not_qualified: "#неподходит",  # Not qualified
    DialogStatus.meeting_scheduled: "#успех",  # Meeting scheduled
}

# Tag descriptions for the message
TAG_DESCRIPTIONS = {
    "#уточнение": "Требуется уточнение деталей",
    "#продажа": "Успешная продажа",
    "#неподходит": "Клиент не соответствует критериям",
    "#отказ": "Отказ от покупки",
    "#успех": "Назначена встреча с клиентом",
    "#тест": "Тестовый диалог с отделом продаж",
    "#заблокировал": "Клиент заблокировал бота",
}


async def send_completion_message(
    message: Message, thread_link: str, stopped: bool = False
):
    """Send completion message with thread link and feedback instructions."""
    action = "остановлен" if stopped else "завершен"
    await message.reply(
        f"Диалог {action} и переслан в группу анализа.\n"
        f"Вот ссылка на тред: {thread_link}\n\n"
        "Пожалуйста, оцените сообщения бота:\n"
        "- Поставьте реакции 👍/👎\n"
        "- Ответьте на сообщение с комментарием\n"
        "- Запишите общее впечатление (можно голосовым)"
    )


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
            sent_msg = await message.reply(text)
            if user_id in dialog_messages:
                dialog_messages[user_id].append(sent_msg)

        conductor = DialogConductor(send_func=send_message)
        test_dialogs[user_id] = conductor
        dialog_messages[user_id] = [message]  # Store initial message

        # Start dialog
        await conductor.start_dialog()
        logger.info(f"Started test dialog for user {user_id}")

    except Exception as e:
        logger.error(f"Error starting test dialog: {e}", exc_info=True)
        await message.reply("⚠️ Не удалось запустить тестовый диалог. Попробуйте позже.")
        if user_id in test_dialogs:
            del test_dialogs[user_id]
        if user_id in dialog_messages:
            del dialog_messages[user_id]


@app.on_message(filters.command("stop") & filters.private)
async def cmd_stop_dialog(client: Client, message: Message):
    """Stop active test dialog."""
    user_id = message.from_user.id

    if user_id not in test_dialogs:
        await message.reply("У вас нет активного тестового диалога.")
        return

    try:
        # Forward dialog to testing group
        thread_link = await forward_dialog_for_analysis(client, user_id)
        # Remove dialog
        del test_dialogs[user_id]
        del dialog_messages[user_id]
        # Send completion message
        await send_completion_message(message, thread_link, stopped=True)

    except Exception as e:
        logger.error(f"Error stopping test dialog: {e}", exc_info=True)
        if user_id in test_dialogs:
            del test_dialogs[user_id]
        if user_id in dialog_messages:
            del dialog_messages[user_id]
        await message.reply("⚠️ Произошла ошибка при остановке диалога.")


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
        # Store user message
        if user_id in dialog_messages:
            dialog_messages[user_id].append(message)
            logger.info(
                f"Stored message for user {user_id}, total messages: {len(dialog_messages[user_id])}"
            )

        # Handle incoming message
        conductor = test_dialogs[user_id]
        logger.info(f"Handling message from user {user_id}")
        is_completed, error = await conductor.handle_message(message.text)
        logger.info(f"Message handled, is_completed: {is_completed}, error: {error}")

        if is_completed:
            logger.info(
                f"Dialog completed for user {user_id}, forwarding to analysis group"
            )
            # Forward dialog to testing group
            thread_link = await forward_dialog_for_analysis(client, user_id)
            logger.info(f"Got thread link: {thread_link}")
            # Remove dialog first to prevent race conditions
            del test_dialogs[user_id]
            del dialog_messages[user_id]
            logger.info(f"Removed dialog data for user {user_id}")
            # Send completion message
            await send_completion_message(message, thread_link)
            logger.info(f"Sent completion message to user {user_id}")
        elif error:
            # Only show error if dialog wasn't completed normally
            logger.warning(f"Error in dialog for user {user_id}: {error}")
            if user_id in test_dialogs:
                del test_dialogs[user_id]
            if user_id in dialog_messages:
                del dialog_messages[user_id]
            await message.reply(
                f"⚠️ Произошла ошибка при обработке сообщения: {error}\nДиалог завершен."
            )

    except Exception as e:
        logger.error(f"Error handling test message: {e}", exc_info=True)
        if user_id in test_dialogs:
            del test_dialogs[user_id]
        if user_id in dialog_messages:
            del dialog_messages[user_id]
        await message.reply(
            "⚠️ Произошла ошибка при обработке сообщения. Диалог завершен."
        )


async def forward_dialog_for_analysis(client: Client, user_id: int) -> str:
    """Forward dialog to testing group for analysis.

    Returns:
        str: Link to the thread message
    """
    try:
        if user_id not in dialog_messages or user_id not in test_dialogs:
            logger.error(f"No messages or dialog found for user {user_id}")
            return ""

        messages = dialog_messages[user_id]
        conductor = test_dialogs[user_id]

        if not messages:
            logger.error("Empty messages list")
            return ""

        logger.info(f"Forwarding {len(messages)} messages for user {user_id}")

        # Get group info
        group = await client.get_chat(TESTING_GROUP)
        if not group or not group.id:
            logger.error("Failed to get testing group info")
            return ""

        logger.info(f"Got testing group: {group.id}")

        # Create forum topic using raw API
        title = f"Диалог с {messages[0].from_user.first_name}"
        channel_peer = await client.resolve_peer(group.id)

        topic = await client.invoke(
            functions.channels.CreateForumTopic(
                channel=channel_peer,
                title=title,
                icon_color=0x6FB9F0,  # Light blue color
                random_id=client.rnd_id(),
            )
        )

        topic_id = topic.updates[0].id
        if not topic_id:
            logger.error("Failed to create forum topic")
            return ""

        logger.info(f"Created forum topic: {topic_id}")

        # Get dialog status and corresponding tag
        status = conductor.get_current_status()
        result_tag = STATUS_TO_TAG.get(status, "#тест")
        tag_description = TAG_DESCRIPTIONS.get(result_tag, "")

        # Send initial message in topic using reply_to
        thread_msg = await client.send_message(
            chat_id=group.id,
            reply_to_message_id=topic_id,
            text=f"📊 Информация о диалоге:\n"
            f"- Продавец: {messages[0].from_user.first_name}\n"
            f"- Дата: {messages[0].date.strftime('%Y-%m-%d')}\n"
            f"- Итог: {result_tag} - {tag_description}\n\n"
            f"💬 Диалог ниже.\n"
            f"Вы можете:\n"
            f"- Ответить на конкретное сообщение с комментарием\n"
            f"- Поставить реакцию на сообщение бота\n"
            f"- Записать общее впечатление (можно голосовым)",
        )

        logger.info(f"Created thread message: {thread_msg.id}")

        # Forward all messages in topic using raw API
        try:
            await client.invoke(
                functions.messages.ForwardMessages(
                    from_peer=await client.resolve_peer(messages[0].chat.id),
                    to_peer=await client.resolve_peer(group.id),
                    top_msg_id=topic_id,
                    id=[msg.id for msg in messages],
                    random_id=[client.rnd_id() for _ in messages],
                )
            )
        except Exception as e:
            logger.error(f"Error forwarding message: {e}")

        # Get thread link
        thread_link = f"https://t.me/c/{str(group.id)[4:]}/{topic_id}/{thread_msg.id}"
        logger.info(f"Generated thread link: {thread_link}")
        return thread_link

    except Exception as e:
        logger.error(f"Error forwarding dialog: {e}", exc_info=True)
        return ""
