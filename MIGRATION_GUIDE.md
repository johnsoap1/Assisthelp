# Pyrogram 2.x Migration Guide

This guide provides solutions to common issues when migrating from Pyrogram 1.x to 2.x.

## Table of Contents
1. [SUDOERS Filter Usage](#1-sudoers-filter-usage)
2. [Error Imports](#2-error-imports)
3. [SUDOERS_SET for Quick Lookups](#3-sudoers_set-for-quick-lookups)
4. [Decorator Issues](#4-decorator-issues)
5. [Common Module Fixes](#5-common-module-fixes)
6. [Missing Decorator Import](#6-missing-decorator-import)
7. [Environment Variables](#7-environment-variables)
8. [MongoDB Imports](#8-mongodb-imports)

---

## 1. SUDOERS Filter Usage

### ❌ Incorrect (Pyrogram 1.x style)
```python
@app.on_message(filters.command("test") & SUDOERS)
```

### ✅ Correct (Pyrogram 2.x style)
```python
from wbb import SUDOERS  # This is now filters.user([...])

@app.on_message(filters.command("test") & SUDOERS)
async def test_cmd(_, message):
    ...
```

## 2. Error Imports

### ❌ Incorrect
```python
from pyrogram.errors.exceptions.forbidden_403 import UserNotParticipant
```

### ✅ Correct (Option 1 - Direct)
```python
from pyrogram.errors import (
    ChatAdminRequired,
    AccessDenied,
    ChatNotFound,
    PeerIdInvalid,
    UserNotParticipant
)
```

### ✅ Correct (Option 2 - With Fallback)
```python
try:
    from pyrogram.errors import UserNotParticipant
except ImportError:
    # Fallback for different Pyrogram versions
    UserNotParticipant = PeerIdInvalid
```

## 3. SUDOERS_SET for Quick Lookups

Use the `SUDOERS_SET` for quick membership checks:

```python
from wbb import SUDOERS_SET, check_user_sudo

async def my_function(_, message):
    if check_user_sudo(message.from_user.id):
        # User is sudoer
        pass
```

## 4. Decorator Issues

### ❌ Avoid Circular Imports
```python
# WRONG - Causes circular imports
from wbb.core.decorators.permissions import adminsOnly
```

### ✅ Use Inline Check Instead
```python
async def is_admin(client, user_id, chat_id):
    """Check if user is admin."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False
```

## 5. Common Module Fixes

### Inactive Kick Module
```python
# Before:
# from pyrogram.errors.exceptions.forbidden_403 import UserNotParticipant

# After:
try:
    from pyrogram.errors import UserNotParticipant
except ImportError:
    class UserNotParticipant(Exception):
        pass
```

### Fixing Inverted Filters
```python
# Before:
# @app.on_message(~filters.me & filters.group & SUDOERS)

# After:
@app.on_message((~filters.me) & filters.group & SUDOERS)
```

## 6. Missing Decorator Import

### ❌ Incorrect
```python
from wbb.core.decorators.errors import capture_err
```

### ✅ Define Locally or Use Try-Except
```python
def capture_err(func):
    """Decorator to capture errors."""
    async def wrapper(client, message):
        try:
            return await func(client, message)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
    return wrapper
```

## 7. Environment Variables

Ensure environment variables are properly handled:

```python
# In __init__.py
try:
    DEEPL_API = os.getenv("DEEPL_API")
except:
    DEEPL_API = None
```

## 8. MongoDB Imports

### ❌ Incorrect
```python
from wbb.core.mongo import db
```

### ✅ Correct
```python
from wbb import db  # Import from main __init__
```

## Complete Example: Fixed Module

Here's a complete example of a fixed module:

```python
import asyncio
from datetime import datetime, timedelta

from pyrogram import filters, Client
from pyrogram.types import Message

# Correct imports for Pyrogram 2.x
try:
    from pyrogram.errors import (
        UserNotParticipant,
        ChatAdminRequired,
        AccessDenied,
        ChatNotFound,
        PeerIdInvalid,
    )
except ImportError:
    # Fallback
    ChatAdminRequired = Exception
    AccessDenied = Exception
    ChatNotFound = Exception
    PeerIdInvalid = Exception
    UserNotParticipant = PeerIdInvalid

from wbb import app, SUDOERS, db, log

@app.on_message(filters.command("example") & SUDOERS)
async def example_cmd(_, message: Message):
    """Example command with proper error handling."""
    try:
        # Your code here
        await message.reply_text("✅ Command executed successfully!")
    except Exception as e:
        log.error(f"Error in example_cmd: {e}")
        await message.reply_text(f"❌ Error: {str(e)[:100]}")
```

## Additional Tips

1. **Testing**: Test each module thoroughly after making changes
2. **Error Handling**: Always wrap database operations in try-except blocks
3. **Logging**: Use the provided `log` instance for consistent logging
4. **Type Hints**: Add type hints for better code maintainability
5. **Documentation**: Update docstrings to reflect any changes in behavior
