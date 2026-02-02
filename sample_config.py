import os

from dotenv import load_dotenv

load_dotenv(
    "config.env" if os.path.isfile("config.env") else "sample_config.env"
)

# Bot configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Required: Get from @BotFather

# Default Telegram API credentials for bot accounts
# These are standard values used by official Telegram clients
API_ID = int(os.environ.get("API_ID", "6"))  # Default Telegram API ID
API_HASH = os.environ.get("API_HASH", "eb06d4abfb49dc3eeb1aeb98ae0f581e")  # Default Telegram API hash
SUDO_USERS_ID = list(map(int, os.environ.get("SUDO_USERS_ID", "").split()))
LOG_GROUP_ID = int(os.environ.get("LOG_GROUP_ID"))
GBAN_LOG_GROUP_ID = int(os.environ.get("GBAN_LOG_GROUP_ID"))
MESSAGE_DUMP_CHAT = int(os.environ.get("MESSAGE_DUMP_CHAT"))
WELCOME_DELAY_KICK_SEC = int(os.environ.get("WELCOME_DELAY_KICK_SEC", 600))
ARQ_API_KEY = os.environ.get("ARQ_API_KEY")
ARQ_API_URL = os.environ.get("ARQ_API_URL", "https://arq.hamker.dev")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")  # OpenRouter API key for AI features
MUSIC_CHANNEL_ID = int(os.environ.get("MUSIC_CHANNEL_ID", "0")) or None  # Music storage channel ID
DEEPL_API = os.environ.get("DEEPL_API")  # Optional: DeepL API key for better translations
LOG_MENTIONS = os.environ.get("LOG_MENTIONS", "True").lower() in ["true", "1"]
RSS_DELAY = int(os.environ.get("RSS_DELAY", 300))
PM_PERMIT = os.environ.get("PM_PERMIT", "True").lower() in ["true", "1"]

# Auto-delete commands feature is controlled per-group via /autodel commands
# Bot needs "Delete Messages" permission in groups to work
# No additional configuration required - works out of the box
