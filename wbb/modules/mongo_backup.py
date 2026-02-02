"""
SQLite Backup Module

Creates/restores backups of the SQLite database file used by the bot.
"""

import asyncio
import shutil
import zipfile
from pathlib import Path

from pyrogram import enums, filters
from pyrogram.types import Message

from wbb import SUDOERS_SET, app

DB_FILE = Path("wbb.sqlite")


@app.on_message(filters.command("backup") & filters.user(list(SUDOERS_SET)))
async def backup(_, message: Message):
    if message.chat.type != enums.ChatType.PRIVATE:
        return await message.reply("This command can only be used in private")

    m = await message.reply("Backing up SQLite database...")

    if not DB_FILE.exists():
        return await m.edit("No SQLite database found (wbb.sqlite).")

    backup_zip = Path("backup_sqlite.zip")
    if backup_zip.exists():
        backup_zip.unlink()

    def create_zip():
        with zipfile.ZipFile(backup_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(DB_FILE, DB_FILE.name)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, create_zip)

    await message.reply_document(str(backup_zip))
    await m.delete()


@app.on_message(filters.command("restore") & filters.user(list(SUDOERS_SET)))
async def restore(_, message: Message):
    if message.chat.type != enums.ChatType.PRIVATE:
        return await message.reply("This command can only be used in private")

    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("Reply to a backup file (zip) with /restore")

    m = await message.reply("Restoring SQLite database...")

    backup_file = await message.reply_to_message.download()
    backup_path = Path(backup_file)

    try:
        extract_dir = Path("restore_tmp")
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(backup_path, "r") as zf:
            zf.extractall(extract_dir)

        extracted_db = extract_dir / DB_FILE.name
        if not extracted_db.exists():
            return await m.edit("Backup zip does not contain wbb.sqlite")

        shutil.move(str(extracted_db), str(DB_FILE))
        await m.edit("Restore complete. Restart the bot to apply changes.")
    finally:
        if backup_path.exists():
            backup_path.unlink()
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
