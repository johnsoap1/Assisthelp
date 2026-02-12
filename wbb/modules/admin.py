"""
Admin Module for AssistBot
Complete admin functionality with command management
"""

import asyncio
import re
from contextlib import suppress
from time import time

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus, ChatType
from pyrogram.errors import FloodWait
from pyrogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    ChatPermissions,
    ChatPrivileges,
    Message,
)

import sqlite3
from pathlib import Path
from wbb import BOT_ID, SUDOERS, SUDOERS_SET, app, log

# Initialize SQLite connection
DB_PATH = Path("wbb.sqlite")

def get_db():
    """Get SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_blocklist_table():
    """Initialize blocklist table if it doesn't exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocklist (
            chat_id INTEGER PRIMARY KEY,
            triggers TEXT,
            mode TEXT DEFAULT 'warn'
        )
    """)
    conn.commit()
    conn.close()

# Initialize table on module load
init_blocklist_table()


from wbb.core.decorators.errors import capture_err
from wbb.core.keyboard import ikb
from wbb.utils.dbfunctions import (
    add_warn,
    get_warn,
    int_to_alpha,
    remove_warns,
    save_filter,
)
from wbb.utils.functions import (
    extract_user,
    extract_user_and_reason,
    time_converter,
)
from wbb.core.decorators.permissions import adminsOnly, member_permissions

__MODULE__ = "Admin"
__HELP__ = """/ban - Ban A User
/dban - Delete the replied message banning its sender
/tban - Ban A User For Specific Time
/unban - Unban A User
/listban - Ban a user from groups listed in a message
/listunban - Unban a user from groups listed in a message
/warn - Warn A User
/dwarn - Delete the replied message warning its sender
/rmwarns - Remove All Warning of A User
/warns - Show Warning Of A User
/kick - Kick A User
/dkick - Delete the replied message kicking its sender
/purge - Purge Messages
/purge [n] - Purge "n" number of messages from replied message
/del - Delete Replied Message
/promote - Promote A Member
/fullpromote - Promote A Member With All Rights
/demote - Demote A Member
/pin - Pin A Message
/mute - Mute A User
/tmute - Mute A User For Specific Time
/unmute - Unmute A User
/ban_ghosts - Ban Deleted Accounts
/report | @admins | @admin - Report A Message To Admins.
/invite - Send Group/SuperGroup Invite Link.
/banall [time] - Ban users who joined in last X time (1h, 24h, 7d)
/inactive - Show activity report for inactive users
/adminlog - Toggle admin action logging

**Blocklist System:**
/addblocklist - Add multiple words/phrases to blocklist
/rmblocklist - Remove items from blocklist
/blocklist - Show current blocklist
/blockmode [warn|mute|ban|delete] - Set enforcement mode"""


admins_in_chat = {}


async def list_admins(chat_id: int):
    """Get list of admin IDs in chat with caching."""
    global admins_in_chat
    if chat_id in admins_in_chat:
        interval = time() - admins_in_chat[chat_id]["last_updated_at"]
        if interval < 3600:
            return admins_in_chat[chat_id]["data"]

    try:
        admins_in_chat[chat_id] = {
            "last_updated_at": time(),
            "data": [
                member.user.id
                async for member in app.get_chat_members(
                    chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                )
            ],
        }
        return admins_in_chat[chat_id]["data"]
    except Exception as e:
        # Handle invalid chats, deleted groups, channels, etc.
        log.warning(f"Failed to fetch admins for chat {chat_id}: {e}")
        # Clear cache entry if it exists
        if chat_id in admins_in_chat:
            del admins_in_chat[chat_id]
        return []


# Admin cache reload


@app.on_chat_member_updated()
async def admin_cache_func(_, cmu: ChatMemberUpdated):
    """Update admin cache when members are promoted/demoted."""
    if cmu.old_chat_member and cmu.old_chat_member.promoted_by:
        try:
            admins_in_chat[cmu.chat.id] = {
                "last_updated_at": time(),
                "data": [
                    member.user.id
                    async for member in app.get_chat_members(
                        cmu.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
                    )
                ],
            }
            log.info(f"Updated admin cache for {cmu.chat.id} [{cmu.chat.title}]")
        except Exception as e:
            log.warning(f"Failed to update admin cache for {cmu.chat.id}: {e}")
            # Clear cache entry if it exists
            if cmu.chat.id in admins_in_chat:
                del admins_in_chat[cmu.chat.id]


# Purge Messages


@app.on_message(filters.command("purge") & ~filters.private)
@adminsOnly("can_delete_messages")
async def purgeFunc(_, message: Message):
    """Purge messages from replied message to current."""
    repliedmsg = message.reply_to_message
    await message.delete()

    if not repliedmsg:
        return await message.reply_text("Reply to a message to purge from.")

    cmd = message.command
    if len(cmd) > 1 and cmd[1].isdigit():
        purge_to = repliedmsg.id + int(cmd[1])
        if purge_to > message.id:
            purge_to = message.id
    else:
        purge_to = message.id

    chat_id = message.chat.id
    message_ids = []

    for message_id in range(
        repliedmsg.id,
        purge_to,
    ):
        message_ids.append(message_id)

        # Max message deletion limit is 100
        if len(message_ids) == 100:
            await app.delete_messages(
                chat_id=chat_id,
                message_ids=message_ids,
                revoke=True,
            )
            message_ids = []

    # Delete if any messages left
    if len(message_ids) > 0:
        await app.delete_messages(
            chat_id=chat_id,
            message_ids=message_ids,
            revoke=True,
        )


# Kick members


@app.on_message(filters.command(["kick", "dkick"]) & ~filters.private)
@adminsOnly("can_restrict_members")
async def kickFunc(_, message: Message):
    """Kick a user from the group."""
    user_id, reason = await extract_user_and_reason(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    if user_id == BOT_ID:
        return await message.reply_text(
            "I can't kick myself, i can leave if you want."
        )
    if user_id in SUDOERS_SET:
        return await message.reply_text("You Wanna Kick The Elevated One?")
    if user_id in (await list_admins(message.chat.id)):
        return await message.reply_text(
            "I can't kick an admin, You know the rules, so do i."
        )
    mention = (await app.get_users(user_id)).mention
    msg = f"""
