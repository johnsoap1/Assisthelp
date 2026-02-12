# wbb/core/decorators/errors.py
"""
Error handling decorator for bot commands.
"""
import traceback
from functools import wraps
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden


def split_limits(text):
    """Split text into chunks under 2048 characters."""
    if len(text) < 2048:
        return [text]
    
    lines = text.splitlines(True)
    small_msg = ""
    result = []
    
    for line in lines:
        if len(small_msg) + len(line) < 2048:
            small_msg += line
        else:
            result.append(small_msg)
            small_msg = line
    else:
        result.append(small_msg)
    
    return result


def capture_err(func):
    """Decorator to capture and log errors in command handlers."""
    @wraps(func)
    async def capture(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden:
            # Bot was removed from chat, leave gracefully
            from wbb import app
            try:
                await app.leave_chat(message.chat.id)
            except:
                pass
            return
        except Exception as err:
            # Format and send error to log group
            from wbb import app, LOG_GROUP_ID
            
            errors = traceback.format_exc()
            
            # Create error message
            error_feedback = split_limits(
                "**ERROR** | `{}` | `{}`\n\n```{}```\n\n```{}```\n".format(
                    0 if not message.from_user else message.from_user.id,
                    0 if not message.chat else message.chat.id,
                    message.text or message.caption or "No text",
                    "".join(errors),
                ),
            )
            
            # Send to log group
            if LOG_GROUP_ID:
                for x in error_feedback:
                    try:
                        await app.send_message(LOG_GROUP_ID, x)
                    except Exception as e:
                        print(f"Failed to send error log: {e}")
            
            # Also print to console
            print(f"Error in {func.__name__}: {err}")
            print(errors)
            
            # Optionally notify user
            try:
                await message.reply_text(
                    "❌ An error occurred while processing your request. "
                    "The error has been logged."
                )
            except:
                pass
            
            raise err
    
    return capture
