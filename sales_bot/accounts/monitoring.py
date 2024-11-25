import logging
from datetime import datetime

from db.queries import AccountQueries

from .client import AccountClient
from .models import Account
from .notifications import AccountNotifier

logger = logging.getLogger(__name__)


class AccountMonitor:
    """
    Компонент для мониторинга состояния аккаунтов
    """

    def __init__(self, queries: AccountQueries, notifier: AccountNotifier):
        self.queries = queries
        self.notifier = notifier

    async def check_accounts(self):
        """Проверка состояния всех аккаунтов"""
        try:
            # Получаем все аккаунты
            accounts = await self.queries.get_all_accounts()

            # Собираем статистику
            stats = {
                "total": len(accounts),
                "active": 0,
                "new": 0,
                "code_requested": 0,
                "password_requested": 0,
                "disabled": 0,
                "blocked": 0,
                "flood_wait": 0,
            }

            # Проверяем каждый аккаунт
            for account in accounts:
                # Обновляем статистику по статусам
                stats[account.status.value] += 1

                # Проверяем флуд-контроль
                if account.is_flood_wait:
                    stats["flood_wait"] += 1

            # Отправляем отчет
            await self.notifier.notify_status_report(stats)

        except Exception as e:
            logger.error(f"Failed to check accounts: {e}", exc_info=True)

    async def check_account(self, account: Account) -> bool:
        """
        Проверка состояния конкретного аккаунта
        Возвращает True если аккаунт в порядке
        """
        try:
            # Создаем клиент
            client = AccountClient(account)

            # Пробуем подключиться
            if not await client.connect():
                await self.notifier.notify_disabled(
                    account, "Не удалось подключиться к аккаунту"
                )
                return False

            # Проверяем базовое состояние
            if not await client.check_auth():
                await self.notifier.notify_disabled(account, "Аккаунт не авторизован")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to check account {account.phone}: {e}", exc_info=True)
            return False

    async def check_flood_wait(self, account: Account) -> bool:
        """
        Проверка флуд-контроля аккаунта
        Возвращает True если аккаунт не в флуд-контроле
        """
        try:
            if account.is_flood_wait:
                # Проверяем не истек ли флуд-контроль
                if datetime.utcnow() >= account.flood_wait_until:
                    await self.queries.clear_flood_wait(account.id)
                    return True
                return False
            return True

        except Exception as e:
            logger.error(
                f"Failed to check flood wait for {account.phone}: {e}", exc_info=True
            )
            return False
