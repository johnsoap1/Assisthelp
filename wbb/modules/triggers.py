"""
Enhanced Triggers Module v2 

Features:
- Global + Local triggers
- Multiple responses (text/media)
- Sentence or word matching
- Randomized responses
- Regex support
- MongoDB + in-memory fallback
- Anti-spam cooldown
"""

import re
import time
import random
from typing import Dict, List, Optional

from pyrogram import filters
from pyrogram.types import Message
from wbb import app

try:
    from wbb import SUDOERS, SUDOERS_SET
except ImportError:
    SUDOERS, SUDOERS_SET = [], set()

try:
    from wbb.core.storage import db
    triggers_db = db.triggers
    stats_db = db.trigger_stats
except Exception:
    triggers_db = None
    stats_db = None
    triggers_storage = {}
    stats_storage = {}

# In-memory storage for cooldowns
trigger_cooldowns: Dict[int, Dict[str, float]] = {}

# Constants
COOLDOWN_TIME = 5  # seconds between trigger uses per user


async def is_trigger_admin(chat_id: int, user_id: int) -> bool:
    """Check if user has permission to manage triggers in a chat."""
    if user_id in SUDOERS_SET:
        return True
    
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except:
        return False


async def add_trigger(chat_id: int, trigger: str, response: str,
                     is_global=False, is_media=False,
                     file_id=None, file_type=None, use_regex=False):
    """Create or append a trigger response."""
    query = {"chat_id": 0 if is_global else chat_id, "trigger": trigger.lower()}
    response_entry = {
        "text": response,
        "is_media": is_media,
        "file_id": file_id,
        "file_type": file_type,
        "added_at": time.time()
    }

    if triggers_db is not None:
        existing = await triggers_db.find_one(query)
        if existing:
            await triggers_db.update_one(query, {"$push": {"responses": response_entry}})
        else:
            await triggers_db.insert_one({
                **query,
                "use_regex": use_regex,
                "created_at": time.time(),
                "usage_count": 0,
                "responses": [response_entry]
            })
    else:
        key = f"{0 if is_global else chat_id}:{trigger.lower()}"
        data = triggers_storage.setdefault(key, {
            "chat_id": 0 if is_global else chat_id,
            "trigger": trigger.lower(),
            "responses": [],
            "use_regex": use_regex,
            "usage_count": 0
        })
        data["responses"].append(response_entry)


async def remove_trigger(chat_id: int, trigger: str, is_global=False) -> bool:
    query = {"chat_id": 0 if is_global else chat_id, "trigger": trigger.lower()}
    if triggers_db is not None:
        result = await triggers_db.delete_many(query)
        return result.deleted_count > 0
    else:
        key = f"{0 if is_global else chat_id}:{trigger.lower()}"
        if key in triggers_storage:
            del triggers_storage[key]
            return True
        return False


async def get_chat_triggers(chat_id: int, include_global=True) -> List[Dict]:
    if triggers_db is not None:
        if include_global:
            cursor = await triggers_db.find({"$or": [{"chat_id": chat_id}, {"chat_id": 0}]})
        else:
            cursor = await triggers_db.find({"chat_id": chat_id})
        return await cursor.to_list(length=None)
    else:
        # Fallback to in-memory
        return [v for v in triggers_storage.values() if v.get("chat_id") == chat_id or (include_global and v.get("chat_id") == 0)]


async def record_trigger_usage(chat_id: int, trigger: str):
    """Record trigger usage for statistics."""
    if stats_db is not None:
        await stats_db.update_one(
            {"chat_id": chat_id, "trigger": trigger.lower()},
            {"$inc": {"count": 1}, "$set": {"last_used": time.time()}},
            upsert=True
        )
    else:
        key = f"{chat_id}:{trigger.lower()}"
        if key not in stats_storage:
            stats_storage[key] = {"count": 0, "last_used": 0}
        stats_storage[key]["count"] += 1
        stats_storage[key]["last_used"] = time.time()


async def check_cooldown(user_id: int, trigger: str) -> bool:
    """Check if user is on cooldown for a trigger."""
    now = time.time()

    if user_id not in trigger_cooldowns:
        trigger_cooldowns[user_id] = {}

    last_used = trigger_cooldowns[user_id].get(trigger, 0)
    if now - last_used < COOLDOWN_TIME:
        return False

    trigger_cooldowns[user_id][trigger] = now
    return True


# Command handlers

@app.on_message(filters.command("addtrigger") & filters.group)
async def add_trigger_cmd(_, message: Message):
    if not await is_trigger_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ You need admin rights.")

    parts = message.text.split(None, 1)
    if len(parts) < 2 or "-" not in parts[1]:
        return await message.reply_text("Usage: /addtrigger <trigger> - <response>")

    trigger, response = map(str.strip, parts[1].split("-", 1))
    if not trigger or not response:
        return await message.reply_text("❌ Invalid format.")

    await add_trigger(message.chat.id, trigger, response)
    await message.reply_text(f"✅ Added trigger for **{trigger}**\n🗣 Response: {response}")


