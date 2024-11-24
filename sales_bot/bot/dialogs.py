import logging
from pyrogram import filters
from .client import app
from db.queries import get_db, save_message
from db.models import Dialog, Message
from .gpt import generate_initial_message, generate_response, check_qualification

logger = logging.getLogger(__name__)

async def get_active_dialog(db, username: str) -> Dialog:
    """Получение активного диалога с пользователем"""
    return db.query(Dialog).filter(
        Dialog.target_username == username,
        Dialog.status == 'active'
    ).first()

async def get_dialog_history(db, dialog_id: int) -> list:
    """Получение истории диалога"""
    messages = db.query(Message).filter(
        Message.dialog_id == dialog_id
    ).order_by(Message.timestamp).all()

    return [
        {'direction': msg.direction, 'content': msg.content}
        for msg in messages
    ]

@app.on_message(filters.private & ~filters.command(["start", "stop", "list", "view", "export", "export_all"]) & ~filters.me)
async def message_handler(client, message):
    """Handle incoming messages"""
    try:
        username = message.from_user.username
        if not username:
            return

        db = await get_db()
        try:
            # Check for active dialog
            dialog = await get_active_dialog(db, username)
            if not dialog:
                return

            # Save incoming message
            message_text = message.text
            await save_message(dialog.id, "in", message_text)

            # Get dialog history
            history = await get_dialog_history(db, dialog.id)

            # Check qualification
            qualified, reason = await check_qualification(history)

            # Generate and send response
            if qualified:
                response = ("Отлично! Вы соответствуете нашим критериям. "
                          "Давайте организуем звонок с менеджером для обсуждения деталей. "
                          "В какое время вам удобно пообщаться?")
                dialog.status = 'qualified'
                db.commit()
            else:
                response = await generate_response(history, message_text)

            # Save and send response
            await save_message(dialog.id, "out", response)
            await message.reply_text(response)

            logger.info(f"Processed message in dialog {dialog.id} with @{username}")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in message_handler: {e}")
        await message.reply_text(
            "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже."
        )

async def start_dialog_with_user(username: str) -> bool:
    """Начало диалога с пользователем"""
    try:
        # Генерируем первое сообщение
        initial_message = await generate_initial_message()

        db = await get_db()

        # Проверяем наличие активного диалога
        existing_dialog = await get_active_dialog(db, username)
        if existing_dialog:
            return False

        try:
            # Пробуем получить пользователя и отправить сообщение
            user = await app.get_input_entity(f"@{username}")
            await app.send_message(user, initial_message)
        except ValueError as e:
            logger.error(f"Could not find user @{username}: {e}")
            return False
        except Exception as e:
            logger.error(f"Could not send message to @{username}: {e}")
            return False

        # Создаем новый диалог только если сообщене отправлено успешно
        dialog = Dialog(target_username=username, status='active')
        db.add(dialog)
        db.commit()

        # Сохраняем первое сообщение
        await save_message(dialog.id, "out", initial_message)

        logger.info(f"Successfully started dialog with @{username}")
        return True

    except Exception as e:
        logger.error(f"Error starting dialog with @{username}: {e}")
        return False
