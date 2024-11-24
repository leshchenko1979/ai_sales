import logging
from typing import Optional

from accounts.manager import AccountManager
from db.models import Dialog, Message
from db.queries import DialogQueries, get_db
from pyrogram import filters

from .client import app
from .gpt import check_qualification, generate_initial_message, generate_response

logger = logging.getLogger(__name__)


async def get_active_dialog(db, username: str) -> Optional[Dialog]:
    """Получение активного диалога с пользователем"""
    return (
        db.query(Dialog)
        .filter(Dialog.target_username == username, Dialog.status == "active")
        .first()
    )


async def get_dialog_history(db, dialog_id: int) -> list:
    """Получение истории диалога"""
    messages = (
        db.query(Message)
        .filter(Message.dialog_id == dialog_id)
        .order_by(Message.timestamp)
        .all()
    )

    return [{"direction": msg.direction, "content": msg.content} for msg in messages]


async def save_message(db, dialog_id: int, direction: str, content: str):
    """Сохранение сообщения"""
    message = Message(dialog_id=dialog_id, direction=direction, content=content)
    db.add(message)
    db.commit()


@app.on_message(
    filters.private
    & ~filters.command(["start", "stop", "list", "view", "export", "export_all"])
    & ~filters.me
)
async def message_handler(client, message):
    """Handle incoming messages"""
    username = message.from_user.username
    if not username:
        return

    try:
        async with get_db() as db:
            # Check for active dialog
            dialog_queries = DialogQueries(db)
            dialog = await dialog_queries.get_active_dialog(username)
            if not dialog:
                return

            # Save incoming message
            message_text = message.text
            await dialog_queries.save_message(dialog.id, "in", message_text)

            # Get dialog history
            history = await dialog_queries.get_dialog_history(dialog.id)

            # Check qualification
            qualified, reason = await check_qualification(history)

            # Generate and send response
            if qualified:
                response = (
                    "Отлично! Вы соответствуете нашим критериям. "
                    "Давайте организуем звонок с менеджером для обсуждения деталей. "
                    "В какое время вам удобно пообщаться?"
                )
                dialog.status = "qualified"
                db.commit()
            else:
                response = await generate_response(history, message_text)

            # Get account manager
            account_manager = AccountManager(db)

            # Get available account (preferably the same one that was used before)
            account = None
            if dialog.account_id:
                account = await account_manager.queries.get_account_by_id(
                    dialog.account_id
                )
                if not account or not account.is_available:
                    account = await account_manager.get_available_account()
            else:
                account = await account_manager.get_available_account()

            if not account:
                logger.error(f"No available accounts to respond in dialog {dialog.id}")
                return

            # Update dialog with account if needed
            if not dialog.account_id:
                dialog.account_id = account.id
                db.commit()

            # Send and save response
            success = await account_manager.send_message(account, username, response)
            if success:
                await save_message(db, dialog.id, "out", response)
                logger.info(f"Processed message in dialog {dialog.id} with @{username}")
            else:
                logger.error(f"Failed to send message in dialog {dialog.id}")

    except Exception as e:
        logger.error(f"Error in message_handler: {e}")
        await message.reply_text(
            "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже."
        )


async def start_dialog_with_user(username: str) -> bool:
    """Начало диалога с пользователем"""
    try:
        async with get_db() as db:
            dialog_queries = DialogQueries(db)
            # Проверяем наличие активного диалога
            existing_dialog = await dialog_queries.get_active_dialog(username)
            if existing_dialog:
                return False

            # Получаем доступный аккаунт
            account_manager = AccountManager(db)
            account = await account_manager.get_available_account()
            if not account:
                logger.error(f"No available accounts to start dialog with @{username}")
                return False

            # Генерируем первое сообщение
            initial_message = await generate_initial_message()

            # Пробуем отправить сообщение
            success = await account_manager.send_message(
                account, username, initial_message
            )
            if not success:
                logger.error(f"Could not send message to @{username}")
                return False

            # Создаем новый диалог
            dialog = Dialog(
                account_id=account.id, target_username=username, status="active"
            )
            db.add(dialog)
            db.commit()

            # Сохраняем первое сообщение
            await save_message(db, dialog.id, "out", initial_message)

            logger.info(f"Successfully started dialog with @{username}")
            return True

    except Exception as e:
        logger.error(f"Error starting dialog with @{username}: {e}")
        return False