**Kicked User:** {mention}
**Kicked By:** {message.from_user.mention if message.from_user else 'Anon'}
**Reason:** {reason or 'No Reason Provided.'}"""
    if message.command[0][0] == "d":
        await message.reply_to_message.delete()
    await message.chat.ban_member(user_id)
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg)
    await asyncio.sleep(1)
    await message.chat.unban_member(user_id)


# Ban members


@app.on_message(filters.command(["ban", "dban", "tban"]) & ~filters.private)
@adminsOnly("can_restrict_members")
async def banFunc(_, message: Message):
    """Ban a user from the group."""
    user_id, reason = await extract_user_and_reason(message, sender_chat=True)

    if not user_id:
        return await message.reply_text("I can't find that user.")
    if user_id == BOT_ID:
        return await message.reply_text(
            "I can't ban myself, i can leave if you want."
        )
    if user_id in SUDOERS_SET:
        return await message.reply_text(
            "You Wanna Ban The Elevated One?, RECONSIDER!"
        )
    if user_id in (await list_admins(message.chat.id)):
        return await message.reply_text(
            "I can't ban an admin, You know the rules, so do i."
        )

    try:
        mention = (await app.get_users(user_id)).mention
    except IndexError:
        mention = (
            message.reply_to_message.sender_chat.title
            if message.reply_to_message
            else "Anon"
        )

    msg = (
        f"**Banned User:** {mention}\n"
        f"**Banned By:** {message.from_user.mention if message.from_user else 'Anon'}\n"
    )
    if message.command[0][0] == "d":
        await message.reply_to_message.delete()
    if message.command[0] == "tban":
        split = reason.split(None, 1)
        time_value = split[0]
        temp_reason = split[1] if len(split) > 1 else ""
        temp_ban = await time_converter(message, time_value)
        msg += f"**Banned For:** {time_value}\n"
        if temp_reason:
            msg += f"**Reason:** {temp_reason}"
        with suppress(AttributeError):
            if len(time_value[:-1]) < 3:
                await message.chat.ban_member(user_id, until_date=temp_ban)
                replied_message = message.reply_to_message
                if replied_message:
                    message = replied_message
                await message.reply_text(msg)
            else:
                await message.reply_text("You can't use more than 99")
        return
    if reason:
        msg += f"**Reason:** {reason}"
    await message.chat.ban_member(user_id)
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg)


# Unban members


@app.on_message(filters.command("unban") & ~filters.private)
@adminsOnly("can_restrict_members")
async def unban_func(_, message: Message):
    """Unban a user from the group."""
    reply = message.reply_to_message

    if reply and reply.sender_chat and reply.sender_chat != message.chat.id:
        return await message.reply_text("You cannot unban a channel")

    if len(message.command) == 2:
        user = message.text.split(None, 1)[1]
    elif len(message.command) == 1 and reply:
        user = message.reply_to_message.from_user.id
    else:
        return await message.reply_text(
            "Provide a username or reply to a user's message to unban."
        )
    await message.chat.unban_member(user)
    umention = (await app.get_users(user)).mention
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(f"Unbanned! {umention}")


# Ban users listed in a message


@app.on_message(filters.user(list(SUDOERS)) & filters.command("listban") & ~filters.chat(ChatType.PRIVATE))
async def list_ban_(c, message: Message):
    """Ban a user from multiple groups listed in a message."""
    userid, msglink_reason = await extract_user_and_reason(message)
    if not userid or not msglink_reason:
        return await message.reply_text(
            "Provide a userid/username along with message link and reason to list-ban"
        )
    if (
        len(msglink_reason.split(" ")) == 1
    ):
        return await message.reply_text(
            "You must provide a reason to list-ban"
        )
    lreason = msglink_reason.split()
    messagelink, reason = lreason[0], " ".join(lreason[1:])

    if not re.search(
        r"(https?://)?t(elegram)?\.me/\w+/\d+", messagelink
    ):
        return await message.reply_text("Invalid message link provided")

    if userid == BOT_ID:
        return await message.reply_text("I can't ban myself.")
    if userid in SUDOERS_SET:
        return await message.reply_text(
            "You Wanna Ban The Elevated One?, RECONSIDER!"
        )
    splitted = messagelink.split("/")
    uname, mid = splitted[-2], int(splitted[-1])
    m = await message.reply_text(
        "Banning User from multiple groups. This may take some time"
    )
    try:
        msgtext = (await app.get_messages(uname, mid)).text
        gusernames = re.findall(r"@\w+", msgtext)
    except:
        return await m.edit_text("Could not get group usernames")
    count = 0
    for username in gusernames:
        try:
            await app.ban_chat_member(username.strip("@"), userid)
            await asyncio.sleep(1)
        except FloodWait as e:
            await asyncio.sleep(e.x)
        except:
            continue
        count += 1
    mention = (await app.get_users(userid)).mention

    msg = f"""
