"""
Anonymous Media Repost Module - Makes bot repost user media anonymously
"""
import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Set, Optional

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChatAdminRequired, MessageDeleteForbidden
from pyrogram.types import Message

# =========================
# CONFIGURATION
# =========================

RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW = 10  # seconds


# =========================
# DATA STORAGE (IN-MEMORY)
# =========================

enabled_chats: Set[int] = set()
whitelisted_users: Dict[int, Set[int]] = defaultdict(set)
rate_limit_tracker: Dict[int, deque] = defaultdict(lambda: deque(maxlen=RATE_LIMIT_COUNT))


@dataclass
class ChatStats:
    total_processed: int = 0
    total_deleted: int = 0
    total_reposted: int = 0
    total_errors: int = 0


stats: Dict[int, ChatStats] = defaultdict(ChatStats)


# =========================
# UTILITY FUNCTIONS
# =========================

async def safe_delete(message: Message) -> bool:
    try:
        await message.delete()
        return True
    except (ChatAdminRequired, MessageDeleteForbidden):
        return False
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await safe_delete(message)
    except Exception:
        return False


async def safe_send(client: Client, message: Message) -> bool:
    try:
        if message.photo:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=message.photo.file_id,
                caption=message.caption or "",
                has_spoiler=message.has_media_spoiler or False
            )

        elif message.video:
            await client.send_video(
                chat_id=message.chat.id,
                video=message.video.file_id,
                caption=message.caption or "",
                has_spoiler=message.has_media_spoiler or False
            )

        elif message.document:
            await client.send_document(
                chat_id=message.chat.id,
                document=message.document.file_id,
                caption=message.caption or ""
            )

        elif message.audio:
            await client.send_audio(
                chat_id=message.chat.id,
                audio=message.audio.file_id,
                caption=message.caption or ""
            )

        elif message.voice:
            await client.send_voice(
                chat_id=message.chat.id,
                voice=message.voice.file_id,
                caption=message.caption or ""
            )

        else:
            return False

        return True

    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await safe_send(client, message)
    except Exception:
        return False


def is_rate_limited(chat_id: int) -> bool:
    now = time.time()
    timestamps = rate_limit_tracker[chat_id]

    while timestamps and now - timestamps[0] > RATE_LIMIT_WINDOW:
        timestamps.popleft()

    if len(timestamps) >= RATE_LIMIT_COUNT:
        return True

    timestamps.append(now)
    return False


def is_media(message: Message) -> bool:
    return any([
        message.photo,
        message.video,
        message.document,
        message.audio,
        message.voice
    ])


# =========================
# MAIN HANDLER
# =========================

@Client.on_message(filters.group & ~filters.service, group=100)
async def anonymous_media_handler(client: Client, message: Message):
    chat_id = message.chat.id

    if chat_id not in enabled_chats:
        return

    if not message.from_user:
        return

    if message.from_user.is_bot:
        return

    if not is_media(message):
        return

    if message.from_user.id in whitelisted_users[chat_id]:
        return

    if is_rate_limited(chat_id):
        return

    chat_stats = stats[chat_id]
    chat_stats.total_processed += 1

    deleted = await safe_delete(message)
    if not deleted:
        chat_stats.total_errors += 1
        return

    chat_stats.total_deleted += 1

    reposted = await safe_send(client, message)
    if reposted:
        chat_stats.total_reposted += 1
    else:
        chat_stats.total_errors += 1


# =========================
# COMMANDS
# =========================

@Client.on_message(filters.command("anon_enable") & filters.group)
async def enable_anonymous(_, message: Message):
    member = await message.chat.get_member(message.from_user.id)
    if not member.privileges or not member.privileges.can_delete_messages:
        return await message.reply("You must be admin with delete permission.")

    enabled_chats.add(message.chat.id)
    await message.reply("Anonymous media mode enabled.")


@Client.on_message(filters.command("anon_disable") & filters.group)
async def disable_anonymous(_, message: Message):
    member = await message.chat.get_member(message.from_user.id)
    if not member.privileges or not member.privileges.can_delete_messages:
        return await message.reply("You must be admin with delete permission.")

    enabled_chats.discard(message.chat.id)
    await message.reply("Anonymous media mode disabled.")


