"""
Notes Module for AssistBot
Save and retrieve notes in chats using SQLite.
"""
import json
import re
import sqlite3
from pathlib import Path
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message
from wbb import app
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly
from wbb.core.keyboard import ikb
from wbb.utils.functions import extract_text_and_keyb

__MODULE__ = "Notes"
__HELP__ = """
/notes - Get all notes in the chat
/save [note_name] - Save a note (reply to message)
/get [note_name] or #note_name - Get a note
/delete [note_name] - Delete a note
"""

# SQLite helper
def get_db():
    conn = sqlite3.connect(Path("wbb.sqlite"))
    conn.row_factory = sqlite3.Row
    return conn

def init_notes_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            chat_id INTEGER,
            note_name TEXT,
            note_type TEXT,
            note_content TEXT,
            file_id TEXT,
            PRIMARY KEY (chat_id, note_name)
        )
    """)
    conn.commit()
    conn.close()

init_notes_table()

# Helper functions
async def get_note(chat_id: int, note_name: str):
    """Get a note from database."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        cursor = conn.execute(
            "SELECT * FROM notes WHERE chat_id = ? AND note_name = ?",
            (chat_id, note_name.lower())
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "type": row["note_type"],
                "content": row["note_content"],
                "file_id": row["file_id"]
            }
        return None
    
    return await loop.run_in_executor(None, db_op)

async def save_note(chat_id: int, note_name: str, note_data: dict):
    """Save a note to database."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        conn.execute("""
            INSERT INTO notes (chat_id, note_name, note_type, note_content, file_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, note_name)
            DO UPDATE SET note_type = ?, note_content = ?, file_id = ?
        """, (
            chat_id, note_name.lower(),
            note_data.get("type", "text"),
            note_data.get("content", ""),
            note_data.get("file_id"),
            note_data.get("type", "text"),
            note_data.get("content", ""),
            note_data.get("file_id")
        ))
        conn.commit()
        conn.close()
    
    await loop.run_in_executor(None, db_op)

async def delete_note(chat_id: int, note_name: str):
    """Delete a note from database."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        conn.execute(
            "DELETE FROM notes WHERE chat_id = ? AND note_name = ?",
            (chat_id, note_name.lower())
        )
        conn.commit()
        conn.close()
    
    await loop.run_in_executor(None, db_op)

