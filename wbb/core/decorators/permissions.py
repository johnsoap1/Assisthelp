from functools import wraps
from traceback import format_exc as err

from pyrogram.errors import ChatWriteForbidden
from pyrogram.types import Message, ChatMember


async def member_permissions(chat_id: int, user_id: int):
    """Get list of permissions for a member in a chat."""
    from wbb import app
    
    perms = []
    try:
        # Check if chat_id is actually a user ID (private chat)
        if chat_id > 0:
            # In private chats, users have all permissions
            return [
                "can_post_messages", "can_edit_messages",
                "can_delete_messages", "can_restrict_members",
                "can_promote_members", "can_change_info",
                "can_invite_users", "can_pin_messages",
                "can_manage_video_chats"
            ]
            
        # For group/supergroup/channel
        member = await app.get_chat_member(chat_id, user_id)
        if not member or not hasattr(member, 'privileges') or not member.privileges:
            return []
            
        priv = member.privileges
        if priv.can_post_messages:
            perms.append("can_post_messages")
        if priv.can_edit_messages:
            perms.append("can_edit_messages")
        if priv.can_delete_messages:
            perms.append("can_delete_messages")
        if priv.can_restrict_members:
            perms.append("can_restrict_members")
        if priv.can_promote_members:
            perms.append("can_promote_members")
        if priv.can_change_info:
            perms.append("can_change_info")
        if priv.can_invite_users:
            perms.append("can_invite_users")
        if priv.can_pin_messages:
            perms.append("can_pin_messages")
        if priv.can_manage_video_chats:
            perms.append("can_manage_video_chats")
    except Exception as e:
        # Log the error if needed, but don't fail
        print(f"[PERMISSIONS] Error in member_permissions: {e}")
    
    return perms


async def authorised(func, subFunc2, client, message, *args, **kwargs):
    from wbb import app, log  # ✅ moved here (lazy import)

    chatID = message.chat.id
    try:
        await func(client, message, *args, **kwargs)
    except ChatWriteForbidden:
        await app.leave_chat(chatID)
    except Exception as e:
        try:
            await message.reply_text(str(e.MESSAGE))
        except AttributeError:
            await message.reply_text(str(e))
        e = err()
        log.error(str(e))
    return subFunc2


async def unauthorised(message: Message, permission, subFunc2):
    from wbb import app  # ✅ moved here (lazy import)

    chatID = message.chat.id
    text = (
        "You don't have the required permission to perform this action."
        + f"\n**Permission:** __{permission}__"
    )
    try:
        await message.reply_text(text)
    except ChatWriteForbidden:
        await app.leave_chat(chatID)
    return subFunc2


def adminsOnly(permission):
    def subFunc(func):
        @wraps(func)
        async def subFunc2(client, message: Message, *args, **kwargs):
            from wbb import SUDOERS  # ✅ moved here (lazy import)

            chatID = message.chat.id
            if not message.from_user:
                # For anonymous admins
                if (
                    message.sender_chat
                    and message.sender_chat.id == message.chat.id
                ):
                    return await authorised(
                        func,
                        subFunc2,
                        client,
                        message,
                        *args,
                        **kwargs,
                    )
                return await unauthorised(message, permission, subFunc2)
            # For admins and sudo users
            userID = message.from_user.id
            permissions = await member_permissions(chatID, userID)
            if userID not in SUDOERS and permission not in permissions:
                return await unauthorised(message, permission, subFunc2)
            return await authorised(
                func, subFunc2, client, message, *args, **kwargs
            )

        return subFunc2

    return subFunc
