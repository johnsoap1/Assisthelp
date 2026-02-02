# antiservice.py - Enhanced
# Advanced service message and command cleanup with granular controls

import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from wbb import app, SUDOERS
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly
from wbb.core.keyboard import ikb
from wbb.utils.dbfunctions import (
    is_antiservice_on,
    antiservice_on,
    antiservice_off,
    get_antiservice_settings,
    update_antiservice_settings
)

__MODULE__ = "AntiService"
__HELP__ = """
🗑️ **Anti-Service Commands**

Automatically remove service messages and commands with granular controls.

**Commands:**
- `/antiservice` - Show current status & settings
- `/antiservice on` - Enable anti-service mode
- `/antiservice off` - Disable anti-service mode
- `/antiservice config` - Configure what to delete

**Settings (via config):**
• Delete join messages
• Delete leave messages
• Delete pinned messages
• Delete title/photo changes
• Delete command messages
• Set command deletion delay (1-10 seconds)

**Features:**
• Per-chat customization
• Admin bypass option
• Statistics tracking
• Detailed logging

**Note:** Bot needs delete message permissions.
"""

# Deletion statistics cache
deletion_stats = {}


@app.on_message(filters.command("antiservice") & filters.group)
@adminsOnly("can_delete_messages")
@capture_err
async def antiservice_command(_, message):
    """Main antiservice command handler."""
    chat_id = message.chat.id
    args = message.command[1:] if len(message.command) > 1 else []
    
    # No arguments - show status
    if not args:
        status = await is_antiservice_on(chat_id)
        settings = await get_antiservice_settings(chat_id)
        
        stats = deletion_stats.get(chat_id, {
            'services': 0, 
            'commands': 0, 
            'total': 0
        })
        
        status_emoji = "✅" if status else "❌"
        status_text = "**Enabled**" if status else "**Disabled**"
        
        config_text = "**Current Configuration:**\n"
        if settings:
            config_text += f"• Join messages: {'✅' if settings.get('delete_joins', True) else '❌'}\n"
            config_text += f"• Leave messages: {'✅' if settings.get('delete_leaves', True) else '❌'}\n"
            config_text += f"• Pinned messages: {'✅' if settings.get('delete_pins', True) else '❌'}\n"
            config_text += f"• Title/Photo changes: {'✅' if settings.get('delete_changes', True) else '❌'}\n"
            config_text += f"• Commands: {'✅' if settings.get('delete_commands', True) else '❌'}\n"
            config_text += f"• Command delay: {settings.get('command_delay', 2)}s\n"
            config_text += f"• Admin bypass: {'✅' if settings.get('admin_bypass', False) else '❌'}\n"
        else:
            config_text += "• Using default settings (all enabled)\n"
        
        stats_text = f"\n**Statistics (this session):**\n"
        stats_text += f"• Service messages deleted: {stats['services']}\n"
        stats_text += f"• Commands deleted: {stats['commands']}\n"
        stats_text += f"• Total deleted: {stats['total']}\n"
        
        buttons = ikb({
            "⚙️ Configure": "as_config",
            "✅ Enable" if not status else "❌ Disable": "as_toggle",
            "📊 Reset Stats": "as_reset_stats"
        }, 2)
        
        await message.reply_text(
            f"🗑️ **Anti-Service Status**\n\n"
            f"Status: {status_emoji} {status_text}\n\n"
            f"{config_text}"
            f"{stats_text}\n"
            f"Use buttons below to manage settings.",
            reply_markup=buttons
        )
        return
    
    # Handle on/off
    action = args[0].lower()
    
    if action in ["on", "enable", "yes"]:
        await antiservice_on(chat_id)
        await message.reply_text(
            "✅ **Anti-Service Enabled**\n\n"
            "Service messages and commands will be automatically deleted.\n"
            "Use `/antiservice config` to customize what gets deleted."
        )
    elif action in ["off", "disable", "no"]:
        await antiservice_off(chat_id)
        await message.reply_text(
            "❌ **Anti-Service Disabled**\n\n"
            "Service messages and commands will not be deleted."
        )
    elif action == "config":
        await show_config_menu(message)
    else:
        await message.reply_text(
            "❌ Invalid option.\n\n"
            "**Usage:**\n"
            "• `/antiservice` - Show status\n"
            "• `/antiservice on` - Enable\n"
            "• `/antiservice off` - Disable\n"
            "• `/antiservice config` - Configure settings"
        )


