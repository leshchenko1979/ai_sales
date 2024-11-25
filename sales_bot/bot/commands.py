import logging
from datetime import datetime

from accounts.manager import AccountManager
from accounts.monitoring import AccountMonitor
from config import ADMIN_TELEGRAM_ID
from db.queries import DialogQueries, get_db
from pyrogram import Client
from pyrogram.filters import command
from pyrogram.types import Message as PyrogramMessage
from utils.export import export_all_dialogs, export_dialog

from .client import app

# Command response messages
UNAUTHORIZED_MSG = "У вас нет прав для выполнения этой команды."
ERROR_MSG = "Произошла ошибка при выполнении команды."
INVALID_FORMAT_MSG = "Неверный формат команды."

# Status emojis
STATUS_EMOJIS = {"active": "🟢", "disabled": "🔴", "blocked": "⛔", "unknown": "❓"}

logger = logging.getLogger(__name__)


async def check_admin(message: PyrogramMessage) -> bool:
    """Check admin rights"""
    if message.from_user.id != ADMIN_TELEGRAM_ID:
        await message.reply_text(UNAUTHORIZED_MSG)
        logger.warning(
            f"Unauthorized access attempt from user {message.from_user.id} "
            f"at {datetime.now().isoformat(timespec='microseconds')}"
        )
        return False
    return True


def admin(func):
    """Декоратор для проверки прав администратора и логирования"""

    async def wrapper(client: Client, message: PyrogramMessage):
        if not await check_admin(message):
            return
        logger.info(f"Command {message.text} executed by admin {message.from_user.id}")
        return await func(client, message)

    return wrapper


