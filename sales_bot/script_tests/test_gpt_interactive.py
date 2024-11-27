"""Interactive GPT test script."""

import asyncio
import logging

# Add root directory to PYTHONPATH
# DO NOT REMOVE
import sys
from pathlib import Path
from typing import Dict, List

root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))


from core.ai.gpt import GPTClient  # noqa: E402


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
    client = GPTClient()
    dialog_history: List[Dict[str, str]] = []

    # Start conversation
    initial_message = await client.generate_initial_message()
    print(f"{Colors.BLUE}Bot: {initial_message}{Colors.RESET}")
    dialog_history.append({"direction": "out", "text": initial_message})

    while True:
        try:
            # Get user input
            user_message = input(f"{Colors.GREEN}You: {Colors.RESET}")

            if not user_message:
                logger.info("Empty input, exiting...")
                break

            dialog_history.append({"direction": "in", "text": user_message})

            # Get advisor tip
            status, warmth, reason, advice, stage = await client.get_advisor_tip(
                dialog_history
            )
            logger.info("\nСтатус диалога:")
            logger.info(f"├─ Статус: {status}")
            logger.info(f"├─ Этап: {stage}")
            logger.info(f"├─ Уровень теплоты: {warmth}")
            logger.info(f"├─ Причина: {reason}")
            logger.info(f"└─ Совет: {advice}\n")

            # Generate response
            bot_response = await client.get_manager_response(
                dialog_history, status, warmth, reason, advice, stage
            )
            print(f"{Colors.BLUE}Bot: {bot_response}{Colors.RESET}")
            dialog_history.append({"direction": "out", "text": bot_response})

            # Check if we should end the conversation
            if status != "IN_PROGRESS":
                logger.info("\nЗавершаем диалог.")
                if status == "SCHEDULE_MEETING":
                    call_msg = (
                        "Отлично! Для назначения звонка, пожалуйста, "
                        "отправьте слово 'звонок' на адрес call@opendev.ru"
                    )
                    print(f"{Colors.BLUE}Bot: {call_msg}{Colors.RESET}")
                break

        except EOFError:
            logger.info("EOF received, exiting gracefully...")
            break
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, exiting gracefully...")
            break
        except Exception:
            logger.error("Error during test: ", exc_info=True)
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting gracefully...")
    except Exception:
        logger.error("Error during test: ", exc_info=True)
