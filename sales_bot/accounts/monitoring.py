import logging

from pyrogram.errors import (
    AuthKeyUnregistered,
    SessionRevoked,
    UserDeactivated,
    UserDeactivatedBan,
)

from .client import AccountClient
from .models import Account, AccountStatus
from .notifications import AccountNotifier

logger = logging.getLogger(__name__)


class AccountMonitor:
    def __init__(self, db):
        self.db = db
        self._error_counts = {}  # account_id -> error_count
        self.notifier = AccountNotifier()

    async def start(self):
        """Start the monitor"""
        await self.notifier.start()

    async def stop(self):
        """Stop the monitor"""
        await self.notifier.stop()

    async def check_account(self, account: Account) -> bool:
        """
        Проверяет работоспособность аккаунта
        Возвращает True если аккаунт работает
        """
        try:
            client = AccountClient(account)
            if not await client.connect():
                return False

            # Пробуем получить информацию о себе
            me = await client.client.get_me()
            if not me:
                return False

            # Сбрасываем счетчик ошибок
            self._error_counts.pop(account.id, None)
            return True

        except (
            UserDeactivated,
            SessionRevoked,
            AuthKeyUnregistered,
            UserDeactivatedBan,
        ) as e:
            # Явные признаки блокировки
            logger.error(f"Account {account.phone} is blocked: {e}")
            await self._mark_account_blocked(account.id, str(e))
            return False

        except Exception as e:
            # Другие ошибки - считаем их
            error_count = self._error_counts.get(account.id, 0) + 1
            self._error_counts[account.id] = error_count

            logger.warning(f"Error checking account {account.phone}: {e}")

            if error_count >= 3:
                await self._mark_account_disabled(
                    account.id, f"3 consecutive errors: {e}"
                )
                return False

            return False

        finally:
            await client.disconnect()

    async def check_all_accounts(self) -> dict:
        """
        Проверяет все активные аккаунты
        Возвращает статистику проверки
        """
        stats = {"total": 0, "active": 0, "disabled": 0, "blocked": 0}

        accounts = await self.db.queries.get_active_accounts()
        stats["total"] = len(accounts)

        for account in accounts:
            if await self.check_account(account):
                stats["active"] += 1
            elif account.status == AccountStatus.BLOCKED:
                stats["blocked"] += 1
            else:
                stats["disabled"] += 1

        # Отправляем отчет
        await self.notifier.notify_status_report(stats)
        return stats

    async def _mark_account_blocked(self, account_id: int, reason: str):
        """Помечает аккаунт как заблокированный"""
        account = await self.db.queries.get_account_by_id(account_id)
        if account:
            await self.db.queries.update_account_status_by_id(
                account_id, AccountStatus.BLOCKED.value
            )
            await self.notifier.notify_blocked(account, reason)
            self._error_counts.pop(account_id, None)

    async def _mark_account_disabled(self, account_id: int, reason: str):
        """Помечает аккаунт как отключенный"""
        account = await self.db.queries.get_account_by_id(account_id)
        if account:
            await self.db.queries.update_account_status_by_id(
                account_id, AccountStatus.DISABLED.value
            )
            await self.notifier.notify_disabled(account, reason)
            self._error_counts.pop(account_id, None)
