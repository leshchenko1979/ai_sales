import logging
from pyrogram import filters, Client
from .client import app
from config import ADMIN_TELEGRAM_ID
from db.queries import create_dialog, get_db
from db.models import Dialog, Message
from utils.export import export_dialog, export_all_dialogs

logger = logging.getLogger(__name__)

async def check_admin(message):
    """Check admin rights"""
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        await message.reply_text("У вас нет прав для выполнения этой команды.")
        return False
    return True

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    """Handler for /start @username command"""
    if not await check_admin(message):
        return

    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].startswith('@'):
            await message.reply_text("Использование: /start @username")
            return

        username = args[1][1:]  # Remove @ from start
        dialog_id = await create_dialog(username)

        await message.reply_text(f"Диалог {dialog_id} с пользователем @{username} начат.")
        logger.info(f"Started dialog {dialog_id} with @{username}")

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await message.reply_text("Произошла ошибка при создании диалога.")

@app.on_message(filters.command("stop") & filters.private)
async def stop_command(client, message):
    """Обработчик команды /stop N"""
    if not await check_admin(message):
        return

    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            await message.reply_text("Использование: /stop N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        async for db in get_db():
            dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
            if not dialog:
                await message.reply_text(f"Диалог {dialog_id} не найден.")
                return

            dialog.status = 'stopped'
            db.commit()

        await message.reply_text(f"Диалог {dialog_id} остановлен.")
        logger.info(f"Stopped dialog {dialog_id}")

    except Exception as e:
        logger.error(f"Error in stop_command: {e}")
        await message.reply_text("Произошла ошибка при остановке диалога.")

@app.on_message(filters.command("list") & filters.private)
async def list_command(client, message):
    """Обработчик команды /list"""
    if not await check_admin(message):
        return

    try:
        async for db in get_db():
            dialogs = db.query(Dialog).filter(Dialog.status == 'active').all()

            if not dialogs:
                await message.reply_text("Нет активных диалогов.")
                return

            response = "Активные диалоги:\n"
            for dialog in dialogs:
                response += f"ID: {dialog.id} - @{dialog.target_username}\n"

            await message.reply_text(response)

    except Exception as e:
        logger.error(f"Error in list_command: {e}")
        await message.reply_text("Произошла ошибка при получении списка диалогов.")

@app.on_message(filters.command("view") & filters.private)
async def view_command(client, message):
    """Обработчик команды /view N"""
    if not await check_admin(message):
        return

    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            await message.reply_text("Использование: /view N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        async for db in get_db():
            messages = db.query(Message).filter(Message.dialog_id == dialog_id).order_by(Message.timestamp).all()

            if not messages:
                await message.reply_text(f"Сообщения для диалога {dialog_id} не найдены.")
                return

            response = f"Диалог {dialog_id}:\n\n"
            for msg in messages:
                direction = "→" if msg.direction == "out" else "←"
                response += f"{direction} {msg.content}\n"

            await message.reply_text(response)

    except Exception as e:
        logger.error(f"Error in view_command: {e}")
        await message.reply_text("Произошла ошибка при просмотре диалога.")

@app.on_message(filters.command("export") & filters.private)
async def export_command(client, message):
    """Обработчик команды /export N"""
    if not await check_admin(message):
        return

    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            await message.reply_text("Использование: /export N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        file_path = await export_dialog(dialog_id)

        if file_path:
            with open(file_path, 'rb') as file:
                await message.reply_document(file)
        else:
            await message.reply_text("Диалог не найден или пуст.")

    except Exception as e:
        logger.error(f"Error in export_command: {e}")
        await message.reply_text("Произошла ошибка при экспорте диалога.")

@app.on_message(filters.command("export_all") & filters.private)
async def export_all_command(client, message):
    """Обработчик команды /export_all"""
    if not await check_admin(message):
        return

    try:
        file_path = await export_all_dialogs()

        if file_path:
            with open(file_path, 'rb') as file:
                await message.reply_document(file)
        else:
            await message.reply_text("Нет диалогов для экспорта.")

    except Exception as e:
        logger.error(f"Error in export_all_command: {e}")
        await message.reply_text("Произошла ошибка при экспорте диалогов.")

@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    """Handler for /help command"""
    if not await check_admin(message):
        return

    try:
        help_text = """
Доступные команды:

Управление диалогами:
/start @username - начать диалог с пользователем
/stop N - остановить диалог номер N
/list - показать список активных диалогов

Просмотр и выгрузка:
/view N - просмотр диалога номер N
/export N - выгрузка диалога номер N в файл
/export_all - выгрузка всех диалогов

Помощь:
/help - показать это сообщение
"""
        await message.reply_text(help_text)
        logger.info("Help command executed")

    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await message.reply_text("Произошла ошибка при выводе справки.")