**List-Banned User:** {mention}
**Banned User ID:** `{userid}`
**Admin:** {message.from_user.mention}
**Affected chats:** `{count}`
**Reason:** {reason}
"""
    await m.edit_text(msg)


# Unban users listed in a message


@app.on_message(filters.user(list(SUDOERS)) & filters.command("listunban") & ~filters.chat(ChatType.PRIVATE))
async def list_unban_(c, message: Message):
    """Unban a user from multiple groups listed in a message."""
    userid, msglink = await extract_user_and_reason(message)
    if not userid or not msglink:
        return await message.reply_text(
            "Provide a userid/username along with message link to list-unban"
        )

    if not re.search(
        r"(https?://)?t(elegram)?\.me/\w+/\d+", msglink
    ):
        return await message.reply_text("Invalid message link provided")

    splitted = msglink.split("/")
    uname, mid = splitted[-2], int(splitted[-1])
    m = await message.reply_text(
        "Unbanning User from multiple groups. This may take some time"
    )
    try:
        msgtext = (await app.get_messages(uname, mid)).text
        gusernames = re.findall(r"@\w+", msgtext)
    except:
        return await m.edit_text("Could not get the group usernames")
    count = 0
    for username in gusernames:
        try:
            await app.unban_chat_member(username.strip("@"), userid)
            await asyncio.sleep(1)
        except FloodWait as e:
            await asyncio.sleep(e.x)
        except:
            continue
        count += 1
    mention = (await app.get_users(userid)).mention
    msg = f"""