@app.on_message(filters.command("addglobaltrigger") & filters.group)
async def add_global_trigger_cmd(_, message: Message):
    """Add a global text trigger (Sudo only)."""
    if message.from_user.id not in SUDOERS_SET:
        return await message.reply_text("❌ This command is only for sudo users!")

    parts = message.text.split(None, 1)
    if len(parts) < 2 or "-" not in parts[1]:
        return await message.reply_text("Usage: /addglobaltrigger <trigger> - <response>")

    trigger, response = map(str.strip, parts[1].split("-", 1))
    if not trigger or not response:
        return await message.reply_text("❌ Invalid format. Use: /addglobaltrigger hello - Hello World!")

    await add_trigger(0, trigger, response, is_global=True)
    await message.reply_text(f"✅ Added GLOBAL trigger for **{trigger}**\n🗣 Response: {response}")


@app.on_message(filters.command("deltrigger") & filters.group)
async def del_trigger_cmd(_, message: Message):
    if not await is_trigger_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Admins only.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /deltrigger <trigger>")
    trig = message.command[1]
    ok = await remove_trigger(message.chat.id, trig)
    await message.reply_text("✅ Deleted." if ok else "❌ Not found.")


@app.on_message(filters.command("delglobaltrigger") & filters.group)
async def del_global_trigger_cmd(_, message: Message):
    """Delete a global trigger (Sudo only)."""
    if message.from_user.id not in SUDOERS_SET:
        return await message.reply_text("❌ This command is only for sudo users!")
    
    if len(message.command) < 2:
        return await message.reply_text("Usage: /delglobaltrigger <trigger>")
    
    trigger = message.command[1]
    deleted = await remove_trigger(0, trigger, is_global=True)
    
    if deleted:
        await message.reply_text(f"✅ Deleted GLOBAL trigger **{trigger}**")
    else:
        await message.reply_text(f"❌ No global trigger found for **{trigger}**")


@app.on_message(filters.command("addmediatrigger") & filters.group)
async def add_media_trigger_cmd(_, message: Message):
    """Add a media trigger (photo/video/document/audio/sticker/gif)."""
    if not await is_trigger_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ You need admin permissions to use this command!")

    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a media message to create a trigger!")

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: Reply to a media and use /addmediatrigger <trigger_word>\n"
            "Example: Reply to a photo, then /addmediatrigger hello"
        )

    trigger = " ".join(message.command[1:]).lower()
    replied_msg = message.reply_to_message

    # Determine media type
    file_type = None
    file_id = None

    if replied_msg.photo:
        file_type = "photo"
        file_id = replied_msg.photo.file_id
    elif replied_msg.video:
        file_type = "video"
        file_id = replied_msg.video.file_id
    elif replied_msg.animation:
        file_type = "gif"
        file_id = replied_msg.animation.file_id
    elif replied_msg.document:
        file_type = "document"
        file_id = replied_msg.document.file_id
    elif replied_msg.audio:
        file_type = "audio"
        file_id = replied_msg.audio.file_id
    elif replied_msg.voice:
        file_type = "voice"
        file_id = replied_msg.voice.file_id
    elif replied_msg.sticker:
        file_type = "sticker"
        file_id = replied_msg.sticker.file_id

    if not file_type or not file_id:
        return await message.reply_text("❌ Unsupported media type! Supported: photo, video, gif, document, audio, voice, sticker")

    caption = replied_msg.caption or ""
    await add_trigger(
        message.chat.id,
        trigger,
        caption,
        is_media=True,
        file_type=file_type,
        file_id=file_id
    )

    await message.reply_text(f"✅ Added {file_type} trigger for **{trigger}**")


