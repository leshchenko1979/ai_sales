import logging
from telethon import events
from .client import client
from config import ADMIN_TELEGRAM_ID
from db.queries import create_dialog, get_db
from db.models import Dialog, Message
from utils.export import export_dialog, export_all_dialogs

logger = logging.getLogger(__name__)

async def check_admin(event):
    """Проверка прав администратора"""
    if event.sender_id != ADMIN_TELEGRAM_ID:
        await event.respond("У вас нет прав для выполнения этой команды.")
        return False
    return True

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    """Обработчик команды /start @username"""
    if not await check_admin(event):
        return

    try:
        args = event.raw_text.split()
        if len(args) != 2 or not args[1].startswith('@'):
            await event.respond("Использование: /start @username")
            return

        username = args[1][1:]  # Убираем @ из начала
        dialog_id = await create_dialog(username)

        await event.respond(f"Диалог {dialog_id} с пользователем @{username} начат.")
        logger.info(f"Started dialog {dialog_id} with @{username}")

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await event.respond("Произошла ошибка при создании диалога.")

async def stop_command(event):
    """Обработчик команды /stop N"""
    if not await check_admin(event):
        return

    try:
        args = event.raw_text.split()
        if len(args) != 2 or not args[1].isdigit():
            await event.respond("Использование: /stop N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        async for db in get_db():
            dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
            if not dialog:
                await event.respond(f"Диалог {dialog_id} не найден.")
                return

            dialog.status = 'stopped'
            db.commit()

        await event.respond(f"Диалог {dialog_id} остановлен.")
        logger.info(f"Stopped dialog {dialog_id}")

    except Exception as e:
        logger.error(f"Error in stop_command: {e}")
        await event.respond("Произошла ошибка при остановке диалога.")

async def list_command(event):
    """Обработчик команды /list"""
    if not await check_admin(event):
        return

    try:
        async for db in get_db():
            dialogs = db.query(Dialog).filter(Dialog.status == 'active').all()

            if not dialogs:
                await event.respond("Нет активных диалогов.")
                return

            response = "Активные диалоги:\n"
            for dialog in dialogs:
                response += f"ID: {dialog.id} - @{dialog.target_username}\n"

            await event.respond(response)

    except Exception as e:
        logger.error(f"Error in list_command: {e}")
        await event.respond("Произошла ошибка при получении списка диалогов.")

async def view_command(event):
    """Обработчик команды /view N"""
    if not await check_admin(event):
        return

    try:
        args = event.raw_text.split()
        if len(args) != 2 or not args[1].isdigit():
            await event.respond("Использование: /view N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        async for db in get_db():
            messages = db.query(Message).filter(Message.dialog_id == dialog_id).order_by(Message.timestamp).all()

            if not messages:
                await event.respond(f"Сообщения для диалога {dialog_id} не найдены.")
                return

            response = f"Диалог {dialog_id}:\n\n"
            for msg in messages:
                direction = "→" if msg.direction == "out" else "←"
                response += f"{direction} {msg.content}\n"

            await event.respond(response)

    except Exception as e:
        logger.error(f"Error in view_command: {e}")
        await event.respond("Произошла ошибка при просмотре диалога.")

async def export_command(event):
    """Обработчик команды /export N"""
    if not await check_admin(event):
        return

    try:
        args = event.raw_text.split()
        if len(args) != 2 or not args[1].isdigit():
            await event.respond("Использование: /export N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        file_path = await export_dialog(dialog_id)

        if file_path:
            with open(file_path, 'rb') as file:
                await event.respond_file(file)
        else:
            await event.respond("Диалог не найден или пуст.")

    except Exception as e:
        logger.error(f"Error in export_command: {e}")
        await event.respond("Произошла ошибка при экспорте диалога.")

async def export_all_command(event):
    """Обработчик команды /export_all"""
    if not await check_admin(event):
        return

    try:
        file_path = await export_all_dialogs()

        if file_path:
            with open(file_path, 'rb') as file:
                await event.respond_file(file)
        else:
            await event.respond("Нет диалогов для экспорта.")

    except Exception as e:
        logger.error(f"Error in export_all_command: {e}")
        await event.respond("Произошла ошибка при экспорте диалогов.")
