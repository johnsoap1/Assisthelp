"""
Enhanced Telegram Media Redirection Module with Advanced Features
"""
import asyncio
import time
from typing import Dict, Optional, Set
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant
from wbb import BOT_ID, SUDOERS, SUDOERS_SET, app
from wbb.core.decorators.errors import capture_err

__MODULE__ = "Redirection"
__HELP__ = """
**ADVANCED MEDIA REDIRECTION MODULE**

Forward media and files between groups with precise control and anti-flood protection.

**Commands:**
/redirection [SOURCE_ID] [DEST_ID]
    Setup live media forwarding with delay options

/clone [SOURCE_ID] [DEST_ID]
    Clone historical messages from when bot joined

/stop_redirection [SOURCE_ID]
    Stop active redirection

/stop_clone [SOURCE_ID]
    Stop active cloning process

/redirections
    View all active redirections and clones

/redirection_stats [SOURCE_ID]
    Get detailed statistics for a redirection

/pause_redirection [SOURCE_ID]
    Temporarily pause a redirection

/resume_redirection [SOURCE_ID]
    Resume a paused redirection

**Features:**
✓ Customizable delays (1s to 24h)
✓ Smart anti-flood protection
✓ Real-time progress tracking
✓ Message filtering options
✓ Automatic retry on errors
✓ Pause/Resume capability
✓ Detailed statistics

**Note:** Only for authorized users. Respects Telegram API limits.
"""

# Global state management
redirections: Dict[int, dict] = {}
clone_tasks: Dict[int, dict] = {}
redirection_stats: Dict[int, dict] = {}
pending_setups: Dict[int, dict] = {}


class RedirectionConfig:
    """Configuration for a redirection"""
    def __init__(self, source: int, destination: int, delay: int = 0):
        self.source = source
        self.destination = destination
        self.delay = delay  # in seconds
        self.active = True
        self.paused = False
        self.created_at = datetime.now()
        self.messages_forwarded = 0
        self.last_message_time = None
        self.errors = 0
        self.media_only = True
        self.skip_text_only = True


def get_delay_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for delay selection"""
    keyboard = [
        [
            InlineKeyboardButton("No Delay", callback_data="delay_0"),
            InlineKeyboardButton("1 sec", callback_data="delay_1"),
            InlineKeyboardButton("5 sec", callback_data="delay_5")
        ],
        [
            InlineKeyboardButton("10 sec", callback_data="delay_10"),
            InlineKeyboardButton("20 sec", callback_data="delay_20"),
            InlineKeyboardButton("30 sec", callback_data="delay_30")
        ],
        [
            InlineKeyboardButton("1 min", callback_data="delay_60"),
            InlineKeyboardButton("2 min", callback_data="delay_120"),
            InlineKeyboardButton("5 min", callback_data="delay_300")
        ],
        [
            InlineKeyboardButton("10 min", callback_data="delay_600"),
            InlineKeyboardButton("30 min", callback_data="delay_1800"),
            InlineKeyboardButton("1 hour", callback_data="delay_3600")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="delay_cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def format_delay_time(seconds: int) -> str:
    """Format seconds into readable time"""
    if seconds == 0:
        return "No delay"
    elif seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    else:
        return f"{seconds // 3600}h"


async def safe_forward(message: Message, chat_id: int, max_retries: int = 3) -> bool:
    """
    Safely forward a message with automatic retry and flood wait handling

    Args:
        message: Message to forward
        chat_id: Destination chat ID
        max_retries: Maximum number of retry attempts

    Returns:
        bool: True if successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            await message.forward(chat_id)
            return True
        except FloodWait as e:
            wait_time = min(e.value, 300)  # Cap at 5 minutes
            await asyncio.sleep(wait_time)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to forward message after {max_retries} attempts: {e}")
                return False
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return False


