# Account Management System Documentation

## Overview
The account management system is responsible for handling Telegram accounts, maintaining their connections, and managing their lifecycle. The system is designed to provide persistent connections while ensuring proper resource management and scalability.

## Components

### AccountManager
The main facade class that provides a unified interface for account operations. It encapsulates the complexity of account management and delegates specific responsibilities to specialized components.

**Responsibilities:**
- Account lifecycle management (creation, updating, deletion)
- Status management
- Integration with database operations
- Coordination of client connections
- Safety rules enforcement

**Key Methods:**
- `add_account(phone_number: str)`: Add new account to database
- `request_code(phone: str)`: Request authorization code
- `authorize_account(phone: str, code: str)`: Complete authorization
- `update_account_status(phone: str, status: AccountStatus)`: Update status
- `get_available_account()`: Get account available for sending messages
- `send_message(account: Account, username: str, text: str)`: Send message

### AccountClientManager (Internal Component)
An internal component of AccountManager that handles Telegram client connections.

**Responsibilities:**
- Maintaining persistent client connections
- Managing client lifecycle
- Ensuring single client instance per account
- Handling connection recovery
- Resource cleanup

### AccountClient
Class for managing individual Telegram account connections and operations.

**Key Methods:**
- `connect()`: Connect to Telegram API
- `authorize(code: str)`: Authorize account with received code
- `sign_in(code: str)`: Sign in with provided code
- `export_session_string()`: Export session string after authorization
- `send_message(username: str, text: str)`: Send message to user

## Authorization Process

### Steps:

1. **Account Creation**
   ```python
   manager = AccountManager()
   account = await manager.get_or_create_account(phone)
   ```

2. **Request Authorization Code**
   ```python
   success = await manager.request_code(phone)
   if not success:
       logger.error("Failed to request code")
       return
   ```

3. **Submit Authorization Code**
   ```python
   success = await manager.authorize_account(phone, code)
   if not success:
       logger.error("Failed to authorize account")
   ```

### Error Handling

#### Telegram API Errors
- `PhoneNumberInvalid`: Invalid phone number
- `PhoneCodeInvalid`: Invalid confirmation code
- `PhoneCodeExpired`: Expired confirmation code
- `PasswordHashInvalid`: Invalid password
- `FloodWait`: Request frequency limit
- `AuthKeyUnregistered`: Authorization error
- `SessionPasswordNeeded`: Two-factor authentication required

#### Safety Mechanisms
- Flood control monitoring
- Message sending limits
- Account status tracking
- Automatic client connection management

## Design Decisions

### Why Internal Component vs Separate Manager
The decision to make AccountClientManager an internal component of AccountManager rather than a separate manager was made based on the following considerations:

**Benefits:**
1. Clear ownership hierarchy
2. Simplified external API
3. Better encapsulation of client management details
4. Easier coordination between account status and client state
5. Reduced complexity in dependency management

**Trade-offs:**
1. Larger AccountManager class
2. More complex unit testing
3. Less flexibility in deployment scenarios

## Account States and Transitions

### AccountStatus
- `new`: Initial state for new accounts
- `code_requested`: Authorization code has been requested
- `password_requested`: Two-factor authentication password needed
- `active`: Account is authorized and ready for use
- `disabled`: Account has been manually disabled
- `blocked`: Account has been blocked by Telegram
- `warming`: Account is in warming up process

### State Transitions
```
new → code_requested → active
new → code_requested → password_requested → active
active → warming → active
active → blocked
active → disabled
```

## Best Practices

1. Always access clients through AccountManager
2. Handle connection errors at the AccountManager level
3. Use proper status transitions
4. Implement proper cleanup in shutdown scenarios
5. Monitor account health and status
6. Implement proper retry mechanisms for temporary failures
7. Use session string storage for persistent authentication

## Error Recovery Strategies

1. **Connection Failures**
   - Automatic retry with exponential backoff
   - Session string re-validation
   - Automatic client recreation if needed

2. **Authorization Failures**
   - Clear session data and restart auth process
   - Mark account as requiring re-authorization
   - Notify system administrators

3. **Rate Limiting**
   - Implement waiting periods
   - Distribute load across accounts
   - Track and adapt to Telegram's limits
