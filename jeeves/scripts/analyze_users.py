import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class TelegramUser:
    chat_id: str
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]


def analyze_users(file_path: Path) -> Dict:
    """Анализирует файл с пользователями и возвращает статистику."""

    with open(file_path, "r", encoding="utf-8") as f:
        users_data = json.load(f)

    users = [TelegramUser(**user) for user in users_data]

    # Подсчет статистики
    stats = {
        "total_users": len(users),
        "users_with_username": len([u for u in users if u.username]),
        "users_by_chat": {},
        "users_without_username_but_with_id": len(
            [u for u in users if not u.username and u.user_id]
        ),
    }

    # Группировка по чатам
    for user in users:
        stats["users_by_chat"][user.chat_id] = (
            stats["users_by_chat"].get(user.chat_id, 0) + 1
        )

    return stats


if __name__ == "__main__":
    root_dir = Path(__file__).parent.parent.parent
    file_path = root_dir / "jeeves" / "core" / "audiences" / "sources" / "users.json"

    stats = analyze_users(file_path)

    print("\nАнализ пользователей:")
    print(f"Всего пользователей: {stats['total_users']}")
    print(f"Пользователей с username: {stats['users_with_username']}")
    print(
        f"Пользователей без username, но с ID: {stats['users_without_username_but_with_id']}"
    )
    print("\nПользователей по чатам:")
    for chat, count in stats["users_by_chat"].items():
        print(f"  {chat}: {count}")