async def get_all_notes(chat_id: int):
    """Get all notes for a chat."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def db_op():
        conn = get_db()
        cursor = conn.execute(
            "SELECT note_name FROM notes WHERE chat_id = ?",
            (chat_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [row["note_name"] for row in rows]
    
    return await loop.run_in_executor(None, db_op)


def extract_urls(reply_markup):
    """Extract URLs from inline keyboard markup."""
    urls = []
    if not reply_markup or not hasattr(reply_markup, 'inline_keyboard'):
        return urls
    
    for row in reply_markup.inline_keyboard:
        for button in row:
            if hasattr(button, 'url') and button.url:
                # Extract button text and URL
                text = getattr(button, 'text', '')
                url = button.url
                # Use button text as name, or generate one
                name = text if text else f"button_{len(urls) + 1}"
                urls.append((name, text, url))
    
    return urls

# Commands
@app.on_message(filters.command("save") & filters.group)
@adminsOnly("can_change_info")
async def save_note_cmd(_, message: Message):
    """Save a note."""
    if len(message.command) < 2:
        return await message.reply_text("Usage: /save [note_name] (reply to a message)")
    
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to save it as a note.")
    
    note_name = message.command[1].lower()
    replied = message.reply_to_message
    
    note_data = {"type": "text", "content": "", "file_id": None}
    
    if replied.text:
        note_data["content"] = replied.text
        note_data["type"] = "text"
    elif replied.photo:
        note_data["file_id"] = replied.photo.file_id
        note_data["type"] = "photo"
        note_data["content"] = replied.caption or ""
    elif replied.video:
        note_data["file_id"] = replied.video.file_id
        note_data["type"] = "video"
        note_data["content"] = replied.caption or ""
    elif replied.document:
        note_data["file_id"] = replied.document.file_id
        note_data["type"] = "document"
        note_data["content"] = replied.caption or ""
    elif replied.audio:
        note_data["file_id"] = replied.audio.file_id
        note_data["type"] = "audio"
        note_data["content"] = replied.caption or ""
    elif replied.voice:
        note_data["file_id"] = replied.voice.file_id
        note_data["type"] = "voice"
    elif replied.sticker:
        note_data["file_id"] = replied.sticker.file_id
        note_data["type"] = "sticker"
    else:
        return await message.reply_text("Unsupported message type.")
    
    await save_note(message.chat.id, note_name, note_data)
    await message.reply_text(f"Saved note: `{note_name}`")

@app.on_message(filters.command("get") & filters.group)
@capture_err
async def get_note_cmd(_, message: Message):
    """Get a note."""
    if len(message.command) < 2:
        return await message.reply_text("Usage: /get [note_name]")
    
    note_name = message.command[1].lower()
    note = await get_note(message.chat.id, note_name)
    
    if not note:
        return await message.reply_text(f"Note `{note_name}` not found.")
    
    note_type = note["type"]
    content = note["content"]
    file_id = note["file_id"]
    
    if note_type == "text":
        await message.reply_text(content)
    elif note_type == "photo":
        await message.reply_photo(file_id, caption=content)
    elif note_type == "video":
        await message.reply_video(file_id, caption=content)
    elif note_type == "document":
        await message.reply_document(file_id, caption=content)
    elif note_type == "audio":
        await message.reply_audio(file_id, caption=content)
    elif note_type == "voice":
        await message.reply_voice(file_id)
    elif note_type == "sticker":
        await message.reply_sticker(file_id)

@app.on_message(filters.regex(r"^#\w+") & filters.group)
@capture_err
async def get_note_hashtag(_, message: Message):
    """Get note using #hashtag."""
    note_name = message.text.split()[0][1:].lower()  # Remove # and get note name
    note = await get_note(message.chat.id, note_name)
    
    if not note:
        return
    
    note_type = note["type"]
    content = note["content"]
    file_id = note["file_id"]
    
    if note_type == "text":
        await message.reply_text(content)
    elif note_type == "photo":
        await message.reply_photo(file_id, caption=content)
    elif note_type == "video":
        await message.reply_video(file_id, caption=content)
    elif note_type == "document":
        await message.reply_document(file_id, caption=content)
    elif note_type == "audio":
        await message.reply_audio(file_id, caption=content)
    elif note_type == "voice":
        await message.reply_voice(file_id)
    elif note_type == "sticker":
        await message.reply_sticker(file_id)

@app.on_message(filters.command("delete") & filters.group)
@adminsOnly("can_change_info")
async def delete_note_cmd(_, message: Message):
    """Delete a note."""
    if len(message.command) < 2:
        return await message.reply_text("Usage: /delete [note_name]")
    
    note_name = message.command[1].lower()
    note = await get_note(message.chat.id, note_name)
    
    if not note:
        return await message.reply_text(f"Note `{note_name}` not found.")
    
    await delete_note(message.chat.id, note_name)
    await message.reply_text(f"Deleted note: `{note_name}`")

@app.on_message(filters.command("notes") & filters.group)
@capture_err
async def list_notes(_, message: Message):
    """List all notes."""
    notes = await get_all_notes(message.chat.id)
    
    if not notes:
        return await message.reply_text("No notes saved in this chat.")
    
    text = "**Saved Notes:**\n\n"
    for i, note in enumerate(notes, 1):
        text += f"{i}. `{note}` - Get with `/get {note}` or `#{note}`\n"
    
    await message.reply_text(text)
