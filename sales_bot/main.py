import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import BOT_TOKEN, LOG_LEVEL, LOG_FILE
from bot.commands import start_command, stop_command, list_command, view_command, export_command, export_all_command
from bot.dialogs import message_handler
from utils.logging import setup_logging

async def main():
    # Настраиваем логирование
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Sales Bot...")

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("view", view_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("export_all", export_all_command))

    # Регистрируем обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Запускаем бота
    logger.info("Bot started successfully")
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