**List-Unbanned User:** {mention}
**Unbanned User ID:** `{userid}`
**Admin:** {message.from_user.mention}
**Affected chats:** `{count}`
"""
    await m.edit_text(msg)


# Delete messages


@app.on_message(filters.command("del") & ~filters.private)
@adminsOnly("can_delete_messages")
async def deleteFunc(_, message: Message):
    """Delete a replied message."""
    if not message.reply_to_message:
        return await message.reply_text("Reply To A Message To Delete It")
    await message.reply_to_message.delete()
    await message.delete()


# Promote Members


@app.on_message(filters.command(["promote", "fullpromote"]) & ~filters.private)
@adminsOnly("can_promote_members")
async def promoteFunc(_, message: Message):
    """Promote a user to admin."""
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")

    bot = (await app.get_chat_member(message.chat.id, BOT_ID)).privileges
    if user_id == BOT_ID:
        return await message.reply_text("I can't promote myself.")
    if not bot:
        return await message.reply_text("I'm not an admin in this chat.")
    if not bot.can_promote_members:
        return await message.reply_text("I don't have enough permissions")

    umention = (await app.get_users(user_id)).mention

    if message.command[0][0] == "f":
        await message.chat.promote_member(
            user_id=user_id,
            privileges=ChatPrivileges(
                can_change_info=bot.can_change_info,
                can_invite_users=bot.can_invite_users,
                can_delete_messages=bot.can_delete_messages,
                can_restrict_members=bot.can_restrict_members,
                can_pin_messages=bot.can_pin_messages,
                can_promote_members=bot.can_promote_members,
                can_manage_chat=bot.can_manage_chat,
                can_manage_video_chats=bot.can_manage_video_chats,
            ),
        )
        return await message.reply_text(f"Fully Promoted! {umention}")

    await message.chat.promote_member(
        user_id=user_id,
        privileges=ChatPrivileges(
            can_change_info=False,
            can_invite_users=bot.can_invite_users,
            can_delete_messages=bot.can_delete_messages,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False,
            can_manage_chat=bot.can_manage_chat,
            can_manage_video_chats=bot.can_manage_video_chats,
        ),
    )
    await message.reply_text(f"Promoted! {umention}")


# Demote Member


@app.on_message(filters.command("demote") & ~filters.private)
@adminsOnly("can_promote_members")
async def demote(_, message: Message):
    """Demote a user from admin."""
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    if user_id == BOT_ID:
        return await message.reply_text("I can't demote myself.")
    if user_id in SUDOERS_SET:
        return await message.reply_text(
            "You wanna demote the elevated one?, RECONSIDER!"
        )
    try:
        member = await app.get_chat_member(message.chat.id, user_id)
        if member.status == ChatMemberStatus.ADMINISTRATOR:
            await message.chat.promote_member(
                user_id=user_id,
                privileges=ChatPrivileges(
                    can_change_info=False,
                    can_invite_users=False,
                    can_delete_messages=False,
                    can_restrict_members=False,
                    can_pin_messages=False,
                    can_promote_members=False,
                    can_manage_chat=False,
                    can_manage_video_chats=False,
                ),
            )
            umention = (await app.get_users(user_id)).mention
            await message.reply_text(f"Demoted! {umention}")
        else:
            await message.reply_text(
                "The person you mentioned is not an admin."
            )
    except Exception as e:
        await message.reply_text(e)


# Pin Messages


@app.on_message(filters.command(["pin", "unpin"]) & ~filters.private)
@adminsOnly("can_pin_messages")
async def pin(_, message: Message):
    """Pin or unpin a message."""
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to pin/unpin it.")
    r = message.reply_to_message
    if message.command[0][0] == "u":
        await r.unpin()
        return await message.reply_text(
            f"**Unpinned [this]({r.link}) message.**",
            disable_web_page_preview=True,
        )
    await r.pin(disable_notification=True)
    await message.reply(
        f"**Pinned [this]({r.link}) message.**",
        disable_web_page_preview=True,
    )
    msg = "Please check the pinned message: ~ " + f"[Check, {r.link}]"
    filter_ = dict(type="text", data=msg)
    await save_filter(message.chat.id, "~pinned", filter_)


# Mute members


@app.on_message(filters.command(["mute", "tmute"]) & ~filters.private)
@adminsOnly("can_restrict_members")
async def mute(_, message: Message):
    """Mute a user in the group."""
    user_id, reason = await extract_user_and_reason(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    if user_id == BOT_ID:
        return await message.reply_text("I can't mute myself.")
    if user_id in SUDOERS_SET:
        return await message.reply_text(
            "You wanna mute the elevated one?, RECONSIDER!"
        )
    if user_id in (await list_admins(message.chat.id)):
        return await message.reply_text(
            "I can't mute an admin, You know the rules, so do i."
        )
    mention = (await app.get_users(user_id)).mention
    keyboard = ikb({"🚨  Unmute  🚨": f"unmute_{user_id}"})
    msg = (
        f"**Muted User:** {mention}\n"
        f"**Muted By:** {message.from_user.mention if message.from_user else 'Anon'}\n"
    )
    if message.command[0] == "tmute":
        split = reason.split(None, 1)
        time_value = split[0]
        temp_reason = split[1] if len(split) > 1 else ""
        temp_mute = await time_converter(message, time_value)
        msg += f"**Muted For:** {time_value}\n"
        if temp_reason:
            msg += f"**Reason:** {temp_reason}"
        try:
            if len(time_value[:-1]) < 3:
                await message.chat.restrict_member(
                    user_id,
                    permissions=ChatPermissions(),
                    until_date=temp_mute,
                )
                replied_message = message.reply_to_message
                if replied_message:
                    message = replied_message
                await message.reply_text(msg, reply_markup=keyboard)
            else:
                await message.reply_text("You can't use more than 99")
        except AttributeError:
            pass
        return
    if reason:
        msg += f"**Reason:** {reason}"
    await message.chat.restrict_member(user_id, permissions=ChatPermissions())
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(msg, reply_markup=keyboard)


# Unmute members


@app.on_message(filters.command("unmute") & ~filters.private)
@adminsOnly("can_restrict_members")
async def unmute(_, message: Message):
    """Unmute a user in the group."""
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    await message.chat.unban_member(user_id)
    umention = (await app.get_users(user_id)).mention
    replied_message = message.reply_to_message
    if replied_message:
        message = replied_message
    await message.reply_text(f"Unmuted! {umention}")


# Ban deleted accounts


@app.on_message(filters.command("ban_ghosts") & ~filters.private)
@adminsOnly("can_restrict_members")
async def ban_deleted_accounts(_, message: Message):
    """Ban all deleted accounts in the group."""
    chat_id = message.chat.id
    deleted_users = []
    banned_users = 0
    m = await message.reply("Finding ghosts...")

    try:
        async for i in app.get_chat_members(chat_id):
            if i.user.is_deleted:
                deleted_users.append(i.user.id)
    except Exception as e:
        await m.edit(f"❌ Error accessing chat members: {str(e)[:100]}")
        return

    if len(deleted_users) > 0:
        for deleted_user in deleted_users:
            try:
                await message.chat.ban_member(deleted_user)
            except Exception:
                pass
            banned_users += 1
        await m.edit(f"Banned {banned_users} Deleted Accounts")
    else:
        await m.edit("There are no deleted accounts in this chat")


# Warn users


@app.on_message(filters.command(["warn", "dwarn"]) & ~filters.private)
@adminsOnly("can_restrict_members")
async def warn_user(_, message: Message):
    """Warn a user."""
    user_id, reason = await extract_user_and_reason(message)
    chat_id = message.chat.id
    if not user_id:
        return await message.reply_text("I can't find that user.")
    if user_id == BOT_ID:
        return await message.reply_text(
            "I can't warn myself, i can leave if you want."
        )
    if user_id in SUDOERS_SET:
        return await message.reply_text(
            "You Wanna Warn The Elevated One?, RECONSIDER!"
        )
    if user_id in (await list_admins(chat_id)):
        return await message.reply_text(
            "I can't warn an admin, You know the rules, so do i."
        )
    user, warns = await asyncio.gather(
        app.get_users(user_id),
        get_warn(chat_id, await int_to_alpha(user_id)),
    )
    mention = user.mention
    keyboard = ikb({"🚨  Remove Warn  🚨": f"unwarn_{user_id}"})
    if warns:
        warns = warns["warns"]
    else:
        warns = 0
    if message.command[0][0] == "d":
        await message.reply_to_message.delete()
    if warns >= 2:
        await message.chat.ban_member(user_id)
        await message.reply_text(
            f"Number of warns of {mention} exceeded, BANNED!"
        )
        await remove_warns(chat_id, await int_to_alpha(user_id))
    else:
        warn = {"warns": warns + 1}
        msg = f"""
