import os
import logging
from datetime import datetime
from db.queries import get_db
from db.models import Dialog, Message

logger = logging.getLogger(__name__)

EXPORT_DIR = "exports"

def ensure_export_dir():
    """Создание директории для экспорта если её нет"""
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

async def export_dialog(dialog_id: int) -> str:
    """Экспорт диалога в файл"""
    try:
        ensure_export_dir()

        async for db in get_db():
            dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
            if not dialog:
                return None

            messages = db.query(Message).filter(
                Message.dialog_id == dialog_id
            ).order_by(Message.timestamp).all()

            if not messages:
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(EXPORT_DIR, f"dialog_{dialog_id}_{timestamp}.txt")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Диалог {dialog_id} с @{dialog.target_username}\n")
                f.write(f"Статус: {dialog.status}\n")
                f.write(f"Создан: {dialog.created_at}\n\n")

                for msg in messages:
                    direction = "→" if msg.direction == "out" else "←"
                    f.write(f"[{msg.timestamp}] {direction} {msg.content}\n")

            return file_path

    except Exception as e:
        logger.error(f"Error exporting dialog {dialog_id}: {e}")
        return None

async def export_all_dialogs() -> str:
    """Экспорт всех диалогов в файл"""
    try:
        ensure_export_dir()

        async for db in get_db():
            dialogs = db.query(Dialog).all()
            if not dialogs:
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(EXPORT_DIR, f"all_dialogs_{timestamp}.txt")

            with open(file_path, 'w', encoding='utf-8') as f:
                for dialog in dialogs:
                    f.write(f"\nДиалог {dialog.id} с @{dialog.target_username}\n")
                    f.write(f"Статус: {dialog.status}\n")
                    f.write(f"Создан: {dialog.created_at}\n\n")

                    messages = db.query(Message).filter(
                        Message.dialog_id == dialog.id
                    ).order_by(Message.timestamp).all()

                    for msg in messages:
                        direction = "→" if msg.direction == "out" else "←"
                        f.write(f"[{msg.timestamp}] {direction} {msg.content}\n")

                    f.write("\n" + "="*50 + "\n")

            return file_path

    except Exception as e:
        logger.error(f"Error exporting all dialogs: {e}")
        return None
