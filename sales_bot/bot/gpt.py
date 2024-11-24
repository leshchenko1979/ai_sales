import logging
import json
import aiohttp
from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    APP_NAME,
    APP_URL
)

logger = logging.getLogger(__name__)

API_BASE = "https://openrouter.ai/api/v1"

# Базовые промпты
INITIAL_PROMPT = """Ты - менеджер по продажам инвестиционных продуктов.
Твоя задача - квалифицировать потенциального инвестора и узнать:
1. Размер возможных инвестиций (интересует от 1 млн рублей)
2. Сроки планируемых инвестиций (в течение 3 месяцев)

Веди диалог вежливо и профессионально. Не дави на собеседника.
Если клиент соответствует критериям - предложи созвониться с менеджером.
Если не соответствует - вежливо заверши разговор."""

RESPONSE_PROMPT = """История диалога:
{dialog_history}

Последнее сообщение клиента:
{last_message}

Ответь на сообщение клиента, следуя этим правилам:
1. Оставайся в роли менеджера по продажам
2. Учитывай контекст всего диалога
3. Стремись узнать размер и сроки инвестиций
4. Предложи звонок только если клиент соответствует критериям"""

async def make_request(messages: list) -> str:
    """Выполнение запроса к OpenRouter API"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": APP_URL,
        "X-Title": APP_NAME,
        "Content-Type": "application/json"
    }

    data = {
        "model": OPENROUTER_MODEL,
        "messages": messages
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/chat/completions",
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenRouter API error: {error_text}")
                    raise Exception(f"API returned status {response.status}")

                result = await response.json()
                return result['choices'][0]['message']['content']

    except Exception as e:
        logger.error(f"Error making request to OpenRouter: {e}")
        raise

async def generate_initial_message() -> str:
    """Генерация первого сообщения"""
    try:
        messages = [
            {"role": "system", "content": INITIAL_PROMPT},
            {"role": "user", "content": "Сгенерируй первое сообщение для начала диалога"}
        ]

        return await make_request(messages)
    except Exception as e:
        logger.error(f"Error generating initial message: {e}")
        return "Здравствуйте! Я представляю инвестиционную компанию. Могу я задать вам несколько вопросов?"

async def generate_response(dialog_history: list, last_message: str) -> str:
    """Генерация ответа на сообщение пользователя"""
    try:
        # Форматируем историю диалога
        history_text = "\n".join([
            f"{'Бот' if msg['direction'] == 'out' else 'Клиент'}: {msg['content']}"
            for msg in dialog_history
        ])

        # Формируем промпт с контекстом
        prompt = RESPONSE_PROMPT.format(
            dialog_history=history_text,
            last_message=last_message
        )

        messages = [
            {"role": "system", "content": INITIAL_PROMPT},
            {"role": "user", "content": prompt}
        ]

        return await make_request(messages)
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return "Извините, произошла техническая ошибка. Давайте продолжим позже."

async def check_qualification(dialog_history: list) -> tuple[bool, str]:
    """Проверка квалификации клиента"""
    try:
        history_text = "\n".join([
            f"{'Бот' if msg['direction'] == 'out' else 'Клиент'}: {msg['content']}"
            for msg in dialog_history
        ])

        prompt = f"""На основе этого диалога определи:
1. Соответствует ли клиент критериям (от 1 млн руб, в течение 3 месяцев)?
2. Если да - почему? Если нет - почему?

Диалог:
{history_text}

Ответь в формате:
QUALIFIED: да/нет
REASON: причина"""

        messages = [
            {
                "role": "system",
                "content": "Ты - аналитик, оценивающий диалоги с потенциальными инвесторами."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        result = await make_request(messages)
        qualified = "QUALIFIED: да" in result.lower()
        reason = result.split("REASON:")[1].strip() if "REASON:" in result else "Причина не указана"

        return qualified, reason
    except Exception as e:
        logger.error(f"Error checking qualification: {e}")
        return False, "Ошибка при проверке квалификации"
