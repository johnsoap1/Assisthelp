"""
Anonymous Media Repost - Fully Self-Contained Production Version
Persistent | SQLite | Restart Safe
"""

import asyncio
import sqlite3
import time
from collections import defaultdict, deque

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageDeleteForbidden, ChatAdminRequired, MediaEmpty

from wbb import app, SUDOERS_SET
from wbb.core.decorators.errors import capture_err


# =========================
# DATABASE SETUP
# =========================

conn = sqlite3.connect("anon_media.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    rate_limit_count INTEGER DEFAULT 10,
    rate_limit_window INTEGER DEFAULT 30,
    media_types TEXT DEFAULT 'photo,video,document,audio,voice,animation,sticker,video_note',
    total_reposted INTEGER DEFAULT 0,
    total_deleted INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS whitelist (
    chat_id INTEGER,
    user_id INTEGER
)
""")

conn.commit()


# =========================
# RATE LIMIT MEMORY CACHE
# =========================

rate_cache = defaultdict(lambda: deque())


# =========================
# DB HELPERS
# =========================

def get_chat(chat_id):
    cursor.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,))
    return cursor.fetchone()


def create_chat(chat_id):
    cursor.execute("INSERT OR IGNORE INTO chats (chat_id, enabled) VALUES (?, 0)", (chat_id,))
    conn.commit()


def is_enabled(chat_id):
    create_chat(chat_id)
    cursor.execute("SELECT enabled FROM chats WHERE chat_id=?", (chat_id,))
    return cursor.fetchone()[0] == 1


def enable_chat(chat_id):
    create_chat(chat_id)
    cursor.execute("UPDATE chats SET enabled=1 WHERE chat_id=?", (chat_id,))
    conn.commit()


def disable_chat(chat_id):
    cursor.execute("UPDATE chats SET enabled=0 WHERE chat_id=?", (chat_id,))
    conn.commit()


def get_whitelist(chat_id):
    cursor.execute("SELECT user_id FROM whitelist WHERE chat_id=?", (chat_id,))
    return [x[0] for x in cursor.fetchall()]


def add_whitelist(chat_id, user_id):
    cursor.execute("INSERT INTO whitelist (chat_id, user_id) VALUES (?,?)", (chat_id, user_id))
    conn.commit()


def remove_whitelist(chat_id, user_id):
    cursor.execute("DELETE FROM whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()


def update_stats(chat_id, field):
    cursor.execute(f"UPDATE chats SET {field} = {field} + 1 WHERE chat_id=?", (chat_id,))
    conn.commit()


# =========================
# MEDIA CHECK
# =========================

def is_supported(message: Message, allowed):
    mapping = {
        "photo": message.photo,
        "video": message.video,
        "document": message.document,
        "audio": message.audio,
        "voice": message.voice,
        "animation": message.animation,
        "sticker": message.sticker,
        "video_note": message.video_note,
    }
    return any(mapping[t] for t in allowed if t in mapping)


# =========================
# SAFE FUNCTIONS
# =========================

async def safe_delete(message: Message):
    try:
        await message.delete()
        return True
    except (MessageDeleteForbidden, ChatAdminRequired):
        return False
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await safe_delete(message)
    except Exception:
        return False


async def safe_send(message: Message):
    chat_id = message.chat.id
    try:
        if message.photo:
            await app.send_photo(chat_id, message.photo.file_id, caption=message.caption or "")
        elif message.video:
            await app.send_video(chat_id, message.video.file_id, caption=message.caption or "")
        elif message.document:
            await app.send_document(chat_id, message.document.file_id, caption=message.caption or "")
        elif message.audio:
            await app.send_audio(chat_id, message.audio.file_id, caption=message.caption or "")
        elif message.voice:
            await app.send_voice(chat_id, message.voice.file_id)
        elif message.animation:
            await app.send_animation(chat_id, message.animation.file_id)
        elif message.sticker:
            await app.send_sticker(chat_id, message.sticker.file_id)
        elif message.video_note:
            await app.send_video_note(chat_id, message.video_note.file_id)
        else:
            return False
        return True
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await safe_send(message)
    except MediaEmpty:
        return False
    except Exception:
        return False


# =========================
# MAIN HANDLER
# =========================

@app.on_message(filters.group & ~filters.service, group=100)
@capture_err
async def anonymous_handler(_, message: Message):

    chat_id = message.chat.id

    if not is_enabled(chat_id):
        return

    if not message.from_user or message.from_user.is_bot:
        return

    whitelist = get_whitelist(chat_id)
    if message.from_user.id in whitelist:
        return

    cursor.execute("SELECT rate_limit_count, rate_limit_window, media_types FROM chats WHERE chat_id=?", (chat_id,))
    rate_count, rate_window, media_types = cursor.fetchone()

    allowed = media_types.split(",")

    if not is_supported(message, allowed):
        return

    # Rate limit
    now = time.time()
    queue = rate_cache[chat_id]

    while queue and now - queue[0] > rate_window:
        queue.popleft()

    if len(queue) >= rate_count:
        return

    queue.append(now)

    deleted = await safe_delete(message)
    if not deleted:
        update_stats(chat_id, "total_errors")
        return

    update_stats(chat_id, "total_deleted")

    sent = await safe_send(message)
    if sent:
        update_stats(chat_id, "total_reposted")
    else:
        update_stats(chat_id, "total_errors")


# =========================
# COMMANDS
# =========================

@app.on_message(filters.command("anon_enable") & filters.user(list(SUDOERS_SET)))
async def cmd_enable(_, message: Message):
    chat_id = int(message.command[1])
    enable_chat(chat_id)
    await message.reply("Anonymous enabled.")


@app.on_message(filters.command("anon_disable") & filters.user(list(SUDOERS_SET)))
async def cmd_disable(_, message: Message):
    chat_id = int(message.command[1])
    disable_chat(chat_id)
    await message.reply("Anonymous disabled.")


@app.on_message(filters.command("anon_whitelist_add") & filters.user(list(SUDOERS_SET)))
async def cmd_w_add(_, message: Message):
    chat_id = int(message.command[1])
    user_id = int(message.command[2])
    add_whitelist(chat_id, user_id)
    await message.reply("User added to whitelist.")


@app.on_message(filters.command("anon_whitelist_remove") & filters.user(list(SUDOERS_SET)))
async def cmd_w_remove(_, message: Message):
    chat_id = int(message.command[1])
    user_id = int(message.command[2])
    remove_whitelist(chat_id, user_id)
    await message.reply("User removed from whitelist.")


@app.on_message(filters.command("anon_stats") & filters.user(list(SUDOERS_SET)))
async def cmd_stats(_, message: Message):
    chat_id = int(message.command[1])
    cursor.execute("SELECT total_reposted, total_deleted, total_errors FROM chats WHERE chat_id=?", (chat_id,))
    r, d, e = cursor.fetchone()
    await message.reply(f"Reposted: {r}\nDeleted: {d}\nErrors: {e}")
