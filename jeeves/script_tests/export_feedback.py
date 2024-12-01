"""Script to export feedback from topics."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from core.accounts import AccountManager
from core.accounts.client_manager import ClientManager
from infrastructure.config import ANALYSIS_GROUP
from pyrogram import Client
from pyrogram.raw import functions, types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


EXPORT_DIR = ROOT_DIR / "exports"


def ensure_export_dir():
    """Create export directory if it doesn't exist."""
    EXPORT_DIR.mkdir(exist_ok=True)


async def get_topic_messages(client: Client, chat_id: int, topic_id: int) -> List[Dict]:
    """Get all messages from topic."""
    messages = []
    thread_info = None

    # Get messages from topic using raw API
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

        # First message in topic contains dialog info
        if (
            not thread_info
            and message.message
            and "📊 Информация о диалоге:" in message.message
        ):
            thread_info = message
            continue

        # Determine message type and author
        if message.fwd_from:
            # This is a forwarded message from original dialog
            message_type = "dialog"
            # For forwarded messages, get original author
            from_user = message.fwd_from.from_id
        else:
            # This is a feedback message
            message_type = "feedback"
            from_user = message.from_id

        # Format message data
        message_data = {
            "id": message.id,
            "timestamp": datetime.fromtimestamp(message.date).isoformat(),
            "from_user": {
                "id": (
                    from_user.user_id if isinstance(from_user, types.PeerUser) else None
                ),
                "name": None,  # Need additional API call to get user info
                "is_bot": None,  # Need additional API call to get user info
            },
            "text": message.message,
            "reply_to_message_id": (
                message.reply_to.reply_to_msg_id if message.reply_to else None
            ),
            "message_type": message_type,
            # Add original timestamp for forwarded messages
            "original_timestamp": (
                datetime.fromtimestamp(message.fwd_from.date).isoformat()
                if message.fwd_from and message.fwd_from.date
                else None
            ),
        }

        messages.append(message_data)

    # Add metadata from first message if exists
    if thread_info:
        messages.insert(
            0,
            {
                "id": thread_info.id,
                "timestamp": datetime.fromtimestamp(thread_info.date).isoformat(),
                "from_user": {
                    "id": (
                        thread_info.from_id.user_id
                        if isinstance(thread_info.from_id, types.PeerUser)
                        else None
                    ),
                    "name": None,
                    "is_bot": None,
                },
                "text": thread_info.message,
                "message_type": "thread_info",
            },
        )

    return messages


async def get_forum_topics(
    client: Client, chat_id: int, since_date: datetime
) -> List[Dict]:
    """Get forum topics using raw API."""
    topics = []

    try:
        # Get channel/supergroup entity
        peer = await client.resolve_peer(chat_id)

        # Use raw API to get topics without date filtering
        result = await client.invoke(
            functions.channels.GetForumTopics(
                channel=peer,
                offset_date=0,  # Changed to 0 to get all topics
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )

        logger.debug(f"Found {len(result.topics)} total topics")

        for topic in result.topics:
            # Skip non-message topics
            if not isinstance(topic, types.ForumTopic):
                continue

            topic_date = datetime.fromtimestamp(topic.date)
            # Filter topics by date in Python
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

        logger.info(f"Found {len(topics)} topics since {since_date}")
        return topics

    except Exception as e:
        logger.error(f"Error getting forum topics: {e}")
        return []


async def export_group_dialogs(group_id: int, since_date: datetime) -> Optional[str]:
    """Export dialogs from group with feedback."""
    try:
        ensure_export_dir()

        # Get active account - modified to get first available account
        account_manager = AccountManager()
        accounts = await account_manager.get_available_accounts()

        if not accounts:
            logger.error("No available accounts found")
            return None

        # Use the first available account
        account = accounts[0]
        logger.info(f"Using account {account.phone} for export")

        # Get client through ClientManager
        client_manager = ClientManager()
        account_client = await client_manager.get_client(
            account.phone, account.session_string
        )

        if not account_client:
            logger.error(f"Failed to initialize client for account {account.phone}")
            return None

        try:
            # Use the underlying Pyrogram client
            client = account_client.client
            if not client:
                logger.error("Failed to get Pyrogram client")
                return None

            # Get group info
            group = await client.get_chat(group_id)
            if not group:
                logger.error(f"Could not find group {group_id}")
                return None

            # Structure for JSON export
            export_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "group_id": group_id,
                    "group_title": group.title,
                    "since_date": since_date.isoformat(),
                    "exported_by": account.phone,
                },
                "dialogs": [],
            }

            # Get topics with feedback info using raw API
            topics = await get_forum_topics(client, group_id, since_date)

            for topic in topics:
                messages = await get_topic_messages(client, group_id, topic["id"])
                if not messages:
                    continue

                # Get thread info from first message
                thread_info = next(
                    (msg for msg in messages if msg["message_type"] == "thread_info"),
                    None,
                )

                # Add dialog data
                dialog_data = {
                    "topic_id": topic["id"],
                    "title": (
                        thread_info["text"].split("\n")[0]
                        if thread_info
                        else topic["title"]
                    ),
                    "date": topic["date"].isoformat(),
                    "messages": messages,
                }
                export_data["dialogs"].append(dialog_data)
                logger.info(f"Processed topic {topic['id']}")

            if not export_data["dialogs"]:
                logger.info("No dialogs found in the specified period")
                return None

            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = EXPORT_DIR / f"dialogs_feedback_{timestamp}.json"

            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(
                f"Successfully exported {len(export_data['dialogs'])} dialogs to {file_path}"
            )
            return str(file_path)

        finally:
            # Always release the client when done
            await client_manager.release_client(account.phone)

    except Exception as e:
        logger.error(f"Error exporting group dialogs: {e}", exc_info=True)
        return None


async def main():
    """Main function."""
    # Export dialogs from the last 7 days
    since_date = datetime.now() - timedelta(days=7)

    try:
        # Get group info first
        account_manager = AccountManager()
        accounts = await account_manager.get_available_accounts()

        if not accounts:
            logger.error("No available accounts found")
            return

        account = accounts[0]
        client_manager = ClientManager()
        account_client = await client_manager.get_client(
            account.phone, account.session_string
        )

        if not account_client:
            logger.error("Failed to initialize client")
            return

        try:
            client = account_client.client
            # Resolve group ID from username
            chat = await client.get_chat(ANALYSIS_GROUP)
            group_id = chat.id

            logger.info(
                f"Exporting feedback from group: {ANALYSIS_GROUP} (ID: {group_id})"
            )
            result = await export_group_dialogs(group_id, since_date)

            if result:
                print(f"Export completed successfully. File saved at: {result}")
            else:
                print("Export failed")

        finally:
            await client_manager.release_client(account.phone)

    except Exception as e:
        logger.error(f"Failed to resolve group ID: {e}")
        print("Export failed")


if __name__ == "__main__":
    asyncio.run(main())