@Client.on_message(filters.command("anon_whitelist") & filters.group)
async def whitelist_user(_, message: Message):
    if not message.reply_to_message:
        return await message.reply("Reply to a user to whitelist them.")

    member = await message.chat.get_member(message.from_user.id)
    if not member.privileges or not member.privileges.can_delete_messages:
        return await message.reply("You must be admin.")

    user_id = message.reply_to_message.from_user.id
    whitelisted_users[message.chat.id].add(user_id)

    await message.reply("User whitelisted.")


@Client.on_message(filters.command("anon_stats") & filters.group)
async def show_stats(_, message: Message):
    chat_id = message.chat.id
    chat_stats = stats.get(chat_id)

    if not chat_stats:
        return await message.reply("No stats available yet.")

    text = (
        f"Processed: {chat_stats.total_processed}\n"
        f"Deleted: {chat_stats.total_deleted}\n"
        f"Reposted: {chat_stats.total_reposted}\n"
        f"Errors: {chat_stats.total_errors}"
    )

    await message.reply(text)


# =========================
# MODULE METADATA
# =========================

__MODULE__ = "Anonymous Media"
__HELP__ = """
**ANONYMOUS MEDIA REPOST MODULE**

Automatically deletes user media and reposts it as the bot, making all media anonymous.

**Admin Commands:**
/anon_enable [CHAT_ID]
    Enable anonymous mode in a group
    
/anon_disable [CHAT_ID]
    Disable anonymous mode in a group
    
/anon_status [CHAT_ID]
    Check status and statistics
    
/anon_whitelist_add [CHAT_ID] [USER_ID]
    Whitelist a user (their media won't be anonymized)
    
/anon_whitelist_remove [CHAT_ID] [USER_ID]
    Remove user from whitelist
    
/anon_whitelist_show [CHAT_ID]
    Show all whitelisted users
    
/anon_config [CHAT_ID]
    Configure settings (media types, delays, etc.)
    
/anon_stats [CHAT_ID]
    Detailed statistics for a group

**Features:**
✓ Smart rate limiting (respects Telegram API)
✓ Per-chat whitelisting
✓ Configurable media type filtering
✓ Flood protection
✓ Auto-retry on errors
✓ Detailed statistics
✓ Optional delay before repost
✓ Caption preservation
✓ Spoiler support

**Requirements:**
- Bot must be admin
- Bot needs Delete Messages permission
- Bot needs Send Media permissions
- Privacy mode disabled in @BotFather

**Note:** Text messages are never affected - only media.
"""

# State management
anon_enabled_chats: Set[int] = set()
anon_config: Dict[int, dict] = {}
anon_stats: Dict[int, dict] = {}
anon_whitelist: Dict[int, Set[int]] = defaultdict(set)

# Rate limiting (per chat)
rate_limiter: Dict[int, deque] = defaultdict(lambda: deque(maxlen=20))
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 20  # max messages per window


class AnonConfig:
    """Configuration for anonymous mode in a chat"""
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.enabled_types = {
            'photo': True,
            'video': True,
            'document': True,
            'audio': True,
            'animation': True,
            'voice': True,
            'video_note': True,
            'sticker': False  # Disabled by default
        }
        self.delay_before_repost = 0  # seconds
        self.delete_delay = 0  # instant delete by default
        self.preserve_caption = True
        self.created_at = datetime.now()
        self.enabled_by = None


class AnonStats:
    """Statistics tracker for anonymous mode"""
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.total_reposted = 0
        self.total_deleted = 0
        self.total_errors = 0
        self.by_type = defaultdict(int)
        self.by_user = defaultdict(int)
        self.last_repost = None
        self.rate_limit_hits = 0
        self.created_at = datetime.now()


def get_media_info(message: Message) -> tuple[str, str, Optional[str]]:
    """
    Extract media type, file_id, and caption from message
    
    Returns:
        tuple: (media_type, file_id, caption)
    """
    if message.photo:
        return ('photo', message.photo.file_id, message.caption)
    elif message.video:
        return ('video', message.video.file_id, message.caption)
    elif message.document:
        return ('document', message.document.file_id, message.caption)
    elif message.audio:
        return ('audio', message.audio.file_id, message.caption)
    elif message.animation:
        return ('animation', message.animation.file_id, message.caption)
    elif message.voice:
        return ('voice', message.voice.file_id, message.caption)
    elif message.video_note:
        return ('video_note', message.video_note.file_id, None)
    elif message.sticker:
        return ('sticker', message.sticker.file_id, None)
    else:
        return (None, None, None)


