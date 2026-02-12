"""
Media Deduplication & Tracking Module for Telegram

Features:
- Automatic duplicate media detection and removal
- Per-user media count tracking
- Media leaderboards with rankings
- Inactive user detection and removal
- Admin controls for moderation

Commands:
- /dedupe [on|off] - Enable/disable deduplication
- /mycount - Check your media count
- /count <user> - Check any user's media count (admin/sudo)
- /leaderboard - Show top media contributors
- /kick50 - Kick users with less than 50 media (admin/sudo)
- /inactivekick <time> - Kick users inactive for specified time (admin/sudo)
- /mediastats - Show chat media statistics
"""

import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
from wbb import app, SUDOERS, SUDOERS_SET

from wbb.utils.dbfunctions import (
    is_dedupe_enabled, set_dedupe_enabled, check_duplicate_media, save_media_hash,
    increment_user_media, get_user_media_stats, get_media_leaderboard,
    get_inactive_media_users, get_low_media_users, get_chat_media_stats
)

__MODULE__ = "Media Dedupe"
__HELP__ = """
📊 **Media Deduplication & Tracking**

Automatically detect and remove duplicate media, track user contributions, and manage inactive members.

**User Commands:**
• `/mycount` - Check your media count
• `/leaderboard` - View top media contributors

**Admin Commands:**
• `/dedupe on` - Enable duplicate detection
• `/dedupe off` - Disable duplicate detection
• `/dedupe status` - Check current status
• `/count <user>` - Check any user's media count
• `/mediastats` - Chat media statistics
• `/leaderboard full` - Extended leaderboard (top 20)

**Moderation Commands (Admin/Sudo):**
• `/kick50` - Remove users with < 50 media posts
• `/inactivekick <time>` - Remove inactive users
  Examples: `/inactivekick 7d`, `/inactivekick 1m` 
• `/scaninactive <time>` - Preview inactive users without kicking

**Features:**
✅ Automatic duplicate media removal
✅ Per-user photo & video tracking
✅ Gold/Silver/Bronze leaderboard rankings
✅ Inactive user detection
✅ Detailed statistics

**Notes:**
- Only tracks media sent after bot is added
- Counts photos and videos only (not documents)
- Duplicate detection uses file hash matching
- Inactive kick requires admin privileges
"""

# ==================== CONSTANTS ====================

# Time parsing
TIME_UNITS = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800,
    'M': 2592000,  # 30 days
}

# Leaderboard emojis
RANK_EMOJIS = {
    1: "🥇",
    2: "🥈", 
    3: "🥉",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟"
}

# ==================== HELPER FUNCTIONS ====================

def parse_time(time_str: str) -> Optional[int]:
    """Parse time string like '7d', '1m', '24h' to seconds."""
    if not time_str:
        return None
    
    time_str = time_str.lower().strip()
    
    # Extract number and unit
    import re
    match = re.match(r'^(\d+)([smhdwM])$', time_str)
    if not match:
        return None
    
    amount, unit = match.groups()
    amount = int(amount)
    
    return amount * TIME_UNITS.get(unit, 0)

def format_time_ago(timestamp: int) -> str:
    """Format timestamp as 'X days ago'."""
    now = int(time.time())
    diff = now - timestamp
    
    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = diff // 60
        return f"{mins}m ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours}h ago"
    elif diff < 604800:
        days = diff // 86400
        return f"{days}d ago"
    elif diff < 2592000:
        weeks = diff // 604800
        return f"{weeks}w ago"
    else:
        months = diff // 2592000
        return f"{months}mo ago"

def get_media_hash(file_unique_id: str) -> str:
    """Generate hash from file unique ID."""
    return hashlib.sha256(file_unique_id.encode()).hexdigest()

async def is_admin_or_sudo(chat_id: int, user_id: int) -> bool:
    """Check if user is admin or sudo."""
    if user_id in SUDOERS_SET:
        return True
    
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False

# ==================== MESSAGE HANDLERS ====================

