"""Script to export last feedback dialog from the group."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from infrastructure.config import ANALYSIS_GROUP
from utils.exporters.telegram_exporter import TelegramDialogExporter


async def export_last_dialog() -> None:
    """Export last dialog from feedback group."""
    try:
        # Initialize exporter
        exporter = TelegramDialogExporter()
        logging.info("Initialized exporter")

        # Get topics since yesterday to ensure we get the latest
        since_date = datetime.now() - timedelta(days=1)
        logging.info(f"Looking for topics since {since_date}")

        # Get client and check group
        client = await exporter._get_client()
        if not client:
            logging.error("Failed to initialize Telegram client")
            return
        logging.info("Got Telegram client")

        # Get recent topics
        topics = await exporter._get_forum_topics(client, ANALYSIS_GROUP, since_date)
        if not topics:
            logging.error("No topics found in the last 24 hours")
            return
        logging.info(f"Found {len(topics)} topics")

        # Sort topics by date and get the latest
        latest_topic = max(topics, key=lambda x: x["date"])
        logging.info(
            f"Found latest topic: {latest_topic['title']} from {latest_topic['date']}"
        )

        # Export the dialog
        result = await exporter.export_dialog(latest_topic["id"])
        if result:
            logging.info(f"Dialog exported successfully to: {result}")
        else:
            logging.error("Failed to export dialog")

    except Exception as e:
        logging.error(f"Error exporting last dialog: {e}", exc_info=True)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main():
    """Main entry point."""
    setup_logging()
    asyncio.run(export_last_dialog())


if __name__ == "__main__":
    main()
