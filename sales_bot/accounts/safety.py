import time
from datetime import datetime, timedelta
from typing import Dict

from sales_bot.config import MIN_MESSAGE_DELAY
from .models import Account

class AccountSafety:
    def __init__(self):
        self._last_message_time: Dict[int, float] = {}

    def can_send_message(self, account: Account) -> bool:
        """Check if it's safe to send message from account"""
        last_time = self._last_message_time.get(account.id, 0)
        return time.time() - last_time >= MIN_MESSAGE_DELAY

    def record_message(self, account: Account):
        """Record message sent from account"""
        self._last_message_time[account.id] = time.time()