**Warned User:** {mention}
**Warned By:** {message.from_user.mention if message.from_user else 'Anon'}
**Reason:** {reason or 'No Reason Provided.'}
**Warns:** {warns + 1}/3"""
        replied_message = message.reply_to_message
        if replied_message:
            message = replied_message
        await message.reply_text(msg, reply_markup=keyboard)
        await add_warn(chat_id, await int_to_alpha(user_id), warn)


@app.on_callback_query(filters.regex("unwarn_"))
async def remove_warning(_, cq: CallbackQuery):
    """Remove a warning via button."""
    from_user = cq.from_user
    chat_id = cq.message.chat.id
    permissions = await member_permissions(chat_id, from_user.id)
    permission = "can_restrict_members"
    if permission not in permissions:
        return await cq.answer(
            "You don't have enough permissions to perform this action.\n"
            + f"Permission needed: {permission}",
            show_alert=True,
        )
    user_id = cq.data.split("_")[1]
    warns = await get_warn(chat_id, await int_to_alpha(user_id))
    if warns:
        warns = warns["warns"]
    if not warns or warns == 0:
        return await cq.answer("User has no warnings.")
    warn = {"warns": warns - 1}
    await add_warn(chat_id, await int_to_alpha(user_id), warn)
    text = cq.message.text.markdown
    text = f"~~{text}~~\n\n"
    text += f"__Warn removed by {from_user.mention}__"
    await cq.message.edit(text)


# Remove Warnings


@app.on_message(filters.command("rmwarns") & ~filters.private)
@adminsOnly("can_restrict_members")
async def remove_warnings(_, message: Message):
    """Remove all warnings of a user."""
    if not message.reply_to_message:
        return await message.reply_text(
            "Reply to a message to remove a user's warnings."
        )
    user_id = message.reply_to_message.from_user.id
    mention = message.reply_to_message.from_user.mention
    chat_id = message.chat.id
    warns = await get_warn(chat_id, await int_to_alpha(user_id))
    if warns:
        warns = warns["warns"]
    if warns == 0 or not warns:
        await message.reply_text(f"{mention} have no warnings.")
    else:
        await remove_warns(chat_id, await int_to_alpha(user_id))
        await message.reply_text(f"Removed warnings of {mention}.")


# Check Warnings


@app.on_message(filters.command("warns") & ~filters.private)
@capture_err
async def check_warns(_, message: Message):
    """Check warnings of a user."""
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    warns = await get_warn(message.chat.id, await int_to_alpha(user_id))
    mention = (await app.get_users(user_id)).mention
    if warns:
        warns = warns["warns"]
    else:
        return await message.reply_text(f"{mention} has no warnings.")
    return await message.reply_text(f"{mention} has {warns}/3 warnings.")


# Report users


@app.on_message(
    (
        filters.command("report")
        | filters.command(["admins", "admin"], prefixes="@")
    )
    & ~filters.private
)
@capture_err
async def report_user(_, message):
    """Report a user to admins."""
    if len(message.text.split()) <= 1 and not message.reply_to_message:
        return await message.reply_text(
            "Reply to a message to report that user."
        )

    reply = message.reply_to_message if message.reply_to_message else message
    reply_id = reply.from_user.id if reply.from_user else reply.sender_chat.id
    user_id = (
        message.from_user.id if message.from_user else message.sender_chat.id
    )

    list_of_admins = await list_admins(message.chat.id)
    try:
        linked_chat = (await app.get_chat(message.chat.id)).linked_chat
    except Exception as e:
        log.warning(f"Failed to get chat info for report in chat {message.chat.id}: {e}")
        linked_chat = None

    if linked_chat is not None:
        if (
            reply_id in list_of_admins
            or reply_id == message.chat.id
            or reply_id == linked_chat.id
        ):
            return await message.reply_text(
                "Do you know that the user you are replying is an admin ?"
            )
    else:
        if reply_id in list_of_admins or reply_id == message.chat.id:
            return await message.reply_text(
                "Do you know that the user you are replying is an admin ?"
            )

    user_mention = (
        reply.from_user.mention if reply.from_user else reply.sender_chat.title
    )
    text = f"Reported {user_mention} to admins!."
    try:
        admin_data = [
            i
            async for i in app.get_chat_members(
                chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
            )
        ]
        for admin in admin_data:
            if admin.user.is_bot or admin.user.is_deleted:
                continue
            text += f"[\u2063](tg://user?id={admin.user.id})"

        await reply.reply_text(text)
    except Exception as e:
        log.warning(f"Failed to fetch admin data for report in chat {message.chat.id}: {e}")
        await reply.reply_text(f"Reported {user_mention} to admins!.")


# Invite link


@app.on_message(filters.command("invite"))
@adminsOnly("can_invite_users")
async def invite(_, message):
    """Send group invite link."""
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        link = (await app.get_chat(message.chat.id)).invite_link
        if not link:
            link = await app.export_chat_invite_link(message.chat.id)
        text = f"Here's This Group's Invite Link.\n\n{link}"
        if message.reply_to_message:
            await message.reply_to_message.reply_text(
                text, disable_web_page_preview=True
            )
        else:
            await message.reply_text(text, disable_web_page_preview=True)


# Remove Commands Feature


# Bulk Actions

@app.on_message(filters.command("banall") & ~filters.private)
@adminsOnly("can_restrict_members")
async def ban_all_new_users(_, message: Message):
    """Ban all users who joined in the last X hours/days."""
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/banall [time]`\n"
            "Examples:\n"
            "• `/banall 1h` - Ban users from last hour\n"
            "• `/banall 24h` - Ban users from last day\n"
            "• `/banall 7d` - Ban users from last week"
        )
    
    time_str = message.command[1]
    try:
        time_val = await time_converter(message, time_str)
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(seconds=time_val)
    except:
        return await message.reply_text("❌ Invalid time format!")
    
    progress_msg = await message.reply_text("🔍 Scanning for recent members...")
    
    banned_count = 0
    checked_count = 0
    
    async for member in app.get_chat_members(message.chat.id):
        checked_count += 1
        
        # Skip admins and bots
        if member.status in ["creator", "administrator"] or member.user.is_bot:
            continue
        
        # Check join date (if available)
        if hasattr(member, 'joined_date') and member.joined_date:
            if member.joined_date > cutoff_time:
                try:
                    await message.chat.ban_member(member.user.id)
                    banned_count += 1
                    await asyncio.sleep(0.5)  # Rate limiting
                except:
                    pass
        
        if checked_count % 50 == 0:
            await progress_msg.edit_text(
                f"⏳ Checked: {checked_count}\n"
                f"⛔️ Banned: {banned_count}"
            )
    
    await progress_msg.edit_text(
        f"✅ **Bulk Ban Complete**\n\n"
        f"• Checked: {checked_count} members\n"
        f"• Banned: {banned_count} members\n"
        f"• Time range: {time_str}"
    )


@app.on_message(filters.command("inactive") & ~filters.private)
@adminsOnly("can_restrict_members")
async def find_inactive_users(_, message: Message):
    """Find users who haven't been active."""
    progress_msg = await message.reply_text("🔍 Scanning for inactive members...")
    
    active_users = set()
    
    # Get last 1000 messages
    async for msg in app.get_chat_history(message.chat.id, limit=1000):
        if msg.from_user and not msg.from_user.is_bot:
            active_users.add(msg.from_user.id)
    
    # Get all members
    total_members = await app.get_chat_members_count(message.chat.id)
    active_count = len(active_users)
    inactive_count = total_members - active_count - 1  # -1 for bot
    
    await progress_msg.edit_text(
        f"📊 **Activity Report**\n\n"
        f"• Total members: {total_members}\n"
        f"• Active (last 1k messages): {active_count}\n"
        f"• Likely inactive: {inactive_count}\n\n"
        f"Note: This is an estimate based on recent message history."
    )