@app.on_message(filters.group & (filters.photo | filters.video))
async def handle_media(_, message: Message):
    """Handle incoming media for deduplication and tracking."""
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    
    if user_id == 0:  # Anonymous admin or channel
        return
    
    # Determine media type and get file
    media_type = None
    file_unique_id = None
    
    if message.photo:
        media_type = "photo"
        file_unique_id = message.photo.file_unique_id
    elif message.video:
        media_type = "video"
        file_unique_id = message.video.file_unique_id
    
    if not file_unique_id:
        return
    
    # Generate hash
    file_hash = get_media_hash(file_unique_id)
    
    # Check if deduplication is enabled
    if await is_dedupe_enabled(chat_id):
        # Check for duplicate
        duplicate = await check_duplicate_media(chat_id, file_hash)
        
        if duplicate:
            try:
                # Delete duplicate
                await message.delete()
                
                # Get original poster
                original_user = duplicate.get("user_id")
                
                # Notify user (silently)
                try:
                    await app.send_message(
                        user_id,
                        f"⚠️ Your {media_type} was removed from **{message.chat.title}** "
                        f"because it was already posted by another user."
                    )
                except:
                    pass  # User has blocked bot
                
                print(f"[DEDUPE] Removed duplicate {media_type} from user {user_id} in chat {chat_id}")
                return
            except Exception as e:
                print(f"[DEDUPE] Failed to delete duplicate: {e}")
    
    # Save hash to prevent future duplicates
    await save_media_hash(chat_id, file_hash, user_id, message.id)
    
    # Increment user's media count
    await increment_user_media(chat_id, user_id, media_type)

# ==================== COMMAND HANDLERS ====================

