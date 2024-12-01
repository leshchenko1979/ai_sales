"""Script to export feedback from topics."""

# Standard library
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

# Setup path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

# Local imports
from core.accounts import AccountManager
from core.accounts.client_manager import ClientManager
from infrastructure.config import ANALYSIS_GROUP

# Third-party imports
from pyrogram import Client
from pyrogram.raw import functions, types

# Constants
EXPORT_DIR = ROOT_DIR / "exports"


class MessageFormatter:
    """Message formatting utilities."""

    @staticmethod
    def format_user_data(from_user: Union[types.PeerUser, None]) -> Dict:
        """Format user data from peer."""
        return {
            "id": from_user.user_id if isinstance(from_user, types.PeerUser) else None,
            "name": None,  # Need additional API call to get user info
            "is_bot": None,  # Need additional API call to get user info
        }

    @staticmethod
    def format_message_data(message: types.Message, message_type: str) -> Dict:
        """Format message data."""
        from_user = message.fwd_from.from_id if message.fwd_from else message.from_id

        return {
            "id": message.id,
            "timestamp": datetime.fromtimestamp(message.date).isoformat(),
            "from_user": MessageFormatter.format_user_data(from_user),
            "text": message.message,
            "reply_to_message_id": (
                message.reply_to.reply_to_msg_id if message.reply_to else None
            ),
            "message_type": message_type,
            "original_timestamp": (
                datetime.fromtimestamp(message.fwd_from.date).isoformat()
                if message.fwd_from and message.fwd_from.date
                else None
            ),
        }


class TopicExporter:
    """Topic export functionality."""

    def __init__(self):
        """Initialize exporter."""
        self.logger = logging.getLogger(__name__)
        self.formatter = MessageFormatter()

    async def get_topic_messages(
        self, client: Client, chat_id: int, topic_id: int
    ) -> List[Dict]:
        """Get all messages from topic."""
        messages = []
        thread_info = None

        # Get messages using raw API
        peer = await client.resolve_peer(chat_id)
        result = await client.invoke(
            functions.messages.GetReplies(
                peer=peer,
                msg_id=topic_id,
                offset_id=0,
                offset_date=0,
                add_offset=0,
                limit=100,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )

        for message in result.messages:
            if not isinstance(message, types.Message):
                continue

            # Handle thread info message
            if (
                not thread_info
                and message.message
                and "📊 Информация о диалоге:" in message.message
            ):
                thread_info = message
                continue

            # Determine message type
            message_type = "dialog" if message.fwd_from else "feedback"
            messages.append(self.formatter.format_message_data(message, message_type))

        # Add thread info if exists
        if thread_info:
            messages.insert(
                0,
                self.formatter.format_message_data(thread_info, "thread_info"),
            )

        return messages

    async def get_forum_topics(
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

            self.logger.debug(f"Found {len(result.topics)} total topics")

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
                        "top_message": topic.top_message,
                    }
                )

            self.logger.info(f"Found {len(topics)} topics since {since_date}")
            return topics

        except Exception as e:
            self.logger.error(f"Error getting forum topics: {e}")
            return []


class FeedbackExporter:
    """Feedback export functionality."""

    def __init__(self):
        """Initialize exporter."""
        self.logger = logging.getLogger(__name__)
        self.topic_exporter = TopicExporter()
        EXPORT_DIR.mkdir(exist_ok=True)

    async def get_client(self) -> Optional[Client]:
        """Get Pyrogram client from available account."""
        account_manager = AccountManager()
        accounts = await account_manager.get_available_accounts()

        if not accounts:
            self.logger.error("No available accounts found")
            return None

        account = accounts[0]
        self.logger.info(f"Using account {account.phone} for export")

        client_manager = ClientManager()
        account_client = await client_manager.get_client(
            account.phone, account.session_string
        )

        if not account_client or not account_client.client:
            self.logger.error(
                f"Failed to initialize client for account {account.phone}"
            )
            return None

        return account_client.client

    async def export_group_dialogs(
        self, group_id: int, since_date: datetime
    ) -> Optional[str]:
        """Export dialogs from group with feedback."""
        try:
            client = await self.get_client()
            if not client:
                return None

            # Get group info
            group = await client.get_chat(group_id)
            if not group:
                self.logger.error(f"Could not find group {group_id}")
                return None

            # Prepare export data
            export_data = self.prepare_export_metadata(group, since_date)

            # Get and process topics
            topics = await self.topic_exporter.get_forum_topics(
                client, group_id, since_date
            )
            await self.process_topics(client, group_id, topics, export_data)

            # Save export
            return await self.save_export(export_data)

        except Exception as e:
            self.logger.error(f"Export error: {e}", exc_info=True)
            return None

    def prepare_export_metadata(self, group, since_date: datetime) -> Dict:
        """Prepare export metadata."""
        return {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "group_id": group.id,
                "group_title": group.title,
                "since_date": since_date.isoformat(),
            },
            "dialogs": [],
        }

    async def process_topics(
        self, client: Client, group_id: int, topics: List[Dict], export_data: Dict
    ) -> None:
        """Process topics and add to export data."""
        for topic in topics:
            messages = await self.topic_exporter.get_topic_messages(
                client, group_id, topic["id"]
            )
            if not messages:
                continue

            thread_info = next(
                (msg for msg in messages if msg["message_type"] == "thread_info"),
                None,
            )

            export_data["dialogs"].append(
                {
                    "topic_id": topic["id"],
                    "title": (
                        thread_info["text"].split("\n")[0]
                        if thread_info
                        else topic["title"]
                    ),
                    "created_at": topic["date"].isoformat(),
                    "messages": messages,
                }
            )

    async def save_export(self, export_data: Dict) -> str:
        """Save export data to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = EXPORT_DIR / f"feedback_export_{timestamp}.json"

        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Export saved to {export_file}")
        return str(export_file)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main():
    """Main entry point."""
    setup_logging()
    exporter = FeedbackExporter()
    since_date = datetime.now() - timedelta(days=7)
    asyncio.run(exporter.export_group_dialogs(ANALYSIS_GROUP, since_date))
