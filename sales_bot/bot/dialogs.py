import logging
from typing import Any, Dict, List, Tuple

from accounts.manager import AccountManager
from db.models import Dialog, DialogStatus, MessageDirection
from db.queries import AccountQueries, DialogQueries, with_queries
from pyrogram import filters
from pyrogram.types import Message as PyrogramMessage

from .client import app
from .gpt import check_qualification, generate_initial_message, generate_response

logger = logging.getLogger(__name__)


@with_queries(DialogQueries)
async def get_dialog_history(
    dialog_id: int, queries: DialogQueries
) -> List[Dict[str, Any]]:
    """
    Получение истории диалога

    :param dialog_id: Dialog ID to get history for
    :param queries: Dialog queries executor
    :return: List of messages with direction and content
    """
    messages = await queries.get_dialog_messages(dialog_id)
    return [{"direction": msg.direction, "content": msg.content} for msg in messages]


@with_queries(DialogQueries)
async def check_and_process_message(
    message: PyrogramMessage, dialog: Dialog, queries: DialogQueries
) -> Tuple[str, bool]:
    """
    Проверка и обработка входящего сообщения

    :param message: Incoming message
    :param dialog: Active dialog
    :param queries: Dialog queries executor
    :return: Tuple of (response text, whether user is qualified)
    """
    # Save incoming message
    message_text = message.text
    await queries.save_message(dialog.id, MessageDirection.in_, message_text)

    # Get dialog history
    history = await get_dialog_history(dialog.id, queries)

    # Check qualification
    qualified, reason = await check_qualification(history)

    # Generate response
    if qualified:
        response = (
            "Отлично! Вы соответствуете нашим критериям. "
            "Давайте организуем звонок с менеджером для обсуждения деталей. "
            "В какое время вам удобно пообщаться?"
        )
        await queries.update_dialog_status(dialog.id, DialogStatus.qualified)
    else:
        response = await generate_response(history, message_text)

    return response, qualified


@app.on_message(
    filters.private
    & ~filters.command(["start", "stop", "list", "view", "export", "export_all"])
    & ~filters.me
)
@with_queries(DialogQueries, AccountQueries)
async def message_handler(
    client,
    message: PyrogramMessage,
    queries: DialogQueries,
    account_queries: AccountQueries,
):
    """
    Handle incoming messages

    :param client: Pyrogram client
    :param message: Incoming message
    :param queries: Dialog queries executor
    :param account_queries: Account queries executor
    """
    username = message.from_user.username
    if not username:
        return

    try:
        # Check for active dialog
        dialog = await queries.get_active_dialog(username)
        if not dialog:
            return

        # Process message
        response, qualified = await check_and_process_message(message, dialog, queries)

        # Get account manager
        manager = AccountManager()

        # Get available account (preferably the same one that was used before)
        account = None
        if dialog.account_id:
            account = await account_queries.get_account_by_id(dialog.account_id)
            if not account or not account.can_be_used:
                account = await manager.get_available_account()
        else:
            account = await manager.get_available_account()

        if not account:
            logger.error("No available accounts to send message")
            return

        # Update dialog account if changed
        if dialog.account_id != account.id:
            await queries.update_dialog_account(dialog.id, account.id)

        # Send response
        if await manager.send_message(account, username, response):
            # Save outgoing message
            await queries.save_message(dialog.id, MessageDirection.out, response)
        else:
            logger.error(f"Failed to send message to {username}")

    except Exception as e:
        logger.error(f"Error handling message from {username}: {e}", exc_info=True)


@with_queries(DialogQueries, AccountQueries)
async def start_dialog_with_user(
    username: str, queries: DialogQueries, account_queries: AccountQueries
) -> bool:
    """
    Начало диалога с пользователем

    :param username: Username to start dialog with
    :param queries: Dialog queries executor
    :param account_queries: Account queries executor
    :return: True if dialog started successfully
    """
    try:
        # Check if user already has active dialog
        existing_dialog = await queries.get_active_dialog(username)
        if existing_dialog:
            logger.warning(f"User {username} already has active dialog")
            return False

        # Get available account
        manager = AccountManager()
        account = await manager.get_available_account()
        if not account:
            logger.error("No available accounts")
            return False

        # Create dialog
        dialog = await queries.create_dialog(username, account.id)
        if not dialog:
            logger.error(f"Failed to create dialog for {username}")
            return False

        # Generate and send initial message
        initial_message = await generate_initial_message()
        if await manager.send_message(account, username, initial_message):
            # Save outgoing message
            await queries.save_message(dialog.id, MessageDirection.out, initial_message)
            return True
        else:
            logger.error(f"Failed to send initial message to {username}")
            await queries.update_dialog_status(dialog.id, DialogStatus.failed)
            return False

    except Exception as e:
        logger.error(f"Error starting dialog with {username}: {e}", exc_info=True)
        return False
