# База данных

## Архитектура

### Основные компоненты
- Аккаунты и профили (`jeeves/core/accounts/models/`)
  - `account.py` - модели аккаунтов и их состояний
  - `profile.py` - модели профилей и их истории
- Диалоги и сообщения (`jeeves/core/messaging/models/`)
  - `dialog.py` - модели диалогов и их статусы
  - `message.py` - модели сообщения и направления
- Аудитории и контакты (`jeeves/core/audiences/models/`)
  - `models.py` - модели аудиторий и контактов
- Компании и кампании (`jeeves/core/companies/models/`)
  - `company.py` - модели компаний и их настройки
  - `campaign.py` - модели рекламных кампаний

### Общая схема
```mermaid
erDiagram
    Account ||--o| AccountProfile : has
    Account ||--o{ Dialog : manages
    Account }|--o{ Campaign : participates
    AccountProfile ||--o{ ProfileHistory : tracks
    AccountProfile ||--o| ProfileTemplate : uses
    Dialog ||--o{ Message : contains
    Dialog }o--o| Campaign : belongs_to
    Dialog ||--|| Contact : with
    Audience ||--o{ Contact : contains
    Campaign }|--o{ Audience : targets
    Company ||--o{ Campaign : owns

    Account {
        bigint id PK
        string phone UK
        string session_string
        enum status
        int messages_sent
        int daily_messages
        bool is_available
        datetime created_at
        datetime updated_at
        datetime last_used_at
    }

    AccountProfile {
        bigint id PK
        bigint account_id FK
        bigint template_id FK
        string username
        string first_name
        string last_name
        text bio
        bytes photo
        bool is_synced
        datetime last_synced_at
        datetime created_at
        datetime updated_at
    }

    Dialog {
        bigint id PK
        string username
        bigint account_id FK
        bigint campaign_id FK
        bigint contact_id FK
        datetime last_message_at
        bool is_active
        enum status
        datetime created_at
        datetime updated_at
    }

    Message {
        bigint id PK
        bigint dialog_id FK
        enum direction
        string content
        datetime timestamp
        datetime created_at
        datetime updated_at
    }

    Contact {
        bigint id PK
        string telegram_username
        bigint telegram_id
        string phone
        bool is_valid
        datetime created_at
        datetime updated_at
    }

    Audience {
        bigint id PK
        string name
        text description
        enum status
        datetime created_at
        datetime updated_at
    }

    Campaign {
        bigint id PK
        bigint company_id FK
        string name
        text description
        enum status
        datetime created_at
        datetime updated_at
    }

    Company {
        bigint id PK
        string name UK
        text description
        json settings
        bool is_active
        datetime created_at
        datetime updated_at
    }
```

## Работа с базой данных

### Декоратор @with_queries

Декоратор для автоматического управления сессиями базы данных. Поддерживает работу с одним или несколькими классами запросов:

```python
# Один класс запросов
@with_queries(AccountQueries)
async def get_accounts(queries: AccountQueries):
    return await queries.get_all_accounts()

# Несколько классов запросов
@with_queries((DialogQueries, AccountQueries))
async def start_dialog(
    dialog_queries: DialogQueries,
    account_queries: AccountQueries
):
    account = await account_queries.get_available_account()
    return await dialog_queries.create_dialog(account.id)
```

#### Особенности работы
1. Автоматическое создание и закрытие сессии
2. Общая сессия для всех классов запросов
3. Автоматический rollback при ошибках
4. Именование параметров по типу запросов

#### Правила использования

✅ Правильно:
```python
@with_queries(AccountQueries)
async def check_account(queries: AccountQueries):
    account = await queries.get_account_by_phone(phone)
    return account.status == AccountStatus.active

@with_queries((DialogQueries, AccountQueries))
async def process_dialog(
    dialog_queries: DialogQueries,
    account_queries: AccountQueries
):
    # Все операции в одной транзакции
    account = await account_queries.get_account()
    dialog = await dialog_queries.create_dialog(account.id)
```

❌ Неправильно:
```python
# Не храните сессию как атрибут класса
class BadManager:
    def __init__(self):
        self.session = AsyncSession(engine)

# Не создавайте множественные сессии
async def bad_operation():
    async with get_db() as session1:
        # Первая операция
        pass
    async with get_db() as session2:
        # Связанная операция
        pass
```