@app.on_message(filters.command("adminlog") & ~filters.private)
@adminsOnly("can_restrict_members")
async def toggle_admin_log(_, message: Message):
    """Enable admin action logging."""
    chat_id = message.chat.id
    
    # Toggle in database
    from wbb.utils.dbfunctions import toggle_admin_log, is_admin_log_enabled
    
    current = await is_admin_log_enabled(chat_id)
    await toggle_admin_log(chat_id, not current)
    
    status = "enabled" if not current else "disabled"
    await message.reply_text(
        f"✅ Admin logging is now **{status}**.\n\n"
        f"{'All admin actions will be logged.' if not current else 'Admin actions will not be logged.'}"
    )


# ============= BLOCKLIST SYSTEM =============

@app.on_message(filters.command("addblocklist") & filters.group)
@adminsOnly("can_restrict_members")
async def add_blocklist(_, message: Message):
    """Add multiple triggers to blocklist."""
    lines = message.text.splitlines()
    
    if len(lines) < 2:
        return await message.reply_text(
            "Usage:\n"
            "/addblocklist\n"
            "word\n"
            "phrase here\n"
            "another phrase"
        )
    
    triggers = []
    for line in lines[1:]:
        t = line.strip().lower()
        if len(t) < 2:
            continue
        triggers.append(t)
    
    if not triggers:
        return await message.reply_text("No valid blocklist items found.")
    
    # Get existing blocklist from SQLite
    conn = get_db()
    cursor = conn.execute(
        "SELECT triggers FROM blocklist WHERE chat_id = ?",
        (message.chat.id,)
    )
    row = cursor.fetchone()
    
    if row:
        # Merge with existing
        import json
        current_triggers = set(json.loads(row["triggers"]))
        new_triggers = set(triggers)
        all_triggers = list(current_triggers.union(new_triggers))
        added = len(all_triggers) - len(current_triggers)
        
        conn.execute(
            "UPDATE blocklist SET triggers = ? WHERE chat_id = ?",
            (json.dumps(all_triggers), message.chat.id)
        )
    else:
        # Create new
        import json
        conn.execute(
            "INSERT INTO blocklist (chat_id, triggers, mode) VALUES (?, ?, ?)",
            (message.chat.id, json.dumps(triggers), "warn")
        )
        added = len(triggers)
    
    conn.commit()
    conn.close()
    
    await message.reply_text(f"✅ Added {added} blocklist item(s).")


