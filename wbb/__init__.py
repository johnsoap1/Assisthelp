# wbb/__init__.py
"""
William Butcher Bot - Main initialization module.
"""
import asyncio
import os
import time
from pathlib import Path
from aiohttp import ClientSession
from pyrogram import Client, filters
from Python_ARQ import ARQ
from telegraph import Telegraph

# Load config first
is_config = os.path.exists("config.py")
if is_config:
    from config import *
else:
    from sample_config import *

# Ensure required directories exist
Path("sessions").mkdir(exist_ok=True)

# Initialize globals
MOD_LOAD = []
MOD_NOLOAD = []
SUDOERS_SET = set()
bot_start_time = time.time()

# Define SUDOERS filter
def sudo_filter(_, __, message):
    return message.from_user and message.from_user.id in SUDOERS_SET

SUDOERS = filters.create(sudo_filter)

# Logging class
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
    
    def error(self, msg):
        print(f"[ERROR]: {msg}")
        if self.save_to_file:
            with open(self.file_name, "a") as f:
                f.write(f"[ERROR]({time.ctime(time.time())}): {msg}\n")

log = Log(True, "bot.log")

# Initialize clients and sessions (will be set in startup)
app = None
aiohttpsession = None
arq = None
telegraph = None

# Bot info (will be set in startup)
BOT_ID = None
BOT_NAME = None
BOT_USERNAME = None
BOT_MENTION = None
BOT_DC_ID = None
LOG_GROUP_ID = None

# Load sudoers from database
async def load_sudoers():
    """Load sudo users from database."""
    global SUDOERS_SET
    import sqlite3
    import json
    
    conn = sqlite3.connect("wbb.sqlite")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sudoers (
            id INTEGER PRIMARY KEY,
            sudo TEXT DEFAULT 'sudo',
            data TEXT
        )
    """)
    
    cursor = conn.execute("SELECT data FROM sudoers WHERE sudo = 'sudo'")
    row = cursor.fetchone()
    
    if row:
        try:
            sudoers_data = json.loads(row[0])
            sudoers_list = sudoers_data.get("sudoers", [])
        except:
            sudoers_list = []
    else:
        sudoers_list = []
    
    # Add from config
    if 'SUDO_USERS_ID' in globals():
        for user_id in SUDO_USERS_ID:
            if user_id not in sudoers_list:
                sudoers_list.append(user_id)
    
    # Save updated list
    sudoers_data = {"sudoers": sudoers_list}
    conn.execute("""
        INSERT OR REPLACE INTO sudoers (sudo, data)
        VALUES ('sudo', ?)
    """, (json.dumps(sudoers_data),))
    
    conn.commit()
    conn.close()
    
    SUDOERS_SET = set(sudoers_list)
    log.info(f"Loaded SUDOERS: {SUDOERS_SET}")


# Startup function
async def startup():
    """Initialize and start the bot."""
    global app, aiohttpsession, arq, telegraph
    global BOT_ID, BOT_NAME, BOT_USERNAME, BOT_MENTION, BOT_DC_ID, LOG_GROUP_ID
    
    # Initialize storage
    from wbb.core.storage import init_storage
    await init_storage()
    
    # Load sudoers
    await load_sudoers()
    
    # Get config values
    BOT_TOKEN = globals().get('BOT_TOKEN')
    ARQ_API_URL = globals().get('ARQ_API_URL', 'https://arq.hamker.in')
    ARQ_API_KEY = globals().get('ARQ_API_KEY', '')
    LOG_GROUP_ID = globals().get('LOG_GROUP_ID')
    
    # Initialize Pyrogram client
    app = Client(
        "assistbot",
        api_id=6,  # Default for bots
        api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",  # Default for bots
        bot_token=BOT_TOKEN
    )
    
    # Initialize HTTP session and services
    aiohttpsession = ClientSession()
    arq = ARQ(ARQ_API_URL, ARQ_API_KEY, aiohttpsession)
    
    log.info("Starting bot...")
    await app.start()
    
    # Get bot info
    x = await app.get_me()
    BOT_ID = x.id
    BOT_NAME = x.first_name + (x.last_name or "")
    BOT_USERNAME = x.username
    BOT_MENTION = x.mention
    BOT_DC_ID = x.dc_id
    
    # Initialize Telegraph
    telegraph = Telegraph(domain="graph.org")
    telegraph.create_account(short_name=BOT_USERNAME)
    
    log.info(f"Bot started as @{BOT_USERNAME}")


# Shutdown function
async def shutdown():
    """Gracefully shutdown the bot."""
    log.info("Stopping clients...")
    if aiohttpsession:
        await aiohttpsession.close()
    if app:
        await app.stop()
    log.info("Shutdown complete.")


# Helper function for edit or reply
from inspect import getfullargspec

async def eor(msg, **kwargs):
    """Edit or reply to a message."""
    func = (
        (msg.edit_text if getattr(msg.from_user, "is_self", False) else msg.reply)
        if msg.from_user
        else msg.reply
    )
    spec = getfullargspec(func.__wrapped__).args
    return await func(**{k: v for k, v in kwargs.items() if k in spec})


# Run startup
loop = asyncio.get_event_loop()
loop.run_until_complete(startup())
