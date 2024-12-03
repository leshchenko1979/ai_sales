"""Base classes for dialog export functionality."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

EXPORT_DIR = Path(__file__).parent.parent.parent.parent / "exports"


@dataclass
class Message:
    """Message in export format."""

    id: int
    timestamp: datetime
    content: str
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    is_bot: bool = False
    reply_to: Optional[int] = None
    message_type: str = "bot"  # "bot", "client", "feedback", or "separator"
    original_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "is_bot": self.is_bot,
            "reply_to": self.reply_to,
            "message_type": self.message_type,
            "original_timestamp": (
                self.original_timestamp.isoformat() if self.original_timestamp else None
            ),
        }

    def format_message(self) -> str:
        """Format message for text export."""
        timestamp = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Format prefix based on message type
        if self.message_type == "bot":
            prefix = "🤖"
        elif self.message_type == "client":
            prefix = "👤"
        elif self.message_type == "feedback":
            prefix = "💬"
        else:  # separator
            return self.content

        # Add sender ID if available
        sender_id = f" {self.sender_id}" if self.sender_id else ""

        # Format message content with indentation for replies
        content_lines = self.content.split("\n")
        formatted_content = "\n    ".join(content_lines)

        return f"[{timestamp}] {prefix}{sender_id} 📝:\n    {formatted_content}"


class Dialog:
    """Unified dialog representation."""

    def __init__(
        self,
        id: int,
        title: str,
        created_at: datetime,
        messages: List[Message],
        metadata: Optional[Dict] = None,
    ):
        self.id = id
        self.title = title
        self.created_at = created_at
        self.messages = messages
        self.metadata = metadata or {}

    def to_dict(self) -> Dict:
        """Convert dialog to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "messages": [msg.to_dict() for msg in self.messages],
        }


class BaseExporter(ABC):
    """Base class for dialog exporters."""

    def __init__(self):
        """Initialize exporter."""
        EXPORT_DIR.mkdir(exist_ok=True)

    @abstractmethod
    async def export_dialog(self, dialog_id: int) -> Optional[str]:
        """Export single dialog."""

    @abstractmethod
    async def export_all_dialogs(self) -> Optional[str]:
        """Export all dialogs."""

    def _format_message_block(
        self, msg: Message, reply_msg: Optional[Message] = None, indent: int = 0
    ) -> List[str]:
        """Format a message block with optional reply context."""
        lines = []
        prefix = "🤖" if msg.is_bot else "👤"
        sender = f"@{msg.sender_name}" if msg.sender_name else str(msg.sender_id)

        # Add original timestamp for forwarded messages
        timestamp_str = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        if msg.original_timestamp:
            timestamp_str += (
                f" (original: {msg.original_timestamp.strftime('%Y-%m-%d %H:%M:%S')})"
            )

        # Add reply context if exists
        if reply_msg:
            reply_text = reply_msg.content.split("\n")[0][:50]  # First line, truncated
            lines.append(" " * (indent + 4) + f"↳ В ответ на: {reply_text}...")
            lines.append(" " * (indent + 4) + f"[{timestamp_str}] 💬 {sender} 📝:")

        # Add message header
        header = f"[{timestamp_str}] {prefix} {sender}"
        if msg.message_type == "feedback":
            header += " 📝"  # Mark feedback messages
        lines.append(" " * indent + header + ":")

        # Add message content
        lines.extend(" " * (indent + 4) + line for line in msg.content.split("\n"))
        return lines

    def _format_human_readable(self, dialog: Dialog) -> str:
        """Format dialog for human reading with improved feedback handling."""
        lines = [
            f"Диалог {dialog.id}: {dialog.title}",
            f"Создан: {dialog.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        # Add metadata if exists
        if dialog.metadata:
            lines.append("Метаданные:")
            for key, value in dialog.metadata.items():
                if key not in ["chat_id", "topic_id"]:  # Skip technical fields
                    lines.append(f"  {key}: {value}")

        lines.append("")  # Empty line before messages

        # Create message lookup for replies
        msg_lookup = {msg.id: msg for msg in dialog.messages}

        # Group messages by their reply chains
        processed_ids = set()
        for msg in dialog.messages:
            if msg.id in processed_ids:
                continue

            # Start new message chain
            chain = []
            current_msg = msg
            indent = 0

            # Follow reply chain backwards
            while current_msg and indent < 20:  # Limit indent to prevent infinite loops
                chain.insert(0, (current_msg, indent))
                processed_ids.add(current_msg.id)

                if current_msg.reply_to and current_msg.reply_to in msg_lookup:
                    current_msg = msg_lookup[current_msg.reply_to]
                    indent += 2
                else:
                    break

            # Format message chain
            for msg, indent in chain:
                reply_to = msg_lookup.get(msg.reply_to) if msg.reply_to else None
                lines.extend(self._format_message_block(msg, reply_to, indent))
            lines.append("")  # Empty line between chains

        return "\n".join(lines)

    async def save_export(
        self, dialogs: List[Dialog], format: str = "both", prefix: str = "export"
    ) -> str:
        """Save dialogs to file(s)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_files = []

        if format in ["json", "both"]:
            json_file = EXPORT_DIR / f"{prefix}_{timestamp}.json"
            import json

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "metadata": {
                            "export_date": datetime.now().isoformat(),
                            "dialog_count": len(dialogs),
                        },
                        "dialogs": [dialog.to_dict() for dialog in dialogs],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            result_files.append(str(json_file))

        if format in ["text", "both"]:
            text_file = EXPORT_DIR / f"{prefix}_{timestamp}.txt"
            with open(text_file, "w", encoding="utf-8") as f:
                for dialog in dialogs:
                    f.write(self._format_human_readable(dialog))
                    f.write("\n" + "=" * 80 + "\n\n")
            result_files.append(str(text_file))

        return ", ".join(result_files)

    def _format_message(self, message: Message) -> str:
        """Format message for text export."""
        timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        sender = "🤖" if message.is_bot else "👤"
        sender_id = f" {message.sender_id}" if message.sender_id else ""

        # Format message content
        content_lines = message.content.split("\n")
        formatted_content = "\n    ".join(content_lines)

        # Add feedback marker if it's feedback
        if message.message_type == "feedback":
            return f"[{timestamp}] 💬 {sender}{sender_id} 📝:\n    {formatted_content}"
        else:
            return f"[{timestamp}] {sender}{sender_id} 📝:\n    {formatted_content}"

    def _format_dialog(self, dialog: Dialog) -> str:
        """Format dialog for text export."""
        # Format header
        lines = [
            f"Диалог {dialog.id}: {dialog.title}",
            f"Создан: {dialog.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "Метаданные:",
        ]

        # Add metadata
        if dialog.metadata:
            for key, value in dialog.metadata.items():
                lines.append(f"  {key}: {value}")

        lines.append("")  # Empty line after metadata

        # Add messages
        for message in dialog.messages:
            lines.append(self._format_message(message))
            lines.append("")  # Empty line between messages

        lines.append("=" * 80)  # Separator line
        lines.append("")  # Empty line at the end

        return "\n".join(lines)
