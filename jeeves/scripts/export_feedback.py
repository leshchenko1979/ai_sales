"""Script to export feedback from topics."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from core.telegram import get_forum_topics

# Local imports
from infrastructure.config import ANALYSIS_GROUP
from utils.exporters.telegram_exporter import TelegramDialogExporter


async def export_dialogs(since_date: datetime) -> None:
    """Export dialogs from feedback group."""
    try:
        # Initialize exporter
        exporter = TelegramDialogExporter()
        logging.info("Initialized exporter")

        logging.info(f"Looking for topics since {since_date}")

        # Get client and check group
        client = await exporter.get_client()
        if not client:
            logging.error("Failed to get client")
            return
        logging.info("Got Telegram client")

        # Get topics
        topics = await get_forum_topics(client, ANALYSIS_GROUP, since_date)
        if not topics:
            logging.error("No topics found")
            return
        logging.info(f"Found {len(topics)} topics")

        # Export each dialog
        exported_count = 0
        for topic in topics:
            logging.info(f"Exporting topic: {topic['title']} from {topic['date']}")
            result = await exporter.export_dialog(topic["id"])
            if result:
                logging.info(f"Dialog exported successfully to: {result}")
                exported_count += 1
            else:
                logging.error(f"Failed to export dialog {topic['id']}")

        logging.info(f"Exported {exported_count} dialogs successfully")

    except Exception as e:
        logging.error(f"Error exporting dialogs: {e}", exc_info=True)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main():
    """Main entry point."""
    setup_logging()
    since_date = datetime.now() - timedelta(days=7)
    asyncio.run(export_dialogs(since_date))


if __name__ == "__main__":
    main()
