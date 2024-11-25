import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent / "sales_bot"
assert root_dir.is_dir(), f"Неверная директория: {root_dir}"
sys.path.append(str(root_dir))

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG,  # Изменяем уровень на DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Устанавливаем DEBUG для всех логгеров
logging.getLogger("accounts.client").setLevel(logging.DEBUG)
logging.getLogger("accounts.manager").setLevel(logging.DEBUG)
logging.getLogger("pyrogram").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def authorize_new_account():
    """
    Тест авторизации нового аккаунта:
    1. Создание аккаунта
    2. Запрос кода
    3. Ввод кода
    4. Проверка состояния
    """

    from dotenv import load_dotenv

    # Загружаем переменные окружения
    load_dotenv()

    from accounts.manager import AccountManager
    from accounts.monitoring import AccountMonitor
    from accounts.notifications import AccountNotifier
    from db.queries import AccountQueries, get_db

    try:
        # Создаем сессию для всего теста
        async with get_db() as session:
            queries = AccountQueries(session)
            notifier = AccountNotifier()
            monitor = AccountMonitor(queries, notifier)
            manager = AccountManager(session)

            # Жестко прописанный номер телефона
            phone = "79306974071"

            # Проверяем существование или создаем новый аккаунт
            logger.info("Проверяем существование аккаунта...")
            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.info("Создаем новый аккаунт...")
                account = await queries.create_account(phone)
                # Убеждаемся, что транзакция завершена
                await session.commit()
                logger.debug(f"Created account with ID: {account.id}")

            # Запрашиваем код авторизации
            logger.info("Запрашиваем код авторизации...")
            if not await manager.request_code(phone):
                logger.error("Не удалось запросить код")
                return

            # Ждем ввода кода от пользователя
            code = input("Введите код авторизации: ")

            # Авторизуем аккаунт
            logger.info("Авторизуем аккаунт...")
            if await manager.authorize_account(phone, code):
                logger.info("Аккаунт успешно авторизован!")
            else:
                logger.error("Не удалось авторизовать аккаунт")

            # Проверяем состояние
            logger.info("Проверяем состояние аккаунта...")
            account = await queries.get_account_by_phone(phone)
            if await monitor.check_account(account):
                logger.info("Аккаунт успешно авторизован и готов к работе!")
            else:
                logger.error("Аккаунт не прошел проверку")

            # Проверяем last_used_at
            assert account.last_used_at is not None
            assert isinstance(account.last_used_at, datetime)
            assert account.last_used_at <= datetime.utcnow()

    except Exception as e:
        logger.error(f"Ошибка при авторизации: {e}", exc_info=True)


if __name__ == "__main__":
    # Запускаем тест
    asyncio.run(authorize_new_account())
