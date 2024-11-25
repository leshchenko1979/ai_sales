# AI Sales Bot API Documentation

## Table of Contents
1. [Data Models](#data-models)
2. [Account Management](#account-management)
3. [Message Management](#message-management)
4. [Error Handling](#error-handling)
5. [Database Operations](#database-operations)
6. [Authorization Process](#authorization-process)
7. [Usage Examples](#usage-examples)

## Data Models

### Account
The main model for storing Telegram account data.

#### Fields:
- `id` (BigInteger, primary key)
- `phone` (String, unique)
- `session_string` (String)
- `status` (AccountStatus)
- `created_at` (DateTime)
- `updated_at` (DateTime)
- `last_used_at` (DateTime)
- `messages_sent` (Integer)
- `is_available` (Boolean)
- `warmup_count` (Integer)
- `ban_count` (Integer)

#### Properties:
- `is_in_flood_wait`: Check if account is in flood control mode
- `can_be_used`: Check if account can be used for sending messages

### AccountStatus
Enum representing possible account statuses:
- `new`: New account
- `code_requested`: Code has been requested
- `password_requested`: Password has been requested
- `active`: Account is active
- `disabled`: Account is disabled
- `blocked`: Account is blocked
- `warming`: Account is in warming up process

### Dialog
Model for storing conversations.

#### Fields:
- `id` (BigInteger, primary key)
- `account_id` (BigInteger, foreign key to Account)
- `target_username` (String)
- `status` (DialogStatus)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### DialogStatus
Enum representing possible dialog statuses:
- `active`: Dialog is active
- `qualified`: Dialog is qualified
- `stopped`: Dialog is stopped
- `failed`: Dialog failed

### Message
Model for storing messages in dialogs.

#### Fields:
- `id` (BigInteger, primary key)
- `dialog_id` (BigInteger, foreign key to Dialog)
- `direction` (MessageDirection)
- `content` (String)
- `timestamp` (DateTime)

### MessageDirection
Enum representing message direction:
- `in_`: Incoming message
- `out`: Outgoing message

## Account Management

### AccountClient
Class for managing individual Telegram accounts.

#### Methods:

##### connect()
Connect to Telegram API.
```python
client = AccountClient(account)
success = await client.connect()
```

##### authorize(code: str)
Authorize account with received code.
```python
session_string = await client.authorize(code)
```

##### sign_in(code: str)
Sign in with the provided code using stored phone code hash.
```python
success = await client.sign_in(code)
```

##### export_session_string()
Export session string after successful authorization.
```python
session_string = await client.export_session_string()
```

##### send_message(username: str, text: str)
Send message to user.
```python
success = await client.send_message(username, text)
```

### AccountManager
Class for managing multiple Telegram accounts.

#### Methods:

##### add_account(phone_number: str)
Add new account to database.
```python
account = await manager.add_account(phone_number)
```

##### request_code(phone: str)
Request authorization code for account.
```python
success = await manager.request_code(phone)
```

##### authorize_account(phone: str, code: str)
Authorize account with received code.
```python
success = await manager.authorize_account(phone, code)
```

##### update_account_status(phone: str, status: AccountStatus)
Update account status.
```python
await manager.update_account_status(phone, status)
```

##### get_available_account()
Get account available for sending messages.
```python
account = await manager.get_available_account()
```

##### send_message(account: Account, username: str, text: str)
Send message using specified account.
```python
success = await manager.send_message(account, username, text)
```

## Message Management

## Error Handling

### Telegram API Errors
- `PhoneNumberInvalid`: Invalid phone number
- `PhoneCodeInvalid`: Invalid confirmation code
- `PhoneCodeExpired`: Expired confirmation code
- `PasswordHashInvalid`: Invalid password
- `FloodWait`: Request frequency limit
- `AuthKeyUnregistered`: Authorization error
- `SessionPasswordNeeded`: Two-factor authentication password required

### Safety Mechanisms
- Flood control monitoring
- Message sending limits
- Account status tracking
- Automatic client connection management

## Database Operations

### Database Connection
```python
@asynccontextmanager
async def get_db():
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### AccountQueries
Class for managing account-related database operations.

#### Methods:

##### get_account_by_phone(phone: str)
Get account by phone number.
```python
account = await queries.get_account_by_phone(phone)
```

##### get_account_by_id(account_id: int)
Get account by ID.
```python
account = await queries.get_account_by_id(account_id)
```

##### get_active_accounts()
Get all active accounts ordered by message count.
```python
accounts = await queries.get_active_accounts()
```

##### get_accounts_by_status(status: AccountStatus)
Get accounts by status.
```python
accounts = await queries.get_accounts_by_status(status)
```

##### create_account(phone_number: str)
Create new account.
```python
account = await queries.create_account(phone_number)
```

##### update_account_status(account_id: int, status: AccountStatus)
Update account status.
```python
success = await queries.update_account_status(account_id, status)
```

##### update_session(account_id: int, session_string: str)
Update account session string.
```python
success = await queries.update_session(account_id, session_string)
```

##### increment_messages(account_id: int)
Increment daily message counter.
```python
success = await queries.increment_messages(account_id)
```

### DialogQueries
Class for managing dialog-related database operations.

#### Methods:

##### create_dialog(username: str, account_id: int)
Create new dialog.
```python
dialog = await queries.create_dialog(username, account_id)
```

##### get_dialog(dialog_id: int)
Get dialog by ID.
```python
dialog = await queries.get_dialog(dialog_id)
```

##### get_active_dialogs()
Get all active dialogs.
```python
dialogs = await queries.get_active_dialogs()
```

##### get_messages(dialog_id: int)
Get all messages for a dialog.
```python
messages = await queries.get_messages(dialog_id)
```

##### save_message(dialog_id: int, direction: MessageDirection, content: str)
Save message.
```python
success = await queries.save_message(dialog_id, direction, content)

```

## Authorization Process

The authorization process in AI Sales Bot consists of several steps:

1. Account Creation
```python
async with get_db() as session:
    queries = AccountQueries(session)
    # Create new account or get existing one
    account = await queries.get_account_by_phone(phone)
    if not account:
        account = await queries.create_account(phone)
```

2. Request Authorization Code
```python
# Initialize account manager
manager = AccountManager(session)

# Request authorization code
# This will send a code to the Telegram account
success = await manager.request_code(phone)
if not success:
    logger.error("Failed to request code")
    return
```

3. Submit Authorization Code
```python
# After receiving the code from user
if await manager.authorize_account(phone, code):
    logger.info("Account successfully authorized!")
else:
    logger.error("Failed to authorize account")
```

4. Verify Account Status
```python
# Check account state
account = await queries.get_account_by_phone(phone)
monitor = AccountMonitor(queries, notifier)
if await monitor.check_account(account):
    logger.info("Account is authorized and ready!")
```

### Authorization States

The account goes through several states during authorization:
1. `new` - Initial state after account creation
2. `code_requested` - After requesting authorization code
3. `password_requested` - If 2FA is enabled (optional)
4. `active` - After successful authorization
5. `blocked` - If account gets blocked
6. `disabled` - If account is manually disabled
7. `warming` - During the warming up process

## Usage Examples

### 1. Basic Account Management

#### Creating and Authorizing Account
```python
async def setup_account(phone: str):
    async with get_db() as session:
        queries = AccountQueries(session)
        manager = AccountManager(session)

        # Create account
        account = await queries.create_account(phone)

        # Request authorization code
        await manager.request_code(phone)

        # Submit code (received externally)
        code = "12345"  # Get this from user input
        success = await manager.authorize_account(phone, code)

        return success
```

#### Sending Messages
```python
async def send_message_example(phone: str, target: str, text: str):
    async with get_db() as session:
        queries = AccountQueries(session)
        manager = AccountManager(session)

        # Get account
        account = await queries.get_account_by_phone(phone)
        if not account or not account.can_be_used:
            return False

        # Send message
        return await manager.send_message(account, target, text)
```

### 2. Dialog Management

#### Creating and Managing Dialog
```python
async def manage_dialog(account_id: int, username: str):
    async with get_db() as session:
        # Получаем необходимые объекты для работы
        account_queries = AccountQueries(session)
        dialog_queries = DialogQueries(session)
        manager = AccountManager(session)

        # Получаем аккаунт
        account = await account_queries.get_account_by_id(account_id)
        if not account or not account.can_be_used:
            logger.error("Account not available")
            return None

        # Создаем новый диалог
        dialog = await dialog_queries.create_dialog(username, account_id)

        # Отправляем сообщение через Telegram
        message_text = "Hello! How can I help you?"
        success = await manager.send_message(account, username, message_text)

        if success:
            # Если сообщение успешно отправлено, сохраняем его в базу
            await dialog_queries.save_message(
                dialog.id,
                MessageDirection.out,
                message_text
            )

            # Получаем все сообщения диалога
            messages = await dialog_queries.get_messages(dialog.id)
            return messages
        else:
            logger.error("Failed to send message")
            return None
```

### 3. Account Monitoring

#### Checking Account Health
```python
async def check_account_health(phone: str):
    async with get_db() as session:
        queries = AccountQueries(session)
        notifier = AccountNotifier()
        monitor = AccountMonitor(queries, notifier)

        account = await queries.get_account_by_phone(phone)
        if not account:
            return False

        # Check account status
        is_healthy = await monitor.check_account(account)

        # Handle unhealthy account
        if not is_healthy:
            await notifier.notify_account_problem(account)

        return is_healthy
```

### 4. Error Handling

#### Handling Flood Control
```python
async def send_with_flood_control(account: Account, username: str, text: str):
    try:
        async with get_db() as session:
            manager = AccountManager(session)
            await manager.send_message(account, username, text)

    except FloodWait as e:
        # Wait for the specified time
        await asyncio.sleep(e.value)
        # Retry sending
        return await send_with_flood_control(account, username, text)
