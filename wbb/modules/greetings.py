"""
Greetings Module - Welcome and Goodbye Messages
Stores welcome/goodbye settings in SQLite.
"""
import json
import sqlite3
from pathlib import Path
from pyrogram import filters
from pyrogram.types import ChatMemberUpdated, Message
from wbb import app
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly

__MODULE__ = "Greetings"
__HELP__ = """
/setwelcome [message] - Set welcome message
/delwelcome - Delete welcome message
/welcome - Get current welcome message
/setgoodbye [message] - Set goodbye message
/delgoodbye - Delete goodbye message
/goodbye - Get current goodbye message

**Variables:**
{mention} - Mention the user
{name} - User's first name
{chat} - Chat name
{count} - Member count
"""

# SQLite helper
def get_db():
    conn = sqlite3.connect(Path("wbb.sqlite"))
    conn.row_factory = sqlite3.Row
    return conn

def init_greetings_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS greetings (
            chat_id INTEGER PRIMARY KEY,
            welcome_message TEXT,
            goodbye_message TEXT,
            welcome_enabled INTEGER DEFAULT 1,
            goodbye_enabled INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

init_greetings_table()

# Helper functions
async def get_welcome(chat_id: int):
    """Get welcome message."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        cursor = conn.execute(
            "SELECT welcome_message, welcome_enabled FROM greetings WHERE chat_id = ?",
            (chat_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row and row["welcome_enabled"]:
            return row["welcome_message"]
        return None
    
    return await loop.run_in_executor(None, db_op)

async def set_welcome(chat_id: int, message: str):
    """Set welcome message."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        conn.execute("""
            INSERT INTO greetings (chat_id, welcome_message, welcome_enabled)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id)
            DO UPDATE SET welcome_message = ?, welcome_enabled = 1
        """, (chat_id, message, message))
        conn.commit()
        conn.close()
    
    await loop.run_in_executor(None, db_op)

async def delete_welcome(chat_id: int):
    """Delete welcome message."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        conn.execute(
            "UPDATE greetings SET welcome_enabled = 0 WHERE chat_id = ?",
            (chat_id,)
        )
        conn.commit()
        conn.close()
    
    await loop.run_in_executor(None, db_op)

async def get_goodbye(chat_id: int):
    """Get goodbye message."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        cursor = conn.execute(
            "SELECT goodbye_message, goodbye_enabled FROM greetings WHERE chat_id = ?",
            (chat_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row and row["goodbye_enabled"]:
            return row["goodbye_message"]
        return None
    
    return await loop.run_in_executor(None, db_op)

async def set_goodbye(chat_id: int, message: str):
    """Set goodbye message."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        conn.execute("""
            INSERT INTO greetings (chat_id, goodbye_message, goodbye_enabled)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id)
            DO UPDATE SET goodbye_message = ?, goodbye_enabled = 1
        """, (chat_id, message, message))
        conn.commit()
        conn.close()
    
    await loop.run_in_executor(None, db_op)

async def delete_goodbye(chat_id: int):
    """Delete goodbye message."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        conn.execute(
            "UPDATE greetings SET goodbye_enabled = 0 WHERE chat_id = ?",
            (chat_id,)
        )
        conn.commit()
        conn.close()
    
    await loop.run_in_executor(None, db_op)

# Commands
@app.on_message(filters.command("setwelcome") & filters.group)
@adminsOnly("can_change_info")
async def set_welcome_cmd(_, message: Message):
    """Set welcome message."""
    if len(message.text.split(None, 1)) < 2:
        return await message.reply_text(
            "Usage: /setwelcome [message]\n\n"
            "Variables: {mention}, {name}, {chat}, {count}"
        )
    
    welcome_text = message.text.split(None, 1)[1]
    await set_welcome(message.chat.id, welcome_text)
    await message.reply_text("✅ Welcome message set!")

@app.on_message(filters.command("delwelcome") & filters.group)
@adminsOnly("can_change_info")
async def delete_welcome_cmd(_, message: Message):
    """Delete welcome message."""
    await delete_welcome(message.chat.id)
    await message.reply_text("✅ Welcome message deleted!")

