import logging
from typing import List

from db.queries import AccountQueries

from .client import AccountClient
from .models import Account, AccountStatus
from .monitor import AccountMonitor
from .notifications import AccountNotifier

logger = logging.getLogger(__name__)


class AccountRotation:
    """
    Компонент для ротации аккаунтов:
    - Активация новых аккаунтов
    - Отключение проблемных аккаунтов
    - Балансировка нагрузки
    """

    def __init__(self, queries: AccountQueries, notifier: AccountNotifier):
        self.queries = queries
        self.notifier = notifier
        self.monitor = AccountMonitor(queries, notifier)

    async def rotate_accounts(self, min_active: int = 10) -> dict:
        """
        Ротация аккаунтов для поддержания нужного количества активных
        """
        try:
            stats = {
                "total": 0,
                "activated": 0,
                "disabled": 0,
                "blocked": 0,
                "flood_wait": 0,
            }

            # Получаем все аккаунты
            accounts = await self.queries.get_all_accounts()
            stats["total"] = len(accounts)

            # Проверяем активные аккаунты
            active_accounts = [a for a in accounts if a.status == AccountStatus.active]

            # Если активных достаточно - проверяем их состояние
            if len(active_accounts) >= min_active:
                await self._check_active_accounts(active_accounts, stats)

            # Если активных мало - активируем новые
            else:
                needed = min_active - len(active_accounts)
                await self._activate_new_accounts(accounts, needed, stats)

            # Отправляем отчет
            await self.notifier.notify_rotation_report(stats)
            return stats

        except Exception as e:
            logger.error(f"Failed to rotate accounts: {e}", exc_info=True)
            return stats

    async def _check_active_accounts(self, accounts: List[Account], stats: dict):
        """Проверка активных аккаунтов"""
        for account in accounts:
            try:
                # Проверяем флуд-контроль
                if not await self.monitor.check_flood_wait(account):
                    stats["flood_wait"] += 1
                    continue

                # Проверяем состояние
                if not await self.monitor.check_account(account):
                    stats["disabled"] += 1

            except Exception as e:
                logger.error(
                    f"Failed to check account {account.phone}: {e}", exc_info=True
                )
                stats["disabled"] += 1

    async def _activate_new_accounts(
        self, accounts: List[Account], needed: int, stats: dict
    ):
        """Активация новых аккаунтов"""
        # Получаем неактивные аккаунты
        inactive = [
            a
            for a in accounts
            if a.status not in [AccountStatus.active, AccountStatus.blocked]
            and not a.is_flood_wait
        ]

        # Пробуем активировать нужное количество
        for account in inactive[:needed]:
            try:
                # Создаем клиент
                client = AccountClient(account)
                if not await client.connect():
                    continue

                # Проверяем состояние
                if await self.monitor.check_account(account):
                    # Активируем аккаунт
                    await account.activate()
                    stats["activated"] += 1
                else:
                    stats["disabled"] += 1

            except Exception as e:
                logger.error(
                    f"Failed to activate account {account.phone}: {e}", exc_info=True
                )
                stats["disabled"] += 1

    async def get_active_accounts(self, count: int = 10) -> List[Account]:
        """Получение списка активных аккаунтов для работы"""
        try:
            # Получаем все активные аккаунты
            accounts = await self.queries.get_active_accounts()

            # Фильтруем по возможности использования
            available = [a for a in accounts if a.can_be_used and not a.is_flood_wait]

            # Сортируем по количеству сообщений
            available.sort(key=lambda x: x.messages_sent)

            return available[:count]

        except Exception as e:
            logger.error(f"Failed to get active accounts: {e}", exc_info=True)
            return []

    async def disable_account(self, account: Account, reason: str):
        """Отключение аккаунта"""
        try:
            # Отключаем аккаунт
            await account.disable()

            # Отправляем уведомление
            await self.notifier.notify_disabled(account, reason)

        except Exception as e:
            logger.error(
                f"Failed to disable account {account.phone}: {e}", exc_info=True
            )

    async def block_account(self, account: Account, reason: str):
        """Блокировка аккаунта"""
        try:
            # Блокируем аккаунт
            await account.block()

            # Отправляем уведомление
            await self.notifier.notify_blocked(account, reason)

        except Exception as e:
            logger.error(f"Failed to block account {account.phone}: {e}", exc_info=True)