@app.on_message(filters.command("addglobalmediatrigger") & filters.group)
async def add_global_media_trigger_cmd(_, message: Message):
    """Add a global media trigger (sudo only)."""
    if message.from_user.id not in SUDOERS_SET:
        return await message.reply_text("❌ This command is only for sudo users!")

    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a media message to create a trigger!")

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: Reply to a media and use /addglobalmediatrigger <trigger_word>\n"
            "Example: Reply to a photo, then /addglobalmediatrigger hello"
        )

    trigger = " ".join(message.command[1:]).lower()
    replied_msg = message.reply_to_message

    # Determine media type
    file_type = None
    file_id = None

    if replied_msg.photo:
        file_type = "photo"
        file_id = replied_msg.photo.file_id
    elif replied_msg.video:
        file_type = "video"
        file_id = replied_msg.video.file_id
    elif replied_msg.animation:
        file_type = "gif"
        file_id = replied_msg.animation.file_id
    elif replied_msg.document:
        file_type = "document"
        file_id = replied_msg.document.file_id
    elif replied_msg.audio:
        file_type = "audio"
        file_id = replied_msg.audio.file_id
    elif replied_msg.voice:
        file_type = "voice"
        file_id = replied_msg.voice.file_id
    elif replied_msg.sticker:
        file_type = "sticker"
        file_id = replied_msg.sticker.file_id

    if not file_type or not file_id:
        return await message.reply_text("❌ Unsupported media type! Supported: photo, video, gif, document, audio, voice, sticker")

    caption = replied_msg.caption or ""
    await add_trigger(
        0,
        trigger,
        caption,
        is_global=True,
        is_media=True,
        file_type=file_type,
        file_id=file_id
    )

    await message.reply_text(f"✅ Added GLOBAL {file_type} trigger for **{trigger}**")


@app.on_message(filters.command("addstickertrigger") & filters.group)
async def add_sticker_trigger_cmd(_, message: Message):
    """Add a sticker trigger (shortcut for addmediatrigger with stickers)."""
    if not await is_trigger_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ You need admin permissions to use this command!")

    if not message.reply_to_message or not message.reply_to_message.sticker:
        return await message.reply_text("❌ Reply to a sticker to create a trigger!")

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: Reply to a sticker and use /addstickertrigger <trigger_word>\n"
            "Example: Reply to a sticker, then /addstickertrigger happy"
        )

    trigger = " ".join(message.command[1:]).lower()
    sticker = message.reply_to_message.sticker

    await add_trigger(
        message.chat.id,
        trigger,
        "",
        is_media=True,
        file_type="sticker",
        file_id=sticker.file_id
    )

    await message.reply_text(f"✅ Added sticker trigger for **{trigger}**")


@app.on_message(filters.command("addglobalstickertrigger") & filters.group)
async def add_global_sticker_trigger_cmd(_, message: Message):
    """Add a global sticker trigger (sudo only)."""
    if message.from_user.id not in SUDOERS_SET:
        return await message.reply_text("❌ This command is only for sudo users!")

    if not message.reply_to_message or not message.reply_to_message.sticker:
        return await message.reply_text("❌ Reply to a sticker to create a global trigger!")

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: Reply to a sticker and use /addglobalstickertrigger <trigger_word>\n"
            "Example: Reply to a sticker, then /addglobalstickertrigger awesome"
        )

    trigger = " ".join(message.command[1:]).lower()
    sticker = message.reply_to_message.sticker

    await add_trigger(
        0,
        trigger,
        "",
        is_global=True,
        is_media=True,
        file_type="sticker",
        file_id=sticker.file_id
    )

    await message.reply_text(f"✅ Added GLOBAL sticker trigger for **{trigger}**")


@app.on_message(filters.command("triggers") & filters.group)
async def list_triggers_cmd(_, message: Message):
    """List all triggers for the current chat."""
    triggers = await get_chat_triggers(message.chat.id)

    if not triggers:
        return await message.reply_text("No triggers set up in this chat yet!")

    global_triggers = [t for t in triggers if t["chat_id"] == 0]
    chat_triggers = [t for t in triggers if t["chat_id"] != 0]

    response = []

    if global_triggers:
        response.append("🌍 **Global Triggers** (work everywhere):")
        for i, t in enumerate(global_triggers, 1):
            count = len(t.get("responses", []))
            response.append(f"{i}. **{t['trigger']}** ({count} response{'s' if count != 1 else ''})")

    if chat_triggers:
        if response:
            response.append("")
        response.append("💬 **Chat Triggers** (this chat only):")
        for i, t in enumerate(chat_triggers, 1):
            count = len(t.get("responses", []))
            response.append(f"{i}. **{t['trigger']}** ({count} response{'s' if count != 1 else ''})")

    await message.reply_text("\n".join(response))


