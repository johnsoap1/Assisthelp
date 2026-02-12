"""
Sudoers Module - Admin/Sudo Only Commands

Provides system monitoring, global bans, broadcasting, and maintenance commands.
"""
import asyncio
import os
import subprocess
import time

import psutil
from pyrogram import filters, types
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup

from wbb import (
    BOT_ID,
    GBAN_LOG_GROUP_ID,
    SUDOERS,
    SUDOERS_SET,
    BOT_USERNAME,
    app,
    bot_start_time,
)
from wbb.core.decorators.errors import capture_err
from wbb.utils import formatter
from wbb.utils.dbfunctions import (
    add_gban_user,
    get_served_chats,
    get_served_users,
    is_gbanned_user,
    remove_gban_user,
)
from wbb.utils.functions import extract_user, extract_user_and_reason, restart

__MODULE__ = "Sudoers"
__HELP__ = """
/stats - To Check System Status.

/gstats - To Check Bot's Global Stats.

/gban - To Ban A User Globally.

/ungban - To Unban A User Globally.

/clean_db - Clean database.

/broadcast - To Broadcast A Message To All Groups.

/ubroadcast - To Broadcast A Message To All Users.

/update - To Update And Restart The Bot

/restart - To Restart the bot

/eval - Execute Python Code

/sh - Execute Shell Code
"""


# Helper function to check if user is sudo
def is_sudo(user_id: int) -> bool:
    """Check if a user is in the SUDOERS list."""
    return user_id in SUDOERS_SET


# Stats Module


async def bot_sys_stats():
    """Get bot system statistics."""
    bot_uptime = int(time.time() - bot_start_time)
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    process = psutil.Process(os.getpid())
    stats = f"""
{BOT_USERNAME}@William
------------------
UPTIME: {formatter.get_readable_time(bot_uptime)}
BOT: {round(process.memory_info()[0] / 1024 ** 2)} MB
CPU: {cpu}%
RAM: {mem}%
DISK: {disk}%
"""
    return stats


@app.on_message(filters.command("stats"))
@capture_err
async def show_stats(_, message):
    """Show bot system statistics."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    stats = await bot_sys_stats()
    await message.reply_text(f"`{stats}`")


# Gban


@app.on_message(filters.command("gban"))
@capture_err
async def ban_globally(_, message):
    """Ban a user globally across all chats."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    user_id, reason = await extract_user_and_reason(message)
    user = await app.get_users(user_id)
    from_user = message.from_user

    if not user_id:
        return await message.reply_text("I can't find that user.")
    if not reason:
        return await message.reply("No reason provided.")

    if user_id in [from_user.id, BOT_ID] or is_sudo(user_id):
        return await message.reply_text("I can't ban that user.")

    served_chats = await get_served_chats()
    m = await message.reply_text(
        f"**Banning {user.mention} Globally!**"
        + f" **This Action Should Take About {len(served_chats)} Seconds.**"
    )
    await add_gban_user(user_id)
    number_of_chats = 0
    for served_chat in served_chats:
        try:
            chat_member = await app.get_chat_member(
                served_chat, user.id
            )
            if chat_member.status == ChatMemberStatus.MEMBER:
                await app.ban_chat_member(served_chat, user.id)
                number_of_chats += 1
            await asyncio.sleep(1)
        except FloodWait as e:
            await asyncio.sleep(int(e.value))
        except Exception:
            pass
    try:
        await app.send_message(
            user.id,
            f"Hello, You have been globally banned by {from_user.mention},"
            + " You can appeal for this ban by talking to him.",
        )
    except Exception:
        pass
    await m.edit(f"Banned {user.mention} Globally!")
    ban_text = f"""
__**New Global Ban**__
**Origin:** {message.chat.title} [`{message.chat.id}`]
**Admin:** {from_user.mention}
**Banned User:** {user.mention}
**Banned User ID:** `{user_id}`
**Reason:** __{reason}__
**Chats:** `{number_of_chats}`"""
    try:
        m2 = await app.send_message(
            GBAN_LOG_GROUP_ID,
            text=ban_text,
            disable_web_page_preview=True,
        )
        await m.edit(
            f"Banned {user.mention} Globally!\nAction Log: {m2.link}",
            disable_web_page_preview=True,
        )
    except Exception:
        await message.reply_text(
            "User Gbanned, But This Gban Action Wasn't Logged, Add Me In GBAN_LOG_GROUP"
        )


