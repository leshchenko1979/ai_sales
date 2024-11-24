import logging

from accounts.manager import AccountManager
from accounts.monitoring import AccountMonitor
from config import ADMIN_TELEGRAM_ID
from db.models import Dialog, Message
from db.queries import create_dialog, get_db
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.export import export_all_dialogs, export_dialog

from .client import app

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
        if len(args) != 2 or not args[1].startswith("@"):
            await message.reply_text("Использование: /start @username")
            return

        username = args[1][1:]  # Remove @ from start
        dialog_id = await create_dialog(username)

        await message.reply_text(
            f"Диалог {dialog_id} с пользователем @{username} начат."
        )
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
        db = await get_db()
        try:
            dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
            if not dialog:
                await message.reply_text(f"Диалог {dialog_id} не найден.")
                return

            dialog.status = "stopped"
            db.commit()
            await message.reply_text(f"Диалог {dialog_id} остановлен.")
            logger.info(f"Stopped dialog {dialog_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in stop_command: {e}")
        await message.reply_text("Произошла ошибка при остановке диалога.")


@app.on_message(filters.command("list") & filters.private)
async def list_command(client, message):
    """Обработчик команды /list"""
    if not await check_admin(message):
        return

    try:
        db = await get_db()
        try:
            dialogs = db.query(Dialog).filter(Dialog.status == "active").all()

            if not dialogs:
                await message.reply_text("Нет активных диалогов.")
                return

            response = "Активные диалоги:\n"
            for dialog in dialogs:
                response += f"ID: {dialog.id} - @{dialog.target_username}\n"

            await message.reply_text(response)
        finally:
            db.close()

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
        db = await get_db()
        try:
            messages = (
                db.query(Message)
                .filter(Message.dialog_id == dialog_id)
                .order_by(Message.timestamp)
                .all()
            )

            if not messages:
                await message.reply_text(
                    f"Сообщения для диалога {dialog_id} не найдены."
                )
                return

            response = f"Диалог {dialog_id}:\n\n"
            for msg in messages:
                direction = "→" if msg.direction == "out" else "←"
                response += f"{direction} {msg.content}\n"

            await message.reply_text(response)
        finally:
            db.close()

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
            with open(file_path, "rb") as file:
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
            with open(file_path, "rb") as file:
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


def admin_only(func):
    """Декоратор для проверки прав администратора"""

    async def wrapper(client: Client, message: Message):
        if message.from_user.id != ADMIN_TELEGRAM_ID:
            await message.reply("У вас нет прав для выполнения этой команды.")
            return
        return await func(client, message)

    return wrapper


