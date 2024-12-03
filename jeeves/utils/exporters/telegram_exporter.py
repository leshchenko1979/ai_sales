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
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.accounts.client_manager import ClientManager
from core.accounts.queries.account import AccountQueries
from core.db.decorators import with_queries
from infrastructure.config import ANALYSIS_GROUP
from pyrogram import Client
from pyrogram.raw import functions, types

from . import BaseExporter, Dialog
from . import Message as ExportMessage


class TelegramDialogExporter(BaseExporter):
    """Export dialogs from Telegram feedback group."""

    def __init__(self):
        """Initialize exporter."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.client_manager = ClientManager()

    @with_queries(AccountQueries)
    async def _get_client(self, queries: AccountQueries) -> Optional[Client]:
        """Get Pyrogram client from available account."""
        try:
            # Get active accounts
            accounts = await queries.get_active_accounts()

            if not accounts:
                self.logger.error("No available accounts found")
                return None

            account = accounts[0]
            self.logger.info(f"Using account {account.phone} for export")

            account_client = await self.client_manager.get_client(
                account.phone, account.session_string
            )

            if not account_client or not account_client.client:
                self.logger.error(
                    f"Failed to initialize client for account {account.phone}"
                )
                return None

            return account_client.client

        except Exception as e:
            self.logger.error(f"Error getting client: {e}", exc_info=True)
            return None

    def _convert_message(self, message: types.Message, users: Dict) -> ExportMessage:
        """Convert Telegram message to export format."""
        try:
            # Get message content
            content = message.message if hasattr(message, "message") else ""

            # Skip empty messages but log them
            if not content:
                self.logger.debug(
                    f"Skipping empty message {message.id} of type {type(message)}"
                )
                return None

            # Get sender ID and timestamp
            from_id = message.from_id
            sender_id = from_id.user_id if isinstance(from_id, types.PeerUser) else None
            timestamp = datetime.fromtimestamp(message.date)

            # Get sender info
            sender = users.get(sender_id) if sender_id else None
            is_bot = sender and sender.bot

            # Determine message type
            if message.fwd_from:
                # This is a dialog message (forwarded)
                timestamp = datetime.fromtimestamp(message.fwd_from.date)
                fwd_from = message.fwd_from
                fwd_sender = fwd_from.from_id
                fwd_sender_id = (
                    fwd_sender.user_id
                    if isinstance(fwd_sender, types.PeerUser)
                    else None
                )
                fwd_user = users.get(fwd_sender_id) if fwd_sender_id else None
                is_bot = fwd_user and fwd_user.bot
                sender_id = fwd_sender_id
                message_type = "bot" if is_bot else "client"
            else:
                # Not forwarded - this is feedback
                message_type = "feedback"
                is_bot = False

            # Create export message
            result = ExportMessage(
                id=message.id,
                timestamp=timestamp,
                content=content,
                sender_id=sender_id,
                is_bot=is_bot,
                message_type=message_type,
                reply_to=message.reply_to.reply_to_msg_id if message.reply_to else None,
            )
            return result
        except Exception as e:
            self.logger.error(
                f"Error converting message {message.id}: {e}", exc_info=True
            )
            return None

    def _build_message_tree(self, messages: List[ExportMessage]) -> List[ExportMessage]:
        """Build a tree of messages with replies."""
        if not messages:
            return []

        # Sort messages by timestamp
        messages.sort(key=lambda x: x.timestamp)
        return messages

    def _process_dialog(self, messages: List[ExportMessage]) -> List[ExportMessage]:
        """Process a single dialog."""
        # Skip empty dialogs
        if not messages:
            return []

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

    async def _get_topic_messages(
        self, client: Client, topic_id: int, thread_info: Optional[Dict] = None
    ) -> List[ExportMessage]:
        """Get all messages from a topic."""
        try:
            # Get messages in batches
            all_messages = []
            offset_id = 0
            users = {}  # Store users by ID
            while True:
                # Get messages
                result = await client.invoke(
                    functions.messages.GetReplies(
                        peer=await client.resolve_peer(ANALYSIS_GROUP),
                        msg_id=topic_id,
                        offset_id=offset_id,
                        offset_date=0,
                        add_offset=0,
                        limit=100,
                        max_id=0,
                        min_id=0,
                        hash=0,
                    )
                )

                # Update users dict
                for user in result.users:
                    users[user.id] = user

                # Add messages
                raw_messages_count = len(result.messages)
                self.logger.info(f"Got {raw_messages_count} raw messages from Telegram")

                converted_count = 0
                for message in result.messages:
                    if isinstance(message, types.Message):
                        msg = self._convert_message(message, users)
                        if msg:  # Skip None messages (service messages)
                            all_messages.append(msg)
                            converted_count += 1

                self.logger.info(f"Converted {converted_count} messages successfully")

                # Check if we got all messages
                if len(result.messages) < 100:
                    break

                # Update offset
                if result.messages:
                    offset_id = result.messages[-1].id

            # Log message counts
            self.logger.info(f"Found {len(all_messages)} messages total")
            dialog_msgs = [
                m for m in all_messages if m.message_type in ("bot", "client")
            ]
            feedback_msgs = [m for m in all_messages if m.message_type == "feedback"]
            self.logger.info(f"Dialog messages: {len(dialog_msgs)}")
            self.logger.info(f"Feedback messages: {len(feedback_msgs)}")

            # Process all messages as a single dialog
            final_messages = self._process_dialog(all_messages)
            self.logger.info(
                f"Final message count after processing: {len(final_messages)}"
            )

            if not final_messages:
                self.logger.error("No messages after processing")
                return []

            return final_messages

        except Exception as e:
            self.logger.error(f"Error getting topic messages: {e}", exc_info=True)
            return []

    async def _get_forum_topics(
        self, client: Client, chat_id: int, since_date: datetime
    ) -> List[Dict]:
        """Get forum topics using raw API."""
        try:
            peer = await client.resolve_peer(chat_id)
            result = await client.invoke(
                functions.channels.GetForumTopics(
                    channel=peer,
                    offset_date=0,
                    offset_id=0,
                    offset_topic=0,
                    limit=100,
                )
            )

            topics = []
            for topic in result.topics:
                if not isinstance(topic, types.ForumTopic):
                    continue

                topic_date = datetime.fromtimestamp(topic.date)
                if topic_date < since_date:
                    continue

                topics.append(
                    {
                        "id": topic.id,
                        "title": topic.title,
                        "date": topic_date,
                    }
                )

            self.logger.info(f"Found {len(topics)} topics since {since_date}")
            return topics

        except Exception as e:
            self.logger.error(f"Error getting forum topics: {e}")
            return []

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
            ):
                if msg.is_bot == prev_msg.is_bot:
                    results["errors"].append(
                        f"Two consecutive messages from {'bot' if msg.is_bot else 'client'} "
                        f"at {msg.timestamp}"
                    )
            prev_msg = msg

        return results

    async def export_dialog(self, topic_id: int) -> Optional[str]:
        """Export single dialog."""
        try:
            # Get client
            client = await self._get_client()
            if not client:
                return None

            # Get thread info
            thread_info = await self._get_thread_info(client, topic_id)
            if not thread_info:
                self.logger.error("Failed to get thread info")
                return None

            # Store thread info for message conversion
            self.thread_info = thread_info

            # Get messages
            messages = await self._get_topic_messages(client, topic_id, thread_info)
            if not messages:
                self.logger.error("No messages found")
                return None

            # Sort messages by timestamp
            messages.sort(key=lambda x: x.timestamp)

            # Create dialog
            dialog = Dialog(
                id=topic_id,
                title=thread_info.get("title", f"Topic {topic_id}"),
                created_at=messages[0].timestamp,
                messages=messages,
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

    async def _get_thread_info(self, client: Client, topic_id: int) -> Optional[Dict]:
        """Get thread info from the first message."""
        try:
            # Get messages in batches
            messages = []
            offset_id = 0
            while True:
                # Get messages
                result = await client.invoke(
                    functions.messages.GetReplies(
                        peer=await client.resolve_peer(ANALYSIS_GROUP),
                        msg_id=topic_id,
                        offset_id=offset_id,
                        offset_date=0,
                        add_offset=0,
                        limit=100,
                        max_id=0,
                        min_id=0,
                        hash=0,
                    )
                )

                # Add messages
                for message in result.messages:
                    if isinstance(message, types.Message):
                        messages.append(message)

                # Check if we got all messages
                if len(result.messages) < 100:
                    break

                # Update offset
                if result.messages:
                    offset_id = result.messages[-1].id

            # Find thread info message
            thread_info = None
            for message in messages:
                if message.message and "📊 Информация о диалоге:" in message.message:
                    # Parse thread info
                    info = {}
                    lines = message.message.split("\n")
                    for line in lines:
                        if "Продаве:" in line:
                            info["seller"] = line.split(":")[1].strip()
                        elif "Дата:" in line:
                            info["date"] = line.split(":")[1].strip()
                        elif "Итог:" in line:
                            info["result"] = line.split(":")[1].strip()

                    # Get bot ID from message
                    info["bot_id"] = (
                        message.from_id.user_id
                        if isinstance(message.from_id, types.PeerUser)
                        else None
                    )
                    info["title"] = f"Диалог с {info.get('seller', 'Unknown')}"
                    thread_info = info
                    break

            # If no thread info found, create basic info
            if not thread_info and messages:
                # Find bot ID by looking at user objects
                bot_id = None
                for user in result.users:
                    if user.bot:
                        bot_id = user.id
                        break

                thread_info = {
                    "bot_id": bot_id,
                    "title": f"Topic {topic_id}",
                    "seller": "Unknown",
                    "date": datetime.fromtimestamp(messages[0].date).strftime(
                        "%Y-%m-%d"
                    ),
                }

            return thread_info

        except Exception as e:
            self.logger.error(f"Error getting thread info: {e}", exc_info=True)
            return None

    async def export_all_dialogs(
        self, since_date: Optional[datetime] = None
    ) -> Optional[str]:
        """Export all dialogs from Telegram group."""
        try:
            client = await self._get_client()
            if not client:
                return None

            if not since_date:
                since_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

            topics = await self._get_forum_topics(client, ANALYSIS_GROUP, since_date)
            if not topics:
                return None

            dialogs = []
            for topic in topics:
                dialog = await self._get_topic_messages(
                    client, ANALYSIS_GROUP, topic["id"]
                )
                if dialog:
                    dialogs.append(dialog)

            if not dialogs:
                return None

            return await self.save_export(dialogs, prefix="tg_dialogs")

        except Exception as e:
            self.logger.error(f"Error exporting all dialogs: {e}", exc_info=True)
            return None

    def _is_bot_message(self, message: types.Message, users: Dict) -> bool:
        """Check if message is from bot."""
        # Get sender ID from from_id field
        from_id = message.from_id
        sender_id = from_id.user_id if isinstance(from_id, types.PeerUser) else None

        # Check if message is forwarded
        if message.fwd_from:
            # If forwarded, use original sender ID
            fwd_from = message.fwd_from.from_id
            sender_id = (
                fwd_from.user_id if isinstance(fwd_from, types.PeerUser) else None
            )

        # Find user object for sender
        sender = users.get(sender_id) if sender_id else None

        # Message is from bot if:
        # 1. Sender is a bot
        # 2. Or it's a thread info message
        return (sender and sender.bot) or (
            message.message and "📊 Информация о диалоге:" in message.message
        )
