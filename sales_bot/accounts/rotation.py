import logging
from datetime import datetime, timedelta
from typing import List

from .models import Account, AccountStatus
from .monitoring import AccountMonitor
from .notifications import AccountNotifier
from .queries import AccountQueries

logger = logging.getLogger(__name__)


class AccountRotator:
    def __init__(self, db):
        self.db = db
        self.queries = AccountQueries(db)
        self.monitor = AccountMonitor(db)
        self.notifier = AccountNotifier()

    async def rotate_accounts(self) -> dict:
        """
        Выполняет ротацию аккаунтов:
        - Включает отдохнувшие аккаунты
        - Отключает уставшие аккаунты
        """
        stats = {"enabled": 0, "disabled": 0, "errors": 0}

        try:
            # Включаем отдохнувшие аккаунты
            enabled = await self._enable_rested_accounts()
            stats["enabled"] = len(enabled)

            # Отключаем уставшие аккаунты
            disabled = await self._disable_tired_accounts()
            stats["disabled"] = len(disabled)

            # Уведомляем о результатах
            if enabled or disabled:
                await self._notify_rotation_results(enabled, disabled)

            return stats

        except Exception as e:
            logger.error(f"Error in rotate_accounts: {e}")
            stats["errors"] += 1
            return stats

    async def _enable_rested_accounts(self) -> List[Account]:
        """Включает аккаунты, которые достаточно отдохнули"""
        # Получаем отключенные аккаунты
        disabled_accounts = await self.queries.get_accounts_by_status(
            AccountStatus.DISABLED.value
        )
        enabled_accounts = []

        for account in disabled_accounts:
            try:
                # Проверяем время последнего использования
                if account.last_used:
                    rest_time = datetime.now() - account.last_used
                    if rest_time < timedelta(hours=24):
                        continue

                # Проверяем работоспособность
                if await self.monitor.check_account(account):
                    # Включаем аккаунт
                    await self.queries.update_account_status_by_id(
                        account.id, AccountStatus.ACTIVE.value
                    )
                    enabled_accounts.append(account)
                    logger.info(f"Enabled account {account.phone}")

            except Exception as e:
                logger.error(f"Error enabling account {account.phone}: {e}")

        return enabled_accounts

    async def _disable_tired_accounts(self) -> List[Account]:
        """Отключает аккаунты, которые много работали"""
        # Получаем активные аккаунты
        active_accounts = await self.queries.get_accounts_by_status(
            AccountStatus.ACTIVE.value
        )
        disabled_accounts = []

        for account in active_accounts:
            try:
                should_disable = False

                # Проверяем количество сообщений
                if account.daily_messages >= self.db.config.MAX_DAILY_MESSAGES * 0.8:
                    should_disable = True
                    reason = "daily limit approaching"

                # Проверяем время работы
                elif account.last_used:
                    work_time = datetime.now() - account.last_used
                    if work_time > timedelta(hours=12):
                        should_disable = True
                        reason = "long work period"

                if should_disable:
                    # Отключаем аккаунт
                    await self.queries.update_account_status_by_id(
                        account.id, AccountStatus.DISABLED.value
                    )
                    disabled_accounts.append(account)
                    logger.info(f"Disabled account {account.phone}: {reason}")

            except Exception as e:
                logger.error(f"Error disabling account {account.phone}: {e}")

        return disabled_accounts

    async def _notify_rotation_results(
        self, enabled: List[Account], disabled: List[Account]
    ):
        """Отправляет уведомление о результатах ротации"""
        if not enabled and not disabled:
            return

        message = "🔄 Ротация аккаунтов\n\n"

        if enabled:
            message += "✅ Включены:\n"
            for acc in enabled:
                message += f"• {acc.phone}\n"
            message += "\n"

        if disabled:
            message += "🔴 Отключены:\n"
            for acc in disabled:
                message += f"• {acc.phone}\n"

        await self.notifier.send_notification(message)