@admin_only
async def cmd_add_account(client: Client, message: Message):
    """Добавление нового аккаунта"""
    try:
        # Получаем номер телефона из команды
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /add_account phone\nПример: /add_account +79001234567"
            )
            return

        phone = args[1]

        # Создаем аккаунт
        db = await get_db()
        try:
            account_manager = AccountManager(db)
            account = await account_manager.add_account(phone)

            if not account:
                await message.reply("Не удалось добавить аккаунт.")
                return

            await message.reply(
                "Аккаунт добавлен. Введите код подтверждения командой:\n"
                f"/authorize {phone} код"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in cmd_add_account: {e}")
        await message.reply("Произошла ошибка при добавлении аккаунта.")


@admin_only
async def cmd_authorize(client: Client, message: Message):
    """Авторизация аккаунта"""
    try:
        # Получаем номер телефона и код из команды
        args = message.text.split()
        if len(args) != 3:
            await message.reply(
                "Использование: /authorize phone code\n"
                "Пример: /authorize +79001234567 12345"
            )
            return

        phone, code = args[1], args[2]

        # Авторизуем аккаунт
        db = await get_db()
        try:
            account_manager = AccountManager(db)
            success = await account_manager.authorize_account(phone, code)

            if success:
                await message.reply("Аккаунт успешно авторизован.")
            else:
                await message.reply(
                    "Не удалось авторизовать аккаунт. Проверьте код и попробуйте снова."
                )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in cmd_authorize: {e}")
        await message.reply("Произошла ошибка при авторизации аккаунта.")


@admin_only
async def cmd_list_accounts(client: Client, message: Message):
    """Список всех аккаунтов"""
    try:
        db = await get_db()
        try:
            account_manager = AccountManager(db)
            accounts = await account_manager.queries.get_all_accounts()

            if not accounts:
                await message.reply("Нет добавленных аккаунтов.")
                return

            response = "Список аккаунтов:\n\n"
            for acc in accounts:
                status_emoji = {"active": "🟢", "disabled": "🔴", "blocked": "⛔"}.get(
                    acc.status, "❓"
                )

                response += (
                    f"{status_emoji} {acc.phone}\n"
                    f"├ ID: {acc.id}\n"
                    f"├ Сообщений сегодня: {acc.daily_messages}\n"
                    f"└ Последнее использование: {acc.last_used or 'никогда'}\n\n"
                )

            await message.reply(response)

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in cmd_list_accounts: {e}")
        await message.reply("Произошла ошибка при получении списка аккаунтов.")


@admin_only
async def cmd_disable_account(client: Client, message: Message):
    """Отключение аккаунта"""
    try:
        # Получаем номер телефона из команды
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /disable_account phone\n"
                "Пример: /disable_account +79001234567"
            )
            return

        phone = args[1]

        # Отключаем аккаунт
        db = await get_db()
        try:
            account_manager = AccountManager(db)
            success = await account_manager.queries.update_account_status(
                phone, "disabled"
            )

            if success:
                await message.reply("Аккаунт успешно отключен.")
            else:
                await message.reply(
                    "Не удалось отключить аккаунт. Проверьте номер телефона."
                )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in cmd_disable_account: {e}")
        await message.reply("Произошла ошибка при отключении аккаунта.")


@admin_only
async def cmd_check_account(client: Client, message: Message):
    """Проверка состояния аккаунта"""
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "Использование: /check_account phone\n"
                "Пример: /check_account +79001234567"
            )
            return

        phone = args[1]

        db = await get_db()
        try:
            account_manager = AccountManager(db)
            account = await account_manager.queries.get_account_by_phone(phone)

            if not account:
                await message.reply("Аккаунт не найден.")
                return

            monitor = AccountMonitor(db)
            is_working = await monitor.check_account(account)

            status_emoji = "✅" if is_working else "❌"
            await message.reply(
                f"{status_emoji} Аккаунт {phone}\n"
                f"Статус: {account.status}\n"
                f"Сообщений сегодня: {account.daily_messages}\n"
                f"Последнее использование: {account.last_used or 'никогда'}"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in cmd_check_account: {e}")
        await message.reply("Произошла ошибка при проверке аккаунта.")


@admin_only
async def cmd_check_all_accounts(client: Client, message: Message):
    """Проверка всех аккаунтов"""
    try:
        db = await get_db()
        try:
            monitor = AccountMonitor(db)
            stats = await monitor.check_all_accounts()

            await message.reply(
                "Результаты проверки:\n\n"
                f"Всего аккаунтов: {stats['total']}\n"
                f"✅ Работает: {stats['active']}\n"
                f"🔴 Отключено: {stats['disabled']}\n"
                f"⛔ Заблокировано: {stats['blocked']}"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in cmd_check_all_accounts: {e}")
        await message.reply("Произошла ошибка при проверке аккаунтов.")


# Регистрация обработчиков команд
def register_account_commands(app: Client):
    app.add_handler(filters.command("add_account"), cmd_add_account)
    app.add_handler(filters.command("authorize"), cmd_authorize)
    app.add_handler(filters.command("list_accounts"), cmd_list_accounts)
    app.add_handler(filters.command("disable_account"), cmd_disable_account)
    app.add_handler(filters.command("check_account"), cmd_check_account)
    app.add_handler(filters.command("check_all"), cmd_check_all_accounts)
