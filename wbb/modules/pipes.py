"""
MIT License

Copyright (c) 2024 TheHamkerCat

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import asyncio

from pyrogram import filters
from pyrogram.types import Message

from wbb import BOT_ID, SUDOERS, SUDOERS_SET, app
from wbb.core.decorators.errors import capture_err

__MODULE__ = "Pipes"
__HELP__ = """
**THIS MODULE IS ONLY FOR DEVS**

Use this module to create a pipe that will forward messages of one chat/channel to another.


/activate_pipe [FROM_CHAT_ID] [TO_CHAT_ID] [BOT]

    Active a pipe.

    Only BOT option available (userbot removed).


/deactivate_pipe [FROM_CHAT_ID]
    Deactivete a pipe.


/show_pipes
    Show all the active pipes.

**NOTE:**
    These pipes are only temporary, and will be destroyed
    on restart.
"""
pipes_list = {}


@app.on_message(~filters.me, group=500)
@capture_err
async def pipes_worker(_, message: Message):
    chat_id = message.chat.id
    if chat_id in pipes_list:
        await message.forward(pipes_list[chat_id])


@app.on_message(filters.command("activate_pipe") & filters.user(list(SUDOERS_SET)))
@capture_err
async def activate_pipe_func(_, message: Message):
    global pipes_list

    if len(message.command) != 4:
        return await message.reply(
            "**Usage:**\n/activate_pipe [FROM_CHAT_ID] [TO_CHAT_ID] [BOT]"
        )

    text = message.text.strip().split()

    from_chat = int(text[1])
    to_chat = int(text[2])
    fetcher = text[3].lower()

    if fetcher != "bot":
        return await message.reply("Only BOT option available (userbot removed).")

    if from_chat in pipes_list:
        return await message.reply_text("This pipe is already active.")

    pipes_list[from_chat] = to_chat
    await message.reply_text("Activated pipe.")


@app.on_message(filters.command("deactivate_pipe") & filters.user(list(SUDOERS_SET)))
@capture_err
async def deactivate_pipe_func(_, message: Message):
    global pipes_list

    if len(message.command) != 2:
        await message.reply_text("**Usage:**\n/deactivate_pipe [FROM_CHAT_ID]")
        return
    text = message.text.strip().split()
    from_chat = int(text[1])

    if from_chat not in pipes_list:
        await message.reply_text("This pipe is already inactive.")
        return

    del pipes_list[from_chat]
    await message.reply_text("Deactivated pipe.")


@app.on_message(filters.command("pipes") & filters.user(list(SUDOERS_SET)))
@capture_err
async def show_pipes_func(_, message: Message):
    if not pipes_list:
        return await message.reply_text("No pipe is active.")

    text = ""
    for count, pipe in enumerate(pipes_list.items(), 1):
        text += (
            f"**Pipe:** `{count}`\n**From:** `{pipe[0]}`\n"
            + f"**To:** `{pipe[1]}`\n\n"
        )
    await message.reply_text(text)
