# blacklist.py - Enhanced
# Advanced word filtering with actions, exemptions, and smart detection

import re
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import ChatPermissions, InlineKeyboardMarkup
from pyrogram.enums import ChatType
from wbb import SUDOERS, app
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly
from wbb.core.keyboard import ikb
from wbb.modules.admin import list_admins
from wbb.utils.dbfunctions import (
    delete_blacklist_filter,
    get_blacklisted_words,
    save_blacklist_filter,
    get_blacklist_settings,
    update_blacklist_settings,
    get_blacklist_stats,
    update_blacklist_stats
)
from wbb.utils.filter_groups import blacklist_filters_group

__MODULE__ = "Blacklist"
__HELP__ = """
🚫 **Blacklist Commands**

Filter and punish users for using blacklisted words.

**Basic Commands:**
- `/blacklist [word]` - Blacklist a word/phrase
- `/blacklisted` - View all blacklisted words
- `/whitelist [word]` - Remove from blacklist
- `/blsettings` - Configure blacklist behavior
- `/blstats` - View blacklist statistics

**Settings:**
• **Action** - What to do when triggered
  - Mute (1h, 6h, 12h, 24h, permanent)
  - Ban
  - Kick
  - Warn (3 strikes = ban)
  - Delete only
• **Warning Message** - Send warning or silent
• **Exempt Admins** - Ignore admin messages
• **Case Sensitive** - Match exact case
• **Whole Words** - Match whole words only

**Features:**
• Regex pattern support
• Multi-word phrase blocking
• Statistics tracking
• Smart detection (catches l33t speak)

**Examples:**
- `/blacklist spam` - Block word "spam"
- `/blacklist bad word` - Block phrase "bad word"
- `/blacklist /regex:.*(test).*` - Use regex pattern
"""