# Ungban


@app.on_message(filters.command("ungban"))
@capture_err
async def unban_globally(_, message):
    """Unban a globally banned user."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")
    user = await app.get_users(user_id)

    is_gbanned = await is_gbanned_user(user.id)
    if not is_gbanned:
        await message.reply_text("I don't remember Gbanning him.")
    else:
        await remove_gban_user(user.id)
        await message.reply_text(f"Lifted {user.mention}'s Global Ban.")


# Broadcast


@app.on_message(filters.command("broadcast"))
@capture_err
async def broadcast_message(_, message):
    """Broadcast a message to all served chats."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    sleep_time = 0.1
    reply_message = message.reply_to_message
    if not reply_message:
        return await message.reply_text("Reply to a message to broadcast it")
        
    sent = 0
    schats = await get_served_chats()
    chats = schats
    m = await message.reply_text(
        f"Broadcast in progress, will take {len(chats) * sleep_time} seconds."
    )
    to_copy = not reply_message.poll
    for i in chats:
        try:
            if to_copy:
                await reply_message.copy(i)
            else:
                await reply_message.forward(i)
            sent += 1
            await asyncio.sleep(sleep_time)
        except FloodWait as e:
            await asyncio.sleep(int(e.value))
        except Exception:
            pass
    await m.edit(f"**Broadcasted Message In {sent} Chats.**")


# User Broadcast


@app.on_message(filters.command("ubroadcast"))
@capture_err
async def broadcast_to_users(_, message):
    """Broadcast a message to all served users."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    sleep_time = 0.1
    sent = 0
    schats = await get_served_users()
    chats = schats
    reply_message = message.reply_to_message
    if not reply_message:
        return await message.reply_text("Reply to a message to broadcast it")

    m = await message.reply_text(
        f"Broadcast in progress, will take {len(chats) * sleep_time} seconds."
    )

    to_copy = not reply_message.poll
    for i in chats:
        try:
            if to_copy:
                await reply_message.copy(i)
            else:
                await reply_message.forward(i)
            sent += 1
            await asyncio.sleep(sleep_time)
        except FloodWait as e:
            await asyncio.sleep(int(e.value))
        except Exception:
            pass
    await m.edit(f"**Broadcasted Message to {sent} Users.**")


# Update


@app.on_message(filters.command("update"))
async def update_restart(_, message):
    """Update bot from git and restart."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    try:
        out = subprocess.check_output(["git", "pull"]).decode("UTF-8")
        if "Already up to date." in str(out):
            return await message.reply_text("It's already up to date!")
        await message.reply_text(f"```{out}```")
    except Exception as e:
        return await message.reply_text(str(e))
    m = await message.reply_text(
        "**Updated with default branch, restarting now.**"
    )
    await restart(m)


# Restart


@app.on_message(filters.command("restart"))
async def restart_bot(_, message):
    """Restart the bot."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    m = await message.reply_text(
        "**Bot is restarting now.**"
    )
    await restart(m)


# Global Stats


@app.on_message(filters.command("gstats"))
@capture_err
async def global_stats(_, message):
    """Show global bot statistics."""
    if not is_sudo(message.from_user.id):
        return await message.reply_text("❌ This command is for sudo users only.")
    
    chats = await get_served_chats()
    users = await get_served_users()
    
    stats_text = f"""
**📊 Global Bot Statistics**

**Chats:** {len(chats)}
**Users:** {len(users)}
**Uptime:** {formatter.get_readable_time(int(time.time() - bot_start_time))}
"""
    await message.reply_text(stats_text)