@app.on_message(filters.command("rmblocklist") & filters.group)
@adminsOnly("can_restrict_members")
async def remove_blocklist(_, message: Message):
    """Remove triggers from blocklist."""
    lines = message.text.splitlines()
    
    if len(lines) < 2:
        return await message.reply_text(
            "Usage:\n"
            "/rmblocklist\n"
            "word\n"
            "phrase to remove"
        )
    
    triggers_to_remove = []
    for line in lines[1:]:
        t = line.strip().lower()
        if len(t) < 2:
            continue
        triggers_to_remove.append(t)
    
    if not triggers_to_remove:
        return await message.reply_text("No valid items to remove.")
    
    conn = get_db()
    cursor = conn.execute(
        "SELECT triggers FROM blocklist WHERE chat_id = ?",
        (message.chat.id,)
    )
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return await message.reply_text("No blocklist found for this chat.")
    
    import json
    current_triggers = set(json.loads(row["triggers"]))
    remove_set = set(triggers_to_remove)
    remaining = list(current_triggers - remove_set)
    removed = len(current_triggers) - len(remaining)
    
    if remaining:
        conn.execute(
            "UPDATE blocklist SET triggers = ? WHERE chat_id = ?",
            (json.dumps(remaining), message.chat.id)
        )
    else:
        # Remove entire row if no triggers left
        conn.execute("DELETE FROM blocklist WHERE chat_id = ?", (message.chat.id,))
    
    conn.commit()
    conn.close()
    
    await message.reply_text(f"✅ Removed {removed} blocklist item(s).")