async def clone_messages_task(source_id: int, dest_id: int, delay: int, user_id: int):
    """
    Background task to clone historical messages

    Args:
        source_id: Source chat ID
        dest_id: Destination chat ID
        delay: Delay between messages in seconds
        user_id: User who initiated the clone
    """
    clone_tasks[source_id] = {
        'destination': dest_id,
        'delay': delay,
        'active': True,
        'messages_cloned': 0,
        'started_at': datetime.now(),
        'current_message_id': None,
        'errors': 0,
        'user_id': user_id
    }

    try:
        # Get the bot's join date message or start from beginning
        message_count = 0
        error_count = 0
        last_message_id = None

        # Iterate through messages in the source chat
        async for message in app.get_chat_history(source_id):
            if not clone_tasks.get(source_id, {}).get('active', False):
                break

            # Only clone media and documents
            if message.media or message.document or message.photo or message.video or message.audio:
                clone_tasks[source_id]['current_message_id'] = message.id

                # Apply delay
                if delay > 0 and message_count > 0:
                    await asyncio.sleep(delay)

                # Forward the message
                success = await safe_forward(message, dest_id)

                if success:
                    message_count += 1
                    clone_tasks[source_id]['messages_cloned'] = message_count
                    last_message_id = message.id
                else:
                    error_count += 1
                    clone_tasks[source_id]['errors'] = error_count

                # Safety break if too many errors
                if error_count > 10:
                    break

        # Send completion notification
        try:
            await app.send_message(
                user_id,
                f"✅ **Clone Completed**\n\n"
                f"**Source:** `{source_id}`\n"
                f"**Destination:** `{dest_id}`\n"
                f"**Messages Cloned:** {message_count}\n"
                f"**Errors:** {error_count}\n"
                f"**Delay:** {format_delay_time(delay)}"
            )
        except:
            pass

    except Exception as e:
        try:
            await app.send_message(
                user_id,
                f"❌ **Clone Failed**\n\n"
                f"**Error:** {str(e)}\n"
                f"**Source:** `{source_id}`\n"
                f"**Messages Cloned:** {clone_tasks[source_id].get('messages_cloned', 0)}"
            )
        except:
            pass
    finally:
        if source_id in clone_tasks:
            del clone_tasks[source_id]


@app.on_message(~filters.me & ~filters.bot, group=500)
@capture_err
async def redirection_worker(_, message: Message):
    """Worker that handles active redirections"""
    chat_id = message.chat.id

    if chat_id not in redirections:
        return

    config = redirections[chat_id]

    # Check if paused
    if config.paused:
        return

    # Check if message should be forwarded (media/document only)
    if config.media_only:
        if not (message.media or message.document or message.photo or
                message.video or message.audio or message.animation or message.sticker):
            return

    # Apply delay if configured
    if config.delay > 0:
        current_time = time.time()
        if config.last_message_time:
            elapsed = current_time - config.last_message_time
            if elapsed < config.delay:
                await asyncio.sleep(config.delay - elapsed)
        config.last_message_time = time.time()

    # Forward the message
    success = await safe_forward(message, config.destination)

    # Update statistics
    if success:
        config.messages_forwarded += 1

        # Update global stats
        if chat_id not in redirection_stats:
            redirection_stats[chat_id] = {
                'total_forwarded': 0,
                'total_errors': 0,
                'last_forwarded': None
            }
        redirection_stats[chat_id]['total_forwarded'] += 1
        redirection_stats[chat_id]['last_forwarded'] = datetime.now()
    else:
        config.errors += 1
        if chat_id in redirection_stats:
            redirection_stats[chat_id]['total_errors'] += 1


@app.on_message(filters.command("redirection") & filters.user(list(SUDOERS_SET)))
@capture_err
async def setup_redirection(_, message: Message):
    """Setup a new redirection with delay options"""
    if len(message.command) != 3:
        return await message.reply(
            "**Usage:**\n`/redirection [SOURCE_ID] [DESTINATION_ID]`\n\n"
            "**Example:**\n`/redirection -100123456789 -100987654321`"
        )

    try:
        source_id = int(message.command[1])
        dest_id = int(message.command[2])
    except ValueError:
        return await message.reply("❌ Invalid chat IDs. Please use numeric IDs.")

    # Check if already exists
    if source_id in redirections:
        return await message.reply(
            f"⚠️ Redirection already exists for `{source_id}`\n"
            "Use `/stop_redirection {source_id}` to remove it first."
        )

    # Store pending setup
    pending_setups[message.from_user.id] = {
        'source': source_id,
        'destination': dest_id,
        'message_id': message.id
    }

    # Ask for delay preference
    await message.reply(
        f"**Setting up redirection:**\n"
        f"**Source:** `{source_id}`\n"
        f"**Destination:** `{dest_id}`\n\n"
        f"📊 **Select delay between messages:**",
        reply_markup=get_delay_keyboard()
    )


