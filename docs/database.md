# Database Documentation

## Table of Contents
1. [Data Models](#data-models)
2. [Architecture](#architecture)
3. [Query Classes](#query-classes)
4. [Business Objects](#business-objects)
5. [Session Management](#session-management)
6. [Transaction Management](#transaction-management)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)
9. [Testing](#testing)

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

## Architecture

The database layer uses a clean architecture pattern with separation of concerns between business logic and database operations.
This is achieved through a three-layer architecture:

1. **Query Classes** - Low-level database operations
2. **Business Objects** - High-level business logic
3. **Session Management** - Handled automatically via decorator

### Database Connection

The application uses SQLAlchemy as the ORM and supports both SQLite and PostgreSQL databases. Connection management is handled through environment variables:

```python
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
```

Key features:
- Async database operations with asyncpg
- Connection pooling
- Automatic connection management
- Support for multiple database types

## Query Classes

Query classes handle direct database operations. They inherit from `BaseQueries`:

```python
class BaseQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

class AccountQueries(BaseQueries):
    async def get_account_by_phone(self, phone: str) -> Optional[Account]:
        result = await self.session.execute(
            select(Account).where(Account.phone == phone)
        )
        return result.scalar_one_or_none()
```

Key characteristics:
- Direct session access via self.session
- Low-level database operations
- No business logic
- Clear and focused responsibility
- No session management logic

### Common Query Patterns

1. **Select Operations**
```python
async def get_by_id(self, id: int) -> Optional[Model]:
    return await self.session.get(Model, id)

async def get_all(self) -> List[Model]:
    result = await self.session.execute(select(Model))
    return result.scalars().all()
```

2. **Insert Operations**
```python
async def create(self, **data) -> Model:
    obj = Model(**data)
    self.session.add(obj)
    await self.session.flush()
    return obj
```

3. **Update Operations**
```python
async def update(self, id: int, **data) -> Optional[Model]:
    obj = await self.get_by_id(id)
    if obj:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.session.flush()
    return obj
```

4. **Delete Operations**
```python
async def delete(self, id: int) -> bool:
    obj = await self.get_by_id(id)
    if obj:
        await self.session.delete(obj)
        return True
    return False
```

### Account Operations
- `get_account_by_phone(phone: str)`: Get account by phone number
- `get_account_by_id(account_id: int)`: Get account by ID
- `get_active_accounts()`: Get all active accounts ordered by message count
- `get_accounts_by_status(status: AccountStatus)`: Get accounts by status
- `create_account(phone_number: str)`: Create new account
- `update_account_status(account_id: int, status: AccountStatus)`: Update account status
- `update_session(account_id: int, session_string: str)`: Update account session string
- `increment_messages(account_id: int)`: Increment daily message counter

### Dialog Operations
- `create_dialog(username: str, account_id: int)`: Create new dialog
- `get_dialog(dialog_id: int)`: Get dialog by ID
- `get_active_dialogs()`: Get all active dialogs
- `get_messages(dialog_id: int)`: Get all messages for a dialog
- `save_message(dialog_id: int, direction: MessageDirection, content: str)`: Save message

## Business Objects

Business objects implement high-level business logic and use the `@with_queries` decorator for automatic session management.
The decorator can accept multiple query classes and will create a single shared session for all queries:

```python
@with_queries(DialogQueries, AccountQueries)
async def start_dialog(
    username: str,
    dialog_queries: DialogQueries,
    account_queries: AccountQueries
) -> bool:
    # Both query instances share the same session
    account = await account_queries.get_available_account()
    dialog = await dialog_queries.create_dialog(username, account.id)
    return dialog is not None
```

### Using @with_queries Decorator

The `@with_queries` decorator provides automatic session management for database operations. Here are the key points:

1. **Single vs Multiple Query Classes**:
   ```python
   # Single query class - parameter will be named 'queries'
   @with_queries(AccountQueries)
   async def func1(queries: AccountQueries):
       return await queries.get_all_accounts()

   # Multiple query classes - parameters will be named '{class_name_lower}_queries'
   @with_queries(DialogQueries, AccountQueries)
   async def func2(dialog_queries: DialogQueries, account_queries: AccountQueries):
       account = await account_queries.get_available_account()
       return await dialog_queries.create_dialog(account.id)
   ```

2. **Parameter Naming**:
   - For single query class:
     - Parameter is always named `queries`
     - This maintains backward compatibility
   - For multiple query classes:
     - Parameters are named by converting class name
     - `DialogQueries` -> `dialog_queries`
     - `AccountQueries` -> `account_queries`

3. **Session Sharing**:
   - All query instances share the same database session
   - Session is automatically committed on success
   - Session is automatically rolled back on error

4. **When to Use**:

   DO use `@with_queries` when:
   ```python
   # Single query class
   @with_queries(AccountQueries)
   async def list_accounts(queries: AccountQueries):
       return await queries.get_all_accounts()

   # Multiple query classes
   @with_queries(DialogQueries, AccountQueries)
   async def start_dialog(dialog_queries: DialogQueries, account_queries: AccountQueries):
       account = await account_queries.get_available_account()
       return await dialog_queries.create_dialog(account.id)
   ```

   DON'T use `@with_queries` when:
   ```python
   async def authorize_account():
       # No direct database access, using manager instead
       manager = AccountManager()
       return await manager.authorize_account(phone, code)
   ```

5. **Best Practices**:
   - Only use when direct database access is needed
   - Keep database operations close to the query layer
   - Use business objects to encapsulate complex logic
   - Avoid mixing database and business logic
   - Use single query class when possible for simpler code

### Example Usage

Good example with direct database access:
```python
@with_queries(AccountQueries)
async def check_account(queries: AccountQueries):
    account = await queries.get_account_by_phone(phone)
    if account:
        return account.status == AccountStatus.active
    return False
```

Bad example without database access:
```python
# Don't use @with_queries here!
async def send_message(phone: str, text: str):
    manager = AccountManager()
    return await manager.send_message(phone, text)
```

## Session Management

The application uses two main patterns for session management:

1. **Decorator Pattern** - For business objects via `@with_queries`
2. **Context Manager Pattern** - For direct database access via `get_db()`

### Decorator Pattern

The `@with_queries` decorator automatically manages sessions for business objects:

```python
def with_queries(query_class: Type[Q]) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for business objects that automatically manages database sessions.
    Creates a new session and query object for each method call.

    :param query_class: Query class to instantiate (e.g. AccountQueries)
    :return: Decorated method with automatic session management
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            async with get_db() as session:
                queries = query_class(session)
                return await func(self, queries, *args, **kwargs)
        return wrapper
    return decorator
```

### Context Manager Pattern

For direct database access, use the `get_db()` context manager:

```python
async with get_db() as session:
    # Session is automatically created
    await session.execute(query)
    await session.commit()
    # Session is automatically closed
```

## Transaction Management

Transactions are handled automatically by the session management patterns:

1. **Automatic Commit**: On successful completion of the context
2. **Automatic Rollback**: On exceptions
3. **Nested Transactions**: Supported via savepoints

Example of complex transaction:
```python
@with_queries(AccountQueries)
async def complex_operation(self, queries: AccountQueries):
    # Start transaction
    account = await queries.create_account()
    # If any operation fails, all changes are rolled back
    await queries.create_related_data()
    # Commit happens automatically on success
```

## Error Handling

The database layer includes comprehensive error handling:

1. **Connection Errors**
```python
try:
    async with get_db() as session:
        # Database operations
except ConnectionError:
    logger.error("Database connection failed")
    raise DatabaseConnectionError()
```

2. **Constraint Violations**
```python
try:
    await queries.create_account(phone)
except IntegrityError as e:
    if "unique_phone" in str(e):
        raise DuplicatePhoneError()
    raise
```

3. **Transaction Errors**
```python
try:
    async with get_db() as session:
        await session.execute(query)
        await session.commit()
except SQLAlchemyError:
    # Automatic rollback
    logger.error("Transaction failed")
    raise
```

## Best Practices

### Query Classes
- Keep methods focused on single database operations
- Use type hints for all methods
- Document complex queries
- Use SQLAlchemy core for complex queries

### Business Objects
- Always use `@with_queries` decorator
- Keep business logic separate from database operations
- Handle errors appropriately
- Validate input data before database operations

### Session Management
- Never manage sessions manually in business objects
- Use context managers for direct database access
- Keep transactions as short as possible
- Handle errors at appropriate levels

### Performance
- Use appropriate indexes
- Optimize queries for common operations
- Monitor query performance
- Use bulk operations when possible

### Anti-patterns to avoid

```python
# DON'T: Store session as a long-lived object
class BadAccountManager:
    def __init__(self):
        self.session = AsyncSession(engine)  # Wrong!

# DON'T: Create multiple sessions for related operations
async def bad_operation():
    async with get_db() as session1:
        # First operation
        pass
    async with get_db() as session2:  # Wrong!
        # Related operation
        pass

# DON'T: Mix session management patterns
class BadQueries:
    @staticmethod
    async def operation1(session: AsyncSession):
        pass

    async def operation2(self):  # Wrong!
        self.session.execute(...)
```

### Correct patterns

```python
# DO: Create session per business operation
async def good_operation():
    async with get_db() as session:
        queries = AccountQueries(session)
        # All related operations use same session

# DO: Group related queries in a class
class GoodQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def operation1(self):
        await self.session.execute(...)

    async def operation2(self):
        await self.session.execute(...)

# DO: Use single session for transaction
async def good_transaction():
    async with get_db() as session:
        queries = AccountQueries(session)
        try:
            await queries.operation1()
            await queries.operation2()
            # Commit happens automatically on context exit
        except Exception:
            # Rollback happens on context exit
            raise
```

## Testing

### Unit Tests with Mocked Sessions
```python
async def test_account_creation():
    mock_queries = AsyncMock(spec=AccountQueries)
    mock_queries.create_account.return_value = Account(id=1)

    manager = AccountManager()
    account = await manager.add_account(mock_queries, "1234567890")

    assert account.id == 1
    mock_queries.create_account.assert_called_once()
```

### Integration Tests with Test Database
```python
@pytest.mark.asyncio
async def test_account_creation_integration():
    async with get_test_db() as session:
        queries = AccountQueries(session)
        account = await queries.create_account("1234567890")
        assert account.id is not None
