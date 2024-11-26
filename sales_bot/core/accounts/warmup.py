"""Account warmup module."""

import asyncio
import logging
import random

from core.db import AccountQueries, with_queries
from pyrogram.errors import FloodWait

from .client import AccountClient
from .models import Account
from .monitoring import AccountMonitor
from .notifications import AccountNotifier

logger = logging.getLogger(__name__)

WARMUP_CHANNELS = [
    "telegram",
    "durov",
    "tginfo",
    "cryptocurrency",
    "bitcoin",
    "trading",
]


class AccountWarmup:
    """
    Компонент для прогрева аккаунтов
    """

    def __init__(self):
        """Initialize warmup manager"""
        self.notifier = AccountNotifier()
        self.monitor = AccountMonitor()

    @with_queries(AccountQueries)
    async def warmup_accounts(self, queries: AccountQueries) -> dict:
        """
        Прогрев всех активных аккаунтов

        :param queries: Database queries executor
        :return: Statistics dictionary
        """
        try:
            # Получаем активные аккаунты
            accounts = await queries.get_active_accounts()
            stats = {"total": len(accounts), "success": 0, "failed": 0, "flood_wait": 0}

            # Прогреваем каждый аккаунт
            for account in accounts:
                try:
                    # Проверяем флуд-контроль
                    if not await self.monitor.check_flood_wait(account):
                        stats["flood_wait"] += 1
                        continue

                    # Прогреваем аккаунт
                    if await self._warmup_account(queries, account):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1

                except Exception as e:
                    logger.error(
                        f"Error warming up account {account.phone}: {e}", exc_info=True
                    )
                    stats["failed"] += 1

            # Отправляем отчет
            await self.notifier.notify_warmup_report(stats)
            return stats

        except Exception as e:
            logger.error(f"Error warming up accounts: {e}", exc_info=True)
            return None

    @with_queries(AccountQueries)
    async def _warmup_account(self, queries: AccountQueries, account: Account) -> bool:
        """
        Прогрев конкретного аккаунта

        :param queries: Database queries executor
        :param account: Account to warm up
        :return: True if warmup successful
        """
        try:
            # Создаем клиент
            client = AccountClient(account)
            if not await client.connect():
                logger.error(f"Failed to connect client for {account.phone}")
                return False

            # Выбираем случайные каналы
            channels = random.sample(WARMUP_CHANNELS, 3)

            # Подписываемся и читаем сообщения
            for channel in channels:
                try:
                    # Подписываемся на канал
                    await client.join_channel(channel)
                    await asyncio.sleep(random.randint(30, 60))

                    # Читаем сообщения
                    await client.read_channel_messages(channel)
                    await asyncio.sleep(random.randint(60, 120))

                except FloodWait as e:
                    logger.warning(f"FloodWait for {account.phone}: {e.value} seconds")
                    await queries.set_flood_wait(account.id, e.value)
                    return False

                except Exception as e:
                    logger.error(f"Error in channel {channel}: {e}", exc_info=True)
                    continue

            # Обновляем время последнего использования
            await queries.update_last_used(account.id)
            return True

        except Exception as e:
            logger.error(
                f"Error warming up account {account.phone}: {e}", exc_info=True
            )
            return False