@app.on_message(command("start"))
@admin
async def start_command(client: Client, message: PyrogramMessage):
    """Handler for /start @username command"""
    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].startswith("@"):
            await message.reply_text("Использование: /start @username")
            return

        username = args[1][1:]  # Remove @ from start
        async with get_db() as session:
            dialog_queries = DialogQueries(session)
            dialog = await dialog_queries.create_dialog(username, message.from_user.id)

        await message.reply_text(
            f"Диалог {dialog.id} с пользователем @{username} начат."
        )
        logger.info(f"Started dialog {dialog.id} with @{username}")

    except Exception as e:
        logger.error(
            f"Error in start_command: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply_text(ERROR_MSG)


@app.on_message(command("stop"))
@admin
async def stop_command(client: Client, message: PyrogramMessage):
    """Обработчик команды /stop N"""
    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            await message.reply_text("Использование: /stop N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        async with get_db() as session:
            dialog_queries = DialogQueries(session)
            dialog = await dialog_queries.get_dialog(dialog_id)

            if not dialog:
                await message.reply_text(f"Диалог {dialog_id} не найден.")
                return

            dialog.status = "stopped"
            await session.commit()

        await message.reply_text(f"Диалог {dialog_id} остановлен.")
        logger.info(f"Stopped dialog {dialog_id}")

    except Exception as e:
        logger.error(
            f"Error in stop_command: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply_text(ERROR_MSG)


@app.on_message(command("list"))
@admin
async def list_command(client: Client, message: PyrogramMessage):
    """Обработчик команды /list"""
    try:
        async with get_db() as session:
            dialog_queries = DialogQueries(session)
            dialogs = await dialog_queries.get_active_dialogs()

            if not dialogs:
                await message.reply_text("Нет активных диалогов.")
                return

            response = "Активные диалоги:\n"
            for dialog in dialogs:
                response += f"ID: {dialog.id} - @{dialog.target_username}\n"

        await message.reply_text(response)

    except Exception as e:
        logger.error(
            f"Error in list_command: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply_text(ERROR_MSG)


@app.on_message(command("view"))
@admin
async def view_command(client: Client, message: PyrogramMessage):
    """Обработчик команды /view N"""
    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            await message.reply_text("Использование: /view N, где N - номер диалога")
            return

        dialog_id = int(args[1])
        async with get_db() as session:
            dialog_queries = DialogQueries(session)
            messages = await dialog_queries.get_messages(dialog_id)

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

    except Exception as e:
        logger.error(
            f"Error in view_command: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply_text(ERROR_MSG)


@app.on_message(command("export"))
@admin
async def export_command(client: Client, message: PyrogramMessage):
    """Обработчик команды /export N"""
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
        logger.error(
            f"Error in export_command: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply_text(ERROR_MSG)


@app.on_message(command("export_all"))
@admin
async def export_all_command(client: Client, message: PyrogramMessage):
    """Обработчик команды /export_all"""
    try:
        file_path = await export_all_dialogs()

        if file_path:
            with open(file_path, "rb") as file:
                await message.reply_document(file)
        else:
            await message.reply_text("Нет диалогов для экспорта.")

    except Exception as e:
        logger.error(
            f"Error in export_all_command: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply_text(ERROR_MSG)


@app.on_message(command("help"))
@admin
async def help_command(client: Client, message: PyrogramMessage):
    """Handler for /help command"""
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

Управление аккаунтами:
/add_account phone - добавить новый аккаунт
/authorize phone code - авторизовать аккаунт
/list_accounts - показать список всех аккаунтов
/disable_account phone - отключить аккаунт
/check_account phone - проверить состояние аккаунта
/check_all_accounts - проверить все аккаунты

Помощь:
/help - показать это сообщение
"""
        await message.reply_text(help_text)
        logger.info("Help command executed")

    except Exception as e:
        logger.error(
            f"Error in help_command: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply_text(ERROR_MSG)


@app.on_message(command("add_account"))
@admin
async def cmd_add_account(client: Client, message: PyrogramMessage):
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
        async with get_db() as session:
            account_manager = AccountManager(session)
            account = await account_manager.add_account(phone)

            if not account:
                await message.reply("Не удалось добавить аккаунт.")
                return

            await message.reply(
                "Аккаунт добавлен. Введите код подтверждения командой:\n"
                f"/authorize {phone} код"
            )

    except Exception as e:
        logger.error(
            f"Error in cmd_add_account: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command("authorize"))
@admin
async def cmd_authorize(client: Client, message: PyrogramMessage):
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
        async with get_db() as session:
            account_manager = AccountManager(session)
            success = await account_manager.authorize_account(phone, code)

            if success:
                await message.reply("Аккаунт успешно авторизован.")
            else:
                await message.reply(
                    "Не удалось авторизовать аккаунт. Проверьте код и попробуйте снова."
                )

    except Exception as e:
        logger.error(
            f"Error in cmd_authorize: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command("list_accounts"))
@admin
async def cmd_list_accounts(client: Client, message: PyrogramMessage):
    """Список всех аккаунтов"""
    try:
        async with get_db() as session:
            account_manager = AccountManager(session)
            accounts = await account_manager.queries.get_all_accounts()

            if not accounts:
                await message.reply("Нет добавленных аккаунтов.")
                return

            response = "Список аккаунтов:\n\n"
            for acc in accounts:
                status_emoji = STATUS_EMOJIS.get(acc.status, STATUS_EMOJIS["unknown"])

                response += (
                    f"{status_emoji} {acc.phone}\n"
                    f"├ ID: {acc.id}\n"
                    f"├ Сообщений сегодня: {acc.daily_messages}\n"
                    f"└ Последнее использование: {acc.last_used or 'никогда'}\n\n"
                )

            await message.reply(response)

    except Exception as e:
        logger.error(
            f"Error in cmd_list_accounts: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command("disable_account"))
@admin
async def cmd_disable_account(client: Client, message: PyrogramMessage):
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
        async with get_db() as session:
            account_manager = AccountManager(session)
            success = await account_manager.queries.update_account_status(
                phone, "disabled"
            )

            if success:
                await message.reply("Аккаунт успешно отключен.")
            else:
                await message.reply(
                    "Не удалось отключить аккаунт. Проверьте номер телефона."
                )

    except Exception as e:
        logger.error(
            f"Error in cmd_disable_account: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command("check_account"))
@admin
async def cmd_check_account(client: Client, message: PyrogramMessage):
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

        async with get_db() as session:
            account_manager = AccountManager(session)
            account = await account_manager.queries.get_account_by_phone(phone)

            if not account:
                await message.reply("Аккаунт не найден.")
                return

            monitor = AccountMonitor(session)
            is_working = await monitor.check_account(account)

            status_emoji = "✅" if is_working else "❌"
            await message.reply(
                f"{status_emoji} Аккаунт {phone}\n"
                f"Статус: {account.status}\n"
                f"Сообщений сегодня: {account.daily_messages}\n"
                f"Последнее использование: {account.last_used or 'никогда'}"
            )

    except Exception as e:
        logger.error(
            f"Error in cmd_check_account: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)


@app.on_message(command("check_all_accounts"))
@admin
async def cmd_check_all_accounts(client: Client, message: PyrogramMessage):
    """Проверка всех аккаунтов"""
    try:
        async with get_db() as session:
            monitor = AccountMonitor(session)
            stats = await monitor.check_all_accounts()

            await message.reply(
                "Результаты проверки:\n\n"
                f"Всего аккаунтов: {stats['total']}\n"
                f"✅ Работает: {stats['active']}\n"
                f"🔴 Отключено: {stats['disabled']}\n"
                f"⛔ Заблокировано: {stats['blocked']}"
            )

    except Exception as e:
        logger.error(
            f"Error in cmd_check_all_accounts: {e}",
            exc_info=True,
            extra={"user_id": message.from_user.id, "command": message.text},
        )
        await message.reply(ERROR_MSG)
