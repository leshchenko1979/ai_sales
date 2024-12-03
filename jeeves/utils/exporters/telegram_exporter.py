"""Telegram feedback exporter.

Format description:
- Each message starts with sender icon:
  🤖 - bot messages
  👤 - client messages
  📝 - feedback/analyst messages
- Followed by timestamp in [YYYY-MM-DD HH:MM:SS] format
- Message content is indented with 4 spaces
- Feedback messages have additional 2 space indent (6 total)
- Reply structure:
  ↳ В ответ на: <original message preview>...  # Indented +4 spaces
  📝 [timestamp]:                              # Same indent as reply marker
      <feedback message content>                # Indented +6 spaces
- General feedback (not tied to specific messages) is shown at the end

Example:
👤 [2024-12-02 21:30:27]:
    Hello!

🤖 [2024-12-02 21:30:36]:
    Hi there!
    ↳ В ответ на: Hi there!...
    📝 [2024-12-02 21:35:40]:
        This is feedback

# General feedback
📝 [2024-12-02 21:40:00]:
    This is general feedback about the dialog
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.accounts.client_manager import ClientManager
from core.telegram import get_forum_topics, get_topic_messages
from infrastructure.config import ANALYSIS_GROUP
from pyrogram import Client
from pyrogram.raw import types
from pyrogram.types import Message as TelegramMessage

from . import BaseExporter, Dialog
from . import Message as ExportMessage


@dataclass
class MessageInfo:
    """Message sender info and type."""

    sender_id: Optional[int]
    is_bot: bool
    type: str
    timestamp: datetime


class TelegramDialogExporter(BaseExporter):
    """Export dialogs from Telegram feedback group."""

    def __init__(self):
        """Initialize exporter."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.client_manager = ClientManager()

    async def get_client(self) -> Optional[Client]:
        """Get any available Telegram client."""
        account_client = await self.client_manager.get_any_client()
        return account_client.client if account_client else None

    # Main public methods
    async def export_all_dialogs(
        self, since_date: Optional[datetime] = None
    ) -> Optional[str]:
        """Export all dialogs from Telegram group."""
        try:
            client = await self.get_client()
            if not client:
                return None

            if not since_date:
                since_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

            topics = await get_forum_topics(client, ANALYSIS_GROUP, since_date)
            if not topics:
                return None

            dialogs = []
            for topic in topics:
                messages = await get_topic_messages(client, ANALYSIS_GROUP, topic["id"])
                if messages:
                    # Convert messages to our format
                    converted_messages = [
                        self._convert_message(msg, {}) for msg in messages
                    ]
                    filtered_messages = [msg for msg in converted_messages if msg]
                    if filtered_messages:
                        dialog = Dialog(
                            id=topic["id"],
                            title=topic["title"],
                            created_at=topic["date"],
                            messages=filtered_messages,
                        )
                        dialogs.append(dialog)

            if not dialogs:
                return None

            return await self.save_export(dialogs, prefix="tg_dialogs")

        except Exception as e:
            self.logger.error(f"Error exporting all dialogs: {e}", exc_info=True)
            return None

    async def export_dialog(self, topic_id: int) -> Optional[str]:
        """Export single dialog."""
        try:
            client = await self.get_client()
            if not client:
                return None

            # Get messages
            messages = await get_topic_messages(client, ANALYSIS_GROUP, topic_id)
            if not messages:
                self.logger.error("No messages found")
                return None

            # Get thread info from first message
            thread_info = {
                "title": f"Topic {topic_id}",
                "bot_id": None,
            }
            for msg in messages:
                if msg.text and "📊 Информация о диалоге:" in msg.text:
                    # Parse thread info
                    info = {}
                    lines = msg.text.split("\n")
                    for line in lines:
                        if "Продавец:" in line:
                            info["seller"] = line.split(":")[1].strip()
                        elif "Дата:" in line:
                            info["date"] = line.split(":")[1].strip()
                        elif "Итог:" in line:
                            info["result"] = line.split(":")[1].strip()

                    # Get bot ID from message
                    info["bot_id"] = msg.from_user.id if msg.from_user else None
                    info["title"] = f"Диалог с {info.get('seller', 'Unknown')}"
                    thread_info = info
                    break

            # Convert messages to our format
            converted_messages = [self._convert_message(msg, {}) for msg in messages]
            filtered_messages = [msg for msg in converted_messages if msg]
            if not filtered_messages:
                self.logger.error("No valid messages after conversion")
                return None

            # Sort converted messages by timestamp
            filtered_messages.sort(key=lambda x: x.timestamp)

            # Create dialog
            dialog = Dialog(
                id=topic_id,
                title=thread_info.get("title", f"Topic {topic_id}"),
                created_at=filtered_messages[0].timestamp,
                messages=filtered_messages,
                metadata={
                    "chat_id": ANALYSIS_GROUP,
                    "topic_id": topic_id,
                    **thread_info,
                },
            )

            # Export dialog
            return await self.save_export([dialog], prefix="tg_dialog")

        except Exception as e:
            self.logger.error(f"Error exporting dialog: {e}", exc_info=True)
            return None

    # Message processing
    def _convert_message(
        self, message: TelegramMessage, users: Dict
    ) -> Optional[ExportMessage]:
        """Convert Telegram message to export format."""
        try:
            # Get message content
            content = message.text or message.caption or ""

            # Skip empty messages but log them
            if not content:
                self.logger.debug(
                    f"Skipping empty message {message.id} of type {type(message)}"
                )
                return None

            # Get sender info and timestamp
            sender = message.from_user
            is_bot = sender.is_bot if sender else False
            timestamp = message.date  # Already a datetime object

            # Determine message type
            if message.forward_date:
                # This is a dialog message (forwarded)
                timestamp = message.forward_date  # Already a datetime object
                fwd_sender = message.forward_from
                is_bot = fwd_sender.is_bot if fwd_sender else False
                sender_id = fwd_sender.id if fwd_sender else None
                message_type = "bot" if is_bot else "client"
            else:
                # Not forwarded - this is feedback
                message_type = "feedback"
                is_bot = False
                sender_id = sender.id if sender else None

            # Create export message
            result = ExportMessage(
                id=message.id,
                timestamp=timestamp,
                content=content,
                sender_id=sender_id,
                is_bot=is_bot,
                message_type=message_type,
                reply_to=message.reply_to_message_id,
            )
            return result
        except Exception as e:
            self.logger.error(
                f"Error converting message {message.id if hasattr(message, 'id') else '<unknown>'}: {e}",
                exc_info=True,
            )
            return None

    def _get_message_info(self, message: TelegramMessage, users: Dict) -> MessageInfo:
        """Get message sender info and type."""
        sender_id = message.from_user.id if message.from_user else None
        timestamp = message.date  # Already a datetime object

        if message.forward_date:
            sender_id = message.forward_from.id if message.forward_from else None
            timestamp = message.forward_date  # Already a datetime object

        sender = users.get(sender_id) if sender_id else None
        is_bot = sender.is_bot if sender else False

        # Messages in feedback group are feedback unless forwarded
        message_type = (
            "feedback" if not message.forward_date else "bot" if is_bot else "client"
        )

        return MessageInfo(
            sender_id=sender_id, is_bot=is_bot, type=message_type, timestamp=timestamp
        )

    def _build_message_tree(self, messages: List[ExportMessage]) -> List[ExportMessage]:
        """Build a tree of messages with replies."""
        if not messages:
            return []

        # Sort messages by timestamp
        messages.sort(key=lambda x: x.timestamp)
        return messages

    # Formatting and validation
    def _format_human_readable(self, dialog: Dialog) -> str:
        """Format dialog for human reading with improved feedback handling."""
        lines = [
            f"Диалог {dialog.id}: {dialog.title}",
            f"Создан: {dialog.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        # Add metadata if exists
        if dialog.metadata:
            lines.append("Метаданные:")
            field_names = {
                "seller": "Продавец",
                "date": "Дата",
                "result": "Итог",
                "bot_id": "ID бота",
                "title": "Название",
            }
            for key, value in dialog.metadata.items():
                if key in ["chat_id", "topic_id", "Вы можете"]:  # Skip technical fields
                    continue
                display_key = field_names.get(key, key)
                lines.append(f"  {display_key}: {value}")

        lines.append("")  # Empty line before messages

        # Create message lookup for replies
        msg_lookup = {msg.id: msg for msg in dialog.messages}

        # Group feedback messages by their reply_to
        feedback_by_reply = {}
        general_feedback = []  # For feedback without reply_to
        for msg in dialog.messages:
            if msg.message_type == "feedback":
                if msg.reply_to and msg.reply_to in msg_lookup:
                    if msg.reply_to not in feedback_by_reply:
                        feedback_by_reply[msg.reply_to] = []
                    feedback_by_reply[msg.reply_to].append(msg)
                else:
                    general_feedback.append(msg)  # Collect general feedback

        # Process messages in order
        processed_ids = set()
        for msg in dialog.messages:
            if msg.id in processed_ids or msg.message_type == "feedback":
                continue

            # Format the main message
            reply_to = msg_lookup.get(msg.reply_to) if msg.reply_to else None
            lines.extend(self._format_message_block(msg, reply_to))

            # Add any feedback messages that reply to this message
            if msg.id in feedback_by_reply:
                for feedback_msg in sorted(
                    feedback_by_reply[msg.id], key=lambda x: x.timestamp
                ):
                    lines.extend(
                        self._format_message_block(feedback_msg, msg, indent=2)
                    )

            processed_ids.add(msg.id)
            lines.append("")  # Empty line between messages

        # Add general feedback at the end if exists
        if general_feedback:
            lines.append("# Общая обратная связь")
            for msg in sorted(general_feedback, key=lambda x: x.timestamp):
                lines.extend(self._format_message_block(msg))
                lines.append("")

        return "\n".join(lines)

    def _process_dialog(self, messages: List[ExportMessage]) -> List[ExportMessage]:
        """Process a single dialog."""
        if not messages:
            return []

        # Filter out service messages and mentions
        messages = [
            msg
            for msg in messages
            if not (
                msg.message_type == "feedback"
                and (
                    " Информация о диалоге:" in msg.content
                    or msg.content.strip().startswith("@")
                    or "Вы можете:" in msg.content
                )
            )
        ]

        # Sort messages by timestamp
        messages.sort(key=lambda x: x.timestamp)

        # Create a map of messages by ID
        msg_lookup = {msg.id: msg for msg in messages}

        # Group feedback messages by their reply_to
        feedback_by_reply = {}
        general_feedback = []  # Collect feedback without replies
        for msg in messages:
            if msg.message_type == "feedback":
                # Skip service messages containing "📊 Информация о диалоге:"
                if "📊 Информация о диалоге:" in msg.content:
                    continue

                if msg.reply_to and msg.reply_to in msg_lookup:
                    if msg.reply_to not in feedback_by_reply:
                        feedback_by_reply[msg.reply_to] = []
                    feedback_by_reply[msg.reply_to].append(msg)
                else:
                    general_feedback.append(msg)  # Store feedback without replies

        # Create final message list with feedback messages after their replies
        final_messages = []
        for msg in messages:
            if (
                msg.message_type != "feedback"
            ):  # Skip feedback messages as they'll be added after their replies
                final_messages.append(msg)
                # Add any feedback messages that reply to this message
                if msg.id in feedback_by_reply:
                    final_messages.extend(
                        sorted(feedback_by_reply[msg.id], key=lambda x: x.timestamp)
                    )

        # Add general feedback messages at the end
        final_messages.extend(sorted(general_feedback, key=lambda x: x.timestamp))

        return final_messages

    def _format_message_block(
        self,
        msg: ExportMessage,
        reply_msg: Optional[ExportMessage] = None,
        indent: int = 0,
    ) -> List[str]:
        """Format a message block with optional reply context."""
        lines = []

        # Add reply context if exists
        if reply_msg:
            reply_text = reply_msg.content.split("\n")[0][:50]  # First line, truncated
            lines.append(" " * (indent + 4) + f"↳ В ответ на: {reply_text}...")

            # Format timestamp and header for reply with same indent
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            header = f"📝 [{timestamp}]"  # Emoji at start
            lines.append(" " * (indent + 4) + header + ":")

            # Add message content with proper indent
            content_indent = indent + 6
            lines.extend(
                " " * content_indent + line for line in msg.content.split("\n")
            )
            return lines

        # Format message header for non-reply messages
        timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        if msg.message_type == "feedback":
            prefix = "📝"
        else:
            prefix = "🤖" if msg.is_bot else "👤"

        header = f"{prefix} [{timestamp}]"  # Emoji at start
        lines.append(" " * indent + header + ":")

        # Add message content
        content_indent = indent + 4
        if msg.message_type == "feedback":
            content_indent += 2  # Extra indent for feedback messages
        lines.extend(" " * content_indent + line for line in msg.content.split("\n"))
        return lines

    def _validate_export(self, dialog: Dialog) -> Dict[str, Any]:
        """Validate exported dialog and return validation results."""
        results = {
            "total_messages": len(dialog.messages),
            "dialog_messages": 0,
            "feedback_messages": 0,
            "bot_messages": 0,
            "client_messages": 0,
            "analyst_messages": 0,
            "messages_with_replies": 0,
            "forwarded_messages": 0,
            "errors": [],
        }

        # Count different types of messages
        for msg in dialog.messages:
            if msg.message_type == "dialog":
                results["dialog_messages"] += 1
                if msg.is_bot:
                    results["bot_messages"] += 1
                else:
                    results["client_messages"] += 1
            elif msg.message_type == "feedback":
                results["feedback_messages"] += 1
                results["analyst_messages"] += 1

            if msg.reply_to_id:
                results["messages_with_replies"] += 1
            if msg.original_timestamp:
                results["forwarded_messages"] += 1

        # Basic validation checks
        if results["dialog_messages"] == 0:
            results["errors"].append("No dialog messages found")
        if results["bot_messages"] == 0:
            results["errors"].append("No bot messages found")
        if results["client_messages"] == 0:
            results["errors"].append("No client messages found")
        if results["feedback_messages"] == 0:
            results["errors"].append("No feedback messages found")

        # Check message sequence
        prev_msg = None
        for msg in dialog.messages:
            if (
                msg.message_type == "dialog"
                and prev_msg
                and prev_msg.message_type == "dialog"
                and msg.is_bot == prev_msg.is_bot
            ):
                results["errors"].append(
                    f"Two consecutive messages from {'bot' if msg.is_bot else 'client'} "
                    f"at {msg.timestamp}"
                )
            prev_msg = msg

        return results

    # Helper methods
    def _parse_peer_user_id(self, peer) -> Optional[int]:
        """Extract user ID from peer."""
        return peer.user_id if isinstance(peer, types.PeerUser) else None

    async def _get_thread_info(self, client: Client, topic_id: int) -> Optional[Dict]:
        """Get thread info from the first message."""
        try:
            messages = await get_topic_messages(client, ANALYSIS_GROUP, topic_id)
            if not messages:
                return None

            def is_info_message(msg: types.Message) -> bool:
                """Check if message contains thread info."""
                return bool(msg.message and "📊 Информация о диалоге:" in msg.message)

            def parse_info_line(line: str) -> tuple[str, str]:
                """Parse info line into key-value pair."""
                key, *value = line.split(":")
                return key.strip(), ":".join(value).strip()

            # Find thread info message
            for message in filter(is_info_message, messages):
                info = {}
                lines = message.message.split("\n")
                info.update(
                    dict(
                        parse_info_line(line)
                        for line in lines
                        if ":" in line and line.strip() != "📊 Информация о диалоге:"
                    )
                )

                info["bot_id"] = self._parse_peer_user_id(message.from_id)
                info["title"] = f"Диалог с {info.get('seller', 'Unknown')}"
                return info

        except Exception as e:
            self.logger.error(f"Error getting thread info: {e}", exc_info=True)
            return None
