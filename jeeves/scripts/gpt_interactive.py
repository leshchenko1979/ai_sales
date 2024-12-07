"""Interactive GPT test script."""

# Standard library
import asyncio
import logging
import sys

# Third-party imports
import aioconsole

# Local imports
from core.messaging import DialogConductorFactory, DialogStrategyType


class TerminalColors:
    """Terminal color codes."""

    GREY = "\033[90m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """Formatter for colored logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with grey color."""
        return f"{TerminalColors.GREY}{record.getMessage()}{TerminalColors.RESET}"


def setup_logging() -> logging.Logger:
    """Configure logging with colored output."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter())
    logger.addHandler(handler)

    return logger


class InteractiveDialog:
    """Interactive dialog handler."""

    def __init__(
        self, strategy_type: DialogStrategyType = DialogStrategyType.COLD_MEETING
    ):
        """Initialize dialog handler."""
        self.logger = setup_logging()
        self.conductor = None
        self.strategy_type = strategy_type

    async def print_message(self, text: str) -> None:
        """Print bot message with blue color."""
        print(f"{TerminalColors.BLUE}Bot: {text}{TerminalColors.RESET}")

    async def handle_user_input(self) -> bool:
        """Handle single user input iteration.

        Returns:
            bool: True to continue dialog, False to exit
        """
        try:
            user_message = await aioconsole.ainput(
                f"{TerminalColors.GREEN}You: {TerminalColors.RESET}"
            )

            if not user_message:
                self.logger.info("Empty input, exiting...")
                return False

            # Process message in background
            is_complete, error = await self.conductor.handle_message(user_message)
            if error:
                self.logger.error("Error processing message: %s", error)
            return not is_complete

        except (EOFError, KeyboardInterrupt):
            self.logger.info("Received exit signal, stopping dialog...")
            return False
        except Exception as e:
            self.logger.error("Error in dialog: %s", e, exc_info=True)
            return False

    async def run(self):
        """Run interactive dialog."""
        try:
            # Initialize conductor using factory
            self.conductor = DialogConductorFactory.create_conductor(
                strategy_type=self.strategy_type,
                send_func=self.print_message,
            )
            await self.conductor.start_dialog()

            # Main dialog loop
            while await self.handle_user_input():
                pass

        except Exception as e:
            self.logger.error("Fatal error: %s", e, exc_info=True)
            sys.exit(1)


def main():
    """Main entry point."""
    dialog = InteractiveDialog()
    asyncio.run(dialog.run())


if __name__ == "__main__":
    main()
