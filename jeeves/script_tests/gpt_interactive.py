"""Interactive GPT test script."""

import asyncio
import logging

# Add root directory to PYTHONPATH
# DO NOT REMOVE
import sys
from pathlib import Path

import aioconsole  # Добавляем импорт для асинхронного ввода

root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from core.messaging.conductor import DialogConductor  # noqa: E402


# Цвета для вывода
class Colors:
    GREY = "\033[90m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RESET = "\033[0m"


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ColoredFormatter(logging.Formatter):
    """Форматтер для цветных логов."""

    def format(self, record):
        # Делаем все логи серыми
        return f"{Colors.GREY}{record.getMessage()}{Colors.RESET}"


# Добавляем обработчик для вывода в консоль
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logger.addHandler(handler)


async def main():
    """Run interactive test."""

    # Create conductor with print function
    async def print_message(text: str) -> None:
        print(f"{Colors.BLUE}Bot: {text}{Colors.RESET}")

    conductor = DialogConductor(send_func=print_message)

    # Start conversation
    await conductor.start_dialog()

    while True:
        try:
            # Get user input asynchronously
            user_message = await aioconsole.ainput(f"{Colors.GREEN}You: {Colors.RESET}")

            if not user_message:
                logger.info("Empty input, exiting...")
                break

            # Process message in background
            asyncio.create_task(conductor.handle_message(user_message))

        except EOFError:
            logger.info("EOF received, exiting gracefully...")
            break
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, exiting gracefully...")
            break
        except Exception as e:
            logger.error("Error in dialog: %s", e, exc_info=True)
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
