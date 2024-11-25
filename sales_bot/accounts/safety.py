import logging
from datetime import datetime, timedelta
from typing import Dict

from config import (
    MAX_MESSAGES_PER_DAY,
    MAX_MESSAGES_PER_HOUR,
    MIN_MESSAGE_DELAY,
    RESET_HOUR_UTC,
)
from db.queries import AccountQueries, with_queries

from .models import Account

logger = logging.getLogger(__name__)


class AccountSafety:
    """
    Компонент для обеспечения безопасности аккаунтов:
    - Контроль количества сообщений
    - Контроль задержек между сообщениями
    - Сброс счетчиков в заданное время
    """

    def __init__(self):
        self._last_message_time: Dict[int, float] = {}
        self._hourly_messages: Dict[int, int] = {}
        self._hourly_reset_time: Dict[int, datetime] = {}
        self._daily_reset_time: Dict[int, datetime] = {}

    def can_send_message(self, account: Account) -> bool:
        """Проверка можно ли отправить сообщение с аккаунта"""
        now = datetime.utcnow()

        # Проверяем задержку между сообщениями
        last_time = self._last_message_time.get(account.id, 0)
        if now.timestamp() - last_time < MIN_MESSAGE_DELAY:
            return False

        # Проверяем лимит сообщений в час
        self._reset_hourly_if_needed(account.id, now)
        if self._hourly_messages.get(account.id, 0) >= MAX_MESSAGES_PER_HOUR:
            return False

        # Проверяем дневной лимит
        self._reset_daily_if_needed(account.id, now)
        if account.messages_sent >= MAX_MESSAGES_PER_DAY:
            return False

        return True

    def record_message(self, account: Account):
        """Запись отправленного сообщения"""
        now = datetime.utcnow()

        # Обновляем время последнего сообщения
        self._last_message_time[account.id] = now.timestamp()

        # Увеличиваем счетчик сообщений в час
        self._reset_hourly_if_needed(account.id, now)
        self._hourly_messages[account.id] = self._hourly_messages.get(account.id, 0) + 1

    def _reset_hourly_if_needed(self, account_id: int, now: datetime):
        """Сброс часового счетчика если нужно"""
        last_reset = self._hourly_reset_time.get(account_id)
        if not last_reset or (now - last_reset) >= timedelta(hours=1):
            self._hourly_messages[account_id] = 0
            self._hourly_reset_time[account_id] = now

    def _reset_daily_if_needed(self, account_id: int, now: datetime):
        """Сброс дневного счетчика если нужно"""
        last_reset = self._daily_reset_time.get(account_id)

        # Определяем время следующего сброса
        next_reset = now.replace(hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
        if now.hour >= RESET_HOUR_UTC:
            next_reset += timedelta(days=1)

        # Если прошло время сброса - сбрасываем счетчик
        if not last_reset or now >= next_reset:
            self._daily_reset_time[account_id] = next_reset

    @with_queries(AccountQueries)
    async def reset_daily_limits(self, queries: AccountQueries):
        """Reset daily message limits for all accounts"""
        try:
            await queries.reset_daily_limits()
            logger.info("Daily message limits reset")

            # Reset local counters
            now = datetime.utcnow()
            next_reset = now.replace(
                hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0
            )
            if now.hour >= RESET_HOUR_UTC:
                next_reset += timedelta(days=1)

            # Update all daily reset times
            for account_id in self._daily_reset_time:
                self._daily_reset_time[account_id] = next_reset

        except Exception as e:
            logger.error(f"Failed to reset daily limits: {e}", exc_info=True)
            raise
