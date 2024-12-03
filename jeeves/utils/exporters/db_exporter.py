"""Database dialog exporter."""

from typing import Optional

from core.db.decorators import with_queries
from core.messaging.models import Message
from core.messaging.queries import DialogQueries

from . import BaseExporter, Dialog
from . import Message as ExportMessage


class DBDialogExporter(BaseExporter):
    """Export dialogs from database."""

    def __init__(self):
        """Initialize exporter."""
        super().__init__()

    def _convert_message(self, msg: Message) -> ExportMessage:
        """Convert DB message to export format."""
        return ExportMessage(
            id=msg.id,
            timestamp=msg.timestamp,
            content=msg.content,
            sender_id=msg.user_id,
            is_bot=msg.direction == "out",
            message_type="dialog",
        )

    @with_queries(DialogQueries)
    async def export_dialog(
        self, dialog_id: int, queries: DialogQueries
    ) -> Optional[str]:
        """Export single dialog."""
        try:
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

            export_dialog = Dialog(
                id=dialog.id,
                title=f"Диалог с @{dialog.username}",
                created_at=dialog.created_at,
                messages=[self._convert_message(msg) for msg in messages],
                metadata={"username": dialog.username},
            )

            return await self.save_export([export_dialog], prefix="db_dialog")

        except Exception as e:
            import logging

            logging.error(f"Error exporting dialog {dialog_id}: {e}", exc_info=True)
            return None

    @with_queries(DialogQueries)
    async def export_all_dialogs(self, queries: DialogQueries) -> Optional[str]:
        """Export all dialogs."""
        try:
            dialogs = await queries.get_all_dialogs()
            if not dialogs:
                return None

            export_dialogs = []
            for dialog in dialogs:
                messages = (
                    queries.session.query(Message)
                    .filter(Message.dialog_id == dialog.id)
                    .order_by(Message.timestamp)
                    .all()
                )

                if not messages:
                    continue

                export_dialogs.append(
                    Dialog(
                        id=dialog.id,
                        title=f"Диалог с @{dialog.username}",
                        created_at=dialog.created_at,
                        messages=[self._convert_message(msg) for msg in messages],
                        metadata={"username": dialog.username},
                    )
                )

            if not export_dialogs:
                return None

            return await self.save_export(export_dialogs, prefix="db_dialogs")

        except Exception as e:
            import logging

            logging.error(f"Error exporting all dialogs: {e}", exc_info=True)
            return None
