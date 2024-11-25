import logging

from db.queries import AccountQueries, with_queries

from .client import AccountClient
from .models import Account
from .notifications import AccountNotifier

logger = logging.getLogger(__name__)


class AccountMonitor:
    """
    Компонент для мониторинга состояния аккаунтов
    """

    def __init__(self):
        """Initialize monitor"""
        self.notifier = AccountNotifier()

    @with_queries(AccountQueries)
    async def check_accounts(self, queries: AccountQueries):
        """Проверка состояния всех аккаунтов"""
        try:
            # Получаем все аккаунты
            accounts = await queries.get_all_accounts()

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

            return stats

        except Exception as e:
            logger.error(f"Error checking accounts: {e}", exc_info=True)
            return None

    @with_queries(AccountQueries)
    async def check_account(self, queries: AccountQueries, account: Account) -> bool:
        """
        Проверка состояния конкретного аккаунта

        :param queries: Database queries executor
        :param account: Account to check
        :return: True if account is healthy
        """
        try:
            # Проверяем базовые параметры
            if not account.can_be_used:
                logger.warning(f"Account {account.phone} is not available for use")
                return False

            # Проверяем клиент
            client = AccountClient(account)
            if not await client.connect():
                logger.error(f"Failed to connect client for {account.phone}")
                return False

            # Проверяем авторизацию
            if not account.session_string:
                logger.error(f"Account {account.phone} has no session string")
                return False

            # Проверяем флуд-контроль
            if account.is_flood_wait:
                logger.warning(f"Account {account.phone} is in flood wait")
                return False

            # Обновляем last_used_at
            await queries.update_last_used(account.id)

            return True

        except Exception as e:
            logger.error(f"Error checking account {account.phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def check_flood_wait(self, queries: AccountQueries, account: Account) -> bool:
        """
        Проверка флуд-контроля для аккаунта

        :param queries: Database queries executor
        :param account: Account to check
        :return: True if account is not in flood wait
        """
        try:
            if account.is_flood_wait:
                logger.warning(f"Account {account.phone} is in flood wait")
                return False

            return True

        except Exception as e:
            logger.error(
                f"Error checking flood wait for {account.phone}: {e}", exc_info=True
            )
            return False
