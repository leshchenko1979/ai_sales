# Детализация первого прототипа

## Минимальный набор функций

1. **Управление через Telegram**
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

2. **Базовый сценарий диалога**
   - Первое сообщение
   - Обработка ответа через GPT
   - Квалификация (чек/сроки)
   - Передача менеджеру

## Технические компоненты

1. **Монолитное приложение**
   ```
   sales_bot/
   ├── config.py           # Конфигурация приложения
   ├── main.py            # Точка входа
   ├── bot/               # Логика бота
   │   ├── commands.py    # Обработчики команд админ-бота
   │   ├── dialogs.py     # Управление диалогами
   │   └── gpt.py         # Интеграция с GPT
   ├── accounts/          # Управление аккаунтами
   │   ├── manager.py     # Менеджер аккаунтов
   │   ├── client.py      # MTProto клиент
   │   └── safety.py      # Защита аккаунтов
   ├── db/                # Работа с базой данных
   │   ├── models.py      # Модели данных
   │   └── queries.py     # SQL запросы
   └── utils/             # Вспомогательные функции
       ├── export.py      # Экспорт диалогов
       └── logging.py     # Настройка логирования
   ```

2. **База данных**
   ```sql
   -- Аккаунты
   accounts (
     id: bigserial primary key,
     phone: text,
     session_string: text,
     status: text,
     last_used: timestamp,
     daily_messages: integer
   )

   -- Диалоги
   dialogs (
     id: bigserial primary key,
     account_id: bigint,
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

3. **Системные требования**
   - Ubuntu 22.04
   - 2 CPU
   - 4 GB RAM
   - 40 GB SSD
   - Белый IP

4. **Конфигурация**
   - Настройки бота (токены, API ключи)
   - Промпты для GPT
   - Параметры подключений к БД

## Метрики успеха этапа
- Работающий бот с базовыми командами
- Успешное ведение диалога с пользователем
- Корректная квалификация лидов
