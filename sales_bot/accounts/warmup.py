import asyncio
import logging
import random
from datetime import datetime

from db.queries import AccountQueries

from .client import AccountClient
from .models import Account
from .notifications import AccountNotifier

logger = logging.getLogger(__name__)


class AccountWarmup:
    def __init__(self, db):
        self.db = db
        self.queries = AccountQueries(db)
        self.notifier = AccountNotifier()
        self._warmup_actions = [
            self._join_channels,
            self._update_profile,
            self._send_messages_to_self,
            self._read_channels,
        ]

    async def warmup_account(self, account: Account) -> bool:
        """Прогрев одного аккаунта"""
        try:
            logger.info(f"Starting warmup for account {account.phone}")

            client = AccountClient(account)
            if not await client.connect():
                return False

            try:
                # Выполняем случайные действия прогрева
                actions = random.sample(self._warmup_actions, k=2)
                for action in actions:
                    if not await action(client):
                        return False
                    # Делаем паузу между действиями
                    await asyncio.sleep(random.randint(30, 120))

                # Обновляем статус аккаунта
                await self.db.queries.update_account_warmup_time(account.id)
                return True

            finally:
                await client.disconnect()

        except Exception as e:
            logger.error(
                f"Error warming up account {account.phone}: {e}", exc_info=True
            )
            return False

    async def warmup_new_accounts(self) -> dict:
        """Прогрев новых аккаунтов"""
        stats = {"total": 0, "success": 0, "failed": 0}

        try:
            # Get accounts for warmup using self.queries
            accounts = await self.queries.get_accounts_for_warmup()
            stats["total"] = len(accounts)

            for account in accounts:
                try:
                    if await self.warmup_account(account):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    logger.error(
                        f"Failed to warmup account {account.phone}: {e}", exc_info=True
                    )
                    stats["failed"] += 1

            # Send report
            await self._notify_warmup_results(stats)
            return stats

        except Exception as e:
            logger.error(f"Error during warmup: {e}", exc_info=True)
            return stats

    async def _join_channels(self, client: AccountClient) -> bool:
        """Присоединение к каналам"""
        channels = [
            "telegram",
            "durov",
            "tginfo",
            "cryptocurrency",
            "bitcoin",
            "trading",
        ]
        try:
            # Присоединяемся к 2-3 случайным каналам
            selected = random.sample(channels, k=random.randint(2, 3))
            for channel in selected:
                await client.client.join_chat(channel)
                await asyncio.sleep(random.randint(60, 180))
            return True
        except Exception as e:
            logger.error(f"Error joining channels: {e}", exc_info=True)
            return False

    async def _update_profile(self, client: AccountClient) -> bool:
        """Обновление профиля"""
        try:
            # Устанавливаем имя и био
            first_names = ["Alex", "Michael", "John", "David", "Robert"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
            bios = [
                "Crypto enthusiast",
                "Investor",
                "Trading professional",
                "Financial analyst",
                "Business developer",
            ]

            await client.client.update_profile(
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                bio=random.choice(bios),
            )
            return True
        except Exception as e:
            logger.error(f"Error updating profile: {e}", exc_info=True)
            return False

    async def _send_messages_to_self(self, client: AccountClient) -> bool:
        """Отправка сообщений самому себе"""
        try:
            await client.client.get_me()
            messages = [
                "Investment notes",
                "Market analysis",
                "Trading strategy",
                "Portfolio update",
                "Research materials",
            ]

            # Отправляем 2-3 сообщения
            for _ in range(random.randint(2, 3)):
                await client.client.send_message("me", random.choice(messages))
                await asyncio.sleep(random.randint(30, 90))
            return True
        except Exception as e:
            logger.error(f"Error sending self messages: {e}", exc_info=True)
            return False

    async def _read_channels(self, client: AccountClient) -> bool:
        """Чтение сообщений в каналах"""
        try:
            # Получаем список подписанных каналов
            async for dialog in client.client.get_dialogs():
                if dialog.chat.type in ["channel", "supergroup"]:
                    # Читаем сообщения
                    async for message in client.client.get_chat_history(
                        dialog.chat.id, limit=10
                    ):
                        await client.client.read_chat_history(
                            dialog.chat.id, message.id
                        )
                        await asyncio.sleep(random.randint(5, 15))
                    break  # Читаем только один случайный канал
            return True
        except Exception as e:
            logger.error(f"Error reading channels: {e}", exc_info=True)
            return False

    async def _notify_warmup_results(self, stats: dict):
        """Отправка уведомления о результатах прогрева"""
        message = (
            "🔥 Результаты прогрева аккаунтов\n\n"
            f"Всего аккаунтов: {stats['total']}\n"
            f"✅ Успешно: {stats['success']}\n"
            f"❌ Неудачно: {stats['failed']}\n\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await self.notifier._send_notification(message)
