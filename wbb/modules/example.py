# wbb/modules/example.py
"""Example module for reference."""
from pyrogram import filters
from pyrogram.types import Message
from wbb import app
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly

__MODULE__ = "Example"
__HELP__ = """
**Example Module**

Commands:
- /example - Example command
"""

@app.on_message(filters.command("example") & filters.group)
@capture_err
@adminsOnly("can_change_info")
async def example_command(_, message: Message):
    """Example command handler."""
    await message.reply_text("This is an example command!")
