"""Export utilities."""

import logging
from datetime import datetime
from pathlib import Path

from core.db import DialogQueries, with_queries
from core.messages.models import Message

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).parent.parent / "exports"


def ensure_export_dir():
    """Create export directory if it doesn't exist."""
    EXPORT_DIR.mkdir(exist_ok=True)


@with_queries(DialogQueries)
async def export_dialog(dialog_id: int, queries: DialogQueries) -> str:
    """Export dialog to file."""
    try:
        ensure_export_dir()

        dialog = await queries.get_dialog_by_id(dialog_id)
        if not dialog:
            return None

        messages = (
            queries.session.query(Message)
            .filter(Message.dialog_id == dialog_id)
            .order_by(Message.timestamp)
            .all()
        )

        if not messages:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = EXPORT_DIR / f"dialog_{dialog_id}_{timestamp}.txt"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"Диалог {dialog_id} с @{dialog.username}\n")
            f.write(f"Создан: {dialog.created_at}\n\n")

            for msg in messages:
                direction = "→" if msg.direction == "out" else "←"
                f.write(f"[{msg.timestamp}] {direction} {msg.content}\n")

        return str(file_path)

    except Exception as e:
        logger.error(f"Error exporting dialog {dialog_id}: {e}", exc_info=True)
        return None


@with_queries(DialogQueries)
async def export_all_dialogs(queries: DialogQueries) -> str:
    """Export all dialogs to file."""
    try:
        ensure_export_dir()

        dialogs = await queries.get_all_dialogs()
        if not dialogs:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = EXPORT_DIR / f"all_dialogs_{timestamp}.txt"

        with open(file_path, "w", encoding="utf-8") as f:
            for dialog in dialogs:
                f.write(f"\nДиалог {dialog.id} с @{dialog.username}\n")
                f.write(f"Создан: {dialog.created_at}\n\n")

                messages = (
                    queries.session.query(Message)
                    .filter(Message.dialog_id == dialog.id)
                    .order_by(Message.timestamp)
                    .all()
                )

                for msg in messages:
                    direction = "→" if msg.direction == "out" else "←"
                    f.write(f"[{msg.timestamp}] {direction} {msg.content}\n")

                f.write("\n" + "=" * 50 + "\n")

        return str(file_path)

    except Exception as e:
        logger.error(f"Error exporting all dialogs: {e}", exc_info=True)
        return None
