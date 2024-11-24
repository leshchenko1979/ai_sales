import logging
from datetime import datetime

from bot.client import app
from config import ADMIN_TELEGRAM_ID

from .models import Account

logger = logging.getLogger(__name__)


class AccountNotifier:
    def __init__(self):
        self.admin_id = ADMIN_TELEGRAM_ID
        self._bot = app
        self._last_notification = {}  # account_id -> last_notification_time

    async def notify_blocked(self, account: Account, reason: str):
        """Уведомление о блокировке аккаунта"""
        if not await self._should_notify(account.id, "blocked"):
            return

        message = (
            "⛔️ Аккаунт заблокирован\n\n"
            f"Телефон: {account.phone}\n"
            f"Причина: {reason}\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await self._send_notification(message)
        self._update_notification_time(account.id, "blocked")

    async def notify_disabled(self, account: Account, reason: str):
        """Уведомление об отключении аккаунта"""
        if not await self._should_notify(account.id, "disabled"):
            return

        message = (
            "🔴 Аккаунт отключен\n\n"
            f"Телефон: {account.phone}\n"
            f"Причина: {reason}\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await self._send_notification(message)
        self._update_notification_time(account.id, "disabled")

    async def notify_limit_reached(self, account: Account):
        """Уведомление о достижении лимита сообщений"""
        if not await self._should_notify(account.id, "limit"):
            return

        message = (
            "⚠️ Достигнут дневной лимит сообщений\n\n"
            f"Телефон: {account.phone}\n"
            f"Сообщений: {account.daily_messages}\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await self._send_notification(message)
        self._update_notification_time(account.id, "limit")

    async def notify_status_report(self, stats: dict):
        """Отправка ежедневного отчета о состоянии аккаунтов"""
        message = (
            "📊 Отчет о состоянии аккаунтов\n\n"
            f"Всего аккаунтов: {stats['total']}\n"
            f"✅ Активны: {stats['active']}\n"
            f"🔴 Отключены: {stats['disabled']}\n"
            f"⛔️ Заблокированы: {stats['blocked']}\n\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await self._send_notification(message)

    async def _should_notify(self, account_id: int, notification_type: str) -> bool:
        """Проверяет, нужно ли отправлять уведомление"""
        key = f"{account_id}_{notification_type}"
        last_time = self._last_notification.get(key)

        if not last_time:
            return True

        # Не отправляем одинаковые уведомления чаще чем раз в час
        return (datetime.now() - last_time).total_seconds() >= 3600

    def _update_notification_time(self, account_id: int, notification_type: str):
        """Обновляет время последнего уведомления"""
        key = f"{account_id}_{notification_type}"
        self._last_notification[key] = datetime.now()

    async def send_notification(self, message: str):
        """Отправляет уведомление администратору"""
        try:
            await app.send_message(self.admin_id, message)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