async def check_rate_limit(chat_id: int) -> bool:
    """
    Check if chat is within rate limits
    
    Returns:
        bool: True if within limits, False if rate limited
    """
    now = time.time()
    chat_queue = rate_limiter[chat_id]
    
    # Remove old entries outside the window
    while chat_queue and chat_queue[0] < now - RATE_LIMIT_WINDOW:
        chat_queue.popleft()
    
    # Check if limit exceeded
    if len(chat_queue) >= RATE_LIMIT_MAX:
        return False
    
    # Add current timestamp
    chat_queue.append(now)
    return True


async def safe_delete(message: Message, delay: int = 0) -> bool:
    """
    Safely delete a message with optional delay
    
    Args:
        message: Message to delete
        delay: Optional delay before deletion in seconds
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        await message.delete()
        return True
    except MessageDeleteForbidden:
        print(f"Bot lacks permission to delete message in chat {message.chat.id}")
        return False
    except Exception as e:
        print(f"Error deleting message: {e}")
        return False


async def safe_send_media(
    chat_id: int, 
    media_type: str, 
    file_id: str, 
    caption: Optional[str] = None,
    has_spoiler: bool = False,
    max_retries: int = 3
) -> Optional[Message]:
    """
    Safely send media with automatic retry and flood protection
    
    Args:
        chat_id: Destination chat ID
        media_type: Type of media (photo, video, etc.)
        file_id: Telegram file_id
        caption: Optional caption
        has_spoiler: Whether media has spoiler
        max_retries: Maximum retry attempts
        
    Returns:
        Message if successful, None otherwise
    """
    for attempt in range(max_retries):
        try:
            send_kwargs = {'chat_id': chat_id, media_type: file_id}
            
            if caption and media_type not in ['video_note', 'sticker']:
                send_kwargs['caption'] = caption
            
            if has_spoiler and media_type in ['photo', 'video', 'animation']:
                send_kwargs['has_spoiler'] = has_spoiler
            
            # Send based on media type
            if media_type == 'photo':
                return await app.send_photo(**send_kwargs)
            elif media_type == 'video':
                return await app.send_video(**send_kwargs)
            elif media_type == 'document':
                return await app.send_document(**send_kwargs)
            elif media_type == 'audio':
                return await app.send_audio(**send_kwargs)
            elif media_type == 'animation':
                return await app.send_animation(**send_kwargs)
            elif media_type == 'voice':
                return await app.send_voice(**send_kwargs)
            elif media_type == 'video_note':
                return await app.send_video_note(**send_kwargs)
            elif media_type == 'sticker':
                return await app.send_sticker(**send_kwargs)
            else:
                return None
                
        except FloodWait as e:
            wait_time = min(e.value, 300)  # Cap at 5 minutes
            print(f"FloodWait: sleeping for {wait_time}s")
            await asyncio.sleep(wait_time)
        except MediaEmpty:
            print(f"MediaEmpty error - file_id may be invalid")
            return None
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to send media after {max_retries} attempts: {e}")
                return None
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    return None


@app.on_message(
    filters.group & 
    (filters.photo | filters.video | filters.document | 
     filters.audio | filters.animation | filters.voice | 
     filters.video_note | filters.sticker),
    group=100
)
@capture_err
async def anon_media_handler(_, message: Message):
    """Main handler for anonymous media reposting"""
    chat_id = message.chat.id
    
    # Check if anonymous mode is enabled for this chat
    if chat_id not in anon_enabled_chats:
        return
    
    # Check if user is whitelisted
    if message.from_user and message.from_user.id in anon_whitelist.get(chat_id, set()):
        return
    
    # Skip if message is from the bot itself
    if message.from_user and message.from_user.is_bot:
        return
    
    # Get configuration
    config = anon_config.get(chat_id)
    if not config:
        config = AnonConfig(chat_id)
        anon_config[chat_id] = config
    
    # Get statistics
    if chat_id not in anon_stats:
        anon_stats[chat_id] = AnonStats(chat_id)
    stats = anon_stats[chat_id]
    
    # Extract media information
    media_type, file_id, caption = get_media_info(message)
    
    if not media_type or not file_id:
        return
    
    # Check if this media type is enabled
    if not config.enabled_types.get(media_type, False):
        return
    
    # Check rate limiting
    if not await check_rate_limit(chat_id):
        stats.rate_limit_hits += 1
        print(f"Rate limit hit for chat {chat_id}")
        return
    
    # Check for spoiler
    has_spoiler = False
    if hasattr(message, 'has_media_spoiler'):
        has_spoiler = message.has_media_spoiler
    
    # Preserve caption based on config
    if not config.preserve_caption:
        caption = None
    
    # Apply delay before repost if configured
    if config.delay_before_repost > 0:
        await asyncio.sleep(config.delay_before_repost)
    
    # Delete original message
    delete_success = await safe_delete(message, config.delete_delay)
    
    if delete_success:
        stats.total_deleted += 1
    else:
        stats.total_errors += 1
        return
    
    # Repost as bot
    sent_message = await safe_send_media(
        chat_id=chat_id,
        media_type=media_type,
        file_id=file_id,
        caption=caption,
        has_spoiler=has_spoiler
    )
    
    if sent_message:
        # Update statistics
        stats.total_reposted += 1
        stats.by_type[media_type] += 1
        if message.from_user:
            stats.by_user[message.from_user.id] += 1
        stats.last_repost = datetime.now()
    else:
        stats.total_errors += 1


@app.on_message(filters.command("anon_enable") & filters.user(list(SUDOERS_SET)))
@capture_err
async def enable_anon_mode(_, message: Message):
    """Enable anonymous mode in a group"""
    if len(message.command) != 2:
        return await message.reply(
            "**Usage:**\n`/anon_enable [CHAT_ID]`\n\n"
            "**Example:**\n`/anon_enable -100123456789`"
        )
    
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID. Please use numeric ID.")
    
    # Check if already enabled
    if chat_id in anon_enabled_chats:
        return await message.reply(f"⚠️ Anonymous mode already enabled for `{chat_id}`")
    
    # Verify bot is admin
    try:
        bot_member = await app.get_chat_member(chat_id, (await app.get_me()).id)
        if bot_member.status not in ["administrator", "creator"]:
            return await message.reply(
                f"❌ Bot is not an admin in chat `{chat_id}`\n"
                "Please make the bot admin with:\n"
                "• Delete Messages permission\n"
                "• Send Media permissions"
            )
    except Exception as e:
        return await message.reply(f"❌ Error checking bot status: {str(e)}")
    
    # Enable anonymous mode
    anon_enabled_chats.add(chat_id)
    
    # Initialize config if not exists
    if chat_id not in anon_config:
        config = AnonConfig(chat_id)
        config.enabled_by = message.from_user.id
        anon_config[chat_id] = config
    
    # Initialize stats if not exists
    if chat_id not in anon_stats:
        anon_stats[chat_id] = AnonStats(chat_id)
    
    await message.reply(
        f"✅ **Anonymous Mode Enabled**\n\n"
        f"**Chat ID:** `{chat_id}`\n"
        f"**Enabled By:** {message.from_user.mention}\n\n"
        f"**Active Media Types:**\n"
        f"• Photos ✓\n"
        f"• Videos ✓\n"
        f"• Documents ✓\n"
        f"• Audio ✓\n"
        f"• Animations ✓\n"
        f"• Voice ✓\n"
        f"• Video Notes ✓\n\n"
        f"_All user media will now be reposted anonymously as the bot._\n\n"
        f"Use `/anon_config {chat_id}` to customize settings."
    )


@app.on_message(filters.command("anon_disable") & filters.user(list(SUDOERS_SET)))
@capture_err
async def disable_anon_mode(_, message: Message):
    """Disable anonymous mode in a group"""
    if len(message.command) != 2:
        return await message.reply(
            "**Usage:**\n`/anon_disable [CHAT_ID]`"
        )
    
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")
    
    if chat_id not in anon_enabled_chats:
        return await message.reply(f"⚠️ Anonymous mode not enabled for `{chat_id}`")
    
    # Get stats before disabling
    stats = anon_stats.get(chat_id)
    
    # Disable
    anon_enabled_chats.remove(chat_id)
    
    stats_text = ""
    if stats:
        stats_text = (
            f"\n**Final Statistics:**\n"
            f"• Total Reposted: {stats.total_reposted}\n"
            f"• Total Deleted: {stats.total_deleted}\n"
            f"• Errors: {stats.total_errors}\n"
        )
    
    await message.reply(
        f"✅ **Anonymous Mode Disabled**\n\n"
        f"**Chat ID:** `{chat_id}`\n"
        f"{stats_text}\n"
        f"_User media will no longer be anonymized._"
    )


@app.on_message(filters.command("anon_status") & filters.user(list(SUDOERS_SET)))
@capture_err
async def anon_status(_, message: Message):
    """Check anonymous mode status"""
    if len(message.command) != 2:
        return await message.reply(
            "**Usage:**\n`/anon_status [CHAT_ID]`"
        )
    
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")
    
    if chat_id not in anon_enabled_chats:
        return await message.reply(
            f"📭 **Anonymous mode is DISABLED** for `{chat_id}`\n\n"
            f"Use `/anon_enable {chat_id}` to enable it."
        )
    
    config = anon_config.get(chat_id, AnonConfig(chat_id))
    stats = anon_stats.get(chat_id, AnonStats(chat_id))
    whitelist_count = len(anon_whitelist.get(chat_id, set()))
    
    enabled_types = [k for k, v in config.enabled_types.items() if v]
    
    uptime = datetime.now() - config.created_at
    
    text = (
        f"✅ **Anonymous Mode: ACTIVE**\n\n"
        f"**Chat ID:** `{chat_id}`\n"
        f"**Uptime:** {uptime}\n"
        f"**Whitelisted Users:** {whitelist_count}\n\n"
        f"**📊 Statistics:**\n"
        f"• Reposted: {stats.total_reposted}\n"
        f"• Deleted: {stats.total_deleted}\n"
        f"• Errors: {stats.total_errors}\n"
        f"• Rate Limits Hit: {stats.rate_limit_hits}\n\n"
        f"**⚙️ Configuration:**\n"
        f"• Repost Delay: {config.delay_before_repost}s\n"
        f"• Delete Delay: {config.delete_delay}s\n"
        f"• Preserve Captions: {'✓' if config.preserve_caption else '✗'}\n\n"
        f"**📁 Active Media Types:**\n"
    )
    
    for media_type in enabled_types:
        text += f"• {media_type.title()} ✓\n"
    
    if stats.last_repost:
        text += f"\n**Last Repost:** {stats.last_repost.strftime('%Y-%m-%d %H:%M:%S')}"
    
    await message.reply(text)


@app.on_message(filters.command("anon_whitelist_add") & filters.user(list(SUDOERS_SET)))
@capture_err
async def add_to_whitelist(_, message: Message):
    """Add user to whitelist"""
    if len(message.command) != 3:
        return await message.reply(
            "**Usage:**\n`/anon_whitelist_add [CHAT_ID] [USER_ID]`\n\n"
            "**Example:**\n`/anon_whitelist_add -100123456789 987654321`"
        )
    
    try:
        chat_id = int(message.command[1])
        user_id = int(message.command[2])
    except ValueError:
        return await message.reply("❌ Invalid chat ID or user ID.")
    
    anon_whitelist[chat_id].add(user_id)
    
    await message.reply(
        f"✅ **User Whitelisted**\n\n"
        f"**Chat:** `{chat_id}`\n"
        f"**User ID:** `{user_id}`\n\n"
        f"_This user's media will not be anonymized._"
    )


@app.on_message(filters.command("anon_whitelist_remove") & filters.user(list(SUDOERS_SET)))
@capture_err
async def remove_from_whitelist(_, message: Message):
    """Remove user from whitelist"""
    if len(message.command) != 3:
        return await message.reply(
            "**Usage:**\n`/anon_whitelist_remove [CHAT_ID] [USER_ID]`"
        )
    
    try:
        chat_id = int(message.command[1])
        user_id = int(message.command[2])
    except ValueError:
        return await message.reply("❌ Invalid chat ID or user ID.")
    
    if user_id not in anon_whitelist.get(chat_id, set()):
        return await message.reply("⚠️ User is not whitelisted.")
    
    anon_whitelist[chat_id].remove(user_id)
    
    await message.reply(
        f"✅ **User Removed from Whitelist**\n\n"
        f"**Chat:** `{chat_id}`\n"
        f"**User ID:** `{user_id}`\n\n"
        f"_This user's media will now be anonymized._"
    )


@app.on_message(filters.command("anon_whitelist_show") & filters.user(list(SUDOERS_SET)))
@capture_err
async def show_whitelist(_, message: Message):
    """Show whitelisted users"""
    if len(message.command) != 2:
        return await message.reply(
            "**Usage:**\n`/anon_whitelist_show [CHAT_ID]`"
        )
    
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")
    
    whitelist = anon_whitelist.get(chat_id, set())
    
    if not whitelist:
        return await message.reply(
            f"📭 **No Whitelisted Users**\n\n"
            f"Chat: `{chat_id}`"
        )
    
    text = f"**👥 Whitelisted Users** (`{chat_id}`)\n\n"
    for count, user_id in enumerate(whitelist, 1):
        text += f"{count}. `{user_id}`\n"
    
    await message.reply(text)


@app.on_message(filters.command("anon_stats") & filters.user(list(SUDOERS_SET)))
@capture_err
async def detailed_stats(_, message: Message):
    """Show detailed statistics"""
    if len(message.command) != 2:
        return await message.reply(
            "**Usage:**\n`/anon_stats [CHAT_ID]`"
        )
    
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")
    
    if chat_id not in anon_stats:
        return await message.reply(f"📭 No statistics available for `{chat_id}`")
    
    stats = anon_stats[chat_id]
    
    text = f"**📊 Detailed Statistics** (`{chat_id}`)\n\n"
    
    text += f"**Overall:**\n"
    text += f"• Total Reposted: {stats.total_reposted}\n"
    text += f"• Total Deleted: {stats.total_deleted}\n"
    text += f"• Total Errors: {stats.total_errors}\n"
    text += f"• Rate Limit Hits: {stats.rate_limit_hits}\n"
    
    success_rate = (stats.total_reposted / max(stats.total_reposted + stats.total_errors, 1)) * 100
    text += f"• Success Rate: {success_rate:.1f}%\n\n"
    
    if stats.by_type:
        text += f"**By Media Type:**\n"
        for media_type, count in sorted(stats.by_type.items(), key=lambda x: x[1], reverse=True):
            text += f"• {media_type.title()}: {count}\n"
        text += "\n"
    
    if stats.by_user:
        text += f"**Top Users (by media count):**\n"
        top_users = sorted(stats.by_user.items(), key=lambda x: x[1], reverse=True)[:5]
        for user_id, count in top_users:
            text += f"• `{user_id}`: {count}\n"
        text += "\n"
    
    uptime = datetime.now() - stats.created_at
    text += f"**Tracking Since:** {stats.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    text += f"**Uptime:** {uptime}"
    
    if stats.last_repost:
        text += f"\n**Last Repost:** {stats.last_repost.strftime('%Y-%m-%d %H:%M:%S')}"
    
    await message.reply(text)


@app.on_message(filters.command("anon_config") & filters.user(list(SUDOERS_SET)))
@capture_err
async def configure_anon(_, message: Message):
    """Configure anonymous mode settings"""
    if len(message.command) != 2:
        return await message.reply(
            "**Usage:**\n`/anon_config [CHAT_ID]`"
        )
    
    try:
        chat_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")
    
    if chat_id not in anon_enabled_chats:
        return await message.reply(
            f"⚠️ Anonymous mode not enabled for `{chat_id}`\n"
            f"Use `/anon_enable {chat_id}` first."
        )
    
    config = anon_config.get(chat_id, AnonConfig(chat_id))
    
    text = (
        f"**⚙️ Configuration** (`{chat_id}`)\n\n"
        f"**Current Settings:**\n"
        f"• Repost Delay: {config.delay_before_repost}s\n"
        f"• Delete Delay: {config.delete_delay}s\n"
        f"• Preserve Captions: {'✓' if config.preserve_caption else '✗'}\n\n"
        f"**Media Types:**\n"
    )
    
    for media_type, enabled in config.enabled_types.items():
        status = "✓" if enabled else "✗"
        text += f"• {media_type.title()}: {status}\n"
    
    text += (
        f"\n**Note:** Configuration changes require code modification.\n"
        f"Contact bot admin to adjust settings."
    )
    
    await message.reply(text)
