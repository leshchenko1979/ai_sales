# AI Sales Bot API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Message Management](#message-management)
3. [Error Handling](#error-handling)
4. [Usage Examples](#usage-examples)

For account management documentation, see [Account System Documentation](account_system.md)
For database documentation, see [Database Documentation](database.md)

## Overview

The AI Sales Bot API provides interfaces for managing messages and conversations in automated sales processes. For account management and authorization, please refer to the [Account System Documentation](account_system.md).

## Message Management

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

## Error Handling

### General API Errors
- `InvalidRequest`: Invalid request parameters
- `DatabaseError`: Database operation failed
- `InternalError`: Internal server error

### Safety Mechanisms
- Request rate limiting
- Input validation
- Error logging and monitoring

## Usage Examples

### Creating a Dialog
```python
dialog = await dialog_manager.create_dialog(
    account_id=1,
    target_username="user123"
)
```

### Sending a Message
```python
message = await message_manager.send_message(
    dialog_id=1,
    content="Hello! How can I help you today?"
)
