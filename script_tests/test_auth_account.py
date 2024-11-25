import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent / "sales_bot"
assert root_dir.is_dir(), f"Неверная директория: {root_dir}"
sys.path.append(str(root_dir))

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Устанавливаем DEBUG для всех логгеров
for logger_name in [
    "accounts.client",
    "accounts.manager",
    "accounts.monitoring",
    "pyrogram",
]:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def test_account_flow(phone: Optional[str] = None) -> bool:
    """
    Полный тест жизненного цикла аккаунта:
    1. Создание аккаунта
    2. Запрос кода авторизации
    3. Авторизация
    4. Проверка состояния
    5. Проверка flood wait
    6. Проверка мониторинга

    Args:
        phone: Номер телефона для теста. Если None, используется тестовый номер.

    Returns:
        bool: True если все тесты пройдены успешно
    """
    from dotenv import load_dotenv

    load_dotenv()

    from accounts.manager import AccountManager
    from accounts.models import AccountStatus
    from accounts.monitoring import AccountMonitor
    from accounts.notifications import AccountNotifier

    try:
        # Инициализируем менеджеры
        manager = AccountManager()
        AccountNotifier()
        monitor = AccountMonitor()

        # Используем тестовый номер если не указан
        phone = phone or "79306974071"
        logger.info(f"Тестирование аккаунта {phone}")

        # 1. Создание аккаунта
        logger.info("1. Создание аккаунта...")
        account = await manager.get_or_create_account(phone)
        assert account is not None, "Не удалось создать аккаунт"
        assert account.phone == phone, f"Неверный номер телефона: {account.phone}"
        logger.info(f"Создан аккаунт {account}")

        # 2. Запрос кода авторизации
        if account.status == AccountStatus.new:
            logger.info("2. Запрос кода авторизации...")
            code_requested = await manager.request_code(phone)
            assert code_requested, "Не удалось запросить код"

            # Получаем свежие данные
            account = await manager.get_or_create_account(phone)
            assert (
                account.status == AccountStatus.code_requested
            ), f"Неверный статус: {account.status}"

            # 3. Авторизация
            logger.info("3. Авторизация аккаунта...")
            code = input("Введите код авторизации: ").strip()
            authorized = await manager.authorize_account(phone, code)
            assert authorized, "Не удалось авторизовать аккаунт"

        # 4. Проверка состояния
        logger.info("4. Проверка состояния...")
        account = await manager.get_or_create_account(phone)
        assert (
            account.status == AccountStatus.active
        ), f"Неверный статус: {account.status}"

        # Проверяем session_string
        assert account.session_string is not None, "Отсутствует session_string"

        # 5. Проверка мониторинга
        logger.info("5. Проверка мониторинга...")
        is_healthy = await monitor.check_account(account)
        assert is_healthy, "Аккаунт не прошел проверку мониторинга"

        # Проверяем last_used_at
        assert account.last_used_at is not None, "last_used_at не установлен"
        assert isinstance(account.last_used_at, datetime), "Неверный тип last_used_at"
        assert (
            account.last_used_at <= datetime.utcnow()
        ), "Неверное значение last_used_at"

        logger.info("Все тесты пройдены успешно!")
        return True

    except AssertionError as e:
        logger.error(f"Ошибка проверки: {e}")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Запускаем тест
    success = asyncio.run(test_account_flow())
    sys.exit(0 if success else 1)