@app.on_message(filters.command("blocklist") & filters.group)
@adminsOnly("can_restrict_members")
async def show_blocklist(_, message: Message):
    """Show current blocklist."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT triggers, mode FROM blocklist WHERE chat_id = ?",
        (message.chat.id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row or not row["triggers"]:
        return await message.reply_text("🚫 No blocklist items set.")
    
    import json
    triggers = json.loads(row["triggers"])
    mode = row["mode"] or "warn"
    
    if not triggers:
        return await message.reply_text("🚫 No blocklist items set.")
    
    text = f"🚫 **Blocked Triggers ({len(triggers)})**\n\n"
    text += f"Mode: `{mode}`\n\n"
    
    for i, trigger in enumerate(triggers[:20], 1):  # Show first 20
        text += f"{i}. `{trigger}`\n"
    
    if len(triggers) > 20:
        text += f"\n... and {len(triggers) - 20} more"
    
    await message.reply_text(text)


@app.on_message(filters.command("setblockmode") & filters.group)
@adminsOnly("can_restrict_members")
async def set_block_mode(_, message: Message):
    """Set blocklist mode (warn/delete/ban)."""
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: /setblockmode <warn|delete|ban>"
        )
    
    mode = message.command[1].lower()
    if mode not in ["warn", "delete", "ban"]:
        return await message.reply_text("Invalid mode. Use warn, delete, or ban.")
    
    conn = get_db()
    # Check if blocklist exists for this chat
    cursor = conn.execute(
        "SELECT 1 FROM blocklist WHERE chat_id = ?",
        (message.chat.id,)
    )
    exists = cursor.fetchone() is not None
    
    if exists:
        # Update existing blocklist with new mode
        conn.execute(
            "UPDATE blocklist SET mode = ? WHERE chat_id = ?",
            (mode, message.chat.id)
        )
    else:
        # Create new blocklist with default empty triggers
        conn.execute(
            "INSERT INTO blocklist (chat_id, triggers, mode) VALUES (?, ?, ?)",
            (message.chat.id, "[]", mode)
        )
    
    conn.commit()
    conn.close()
    
    await message.reply_text(f"✅ Blocklist mode set to `{mode}`")


@app.on_message(filters.text & ~filters.private)
async def blocklist_watcher(_, message: Message):
    """Watch messages for blocked content."""
    if not message.from_user:
        return
    
    chat_id = message.chat.id
    user = message.from_user
    
    # Skip if user is admin or sudo
    if user.id in SUDOERS or user.id == BOT_ID:
        return
    
    # Check if user is admin
    try:
        member = await message.chat.get_member(user.id)
        if member.status in ["creator", "administrator"]:
            return
    except Exception:
        pass
    
    # Get blocklist for this chat from SQLite
    conn = get_db()
    cursor = conn.execute(
        "SELECT triggers, mode FROM blocklist WHERE chat_id = ?",
        (chat_id,)
    )
    row = cursor.fetchone()
    
    if not row or not row["triggers"]:
        conn.close()
        return
    
    import json
    triggers = json.loads(row["triggers"])
    mode = row["mode"] or "warn"
    conn.close()
    
    text = message.text.lower()
    
    # Check if message contains any blocked trigger
    matched_triggers = [t for t in triggers if t in text]
    
    if not matched_triggers:
        return
    
    # Take action based on mode
    if mode == "warn":
        await message.reply_text(
            f"⚠️ {user.mention}, your message was deleted because it contained blocked content.\n"
            f"Blocked words: {', '.join(f'`{t}`' for t in matched_triggers)}"
        )
        await message.delete()
    
    elif mode == "delete":
        await message.delete()
    
    elif mode == "ban":
        try:
            await message.chat.ban_member(user.id)
            await message.reply_text(
                f"🚫 {user.mention} was banned for using blocked content.\n"
                f"Blocked words: {', '.join(f'`{t}`' for t in matched_triggers)}"
            )
        except Exception as e:
            await message.reply_text("I don't have permission to ban users here.")
        
        await message.delete()


async def enforce_blocklist(message: Message, trigger: str, mode: str):
    """Enforce blocklist violation."""
    await message.delete()
    
    reason = (
        f"🚫 **Blocked Word Detected**\n"
        f"User: {message.from_user.mention}\n"
        f"Trigger: `{trigger}`"
    )
    
    # Send notification (auto-delete after 15 seconds)
    msg = await message.chat.send_message(reason)
    asyncio.create_task(delete_after_delay(msg, 15))
    
    if mode == "warn":
        # Get current warning count
        current_warn = await get_warn(message.chat.id, await int_to_alpha(message.from_user.id))
        warns = (current_warn["warns"] if current_warn else 0) + 1
        
        # Update warning count
        await add_warn(
            message.chat.id,
            await int_to_alpha(message.from_user.id),
            {"warns": warns},
        )
        
        # Auto-ban after 3 warnings
        if warns >= 3:
            try:
                await message.chat.ban_member(message.from_user.id)
                await message.chat.send_message(f"🚫 {message.from_user.mention} was banned for reaching 3 warnings!")
            except Exception:
                pass
    elif mode == "mute":
        await message.chat.restrict_member(
            message.from_user.id,
            permissions=ChatPermissions(),
            until_date=int(time()) + 300,  # 5 minutes
        )
    elif mode == "ban":
        try:
            await message.chat.ban_member(message.from_user.id)
        except Exception:
            pass


async def delete_after_delay(message, delay_seconds):
    """Delete message after delay."""
    await asyncio.sleep(delay_seconds)
    with suppress(Exception):
        await message.delete()