async def show_config_menu(message):
    """Show configuration menu."""
    chat_id = message.chat.id
    settings = await get_antiservice_settings(chat_id)
    
    buttons = ikb({
        f"{'✅' if settings.get('delete_joins', True) else '❌'} Joins": "as_cfg_joins",
        f"{'✅' if settings.get('delete_leaves', True) else '❌'} Leaves": "as_cfg_leaves",
        f"{'✅' if settings.get('delete_pins', True) else '❌'} Pins": "as_cfg_pins",
        f"{'✅' if settings.get('delete_changes', True) else '❌'} Changes": "as_cfg_changes",
        f"{'✅' if settings.get('delete_commands', True) else '❌'} Commands": "as_cfg_commands",
        f"⏱ Delay: {settings.get('command_delay', 2)}s": "as_cfg_delay",
        f"{'✅' if settings.get('admin_bypass', False) else '❌'} Admin Bypass": "as_cfg_bypass",
        "🔙 Back": "as_back"
    }, 2)
    
    await message.reply_text(
        "⚙️ **Anti-Service Configuration**\n\n"
        "Click buttons to toggle settings:\n\n"
        "• **Joins** - User joined messages\n"
        "• **Leaves** - User left messages\n"
        "• **Pins** - Pinned message notifications\n"
        "• **Changes** - Title/photo changes\n"
        "• **Commands** - Command messages\n"
        "• **Delay** - Command deletion delay\n"
        "• **Admin Bypass** - Don't delete admin commands",
        reply_markup=buttons
    )


@app.on_callback_query(filters.regex("^as_"))
async def antiservice_callbacks(_, callback):
    """Handle antiservice callback queries."""
    chat_id = callback.message.chat.id
    data = callback.data
    
    # Check admin permission
    from wbb.modules.admin import member_permissions
    permissions = await member_permissions(chat_id, callback.from_user.id)
    if "can_delete_messages" not in permissions:
        if callback.from_user.id not in SUDOERS:
            return await callback.answer(
                "❌ You need 'can_delete_messages' permission!",
                show_alert=True
            )
    
    if data == "as_toggle":
        status = await is_antiservice_on(chat_id)
        if status:
            await antiservice_off(chat_id)
            await callback.answer("✅ Anti-Service disabled", show_alert=False)
        else:
            await antiservice_on(chat_id)
            await callback.answer("✅ Anti-Service enabled", show_alert=False)
        
        # Refresh the status message
        await antiservice_command(_, callback.message)
        await callback.message.delete()
        
    elif data == "as_config":
        await callback.message.delete()
        await show_config_menu(callback.message)
        
    elif data == "as_reset_stats":
        if chat_id in deletion_stats:
            deletion_stats[chat_id] = {'services': 0, 'commands': 0, 'total': 0}
        await callback.answer("📊 Statistics reset!", show_alert=False)
        await antiservice_command(_, callback.message)
        await callback.message.delete()
        
    elif data == "as_back":
        await callback.message.delete()
        await antiservice_command(_, callback.message)
        
    elif data.startswith("as_cfg_"):
        setting = data.replace("as_cfg_", "")
        settings = await get_antiservice_settings(chat_id)
        
        if setting == "joins":
            settings['delete_joins'] = not settings.get('delete_joins', True)
        elif setting == "leaves":
            settings['delete_leaves'] = not settings.get('delete_leaves', True)
        elif setting == "pins":
            settings['delete_pins'] = not settings.get('delete_pins', True)
        elif setting == "changes":
            settings['delete_changes'] = not settings.get('delete_changes', True)
        elif setting == "commands":
            settings['delete_commands'] = not settings.get('delete_commands', True)
        elif setting == "bypass":
            settings['admin_bypass'] = not settings.get('admin_bypass', False)
        elif setting == "delay":
            # Cycle through delays: 1, 2, 3, 5, 10
            current = settings.get('command_delay', 2)
            delays = [1, 2, 3, 5, 10]
            next_idx = (delays.index(current) + 1) % len(delays)
            settings['command_delay'] = delays[next_idx]
        
        await update_antiservice_settings(chat_id, settings)
        await callback.answer("✅ Setting updated!", show_alert=False)
        
        # Update the message
        await callback.message.delete()
        await show_config_menu(callback.message)


