import asyncio
import logging
import random
from datetime import datetime, timedelta

from db.queries import AccountQueries
from pyrogram.errors import FloodWait

from .client import AccountClient
from .models import Account
from .monitor import AccountMonitor
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

    def __init__(self, queries: AccountQueries, notifier: AccountNotifier):
        self.queries = queries
        self.notifier = notifier
        self.monitor = AccountMonitor(queries, notifier)

    async def warmup_accounts(self):
        """Прогрев всех активных аккаунтов"""
        try:
            # Получаем активные аккаунты
            accounts = await self.queries.get_active_accounts()

            stats = {"total": len(accounts), "success": 0, "failed": 0, "flood_wait": 0}

            # Прогреваем каждый аккаунт
            for account in accounts:
                try:
                    # Проверяем флуд-контроль
                    if not await self.monitor.check_flood_wait(account):
                        stats["flood_wait"] += 1
                        continue

                    # Проверяем состояние аккаунта
                    if not await self.monitor.check_account(account):
                        stats["failed"] += 1
                        continue

                    # Прогреваем аккаунт
                    if await self._warmup_account(account):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1

                except Exception as e:
                    logger.error(
                        f"Failed to warmup account {account.phone}: {e}", exc_info=True
                    )
                    stats["failed"] += 1

            # Отправляем отчет
            await self.notifier.notify_warmup_report(stats)

        except Exception as e:
            logger.error(f"Failed to warmup accounts: {e}", exc_info=True)

    async def _warmup_account(self, account: Account) -> bool:
        """
        Прогрев одного аккаунта
        Возвращает True если прогрев успешен
        """
        try:
            # Создаем клиент
            client = AccountClient(account)
            if not await client.connect():
                return False

            # Выполняем базовые действия
            await self._perform_basic_actions(client)

            # Обновляем время последнего прогрева
            await self.queries.update_last_warmup(account.id)
            return True

        except FloodWait as e:
            # Обрабатываем флуд-контроль
            flood_wait_until = datetime.utcnow() + timedelta(seconds=e.value)
            await self.queries.update_flood_wait(account.id, flood_wait_until)
            await self.notifier.notify_flood_wait(account, e.value)
            return False

        except Exception as e:
            logger.error(
                f"Error warming up account {account.phone}: {e}", exc_info=True
            )
            return False

    async def _perform_basic_actions(self, client: AccountClient):
        """Выполнение базовых действий для прогрева"""
        try:
            # Получаем информацию о своем аккаунте
            me = await client.client.get_me()
            if not me:
                raise Exception("Failed to get account info")

            # Читаем сообщения из нескольких каналов
            channels = WARMUP_CHANNELS
            for channel in channels:
                try:
                    # Получаем последние сообщения
                    messages = await client.client.get_history(channel, limit=5)

                    # Читаем каждое сообщение
                    for msg in messages:
                        await client.client.read_history(channel, max_id=msg.id)
                        await asyncio.sleep(random.uniform(1, 3))

                except Exception as e:
                    logger.warning(f"Failed to read channel {channel}: {e}")
                    continue

                # Пауза между каналами
                await asyncio.sleep(random.uniform(2, 5))

        except Exception as e:
            logger.error(f"Failed to perform basic actions: {e}", exc_info=True)
            raise