@app.on_callback_query(filters.regex(r"^delay_"))
async def handle_delay_selection(_, query: CallbackQuery):
    """Handle delay selection callback"""
    user_id = query.from_user.id

    if user_id not in pending_setups:
        return await query.answer("⚠️ Setup expired. Please start again.", show_alert=True)

    setup = pending_setups[user_id]

    if query.data == "delay_cancel":
        del pending_setups[user_id]
        await query.message.edit_text("❌ Redirection setup cancelled.")
        return

    # Extract delay value
    delay = int(query.data.split("_")[1])

    # Create redirection
    config = RedirectionConfig(setup['source'], setup['destination'], delay)
    redirections[setup['source']] = config

    # Initialize stats
    if setup['source'] not in redirection_stats:
        redirection_stats[setup['source']] = {
            'total_forwarded': 0,
            'total_errors': 0,
            'last_forwarded': None
        }

    # Clean up
    del pending_setups[user_id]

    await query.message.edit_text(
        f"✅ **Redirection Activated**\n\n"
        f"**Source:** `{setup['source']}`\n"
        f"**Destination:** `{setup['destination']}`\n"
        f"**Delay:** {format_delay_time(delay)}\n"
        f"**Mode:** Media & Documents only\n\n"
        f"_All media from source will now be forwarded to destination._"
    )


@app.on_message(filters.command("clone") & filters.user(list(SUDOERS_SET)))
@capture_err
async def setup_clone(_, message: Message):
    """Clone historical messages from a chat"""
    if len(message.command) != 3:
        return await message.reply(
            "**Usage:**\n`/clone [SOURCE_ID] [DESTINATION_ID]`\n\n"
            "**Example:**\n`/clone -100123456789 -100987654321`"
        )

    try:
        source_id = int(message.command[1])
        dest_id = int(message.command[2])
    except ValueError:
        return await message.reply("❌ Invalid chat IDs. Please use numeric IDs.")

    # Check if clone already running
    if source_id in clone_tasks:
        return await message.reply(
            f"⚠️ Clone already running for `{source_id}`\n"
            f"**Progress:** {clone_tasks[source_id].get('messages_cloned', 0)} messages cloned"
        )

    # Store pending setup
    pending_setups[message.from_user.id] = {
        'source': source_id,
        'destination': dest_id,
        'message_id': message.id,
        'type': 'clone'
    }

    # Ask for delay preference
    await message.reply(
        f"**Setting up message cloning:**\n"
        f"**Source:** `{source_id}`\n"
        f"**Destination:** `{dest_id}`\n\n"
        f"📊 **Select delay between messages:**\n"
        f"_This will clone all media from chat history_",
        reply_markup=get_delay_keyboard()
    )


@app.on_callback_query(filters.regex(r"^delay_") & filters.user(list(SUDOERS_SET)))
async def handle_clone_delay_selection(_, query: CallbackQuery):
    """Handle delay selection for clone"""
    user_id = query.from_user.id

    if user_id not in pending_setups:
        return

    setup = pending_setups[user_id]

    # Check if this is a clone setup
    if setup.get('type') != 'clone':
        return

    if query.data == "delay_cancel":
        del pending_setups[user_id]
        await query.message.edit_text("❌ Clone setup cancelled.")
        return

    # Extract delay value
    delay = int(query.data.split("_")[1])

    # Start clone task
    asyncio.create_task(
        clone_messages_task(setup['source'], setup['destination'], delay, user_id)
    )

    # Clean up
    del pending_setups[user_id]

    await query.message.edit_text(
        f"✅ **Clone Started**\n\n"
        f"**Source:** `{setup['source']}`\n"
        f"**Destination:** `{setup['destination']}`\n"
        f"**Delay:** {format_delay_time(delay)}\n\n"
        f"_Cloning messages in background... You'll be notified when complete._"
    )


@app.on_message(filters.command("stop_redirection") & filters.user(list(SUDOERS_SET)))
@capture_err
async def stop_redirection(_, message: Message):
    """Stop an active redirection"""
    if len(message.command) != 2:
        return await message.reply("**Usage:**\n`/stop_redirection [SOURCE_ID]`")

    try:
        source_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")

    if source_id not in redirections:
        return await message.reply(f"⚠️ No active redirection for `{source_id}`")

    config = redirections[source_id]
    stats = redirection_stats.get(source_id, {})

    del redirections[source_id]

    await message.reply(
        f"✅ **Redirection Stopped**\n\n"
        f"**Source:** `{source_id}`\n"
        f"**Messages Forwarded:** {stats.get('total_forwarded', 0)}\n"
        f"**Errors:** {stats.get('total_errors', 0)}\n"
        f"**Active Duration:** {datetime.now() - config.created_at}"
    )


@app.on_message(filters.command("stop_clone") & filters.user(list(SUDOERS_SET)))
@capture_err
async def stop_clone(_, message: Message):
    """Stop an active clone task"""
    if len(message.command) != 2:
        return await message.reply("**Usage:**\n`/stop_clone [SOURCE_ID]`")

    try:
        source_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")

    if source_id not in clone_tasks:
        return await message.reply(f"⚠️ No active clone for `{source_id}`")

    task_info = clone_tasks[source_id]
    task_info['active'] = False

    await message.reply(
        f"🛑 **Clone Stopped**\n\n"
        f"**Source:** `{source_id}`\n"
        f"**Messages Cloned:** {task_info.get('messages_cloned', 0)}\n"
        f"**Errors:** {task_info.get('errors', 0)}"
    )