# ────────────────────────────────────────────────
#  Delete service messages
# ────────────────────────────────────────────────
@app.on_message(
    filters.group & (
        filters.new_chat_members |
        filters.left_chat_member |
        filters.new_chat_title |
        filters.new_chat_photo |
        filters.delete_chat_photo |
        filters.pinned_message |
        filters.group_chat_created |
        filters.supergroup_chat_created |
        filters.channel_chat_created
    ),
    group=-1
)
@capture_err
async def delete_service_messages(_, message):
    """Delete service messages based on settings."""
    try:
        chat_id = message.chat.id
        
        # Check if antiservice is enabled
        if not await is_antiservice_on(chat_id):
            return
        
        settings = await get_antiservice_settings(chat_id)
        should_delete = False
        
        # Check specific message type against settings
        if message.new_chat_members and settings.get('delete_joins', True):
            should_delete = True
        elif message.left_chat_member and settings.get('delete_leaves', True):
            should_delete = True
        elif message.pinned_message and settings.get('delete_pins', True):
            should_delete = True
        elif (message.new_chat_title or message.new_chat_photo or 
              message.delete_chat_photo) and settings.get('delete_changes', True):
            should_delete = True
        elif (message.group_chat_created or message.supergroup_chat_created or 
              message.channel_chat_created):
            should_delete = True
        
        if should_delete:
            await message.delete()
            
            # Update stats
            if chat_id not in deletion_stats:
                deletion_stats[chat_id] = {'services': 0, 'commands': 0, 'total': 0}
            deletion_stats[chat_id]['services'] += 1
            deletion_stats[chat_id]['total'] += 1
            
    except Exception as e:
        print(f"[AntiService] Error deleting service message in {message.chat.id}: {e}")


# ────────────────────────────────────────────────
#  Delete commands after processing
# ────────────────────────────────────────────────
@app.on_message(
    filters.group & filters.text & filters.regex(r"^/"),
    group=10
)
@capture_err
async def delete_commands(_, message):
    """Delete command messages with configurable delay."""
    try:
        chat_id = message.chat.id
        
        # Skip bot messages
        if message.from_user and message.from_user.is_bot:
            return
        
        # Check if enabled
        if not await is_antiservice_on(chat_id):
            return
        
        settings = await get_antiservice_settings(chat_id)
        
        # Check if command deletion is enabled
        if not settings.get('delete_commands', True):
            return
        
        # Check admin bypass
        if settings.get('admin_bypass', False):
            from wbb.modules.admin import list_admins
            if message.from_user.id in await list_admins(chat_id):
                return
        
        # Get delay setting
        delay = settings.get('command_delay', 2)
        
        # Wait for bot to respond
        await asyncio.sleep(delay)
        await message.delete()
        
        # Update stats
        if chat_id not in deletion_stats:
            deletion_stats[chat_id] = {'services': 0, 'commands': 0, 'total': 0}
        deletion_stats[chat_id]['commands'] += 1
        deletion_stats[chat_id]['total'] += 1
        
    except Exception as e:
        print(f"[AntiService] Error deleting command in {message.chat.id}: {e}")
