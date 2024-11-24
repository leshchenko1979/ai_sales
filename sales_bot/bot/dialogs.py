import logging
from telethon import events
from .client import client
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

@client.on(events.NewMessage())
async def message_handler(event):
    """Обработчик входящих сообщений"""
    if event.is_private and not event.message.out:
        try:
            sender = await event.get_sender()
            username = sender.username
            if not username:
                return

            async for db in get_db():
                # Проверяем наличие активного диалога
                dialog = await get_active_dialog(db, username)
                if not dialog:
                    return

                # Сохраняем входящее сообщение
                message_text = event.message.text
                await save_message(dialog.id, "in", message_text)

                # Получаем историю диалога
                history = await get_dialog_history(db, dialog.id)

                # Проверяем квалификацию
                qualified, reason = await check_qualification(history)

                # Генерируем и отправляем ответ
                if qualified:
                    response = ("Отлично! Вы соответствуете нашим критериям. "
                              "Давайте организуем звонок с менеджером для обсуждения деталей. "
                              "В какое время вам удобно пообщаться?")
                    dialog.status = 'qualified'
                    db.commit()
                else:
                    response = await generate_response(history, message_text)

                # Сохраняем и отправляем ответ
                await save_message(dialog.id, "out", response)
                await event.respond(response)

                logger.info(f"Processed message in dialog {dialog.id} with @{username}")

        except Exception as e:
            logger.error(f"Error in message_handler: {e}")
            await event.respond(
                "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже."
            )

async def start_dialog_with_user(username: str) -> bool:
    """Начало диалога с пользователем"""
    try:
        # Генерируем первое сообщение
        initial_message = await generate_initial_message()

        async for db in get_db():
            # Проверяем наличие активного диалога
            existing_dialog = await get_active_dialog(db, username)
            if existing_dialog:
                return False

            try:
                # Пробуем получить пользователя и отправить сообщение
                user = await client.get_input_entity(f"@{username}")
                await client.send_message(user, initial_message)
            except ValueError as e:
                logger.error(f"Could not find user @{username}: {e}")
                return False
            except Exception as e:
                logger.error(f"Could not send message to @{username}: {e}")
                return False

            # Создаем новый диалог только если сообщение отправлено успешно
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
