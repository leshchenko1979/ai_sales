import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from core.audiences.models import Audience, AudienceStatus, Contact, audiences_contacts
from core.db import with_queries
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class TelegramUser:
    chat_id: str
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]


CHAT_TO_AUDIENCE = {
    "flipping_club": "Флиппинг Клуб",
    "flipping_club_spb": "Флиппинг Клуб СПб",
    "@remont_poisk": "Ремонт Поиск",
}


@with_queries()
async def load_users(*, session: AsyncSession) -> None:
    """Load users to audiences."""
    # Читаем файл с пользователями
    file_path = ROOT_DIR / "jeeves" / "core" / "audiences" / "sources" / "users.json"
    with open(file_path, "r", encoding="utf-8") as f:
        users_data = json.load(f)

    # Группируем пользователей по чатам
    users_by_chat: Dict[str, List[TelegramUser]] = {}
    for user_data in users_data:
        if user_data["chat_id"] == "flipexpo":
            continue
        user = TelegramUser(**user_data)
        users_by_chat.setdefault(user.chat_id, []).append(user)

    # Создаем аудитории и загружаем пользователей
    for chat_id, users in users_by_chat.items():
        # Создаем аудиторию
        audience = Audience(name=CHAT_TO_AUDIENCE[chat_id], status=AudienceStatus.new)
        session.add(audience)
        await session.flush()
        print(f"Created audience: {audience.name}")

        # Создаем контакты пачкой
        contacts = [
            Contact(
                telegram_username=user.username, telegram_id=user.user_id, is_valid=True
            )
            for user in users
        ]
        session.add_all(contacts)
        await session.flush()

        # Связываем контакты с аудиторией через промежуточную таблицу
        values = [
            {"audience_id": audience.id, "contact_id": contact.id}
            for contact in contacts
        ]
        await session.execute(insert(audiences_contacts), values)

        # Обновляем статус аудитории
        audience.status = AudienceStatus.ready
        await session.flush()

        print(f"Loaded {len(users)} contacts to {audience.name}")


if __name__ == "__main__":
    asyncio.run(load_users())