# Message handler for triggers
@app.on_message(filters.group & filters.text & filters.incoming)
async def trigger_handler(_, message: Message):
    """Handle trigger matching for incoming messages."""
    # Skip if service message, command, or from anonymous admin
    if message.service or not message.from_user or message.text.startswith("/"):
        return
    
    text = message.text.strip().lower()
    if not text:
        return

    # Get all triggers for this chat
    triggers = await get_chat_triggers(message.chat.id)
    if not triggers:
        return

    # Collect ALL matching responses from all triggers
    all_matching_responses = []
    matched_trigger_text = None

    # Check each trigger
    for trig in triggers:
        trigger_text = trig["trigger"].strip().lower()
        
        # Skip empty triggers
        if not trigger_text:
            continue

        matched = False

        # Regex matching
        if trig.get("use_regex", False):
            try:
                if re.search(trigger_text, text, re.IGNORECASE):
                    matched = True
            except re.error:
                continue
        # Phrase matching (contains spaces = exact phrase)
        elif " " in trigger_text:
            if trigger_text in text:
                matched = True
        # STRICT single word trigger rules
        # 1. Trigger must be EXACT message OR
        # 2. Trigger must be FIRST word
        else:
            words = text.split()

            # exact message
            if text == trigger_text:
                matched = True

            # first word match
            elif words and words[0] == trigger_text:
                matched = True

        # If matched, collect ALL responses from this trigger
        if matched:
            responses = trig.get("responses", [])
            for response in responses:
                all_matching_responses.append({
                    "trigger": trigger_text,
                    "response": response
                })
            if not matched_trigger_text:
                matched_trigger_text = trigger_text

    # If we found any matching responses, pick one randomly and send it
    if all_matching_responses:
        await handle_trigger_match(message, matched_trigger_text, all_matching_responses)


async def handle_trigger_match(message: Message, trigger_text: str, all_responses: List[Dict]):
    """Handle a matched trigger by sending one random response from all available."""
    # Check cooldown
    if not await check_cooldown(message.from_user.id, trigger_text):
        return
    
    # Record usage
    await record_trigger_usage(message.chat.id, trigger_text)

    # Pick ONE random response from all available responses
    selected = random.choice(all_responses)
    r = selected["response"]
    
    text = r.get("text", "")
    is_media = r.get("is_media", False)
    fid = r.get("file_id")
    ftype = r.get("file_type")

    try:
        if is_media and fid:
            if ftype == "photo":
                await message.reply_photo(fid, caption=text or None)
            elif ftype == "video":
                await message.reply_video(fid, caption=text or None)
            elif ftype == "gif":
                await message.reply_animation(fid, caption=text or None)
            elif ftype == "document":
                await message.reply_document(fid, caption=text or None)
            elif ftype == "audio":
                await message.reply_audio(fid, caption=text or None)
            elif ftype == "voice":
                await message.reply_voice(fid, caption=text or None)
            elif ftype == "sticker":
                await message.reply_sticker(fid)
        elif text:
            await message.reply_text(text)
    except Exception as e:
        print(f"Error sending trigger response: {e}")


__MODULE__ = "Triggers"
__HELP__ = """
**Enhanced Triggers Module v2**

Set up automatic responses to specific words or phrases in your group.

**Text Triggers (Local - Chat Only):**
- `/addtrigger <trigger> - <response>` - Add a new text trigger
- `/deltrigger <trigger>` - Delete a local trigger (admin only)
- `/triggers` - List all triggers in this chat

**Text Triggers (Global - All Chats, Sudo Only):**
- `/addglobaltrigger <trigger> - <response>` - Add a global text trigger
- `/delglobaltrigger <trigger>` - Delete a global trigger (sudo only)

**Media Triggers (Local - Chat Only):**
- `/addmediatrigger <trigger>` - Reply to any media to create a trigger
- `/addstickertrigger <trigger>` - Reply to a sticker to create a sticker trigger

**Media Triggers (Global - All Chats, Sudo Only):**
- `/addglobalmediatrigger <trigger>` - Reply to media for global media trigger
- `/addglobalstickertrigger <trigger>` - Reply to sticker for global sticker trigger

**Examples:**

*Text Triggers:*
- `/addtrigger hello - Hello there!` - Replies with text when someone says "hello"
- `/addtrigger good morning - Good morning! Have a nice day!` - Exact phrase matching
- `/addglobaltrigger rules - Please read the rules!` - Global text trigger
- `/deltrigger hello` - Delete the local "hello" trigger
- `/delglobaltrigger rules` - Delete the global "rules" trigger

*Media Triggers:*
- Reply to a photo with `/addmediatrigger sunset` - Sends photo when someone says "sunset"
- Reply to a sticker with `/addstickertrigger awesome` - Sends sticker when someone says "awesome"
- Reply to a GIF with `/addmediatrigger dance` - Sends GIF when someone says "dance"
- Reply to a photo with `/addglobalmediatrigger welcome` - Global photo trigger
- Reply to a sticker with `/addglobalstickertrigger yes` - Global sticker trigger

**Supported Media Types:**
📷 Photos, 🎬 Videos, 🎞️ GIFs, 📄 Documents, 🎵 Audio, 🎙️ Voice Messages, 😊 Stickers

**Features:**
- Case-insensitive word/phrase matching
- Anti-spam cooldown (5 seconds per user per trigger)
- Local (chat-specific) and global (all chats) triggers
- Media response support
- Multiple responses per trigger with random selection
- Works in groups only
- Admin commands for local triggers, Sudo commands for global triggers
"""