@app.on_message(filters.command("redirections") & filters.user(list(SUDOERS_SET)))
@capture_err
async def show_redirections(_, message: Message):
    """Show all active redirections and clones"""
    if not redirections and not clone_tasks:
        return await message.reply("📭 No active redirections or clones.")

    text = "**📊 Active Redirections & Clones**\n\n"

    # Show redirections
    if redirections:
        text += "**🔄 Live Redirections:**\n"
        for count, (source, config) in enumerate(redirections.items(), 1):
            status = "⏸ Paused" if config.paused else "✅ Active"
            stats = redirection_stats.get(source, {})
            text += (
                f"{count}. {status}\n"
                f"   **Source:** `{source}`\n"
                f"   **Dest:** `{config.destination}`\n"
                f"   **Delay:** {format_delay_time(config.delay)}\n"
                f"   **Forwarded:** {stats.get('total_forwarded', 0)}\n"
                f"   **Errors:** {stats.get('total_errors', 0)}\n\n"
            )

    # Show clones
    if clone_tasks:
        text += "**📥 Active Clones:**\n"
        for count, (source, task) in enumerate(clone_tasks.items(), 1):
            text += (
                f"{count}. **Source:** `{source}`\n"
                f"   **Dest:** `{task['destination']}`\n"
                f"   **Cloned:** {task.get('messages_cloned', 0)}\n"
                f"   **Delay:** {format_delay_time(task['delay'])}\n\n"
            )

    await message.reply(text)


@app.on_message(filters.command("redirection_stats") & filters.user(list(SUDOERS_SET)))
@capture_err
async def show_stats(_, message: Message):
    """Show detailed statistics for a redirection"""
    if len(message.command) != 2:
        return await message.reply("**Usage:**\n`/redirection_stats [SOURCE_ID]`")

    try:
        source_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")

    if source_id not in redirections:
        return await message.reply(f"⚠️ No active redirection for `{source_id}`")

    config = redirections[source_id]
    stats = redirection_stats.get(source_id, {})

    uptime = datetime.now() - config.created_at
    status = "⏸ Paused" if config.paused else "✅ Active"

    text = (
        f"**📊 Redirection Statistics**\n\n"
        f"**Status:** {status}\n"
        f"**Source:** `{source_id}`\n"
        f"**Destination:** `{config.destination}`\n"
        f"**Delay:** {format_delay_time(config.delay)}\n\n"
        f"**📈 Performance:**\n"
        f"**Total Forwarded:** {stats.get('total_forwarded', 0)}\n"
        f"**Total Errors:** {stats.get('total_errors', 0)}\n"
        f"**Success Rate:** {(stats.get('total_forwarded', 0) / max(stats.get('total_forwarded', 0) + stats.get('total_errors', 0), 1) * 100):.1f}%\n\n"
        f"**⏱ Timing:**\n"
        f"**Uptime:** {uptime}\n"
        f"**Created:** {config.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    )

    if stats.get('last_forwarded'):
        text += f"**Last Message:** {stats['last_forwarded'].strftime('%Y-%m-%d %H:%M:%S')}\n"

    await message.reply(text)


@app.on_message(filters.command("pause_redirection") & filters.user(list(SUDOERS_SET)))
@capture_err
async def pause_redirection(_, message: Message):
    """Pause an active redirection"""
    if len(message.command) != 2:
        return await message.reply("**Usage:**\n`/pause_redirection [SOURCE_ID]`")

    try:
        source_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")

    if source_id not in redirections:
        return await message.reply(f"⚠️ No active redirection for `{source_id}`")

    config = redirections[source_id]

    if config.paused:
        return await message.reply("⚠️ Redirection is already paused.")

    config.paused = True
    await message.reply(f"⏸ **Redirection Paused**\n\nSource: `{source_id}`")


@app.on_message(filters.command("resume_redirection") & filters.user(list(SUDOERS_SET)))
@capture_err
async def resume_redirection(_, message: Message):
    """Resume a paused redirection"""
    if len(message.command) != 2:
        return await message.reply("**Usage:**\n`/resume_redirection [SOURCE_ID]`")

    try:
        source_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")

    if source_id not in redirections:
        return await message.reply(f"⚠️ No active redirection for `{source_id}`")

    config = redirections[source_id]

    if not config.paused:
        return await message.reply("⚠️ Redirection is not paused.")

    config.paused = False
    await message.reply(f"▶️ **Redirection Resumed**\n\nSource: `{source_id}`")
