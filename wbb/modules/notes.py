from re import findall

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from wbb import app, eor
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly
from wbb.core.keyboard import ikb
from wbb.modules.admin import member_permissions
from wbb.utils.dbfunctions import (
    delete_note,
    deleteall_notes,
    get_note,
    get_note_names,
    save_note,
)
from wbb.utils.functions import check_format, extract_text_and_keyb, get_data_and_name

__MODULE__ = "Notes"
__HELP__ = """/notes - List all notes in the chat.
/save [NOTE_NAME] - Save a note (text, media, or reply).
/delete [NOTE_NAME] - Delete a note.
/deleteall - Delete all notes in a chat (admins only).
#NOTE_NAME - Fetch a note by its name.
"""

# --------------------- Helpers ---------------------
def extract_urls(reply_markup):
    urls = []
    if reply_markup.inline_keyboard:
        buttons = reply_markup.inline_keyboard
        for i, row in enumerate(buttons):
            for j, button in enumerate(row):
                if button.url:
                    name = (
                        "\n~\nbutton"
                        if i * len(row) + j + 1 == 1
                        else f"button{i * len(row) + j + 1}"
                    )
                    urls.append((f"{name}", button.text, button.url))
    return urls


async def get_reply(message, type, file_id, data, keyb):
    if type == "text":
        await message.reply_text(text=data, reply_markup=keyb, disable_web_page_preview=True)
    elif type == "sticker":
        await message.reply_sticker(sticker=file_id)
    elif type == "animation":
        await message.reply_animation(animation=file_id, caption=data, reply_markup=keyb)
    elif type == "photo":
        await message.reply_photo(photo=file_id, caption=data, reply_markup=keyb)
    elif type == "document":
        await message.reply_document(document=file_id, caption=data, reply_markup=keyb)
    elif type == "video":
        await message.reply_video(video=file_id, caption=data, reply_markup=keyb)
    elif type == "video_note":
        await message.reply_video_note(video_note=file_id)
    elif type == "audio":
        await message.reply_audio(audio=file_id, caption=data, reply_markup=keyb)
    elif type == "voice":
        await message.reply_voice(voice=file_id, caption=data, reply_markup=keyb)

# --------------------- Commands ---------------------
@app.on_message(filters.command("save") & ~filters.private)
@adminsOnly("can_change_info")
async def save_notee(_, message):
    if len(message.command) < 2:
        return await eor(message, "**Usage:**\nReply with /save [NOTE_NAME]")
    replied_message = message.reply_to_message or message
    data, name = await get_data_and_name(replied_message, message)
    if data == "error":
        return await message.reply_text("**Invalid format. Use /save [NOTE_NAME] or reply with a message.**")

    _type, file_id = None, None
    if replied_message.text:
        _type = "text"
    elif replied_message.sticker:
        _type, file_id = "sticker", replied_message.sticker.file_id
    elif replied_message.animation:
        _type, file_id = "animation", replied_message.animation.file_id
    elif replied_message.photo:
        _type, file_id = "photo", replied_message.photo.file_id
    elif replied_message.document:
        _type, file_id = "document", replied_message.document.file_id
    elif replied_message.video:
        _type, file_id = "video", replied_message.video.file_id
    elif replied_message.video_note:
        _type, file_id = "video_note", replied_message.video_note.file_id
    elif replied_message.audio:
        _type, file_id = "audio", replied_message.audio.file_id
    elif replied_message.voice:
        _type, file_id = "voice", replied_message.voice.file_id

    # Extract buttons if present
    if replied_message.reply_markup and not findall(r"\[.+\,.+\]", data):
        urls = extract_urls(replied_message.reply_markup)
        if urls:
            response = "\n".join([f"{name}=[{text}, {url}]" for name, text, url in urls])
            data += response

    if data:
        data = await check_format(ikb, data)
        if not data:
            return await message.reply_text("**Invalid formatting.**")

    chat_id = message.chat.id
    note = {"type": _type, "data": data, "file_id": file_id}
    await save_note(chat_id, name, note)
    await eor(message, f"__**Saved note {name}.**__")


@app.on_message(filters.regex(r"^#.+") & filters.text & ~filters.private)
@capture_err
async def get_one_note(_, message):
    name = message.text.replace("#", "", 1)
    if not name:
        return
    chat_id = message.chat.id
    _note = await get_note(chat_id, name)
    if not _note:
        return
    type, data, file_id = _note["type"], _note["data"], _note.get("file_id")
    keyb = None
    if data:
        if "{chat}" in data:
            data = data.replace("{chat}", message.chat.title)
        if "{name}" in data:
            from_user = message.from_user if message.from_user else message.sender_chat
            data = data.replace("{name}", from_user.mention if message.from_user else from_user.title)
        if findall(r"\[.+\,.+\]", data):
            extracted = extract_text_and_keyb(ikb, data)
            if extracted:
                data, keyb = extracted
    await get_reply(message, type, file_id, data, keyb)


@app.on_message(filters.command("notes") & ~filters.private)
@capture_err
async def get_notes(_, message):
    chat_id = message.chat.id
    _notes = await get_note_names(chat_id)
    if not _notes:
        return await eor(message, "**No notes in this chat.**")
    _notes.sort()
    msg = f"Notes in {message.chat.title}:\n"
    for note in _notes:
        msg += f"**-** `{note}`\n"
    await eor(message, msg)


@app.on_message(filters.command("delete") & ~filters.private)
@adminsOnly("can_change_info")
async def del_note(_, message):
    if len(message.command) < 2:
        return await eor(message, "**Usage:** /delete [NOTE_NAME]")
    name = message.text.split(None, 1)[1].strip()
    chat_id = message.chat.id
    deleted = await delete_note(chat_id, name)
    if deleted:
        await eor(message, f"**Deleted note {name}.**")
    else:
        await eor(message, "**No such note.**")


@app.on_message(filters.command("deleteall") & ~filters.private)
@adminsOnly("can_change_info")
async def delete_all(_, message):
    _notes = await get_note_names(message.chat.id)
    if not _notes:
        return await message.reply_text("**No notes to delete.**")
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("YES, DELETE ALL", callback_data="delete_yes"),
            InlineKeyboardButton("Cancel", callback_data="delete_no")
        ]]
    )
    await message.reply_text("**Delete all notes in this chat?**", reply_markup=keyboard)


@app.on_callback_query(filters.regex("delete_(.*)"))
async def delete_all_cb(_, cb):
    chat_id = cb.message.chat.id
    from_user = cb.from_user
    permissions = await member_permissions(chat_id, from_user.id)
    if "can_change_info" not in permissions:
        return await cb.answer("You don't have permission.", show_alert=True)
    choice = cb.data.split("_")[1]
    if choice == "yes":
        await deleteall_notes(chat_id)
        await cb.message.edit("**All notes deleted successfully.**")
    else:
        await cb.message.delete()