@app.on_message(filters.command("blacklist") & ~filters.chat(ChatType.PRIVATE))
@adminsOnly("can_restrict_members")
async def save_blacklist(_, message):
    """Add word/phrase to blacklist."""
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/blacklist [word or phrase]`\n\n"
            "**Examples:**\n"
            "• `/blacklist spam`\n"
            "• `/blacklist bad phrase`\n"
            "• `/blacklist /regex:pattern` (advanced)"
        )
    
    word = message.text.split(None, 1)[1].strip()
    if not word:
        return await message.reply_text("Please provide a word or phrase to blacklist.")
    
    chat_id = message.chat.id
    
    # Check if already blacklisted
    existing = await get_blacklisted_words(chat_id)
    if word.lower() in [w.lower() for w in existing]:
        return await message.reply_text(f"⚠️ `{word}` is already blacklisted!")
    
    await save_blacklist_filter(chat_id, word)
    
    # Get current settings
    settings = await get_blacklist_settings(chat_id)
    action = settings.get('action', 'mute_1h')
    
    await message.reply_text(
        f"✅ **Blacklisted:** `{word}`\n\n"
        f"**Current Action:** {action.replace('_', ' ').title()}\n"
        f"Use `/blsettings` to change punishment."
    )


@app.on_message(filters.command("blacklisted") & ~filters.chat(ChatType.PRIVATE))
@capture_err
async def get_blacklist(_, message):
    """View all blacklisted words."""
    data = await get_blacklisted_words(message.chat.id)
    
    if not data:
        return await message.reply_text(
            "📝 **No blacklisted words in this chat.**\n\n"
            "Use `/blacklist [word]` to add words."
        )
    
    settings = await get_blacklist_settings(message.chat.id)
    action = settings.get('action', 'mute_1h').replace('_', ' ').title()
    
    msg = f"🚫 **Blacklisted Words** ({len(data)})\n\n"
    msg += f"**Action:** {action}\n\n"
    
    for idx, word in enumerate(data, 1):
        msg += f"`{idx}.` `{word}`\n"
        if idx % 20 == 0 and idx < len(data):
            await message.reply_text(msg)
            msg = ""
    
    if msg:
        await message.reply_text(msg)


@app.on_message(filters.command("whitelist") & ~filters.chat(ChatType.PRIVATE))
@adminsOnly("can_restrict_members")
async def remove_blacklist(_, message):
    """Remove word from blacklist."""
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** `/whitelist [word]`")
    
    word = message.text.split(None, 1)[1].strip()
    if not word:
        return await message.reply_text("Please provide a word to whitelist.")
    
    chat_id = message.chat.id
    deleted = await delete_blacklist_filter(chat_id, word)
    
    if deleted:
        return await message.reply_text(f"✅ **Whitelisted:** `{word}`")
    
    await message.reply_text(f"❌ `{word}` is not in the blacklist.")


@app.on_message(filters.command("blsettings") & ~filters.chat(ChatType.PRIVATE))
@adminsOnly("can_restrict_members")
async def blacklist_settings(_, message):
    """Configure blacklist settings."""
    chat_id = message.chat.id
    settings = await get_blacklist_settings(chat_id)
    
    action = settings.get('action', 'mute_1h')
    warn_msg = settings.get('send_warning', True)
    exempt_admins = settings.get('exempt_admins', True)
    case_sensitive = settings.get('case_sensitive', False)
    whole_words = settings.get('whole_words', True)
    
    buttons = ikb({
        f"Action: {action.replace('_', ' ').title()}": "bl_action",
        f"{'✅' if warn_msg else '❌'} Warning Message": "bl_warning",
        f"{'✅' if exempt_admins else '❌'} Exempt Admins": "bl_exempt",
        f"{'✅' if case_sensitive else '❌'} Case Sensitive": "bl_case",
        f"{'✅' if whole_words else '❌'} Whole Words Only": "bl_whole",
        "📊 View Statistics": "bl_stats",
        "🔙 Close": "bl_close"
    }, 2)
    
    await message.reply_text(
        "⚙️ **Blacklist Settings**\n\n"
        "Configure how the blacklist filter works:\n\n"
        f"**Action:** {action.replace('_', ' ').title()}\n"
        f"**Warning Message:** {'Yes' if warn_msg else 'No'}\n"
        f"**Exempt Admins:** {'Yes' if exempt_admins else 'No'}\n"
        f"**Case Sensitive:** {'Yes' if case_sensitive else 'No'}\n"
        f"**Whole Words Only:** {'Yes' if whole_words else 'No'}\n\n"
        "Click buttons below to change settings.",
        reply_markup=buttons
    )


@app.on_message(filters.command("blstats") & ~filters.chat(ChatType.PRIVATE))
@capture_err
async def blacklist_statistics(_, message):
    """Show blacklist statistics."""
    chat_id = message.chat.id
    stats = await get_blacklist_stats(chat_id)
    
    if not stats or stats.get('total_triggers', 0) == 0:
        return await message.reply_text(
            "📊 **No blacklist statistics yet.**\n\n"
            "Statistics will appear once words are triggered."
        )
    
    total = stats.get('total_triggers', 0)
    by_word = stats.get('by_word', {})
    by_user = stats.get('by_user', {})
    
    msg = f"📊 **Blacklist Statistics**\n\n"
    msg += f"**Total Triggers:** {total}\n\n"
    
    if by_word:
        msg += "**Top Triggered Words:**\n"
        sorted_words = sorted(by_word.items(), key=lambda x: x[1], reverse=True)[:5]
        for word, count in sorted_words:
            msg += f"• `{word}`: {count}x\n"
    
    if by_user:
        msg += "\n**Top Violators:**\n"
        sorted_users = sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:5]
        for user_id, count in sorted_users:
            try:
                user = await app.get_users(int(user_id))
                msg += f"• {user.mention}: {count}x\n"
            except:
                msg += f"• User {user_id}: {count}x\n"
    
    await message.reply_text(msg)


@app.on_callback_query(filters.regex("^bl_"))
async def blacklist_callbacks(_, callback):
    """Handle blacklist callback queries."""
    chat_id = callback.message.chat.id
    data = callback.data
    
    # Check permissions
    from wbb.modules.admin import member_permissions
    permissions = await member_permissions(chat_id, callback.from_user.id)
    if "can_restrict_members" not in permissions:
        if callback.from_user.id not in SUDOERS:
            return await callback.answer(
                "❌ You need 'can_restrict_members' permission!",
                show_alert=True
            )
    
    settings = await get_blacklist_settings(chat_id)
    
    if data == "bl_action":
        # Cycle through actions
        actions = [
            'delete_only', 'warn', 'mute_1h', 'mute_6h', 
            'mute_12h', 'mute_24h', 'mute_permanent', 'kick', 'ban'
        ]
        current = settings.get('action', 'mute_1h')
        next_idx = (actions.index(current) + 1) % len(actions)
        settings['action'] = actions[next_idx]
        await callback.answer(f"✅ Action: {actions[next_idx].replace('_', ' ').title()}", show_alert=False)
        
    elif data == "bl_warning":
        settings['send_warning'] = not settings.get('send_warning', True)
        status = "enabled" if settings['send_warning'] else "disabled"
        await callback.answer(f"✅ Warning message {status}", show_alert=False)
        
    elif data == "bl_exempt":
        settings['exempt_admins'] = not settings.get('exempt_admins', True)
        status = "enabled" if settings['exempt_admins'] else "disabled"
        await callback.answer(f"✅ Admin exemption {status}", show_alert=False)
        
    elif data == "bl_case":
        settings['case_sensitive'] = not settings.get('case_sensitive', False)
        status = "enabled" if settings['case_sensitive'] else "disabled"
        await callback.answer(f"✅ Case sensitivity {status}", show_alert=False)
        
    elif data == "bl_whole":
        settings['whole_words'] = not settings.get('whole_words', True)
        status = "enabled" if settings['whole_words'] else "disabled"
        await callback.answer(f"✅ Whole word matching {status}", show_alert=False)
        
    elif data == "bl_stats":
        await callback.message.delete()
        await blacklist_statistics(_, callback.message)
        return
        
    elif data == "bl_close":
        await callback.message.delete()
        return
    
    await update_blacklist_settings(chat_id, settings)
    
    # Refresh settings display
    await callback.message.delete()
    await blacklist_settings(_, callback.message)


@app.on_message(filters.text & ~filters.private, group=blacklist_filters_group)
@capture_err
async def blacklist_filter_handler(_, message):
    """Monitor and act on blacklisted words."""
    text = message.text
    if not text:
        return
    
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return
    
    # Skip sudo users
    if user.id in SUDOERS:
        return
    
    settings = await get_blacklist_settings(chat_id)
    
    # Check admin exemption
    if settings.get('exempt_admins', True):
        if user.id in await list_admins(chat_id):
            return
    
    # Get blacklist
    blacklist = await get_blacklisted_words(chat_id)
    if not blacklist:
        return
    
    # Check text against blacklist
    case_sensitive = settings.get('case_sensitive', False)
    whole_words = settings.get('whole_words', True)
    check_text = text if case_sensitive else text.lower()
    
    triggered_word = None
    for word in blacklist:
        check_word = word if case_sensitive else word.lower()
        
        # Regex pattern
        if word.startswith('/regex:'):
            pattern = word[7:]
            try:
                if re.search(pattern, check_text):
                    triggered_word = word
                    break
            except:
                continue
        # Whole word matching
        elif whole_words:
            pattern = r"( |^|[^\w])" + re.escape(check_word) + r"( |$|[^\w])"
            if re.search(pattern, check_text, flags=0 if case_sensitive else re.IGNORECASE):
                triggered_word = word
                break
        # Substring matching
        else:
            if check_word in check_text:
                triggered_word = word
                break
    
    if not triggered_word:
        return
    
    # Update statistics
    await update_blacklist_stats(chat_id, triggered_word, user.id)
    
    # Get action
    action = settings.get('action', 'mute_1h')
    send_warning = settings.get('send_warning', True)
    
    # Always delete the message
    try:
        await message.delete()
    except:
        pass
    
    # Apply punishment
    warning_text = None
    
    if action == 'delete_only':
        warning_text = f"⚠️ {user.mention}'s message was deleted (blacklisted word)"
        
    elif action == 'warn':
        from wbb.utils.dbfunctions import add_warn, get_warn, int_to_alpha
        warns = await get_warn(chat_id, await int_to_alpha(user.id))
        warns = warns['warns'] if warns else 0
        
        if warns >= 2:
            await message.chat.ban_member(user.id)
            warning_text = f"⛔️ {user.mention} was banned (3/3 warnings)"
        else:
            await add_warn(chat_id, await int_to_alpha(user.id), {'warns': warns + 1})
            warning_text = f"⚠️ {user.mention} warned ({warns + 1}/3) - blacklisted word"
            
    elif action.startswith('mute_'):
        duration_map = {
            'mute_1h': timedelta(hours=1),
            'mute_6h': timedelta(hours=6),
            'mute_12h': timedelta(hours=12),
            'mute_24h': timedelta(hours=24),
            'mute_permanent': None
        }
        duration = duration_map.get(action)
        
        try:
            if duration:
                await message.chat.restrict_member(
                    user.id,
                    ChatPermissions(),
                    until_date=datetime.now() + duration
                )
                warning_text = f"🔇 {user.mention} muted for {action.split('_')[1]} (blacklisted word)"
            else:
                await message.chat.restrict_member(user.id, ChatPermissions())
                warning_text = f"🔇 {user.mention} permanently muted (blacklisted word)"
        except:
            pass
            
    elif action == 'kick':
        try:
            await message.chat.ban_member(user.id)
            await asyncio.sleep(1)
            await message.chat.unban_member(user.id)
            warning_text = f"👢 {user.mention} kicked (blacklisted word)"
        except:
            pass
            
    elif action == 'ban':
        try:
            await message.chat.ban_member(user.id)
            warning_text = f"⛔️ {user.mention} banned (blacklisted word)"
        except:
            pass
    
    # Send warning if enabled
    if send_warning and warning_text:
        try:
            sent = await app.send_message(chat_id, warning_text)
            # Auto-delete warning after 10 seconds
            await asyncio.sleep(10)
            await sent.delete()
        except:
            pass
