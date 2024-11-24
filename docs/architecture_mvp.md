# Архитектура MVP

## Компоненты системы

### 1. Монолитное приложение (Python)
- **Назначение**: Управление системой и ведение диалогов
- **Хостинг**: VPS (например, Selectel)
- **Режим работы**: Long polling (постоянно запущенный процесс)
- **Функции**:
  - Обработка команд администратора
  - Ведение диалогов с пользователями
  - Интеграция с GPT для генерации ответов
- **Коммуникации**:
  - Telegram API (long polling)
  - OpenAI API (генерация ответов)
  - База данных (хранение данных)
- **Запуск и поддержка**:
  - Systemd сервис для автозапуска
  - Логирование в файл
  - Автоматический перезапуск при сбоях

### 2. База данных (PostgreSQL)
- **Назначение**: Хранение всех данных системы
- **Хостинг**: Тот же VPS
- **Основные таблицы**:
  ```sql
  -- Диалоги
  dialogs (
    id: bigserial primary key,
    target_username: text,
    status: text,
    created_at: timestamp
  )

  -- Сообщения
  messages (
    id: bigserial primary key,
    dialog_id: bigint,
    direction: text, -- in/out
    content: text,
    timestamp: timestamp
  )
  ```

## Схема взаимодействия

```mermaid
graph TD
A[Администратор] -->|Telegram команды| B[Python-приложение]
B -->|Сообщения| C[Пользователь]
C -->|Ответы| B
B -->|Запросы| D[OpenAI API]
D -->|Ответы| B
B -->|CRUD| E[База данных]
```

## Административные команды в Telegram
```
# Управление диалогами
/start @username - начать диалог
/stop N - остановить диалог номер N
/list - список активных диалогов

# Просмотр и выгрузка
/view N - просмотр диалога номер N
/export N - выгрузка диалога номер N в текстовый файл
/export_all - выгрузка всех диалогов
```

## Конфигурация

Конфигурация осуществляется через переменные окружения:

```bash
# Telegram settings
export API_ID=123456
export API_HASH="your_api_hash"
export BOT_TOKEN="your_bot_token"
export ADMIN_TELEGRAM_ID=123456789

# OpenRouter settings
export OPENROUTER_API_KEY="your_openrouter_key"

# Database settings (optional, has default)
export DATABASE_URL="postgresql://user:pass@localhost:5432/sales_bot"

# Logging settings (optional, have defaults)
export LOG_LEVEL="INFO"
export LOG_FILE="/var/log/sales_bot/app.log"
```

## Systemd сервис
```ini
[Unit]
Description=Sales Bot
After=network.target postgresql.service

[Service]
Type=simple
User=sales_bot
WorkingDirectory=/home/sales_bot/sales_bot
ExecStart=/home/sales_bot/sales_bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Требования к серверу
- Ubuntu 22.04
- 2 CPU
- 4 GB RAM
- 40 GB SSD
- Белый IP
