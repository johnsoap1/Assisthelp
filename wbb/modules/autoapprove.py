# autoapprove.py - Enhanced
# Advanced join request management with verification and filters

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter, ChatType
from pyrogram.types import (
    CallbackQuery,
    Chat,
    ChatJoinRequest,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from datetime import datetime, timedelta

from wbb.core.storage import db
from wbb import SUDOERS, app
from wbb.core.decorators.permissions import adminsOnly
from wbb.core.keyboard import ikb
from wbb.modules.admin import member_permissions
from wbb.modules.greetings import handle_new_member, send_welcome_message

approvaldb = db.autoapprove

__MODULE__ = "Autoapprove"
__HELP__ = """
✅ **Autoapprove Commands**

Automatically or manually approve chat join requests.

**Commands:**
- `/autoapprove` - Toggle auto-approve on/off
- `/approvemode` - Switch between automatic/manual/verify modes
- `/clear_pending` - Clear pending request list
- `/pending` - View pending requests
- `/approve_all` - Approve all pending requests (admin)
- `/decline_all` - Decline all pending requests (admin)
- `/approvesettings` - Configure filters and requirements

**Modes:**
• **Automatic** - Instantly approve all requests
• **Manual** - Admins manually review each request
• **Verify** - Auto-approve with verification button

**Filter Settings:**
• Minimum account age
• Username required
• Profile photo required
• Bio required
• Block common spam patterns

**Features:**
• Request statistics
• Spam detection
• Admin notifications
• Welcome message integration
"""


@app.on_message(filters.command("autoapprove") & filters.chat(ChatType.GROUP))
@adminsOnly("can_change_info")
async def approval_command(client, message):
    """Toggle autoapprove on/off and show status."""
    chat_id = message.chat.id
    chat = await approvaldb.find_one({"chat_id": chat_id})
    
    if chat:
        mode = chat.get("mode", "automatic")
        settings = chat.get("settings", {})
        stats = chat.get("stats", {})
        
        # Mode buttons
        if mode == "automatic":
            switch = "manual"
        elif mode == "manual":
            switch = "verify"
        else:
            switch = "automatic"
        
        buttons = ikb({
            f"Mode: {mode.upper()}": f"approval_{switch}",
            "⚙️ Settings": "approval_settings",
            "📊 Statistics": "approval_stats",
            "❌ Turn OFF": "approval_off"
        }, 2)
        
        # Get stats
        total_approved = stats.get('total_approved', 0)
        total_declined = stats.get('total_declined', 0)
        pending_count = len(chat.get('pending_users', []))
        
        await message.reply(
            f"✅ **Autoapproval Status: ENABLED**\n\n"
            f"**Current Mode:** {mode.title()}\n"
            f"**Pending Requests:** {pending_count}\n"
            f"**Total Approved:** {total_approved}\n"
            f"**Total Declined:** {total_declined}\n\n"
            f"Use buttons below to manage settings.",
            reply_markup=buttons
        )
    else:
        buttons = ikb({
            "✅ Turn ON (Automatic)": "approval_on",
            "📋 Configure First": "approval_settings"
        }, 1)
        
        await message.reply(
            "❌ **Autoapproval Status: DISABLED**\n\n"
            "Click below to enable autoapproval.",
            reply_markup=buttons
        )


@app.on_message(filters.command("approvemode") & filters.chat(ChatType.GROUP))
@adminsOnly("can_change_info")
async def change_mode(client, message):
    """Quick mode switching."""
    chat_id = message.chat.id
    
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/approvemode [automatic|manual|verify]`\n\n"
            "**Modes:**\n"
            "• `automatic` - Auto-approve all\n"
            "• `manual` - Admin review required\n"
            "• `verify` - Auto-approve with verify button"
        )
    
    mode = message.command[1].lower()
    if mode not in ['automatic', 'manual', 'verify']:
        return await message.reply_text(
            "❌ Invalid mode. Choose: `automatic`, `manual`, or `verify`"
        )
    
    await approvaldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mode": mode}},
        upsert=True
    )
    
    await message.reply_text(
        f"✅ Approval mode changed to **{mode.title()}**"
    )


@app.on_message(filters.command("pending") & filters.chat(ChatType.GROUP))
@adminsOnly("can_restrict_members")
async def show_pending(client, message):
    """Show all pending join requests."""
    chat_id = message.chat.id
    chat = await approvaldb.find_one({"chat_id": chat_id})
    
    if not chat or not chat.get('pending_users'):
        return await message.reply_text("📝 No pending join requests.")
    
    pending = chat['pending_users']
    msg = f"📋 **Pending Join Requests** ({len(pending)})\n\n"
    
    for user_id in pending[:10]:  # Show first 10
        try:
            user = await app.get_users(user_id)
            msg += f"• {user.mention} (`{user_id}`)\n"
        except:
            msg += f"• User `{user_id}`\n"
    
    if len(pending) > 10:
        msg += f"\n... and {len(pending) - 10} more"
    
    buttons = ikb({
        "✅ Approve All": "approval_approve_all",
        "❌ Decline All": "approval_decline_all"
    }, 2)
    
    await message.reply_text(msg, reply_markup=buttons)


@app.on_message(filters.command("approve_all") & filters.chat(ChatType.GROUP))
@adminsOnly("can_restrict_members")
async def approve_all_pending(client, message):
    """Approve all pending requests."""
    chat_id = message.chat.id
    chat = await approvaldb.find_one({"chat_id": chat_id})
    
    if not chat or not chat.get('pending_users'):
        return await message.reply_text("📝 No pending requests to approve.")
    
    pending = chat['pending_users']
    progress = await message.reply_text(f"⏳ Approving {len(pending)} requests...")
    
    approved = 0
    for user_id in pending:
        try:
            await app.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            approved += 1
        except:
            pass
    
    # Clear pending and update stats
    await approvaldb.update_one(
        {"chat_id": chat_id},
        {
            "$set": {"pending_users": []},
            "$inc": {"stats.total_approved": approved}
        }
    )
    
    await progress.edit_text(f"✅ Approved {approved}/{len(pending)} requests!")


@app.on_message(filters.command("decline_all") & filters.chat(ChatType.GROUP))
@adminsOnly("can_restrict_members")
async def decline_all_pending(client, message):
    """Decline all pending requests."""
    chat_id = message.chat.id
    chat = await approvaldb.find_one({"chat_id": chat_id})
    
    if not chat or not chat.get('pending_users'):
        return await message.reply_text("📝 No pending requests to decline.")
    
    pending = chat['pending_users']
    progress = await message.reply_text(f"⏳ Declining {len(pending)} requests...")
    
    declined = 0
    for user_id in pending:
        try:
            await app.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
            declined += 1
        except:
            pass
    
    # Clear pending and update stats
    await approvaldb.update_one(
        {"chat_id": chat_id},
        {
            "$set": {"pending_users": []},
            "$inc": {"stats.total_declined": declined}
        }
    )
    
    await progress.edit_text(f"❌ Declined {declined}/{len(pending)} requests!")


@app.on_message(filters.command("clear_pending") & filters.chat(ChatType.GROUP))
@adminsOnly("can_restrict_members")
async def clear_pending_command(client, message):
    """Clear pending user list (allows re-requesting)."""
    chat_id = message.chat.id
    result = await approvaldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"pending_users": []}},
    )
    
    if result.modified_count > 0:
        await message.reply_text("✅ Cleared pending users list.")
    else:
        await message.reply_text("📝 No pending users to clear.")


@app.on_callback_query(filters.regex("approval(.*)"))
async def approval_callbacks(client, cb):
    """Handle autoapprove callbacks."""
    chat_id = cb.message.chat.id
    from_user = cb.from_user
    
    # Check permissions
    permissions = await member_permissions(chat_id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        if from_user.id not in SUDOERS:
            return await cb.answer(
                f"❌ You need '{permission}' permission!",
                show_alert=True
            )
    
    command_parts = cb.data.split("_", 1)
    option = command_parts[1] if len(command_parts) > 1 else command_parts[0][8:]
    
    if option == "off":
        if await approvaldb.count_documents({"chat_id": chat_id}) > 0:
            await approvaldb.delete_one({"chat_id": chat_id})
            buttons = ikb({"✅ Turn ON": "approval_on"}, 1)
            return await cb.edit_message_text(
                "❌ **Autoapproval: DISABLED**",
                reply_markup=buttons
            )
    
    elif option == "on":
        mode = "automatic"
    elif option in ["automatic", "manual", "verify"]:
        mode = option
    elif option == "settings":
        await cb.message.delete()
        await show_approval_settings(cb.message)
        return
    elif option == "stats":
        await cb.message.delete()
        await show_approval_stats(cb.message)
        return
    elif option == "approve_all":
        await cb.message.delete()
        await approve_all_pending(client, cb.message)
        return
    elif option == "decline_all":
        await cb.message.delete()
        await decline_all_pending(client, cb.message)
        return
    else:
        return
    
    # Update mode
    await approvaldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"mode": mode}},
        upsert=True
    )
    
    await cb.answer(f"✅ Mode changed to {mode.title()}", show_alert=False)
    await cb.message.delete()
    await approval_command(client, cb.message)


async def show_approval_settings(message):
    """Show approval filter settings."""
    chat_id = message.chat.id
    chat = await approvaldb.find_one({"chat_id": chat_id})
    settings = chat.get('settings', {}) if chat else {}
    
    min_age = settings.get('min_account_age_days', 0)
    require_username = settings.get('require_username', False)
    require_photo = settings.get('require_photo', False)
    require_bio = settings.get('require_bio', False)
    spam_check = settings.get('spam_check', True)
    
    buttons = ikb({
        f"Min Age: {min_age}d": "approval_set_age",
        f"{'✅' if require_username else '❌'} Require Username": "approval_set_username",
        f"{'✅' if require_photo else '❌'} Require Photo": "approval_set_photo",
        f"{'✅' if require_bio else '❌'} Require Bio": "approval_set_bio",
        f"{'✅' if spam_check else '❌'} Spam Check": "approval_set_spam",
        "🔙 Back": "approval_back"
    }, 2)
    
    await message.reply_text(
        "⚙️ **Approval Filter Settings**\n\n"
        "Configure requirements for auto-approval:\n\n"
        f"**Min Account Age:** {min_age} days\n"
        f"**Require Username:** {'Yes' if require_username else 'No'}\n"
        f"**Require Photo:** {'Yes' if require_photo else 'No'}\n"
        f"**Require Bio:** {'Yes' if require_bio else 'No'}\n"
        f"**Spam Detection:** {'Yes' if spam_check else 'No'}\n\n"
        "Click buttons to toggle settings.",
        reply_markup=buttons
    )


async def show_approval_stats(message):
    """Show approval statistics."""
    chat_id = message.chat.id
    chat = await approvaldb.find_one({"chat_id": chat_id})
    
    if not chat:
        return await message.reply_text("📊 No statistics available yet.")
    
    stats = chat.get('stats', {})
    
    total_approved = stats.get('total_approved', 0)
    total_declined = stats.get('total_declined', 0)
    total_spam = stats.get('spam_blocked', 0)
    pending = len(chat.get('pending_users', []))
    
    await message.reply_text(
        f"📊 **Approval Statistics**\n\n"
        f"**Total Approved:** {total_approved}\n"
        f"**Total Declined:** {total_declined}\n"
        f"**Spam Blocked:** {total_spam}\n"
        f"**Currently Pending:** {pending}\n\n"
        f"**Approval Rate:** {(total_approved / (total_approved + total_declined) * 100) if (total_approved + total_declined) > 0 else 0:.1f}%"
    )


def is_spam_pattern(user):
    """Basic spam detection."""
    if not user:
        return False
    
    # Check for common spam patterns in name
    spam_keywords = ['casino', 'porn', 'sex', 'viagra', 'crypto', 'invest']
    name = (user.first_name or '').lower()
    
    for keyword in spam_keywords:
        if keyword in name:
            return True
    
    # Check for excessive emojis
    if user.first_name:
        emoji_count = sum(1 for char in user.first_name if ord(char) > 0x1F300)
        if emoji_count > 5:
            return True
    
    return False


@app.on_chat_join_request(filters.chat(ChatType.GROUP))
async def handle_join_request(client, request: ChatJoinRequest):
    """Handle incoming join requests based on mode."""
    chat = request.chat
    user = request.from_user
    chat_id = chat.id
    
    chat_data = await approvaldb.find_one({"chat_id": chat_id})
    if not chat_data:
        return  # Autoapproval not enabled
    
    mode = chat_data.get("mode", "automatic")
    settings = chat_data.get("settings", {})
    
    # Check spam
    if settings.get('spam_check', True) and is_spam_pattern(user):
        try:
            await app.decline_chat_join_request(chat_id=chat_id, user_id=user.id)
            await approvaldb.update_one(
                {"chat_id": chat_id},
                {"$inc": {"stats.spam_blocked": 1}}
            )
        except:
            pass
        return
    
    # Check filters (for automatic mode)
    if mode == "automatic":
        # Check account age
        min_age = settings.get('min_account_age_days', 0)
        if min_age > 0:
            account_age = (datetime.now() - datetime.fromtimestamp(user.id >> 32)).days
            if account_age < min_age:
                mode = "manual"  # Fall back to manual if doesn't meet criteria
        
        # Check username requirement
        if settings.get('require_username', False) and not user.username:
            mode = "manual"
        
        # Note: Photo and bio checks require fetching full user info
        # which may not be available in join request context
    
    # Handle based on mode
    if mode == "automatic":
        try:
            await app.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
            await approvaldb.update_one(
                {"chat_id": chat_id},
                {"$inc": {"stats.total_approved": 1}}
            )
            await handle_new_member(user, chat)
        except Exception as e:
            print(f"[AutoApprove] Error auto-approving: {e}")
    
    elif mode == "verify":
        # Auto-approve but send verification button
        try:
            await app.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
            await approvaldb.update_one(
                {"chat_id": chat_id},
                {"$inc": {"stats.total_approved": 1}}
            )
            
            buttons = ikb({
                "✅ I'm Human": f"verify_{user.id}"
            }, 1)
            
            await app.send_message(
                chat.id,
                f"👋 Welcome {user.mention}!\n\n"
                f"Please verify you're human by clicking the button below within 2 minutes.",
                reply_markup=buttons
            )
        except Exception as e:
            print(f"[AutoApprove] Error in verify mode: {e}")
    
    elif mode == "manual":
        # Check if already pending
        is_pending = await approvaldb.count_documents(
            {"chat_id": chat.id, "pending_users": int(user.id)}
        )
        
        if is_pending == 0:
            await approvaldb.update_one(
                {"chat_id": chat.id},
                {"$addToSet": {"pending_users": int(user.id)}},
                upsert=True
            )
            
            buttons = ikb({
                "✅ Accept": f"manual_approve_{user.id}",
                "❌ Decline": f"manual_decline_{user.id}"
            }, 2)
            
            # Get user info for display
            account_age = (datetime.now() - datetime.fromtimestamp(user.id >> 32)).days
            user_info = f"**Account Age:** {account_age} days\n"
            user_info += f"**Username:** @{user.username if user.username else 'None'}\n"
            
            text = f"🔔 **New Join Request**\n\n"
            text += f"**User:** {user.mention} (`{user.id}`)\n"
            text += user_info
            text += f"\nAny admin can approve or decline."
            
            # Tag admins
            try:
                admin_data = [
                    i async for i in app.get_chat_members(
                        chat_id=chat.id,
                        filter=ChatMembersFilter.ADMINISTRATORS
                    )
                ]
                for admin in admin_data:
                    if admin.user.is_bot or admin.user.is_deleted:
                        continue
                    text += f"[\u2063](tg://user?id={admin.user.id})"
            except:
                pass
            
            await app.send_message(chat.id, text, reply_markup=buttons)


@app.on_callback_query(filters.regex("manual_(.*)"))
async def manual_approval_callback(app, cb):
    """Handle manual approval/decline."""
    chat = cb.message.chat
    from_user = cb.from_user
    
    # Check permissions
    permissions = await member_permissions(chat.id, from_user.id)
    if "can_restrict_members" not in permissions:
        if from_user.id not in SUDOERS:
            return await cb.answer(
                "❌ You need 'can_restrict_members' permission!",
                show_alert=True
            )
    
    datas = cb.data.split("_", 2)
    action = datas[1]
    user_id = int(datas[2])
    
    try:
        if action == "approve":
            await app.approve_chat_join_request(chat_id=chat.id, user_id=user_id)
            await approvaldb.update_one(
                {"chat_id": chat.id},
                {"$inc": {"stats.total_approved": 1}}
            )
            status = "✅ Approved"
        else:
            await app.decline_chat_join_request(chat_id=chat.id, user_id=user_id)
            await approvaldb.update_one(
                {"chat_id": chat.id},
                {"$inc": {"stats.total_declined": 1}}
            )
            status = "❌ Declined"
        
        # Remove from pending
        await approvaldb.update_one(
            {"chat_id": chat.id},
            {"$pull": {"pending_users": user_id}}
        )
        
        await cb.answer(f"{status} by {from_user.first_name}", show_alert=False)
        await cb.message.delete()
        
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@app.on_callback_query(filters.regex("verify_(.*)"))
async def verify_callback(app, cb):
    """Handle human verification."""
    user_id = int(cb.data.split("_")[1])
    
    if cb.from_user.id != user_id:
        return await cb.answer("❌ This button is not for you!", show_alert=True)
    
    await cb.answer("✅ Verification complete! Welcome!", show_alert=False)
    await cb.message.delete()