@app.on_message(filters.command("dedupe") & filters.group)
async def dedupe_command(_, message: Message):
    """Toggle deduplication on/off."""
    if not await is_admin_or_sudo(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ This command is for admins only!")
    
    args = message.command[1:] if len(message.command) > 1 else []
    
    if not args or args[0].lower() == "status":
        # Show status
        enabled = await is_dedupe_enabled(message.chat.id)
        status = "✅ **Enabled**" if enabled else "❌ **Disabled**"
        
        await message.reply_text(
            f"📊 **Deduplication Status**\n\n"
            f"Status: {status}\n\n"
            f"Use `/dedupe on` to enable or `/dedupe off` to disable."
        )
        return
    
    action = args[0].lower()
    
    if action in ["on", "enable", "yes", "1"]:
        await set_dedupe_enabled(message.chat.id, True)
        await message.reply_text(
            "✅ **Deduplication Enabled**\n\n"
            "Duplicate photos and videos will be automatically removed."
        )
    elif action in ["off", "disable", "no", "0"]:
        await set_dedupe_enabled(message.chat.id, False)
        await message.reply_text(
            "❌ **Deduplication Disabled**\n\n"
            "Duplicate media will no longer be removed."
        )
    else:
        await message.reply_text(
            "❌ Invalid option. Use:\n"
            "• `/dedupe on` - Enable\n"
            "• `/dedupe off` - Disable\n"
            "• `/dedupe status` - Check status"
        )

@app.on_message(filters.command("mycount") & filters.group)
async def my_count_command(_, message: Message):
    """Show user's own media count."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    stats = await get_user_media_stats(chat_id, user_id)
    
    if stats["total"] == 0:
        await message.reply_text(
            "📊 **Your Media Count**\n\n"
            "You haven't posted any photos or videos yet!"
        )
        return
    
    last_media = format_time_ago(stats["last_media"]) if stats["last_media"] else "Never"
    
    await message.reply_text(
        f"📊 **Your Media Count**\n\n"
        f"📷 Photos: **{stats['photos']}**\n"
        f"🎬 Videos: **{stats['videos']}**\n"
        f"📊 Total: **{stats['total']}**\n\n"
        f"🕐 Last posted: {last_media}"
    )

@app.on_message(filters.command("count") & filters.group)
async def count_command(_, message: Message):
    """Check any user's media count (admin/sudo only)."""
    if not await is_admin_or_sudo(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ This command is for admins only!")
    
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text(
            "📝 Usage: `/count <username/id>` or reply to a message with `/count`"
        )
    
    # Get target user
    target_user = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    else:
        # Try to get user from command argument
        try:
            user_input = message.command[1]
            if user_input.isdigit():
                target_user = await app.get_users(int(user_input))
            else:
                target_user = await app.get_users(user_input.strip('@'))
        except Exception as e:
            return await message.reply_text(f"❌ User not found: {e}")
    
    if not target_user:
        return await message.reply_text("❌ Could not find user!")
    
    stats = await get_user_media_stats(message.chat.id, target_user.id)
    
    last_media = format_time_ago(stats["last_media"]) if stats["last_media"] else "Never"
    
    await message.reply_text(
        f"📊 **Media Count for {target_user.mention}**\n\n"
        f"📷 Photos: **{stats['photos']}**\n"
        f"🎬 Videos: **{stats['videos']}**\n"
        f"📊 Total: **{stats['total']}**\n\n"
        f"🕐 Last posted: {last_media}"
    )

@app.on_message(filters.command("leaderboard") & filters.group)
async def leaderboard_command(_, message: Message):
    """Show media leaderboard."""
    is_admin = await is_admin_or_sudo(message.chat.id, message.from_user.id)
    
    # Check for 'full' argument (admin only)
    show_full = False
    if len(message.command) > 1 and message.command[1].lower() == "full":
        if is_admin:
            show_full = True
        else:
            await message.reply_text("❌ Only admins can view the full leaderboard!")
            return
    
    limit = 20 if show_full else 10
    leaders = await get_media_leaderboard(message.chat.id, limit)
    
    if not leaders:
        await message.reply_text(
            "📊 **Media Leaderboard**\n\n"
            "No media has been posted yet!"
        )
        return
    
    text = "🏆 **Media Leaderboard**\n"
    text += f"Top {len(leaders)} Contributors\n\n"
    
    for i, leader in enumerate(leaders, 1):
        rank_emoji = RANK_EMOJIS.get(i, f"{i}.")
        user_id = leader["user_id"]
        total = leader.get("total", 0)
        photos = leader.get("photos", 0)
        videos = leader.get("videos", 0)
        
        try:
            user = await app.get_users(user_id)
            name = user.mention
        except:
            name = f"User {user_id}"
        
        text += f"{rank_emoji} {name}\n"
        text += f"   📊 {total} total (📷 {photos} • 🎬 {videos})\n\n"
    
    # Add footer
    chat_stats = await get_chat_media_stats(message.chat.id)
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"📈 Total: {chat_stats['total_media']} media\n"
    text += f"👥 Active users: {chat_stats['active_users']}"
    
    if not show_full and is_admin:
        text += "\n\n💡 Use `/leaderboard full` for top 20"
    
    await message.reply_text(text)

@app.on_message(filters.command("mediastats") & filters.group)
async def media_stats_command(_, message: Message):
    """Show chat media statistics."""
    if not await is_admin_or_sudo(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ This command is for admins only!")
    
    stats = await get_chat_media_stats(message.chat.id)
    dedupe_enabled = await is_dedupe_enabled(message.chat.id)
    
    dedupe_status = "✅ Enabled" if dedupe_enabled else "❌ Disabled"
    
    await message.reply_text(
        f"📊 **Chat Media Statistics**\n\n"
        f"📷 Total Photos: **{stats['total_photos']}**\n"
        f"🎬 Total Videos: **{stats['total_videos']}**\n"
        f"📊 Total Media: **{stats['total_media']}**\n\n"
        f"👥 Active Users: **{stats['active_users']}**\n"
        f"🔄 Deduplication: {dedupe_status}\n\n"
        f"Use `/leaderboard` to see top contributors!"
    )

@app.on_message(filters.command("kick50") & filters.group)
async def kick50_command(_, message: Message):
    """Kick users with less than 50 media posts."""
    if not await is_admin_or_sudo(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ This command is for admins/sudo only!")
    
    # Check bot permissions
    try:
        bot_member = await app.get_chat_member(message.chat.id, app.me.id)
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR or not bot_member.privileges.can_restrict_members:
            return await message.reply_text(
                "❌ I need admin permissions with 'Ban users' privilege to use this command!"
            )
    except:
        return await message.reply_text("❌ Failed to check bot permissions!")
    
    msg = await message.reply_text("🔍 Scanning for users with < 50 media posts...")
    
    # Get users with less than 50 media
    low_media_users = await get_low_media_users(message.chat.id, 50)
    
    if not low_media_users:
        return await msg.edit_text("✅ No users found with less than 50 media posts!")
    
    await msg.edit_text(
        f"⚠️ Found **{len(low_media_users)}** users with < 50 media.\n"
        f"Starting removal process..."
    )
    
    kicked_count = 0
    failed_count = 0
    
    for user_id in low_media_users:
        try:
            # Don't kick admins or sudo users
            if await is_admin_or_sudo(message.chat.id, user_id):
                continue
            
            # Kick user
            await app.ban_chat_member(message.chat.id, user_id)
            await asyncio.sleep(0.5)  # Rate limiting
            await app.unban_chat_member(message.chat.id, user_id)
            kicked_count += 1
            
            # Update progress every 10 kicks
            if kicked_count % 10 == 0:
                await msg.edit_text(
                    f"⏳ Progress: {kicked_count}/{len(low_media_users)} removed..."
                )
            
        except Exception as e:
            failed_count += 1
            print(f"[KICK50] Failed to kick user {user_id}: {e}")
            continue
    
    await msg.edit_text(
        f"✅ **Removal Complete**\n\n"
        f"👢 Kicked: **{kicked_count}** users\n"
        f"❌ Failed: **{failed_count}** users\n"
        f"📊 Threshold: < 50 media posts"
    )

@app.on_message(filters.command("inactivekick") & filters.group)
async def inactive_kick_command(_, message: Message):
    """Kick users inactive for specified time."""
    if not await is_admin_or_sudo(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ This command is for admins/sudo only!")
    
    if len(message.command) < 2:
        return await message.reply_text(
            "📝 **Usage:** `/inactivekick <time>`\n\n"
            "**Examples:**\n"
            "• `/inactivekick 7d` - 7 days\n"
            "• `/inactivekick 1M` - 1 month\n"
            "• `/inactivekick 24h` - 24 hours\n\n"
            "**Time units:** s, m, h, d, w, M"
        )
    
    # Parse time
    time_str = message.command[1]
    inactive_seconds = parse_time(time_str)
    
    if not inactive_seconds:
        return await message.reply_text(
            "❌ Invalid time format!\n\n"
            "Use format like: `7d`, `1M`, `24h`"
        )
    
    # Check bot permissions
    try:
        bot_member = await app.get_chat_member(message.chat.id, app.me.id)
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR or not bot_member.privileges.can_restrict_members:
            return await message.reply_text(
                "❌ I need admin permissions with 'Ban users' privilege!"
            )
    except:
        return await message.reply_text("❌ Failed to check bot permissions!")
    
    msg = await message.reply_text(
        f"🔍 Scanning for users inactive for {time_str}..."
    )
    
    # Get inactive users
    inactive_users = await get_inactive_media_users(message.chat.id, inactive_seconds)
    
    if not inactive_users:
        return await msg.edit_text(
            f"✅ No inactive users found for timeframe: {time_str}"
        )
    
    await msg.edit_text(
        f"⚠️ Found **{len(inactive_users)}** inactive users.\n"
        f"Starting removal process..."
    )
    
    kicked_count = 0
    failed_count = 0
    
    for user_id in inactive_users:
        try:
            # Don't kick admins or sudo users
            if await is_admin_or_sudo(message.chat.id, user_id):
                continue
            
            # Kick user
            await app.ban_chat_member(message.chat.id, user_id)
            await asyncio.sleep(0.5)
            await app.unban_chat_member(message.chat.id, user_id)
            kicked_count += 1
            
            # Update progress
            if kicked_count % 10 == 0:
                await msg.edit_text(
                    f"⏳ Progress: {kicked_count}/{len(inactive_users)} removed..."
                )
            
        except Exception as e:
            failed_count += 1
            print(f"[INACTIVEKICK] Failed to kick user {user_id}: {e}")
            continue
    
    await msg.edit_text(
        f"✅ **Removal Complete**\n\n"
        f"👢 Kicked: **{kicked_count}** users\n"
        f"❌ Failed: **{failed_count}** users\n"
        f"⏱ Inactive for: {time_str}"
    )

@app.on_message(filters.command("scaninactive") & filters.group)
async def scan_inactive_command(_, message: Message):
    """Preview inactive users without kicking."""
    if not await is_admin_or_sudo(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ This command is for admins/sudo only!")
    
    if len(message.command) < 2:
        return await message.reply_text(
            "📝 **Usage:** `/scaninactive <time>`\n\n"
            "**Examples:**\n"
            "• `/scaninactive 7d`\n"
            "• `/scaninactive 1M`"
        )
    
    time_str = message.command[1]
    inactive_seconds = parse_time(time_str)
    
    if not inactive_seconds:
        return await message.reply_text("❌ Invalid time format!")
    
    msg = await message.reply_text(f"🔍 Scanning...")
    
    inactive_users = await get_inactive_media_users(message.chat.id, inactive_seconds)
    
    if not inactive_users:
        return await msg.edit_text(f"✅ No inactive users found for {time_str}")
    
    # Get first 10 users for preview
    preview_users = inactive_users[:10]
    user_mentions = []
    
    for user_id in preview_users:
        try:
            user = await app.get_users(user_id)
            user_mentions.append(user.mention)
        except:
            user_mentions.append(f"User {user_id}")
    
    text = f"📊 **Inactive Users Preview**\n\n"
    text += f"Found **{len(inactive_users)}** users inactive for {time_str}\n\n"
    text += f"**First 10:**\n"
    for i, mention in enumerate(user_mentions, 1):
        text += f"{i}. {mention}\n"
    
    if len(inactive_users) > 10:
        text += f"\n... and {len(inactive_users) - 10} more"
    
    text += f"\n\nUse `/inactivekick {time_str}` to remove them."
    
    await msg.edit_text(text)

# ==================== INITIALIZATION ====================

print("✅ Media Deduplication module loaded successfully")
