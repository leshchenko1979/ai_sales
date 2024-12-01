"""Account rotation module."""

import logging
from typing import List

from core.accounts.models.account import AccountStatus
from core.db import with_queries

from .client import AccountClient
from .models import Account
from .monitoring import AccountMonitor
from .notifications import AccountNotifier
from .queries.account import AccountQueries

logger = logging.getLogger(__name__)


class AccountRotation:
    """
    Компонент для ротации аккаунтов:
    - Активация новых аккаунтов
    - Отключение проблемных аккаунтов
    - Балансировка нагрузки
    """

    def __init__(self):
        """Initialize rotation manager"""
        self.notifier = AccountNotifier()
        self.monitor = AccountMonitor()

    @with_queries(AccountQueries)
    async def rotate_accounts(
        self, queries: AccountQueries, min_active: int = 10
    ) -> dict:
        """
        Ротация аккаунтов для поддержания нужного количества активных

        :param queries: Database queries executor
        :param min_active: Minimum number of active accounts to maintain
        :return: Statistics dictionary
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
            accounts = await queries.get_all_accounts()
            stats["total"] = len(accounts)

            # Проверяем активные аккаунты
            active_accounts = [a for a in accounts if a.status == AccountStatus.active]

            # Если активных достаточно - проверяем их состояние
            if len(active_accounts) >= min_active:
                await self._check_active_accounts(queries, active_accounts, stats)
            # Если активных мало - активируем новые
            else:
                await self._activate_new_accounts(
                    queries, accounts, min_active - len(active_accounts), stats
                )

            # Отправляем отчет
            await self.notifier.notify_rotation_report(stats)
            return stats

        except Exception as e:
            logger.error(f"Error rotating accounts: {e}", exc_info=True)
            return None

    @with_queries(AccountQueries)
    async def _check_active_accounts(
        self, queries: AccountQueries, accounts: List[Account], stats: dict
    ) -> None:
        """
        Проверка активных аккаунтов

        :param queries: Database queries executor
        :param accounts: List of active accounts to check
        :param stats: Statistics dictionary to update
        """
        try:
            for account in accounts:
                # Проверяем состояние
                if not await self.monitor.check_account(account):
                    # Отключаем проблемный аккаунт
                    await queries.update_account_status(
                        account.id, AccountStatus.disabled
                    )
                    stats["disabled"] += 1
                    continue

                # Проверяем флуд-контроль
                if account.is_flood_wait:
                    stats["flood_wait"] += 1

        except Exception as e:
            logger.error(f"Error checking active accounts: {e}", exc_info=True)

    @with_queries(AccountQueries)
    async def _activate_new_accounts(
        self, queries: AccountQueries, accounts: List[Account], count: int, stats: dict
    ) -> None:
        """
        Активация новых аккаунтов

        :param queries: Database queries executor
        :param accounts: List of all accounts
        :param count: Number of accounts to activate
        :param stats: Statistics dictionary to update
        """
        try:
            # Получаем новые аккаунты
            new_accounts = [a for a in accounts if a.status == AccountStatus.new]

            for account in new_accounts[:count]:
                # Пробуем активировать
                client = AccountClient(account)
                if await client.connect():
                    await queries.update_account_status(
                        account.id, AccountStatus.active
                    )
                    stats["activated"] += 1
                else:
                    await queries.update_account_status(
                        account.id, AccountStatus.blocked
                    )
                    stats["blocked"] += 1

        except Exception as e:
            logger.error(f"Error activating new accounts: {e}", exc_info=True)

    async def get_active_accounts(self, count: int = 10) -> List[Account]:
        """Получение списка активных аккаунтов для работы"""
        try:
            # Получаем все активные аккаунты
            accounts = await AccountQueries().get_active_accounts()

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