@app.on_message(filters.command("welcome") & filters.group)
@capture_err
async def get_welcome_cmd(_, message: Message):
    """Get welcome message."""
    welcome = await get_welcome(message.chat.id)
    
    if not welcome:
        return await message.reply_text("No welcome message set.")
    
    await message.reply_text(f"**Current welcome message:**\n\n{welcome}")

@app.on_message(filters.command("setgoodbye") & filters.group)
@adminsOnly("can_change_info")
async def set_goodbye_cmd(_, message: Message):
    """Set goodbye message."""
    if len(message.text.split(None, 1)) < 2:
        return await message.reply_text(
            "Usage: /setgoodbye [message]\n\n"
            "Variables: {mention}, {name}, {chat}, {count}"
        )
    
    goodbye_text = message.text.split(None, 1)[1]
    await set_goodbye(message.chat.id, goodbye_text)
    await message.reply_text("✅ Goodbye message set!")

@app.on_message(filters.command("delgoodbye") & filters.group)
@adminsOnly("can_change_info")
async def delete_goodbye_cmd(_, message: Message):
    """Delete goodbye message."""
    await delete_goodbye(message.chat.id)
    await message.reply_text("✅ Goodbye message deleted!")

@app.on_message(filters.command("goodbye") & filters.group)
@capture_err
async def get_goodbye_cmd(_, message: Message):
    """Get goodbye message."""
    goodbye = await get_goodbye(message.chat.id)
    
    if not goodbye:
        return await message.reply_text("No goodbye message set.")
    
    await message.reply_text(f"**Current goodbye message:**\n\n{goodbye}")

# Event handlers
@app.on_chat_member_updated(filters.group)
async def welcome_user(_, update: ChatMemberUpdated):
    """Send welcome message on user join."""
    if not update.new_chat_member:
        return
    
    # Check if user joined
    if (
        update.new_chat_member.status not in ["member", "administrator"]
        or update.old_chat_member
        and update.old_chat_member.status not in ["banned", "left", "restricted"]
    ):
        return
    
    welcome = await get_welcome(update.chat.id)
    
    if not welcome:
        return
    
    user = update.new_chat_member.user
    chat = update.chat
    count = await app.get_chat_members_count(chat.id)
    
    # Replace variables
    welcome = welcome.replace("{mention}", user.mention)
    welcome = welcome.replace("{name}", user.first_name)
    welcome = welcome.replace("{chat}", chat.title)
    welcome = welcome.replace("{count}", str(count))
    
    await app.send_message(chat.id, welcome)

@app.on_chat_member_updated(filters.group)
async def goodbye_user(_, update: ChatMemberUpdated):
    """Send goodbye message on user leave."""
    if not update.old_chat_member:
        return
    
    # Check if user left
    if (
        update.new_chat_member.status not in ["banned", "left", "restricted"]
        or update.old_chat_member.status not in ["member", "administrator"]
    ):
        return
    
    goodbye = await get_goodbye(update.chat.id)
    
    if not goodbye:
        return
    
    user = update.old_chat_member.user
    chat = update.chat
    count = await app.get_chat_members_count(chat.id)
    
    # Replace variables
    goodbye = goodbye.replace("{mention}", user.mention)
    goodbye = goodbye.replace("{name}", user.first_name)
    goodbye = goodbye.replace("{chat}", chat.title)
    goodbye = goodbye.replace("{count}", str(count))
    
async def send_welcome_message(chat, user_id, delete: bool = False):
    """Send welcome message to a user (for compatibility with autoapprove)."""
    welcome = await get_welcome(chat.id)
    
    if not welcome:
        return
    
    try:
        user = await app.get_users(user_id)
        chat_info = await app.get_chat(chat.id)
        count = await app.get_chat_members_count(chat.id)
        
        # Replace variables
        welcome_msg = welcome.replace("{mention}", user.mention)
        welcome_msg = welcome_msg.replace("{name}", user.first_name or "")
        welcome_msg = welcome_msg.replace("{chat}", chat_info.title)
        welcome_msg = welcome_msg.replace("{count}", str(count))
        
        await app.send_message(chat.id, welcome_msg)
    except Exception as e:
        print(f"Error sending welcome message: {e}")


async def handle_new_member(member, chat):
    """Handle new member join (for compatibility with autoapprove)."""
    await send_welcome_message(chat, member.id)
