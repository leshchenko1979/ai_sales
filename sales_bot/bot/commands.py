import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_TELEGRAM_ID
from db.queries import create_dialog, get_db
from utils.export import export_dialog, export_all_dialogs

logger = logging.getLogger(__name__)

async def check_admin(update: Update):
    """Проверка прав администратора"""
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return False
    return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start @username"""
    if not await check_admin(update):
        return

    try:
        # Получаем username из аргументов команды
        args = context.args
        if not args or len(args) != 1 or not args[0].startswith('@'):
            await update.message.reply_text("Использование: /start @username")
            return

        username = args[0][1:]  # Убираем @ из начала
        dialog_id = await create_dialog(username)

        await update.message.reply_text(f"Диалог {dialog_id} с пользователем @{username} начат.")
        logger.info(f"Started dialog {dialog_id} with @{username}")

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("Произошла ошибка при создании диалога.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stop N"""
    if not await check_admin(update):
        return

    try:
        args = context.args
        if not args or len(args) != 1 or not args[0].isdigit():
            await update.message.reply_text("Использование: /stop N, где N - номер диалога")
            return

        dialog_id = int(args[0])
        async for db in get_db():
            dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
            if not dialog:
                await update.message.reply_text(f"Диалог {dialog_id} не найден.")
                return

            dialog.status = 'stopped'
            db.commit()

        await update.message.reply_text(f"Диалог {dialog_id} остановлен.")
        logger.info(f"Stopped dialog {dialog_id}")

    except Exception as e:
        logger.error(f"Error in stop_command: {e}")
        await update.message.reply_text("Произошла ошибка при остановке диалога.")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /list"""
    if not await check_admin(update):
        return

    try:
        async for db in get_db():
            dialogs = db.query(Dialog).filter(Dialog.status == 'active').all()

            if not dialogs:
                await update.message.reply_text("Нет активных диалогов.")
                return

            response = "Активные диалоги:\n"
            for dialog in dialogs:
                response += f"ID: {dialog.id} - @{dialog.target_username}\n"

            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error in list_command: {e}")
        await update.message.reply_text("Произошла ошибка при получении списка диалогов.")

async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /view N"""
    if not await check_admin(update):
        return

    try:
        args = context.args
        if not args or len(args) != 1 or not args[0].isdigit():
            await update.message.reply_text("Использование: /view N, где N - номер диалога")
            return

        dialog_id = int(args[0])
        async for db in get_db():
            messages = db.query(Message).filter(Message.dialog_id == dialog_id).order_by(Message.timestamp).all()

            if not messages:
                await update.message.reply_text(f"Сообщения для диалога {dialog_id} не найдены.")
                return

            response = f"Диалог {dialog_id}:\n\n"
            for msg in messages:
                direction = "→" if msg.direction == "out" else "←"
                response += f"{direction} {msg.content}\n"

            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error in view_command: {e}")
        await update.message.reply_text("Произошла ошибка при просмотре диалога.")

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /export N"""
    if not await check_admin(update):
        return

    try:
        args = context.args
        if not args or len(args) != 1 or not args[0].isdigit():
            await update.message.reply_text("Использование: /export N, где N - номер диалога")
            return

        dialog_id = int(args[0])
        file_path = await export_dialog(dialog_id)

        if file_path:
            with open(file_path, 'rb') as file:
                await update.message.reply_document(file)
        else:
            await update.message.reply_text("Диалог не найден или пуст.")

    except Exception as e:
        logger.error(f"Error in export_command: {e}")
        await update.message.reply_text("Произошла ошибка при экспорте диалога.")

async def export_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /export_all"""
    if not await check_admin(update):
        return

    try:
        file_path = await export_all_dialogs()

        if file_path:
            with open(file_path, 'rb') as file:
                await update.message.reply_document(file)
        else:
            await update.message.reply_text("Нет диалогов для экспорта.")

    except Exception as e:
        logger.error(f"Error in export_all_command: {e}")
        await update.message.reply_text("Произошла ошибка при экспорте диалогов.")
