"""Telegram forum topic management."""

import logging
from datetime import datetime
from typing import Dict, List

from pyrogram import Client
from pyrogram.raw import functions, types
from pyrogram.types import Message

logger = logging.getLogger(__name__)


async def create_forum_topic(client: Client, group_id: int, title: str) -> int:
    """Create forum topic and return topic_id and channel_peer."""
    channel_peer = await client.resolve_peer(group_id)

    topic = await client.invoke(
        functions.channels.CreateForumTopic(
            channel=channel_peer,
            title=title,
            icon_color=0x6FB9F0,  # Light blue color
            random_id=client.rnd_id(),
        )
    )

    topic_id = topic.updates[0].id
    if not topic_id:
        logger.error("Failed to create forum topic")
        return 0

    logger.info(f"Created forum topic: {topic_id}")
    return topic_id


async def get_forum_topics(
    client: Client, chat_id: int, since_date: datetime
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

        logger.info(f"Found {len(topics)} topics since {since_date}")
        return topics

    except Exception as e:
        logger.error(f"Error getting forum topics: {e}")
        return []


async def get_topic_messages(
    client: Client, chat_id: int, topic_id: int
) -> List[Message]:
    """Get all messages from a topic."""
    try:
        messages = []
        users = {}
        chats = {}
        offset_id = 0

        # Get channel peer
        peer = await client.resolve_peer(chat_id)

        # Get initial messages
        result = await client.invoke(
            functions.messages.GetReplies(
                peer=peer,
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

        # Store initial chats and users
        for user in result.users:
            users[user.id] = user
        for chat in result.chats:
            chats[chat.id] = chat

        while True:
            # Check if we got any messages
            if not result.messages:
                break

            # Convert raw messages to Pyrogram Message objects
            for raw_msg in result.messages:
                if isinstance(raw_msg, types.Message):
                    try:
                        msg = await Message._parse(client, raw_msg, users, chats)
                        if msg:
                            messages.append(msg)
                    except Exception as e:
                        logger.error(f"Error parsing message {raw_msg.id}: {e}")
                        continue

            # Break if we got less than the limit
            if len(result.messages) < 100:
                break

            # Update offset for next batch
            offset_id = result.messages[-1].id

            # Get next batch of messages
            result = await client.invoke(
                functions.messages.GetReplies(
                    peer=peer,
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

            # Update users and chats
            for user in result.users:
                users[user.id] = user
            for chat in result.chats:
                chats[chat.id] = chat

        logger.info(f"Got {len(messages)} messages from topic {topic_id}")
        return messages

    except Exception as e:
        logger.error(f"Error getting topic messages: {e}", exc_info=True)
        return []


async def forward_messages_to_topic(
    client: Client, messages: List[Message], group_id: int, topic_id: int
) -> None:
    """Forward all dialog messages to the topic."""
    try:
        await client.invoke(
            functions.messages.ForwardMessages(
                from_peer=await client.resolve_peer(messages[0].chat.id),
                to_peer=await client.resolve_peer(group_id),
                top_msg_id=topic_id,
                id=[msg.id for msg in messages],
                random_id=[client.rnd_id() for _ in messages],
            )
        )
    except Exception as e:
        logger.error(f"Error forwarding messages: {e}")
