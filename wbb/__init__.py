import asyncio
import os
import time
from inspect import getfullargspec
from os import path, remove
from pathlib import Path

from aiohttp import ClientSession
from pyrogram import Client, filters
from pyrogram.types import Message
from pyromod import listen
from Python_ARQ import ARQ
from telegraph import Telegraph

from wbb.core.storage import init_storage, db

# Load config
is_config = path.exists("config.py")
if is_config:
    from config import *
else:
    from sample_config import *

# Optional DeepL API key for translation
DEEPL_API = os.environ.get("DEEPL_API")

# Ensure sessions folder exists
Path("sessions").mkdir(exist_ok=True)

# Globals
MOD_LOAD = []
MOD_NOLOAD = []
SUDOERS_SET = set()  # actual user IDs
SUDOERS = filters.user(list(SUDOERS_SET))
bot_start_time = time.time()


# Logging helper
class Log:
    def __init__(self, save_to_file=False, file_name="wbb.log"):
        self.save_to_file = save_to_file
        self.file_name = file_name

    def info(self, msg):
        print(f"[+]: {msg}")
        if self.save_to_file:
            with open(self.file_name, "a") as f:
                f.write(f"[INFO]({time.ctime(time.time())}): {msg}\n")

    def warning(self, msg):
        print(f"[!]: {msg}")
        if self.save_to_file:
            with open(self.file_name, "a") as f:
                f.write(f"[WARNING]({time.ctime(time.time())}): {msg}\n")


log = Log(True, "bot.log")

# Helper to load sudoers
async def load_sudoers():
    global SUDOERS, SUDOERS_SET
    log.info("Loading sudoers from DB")
    sudoers_db = db.sudoers
    sudoers_doc = await sudoers_db.find_one({"sudo": "sudo"})
    sudoers_list = sudoers_doc["sudoers"] if sudoers_doc else []

    for user_id in SUDO_USERS_ID:
        if user_id not in sudoers_list:
            sudoers_list.append(user_id)
            await sudoers_db.update_one(
                {"sudo": "sudo"}, {"$set": {"sudoers": sudoers_list}}, upsert=True
            )

    SUDOERS_SET = set(sudoers_list)
    SUDOERS = filters.user(list(SUDOERS_SET))
    log.info(f"Loaded SUDOERS: {SUDOERS_SET}")


# Async helper to edit or reply safely
async def eor(msg: Message, **kwargs):
    func = (
        (msg.edit_text if getattr(msg.from_user, "is_self", False) else msg.reply)
        if msg.from_user
        else msg.reply
    )
    spec = getfullargspec(func.__wrapped__).args
    return await func(**{k: v for k, v in kwargs.items() if k in spec})


# Startup function
async def startup():
    global app, aiohttpsession, arq, telegraph

    # Initialize SQLite storage
    await init_storage()

    await load_sudoers()

    # Initialize Pyrogram client with default Telegram API credentials for bot accounts
    app = Client(
        "assistbot",
        api_id=6,  # Default Telegram API ID for bot accounts
        api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",  # Default Telegram API hash for bot accounts
        bot_token=BOT_TOKEN
    )

    aiohttpsession = ClientSession()
    arq = ARQ(ARQ_API_URL, ARQ_API_KEY, aiohttpsession)

    log.info("Starting bot...")
    await app.start()

    # Bot profile
    log.info("Fetching bot profile info...")
    x = await app.get_me()

    global BOT_ID, BOT_NAME, BOT_USERNAME, BOT_MENTION, BOT_DC_ID

    BOT_ID = x.id
    BOT_NAME = x.first_name + (x.last_name or "")
    BOT_USERNAME = x.username
    BOT_MENTION = x.mention
    BOT_DC_ID = x.dc_id

    # Telegraph
    log.info("Initializing Telegraph...")
    telegraph = Telegraph(domain="graph.org")
    telegraph.create_account(short_name=BOT_USERNAME)

    log.info("Bot startup complete (userbot disabled).")


# Graceful shutdown
async def shutdown():
    log.info("Stopping clients...")
    await app.stop()
    await aiohttpsession.close()
    log.info("Shutdown complete.")


# Run startup
loop = asyncio.get_event_loop()
loop.run_until_complete(startup())
