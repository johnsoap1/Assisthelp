<h1 align="center"> 
    🤖 AssistBot 🤖
</h1>

<h3 align="center">
    Advanced Telegram Group Manager Bot with Powerful Features
</h3>

<p align="center">
    <a href="https://python.org">
        <img src="http://forthebadge.com/images/badges/made-with-python.svg" alt="made-with-python">
    </a>
    <a href="https://github.com/yourusername/AssistBot">
        <img src="http://ForTheBadge.com/images/badges/built-with-love.svg" alt="built-with-love">
    </a> <br>
    <img src="https://img.shields.io/github/license/yourusername/AssistBot?style=for-the-badge&logo=appveyor" alt="LICENSE">
    <img src="https://img.shields.io/github/contributors/yourusername/AssistBot?style=for-the-badge&logo=appveyor" alt="Contributors">
    <img src="https://img.shields.io/github/repo-size/yourusername/AssistBot?style=for-the-badge&logo=appveyor" alt="Repository Size"> <br>
    <img src="https://img.shields.io/badge/python-3.9+-green?style=for-the-badge&logo=appveyor" alt="Python Version">
    <img src="https://img.shields.io/github/issues/yourusername/AssistBot?style=for-the-badge&logo=appveyor" alt="Issues">
    <img src="https://img.shields.io/github/forks/yourusername/AssistBot?style=for-the-badge&logo=appveyor" alt="Forks">
    <img src="https://img.shields.io/github/stars/yourusername/AssistBot?style=for-the-badge&logo=appveyor" alt="Stars">
</p>

## 🚀 Features

### �️ Storage
- Default: **SQLite** (`wbb.sqlite`) via SQLAlchemy with Mongo-like API (find_one, find, insert_one, update_one, delete_one)
- Optional: set `DB_URL` to point to another SQL backend (e.g., PostgreSQL) without changing modules
- Backup/restore: use `/backup` and `/restore` commands (zips the SQLite file)

### �🔄 Enhanced Pipes Module
Advanced message forwarding with multiple modes and history support.

### 🛠️ Enhanced Admin Module
Comprehensive admin functionality with command auto-deletion and Pyrogram 2.x compatibility.

**Key Features Added:**
- ✅ **Command Auto-Deletion**: Automatically removes command messages after execution
- ✅ **Toggle System**: Enable/disable command deletion per chat with `/rcommands` command
- ✅ **Status Tracking**: In-memory storage tracks settings per chat (resets on restart)
- ✅ **Permission Control**: Proper admin-only access with `can_delete_messages` requirement
- ✅ **Pyrogram 2.x Compatibility**: All imports and async operations updated for latest version

**Commands:**
```
/rcommands on         # Enable auto-delete for this chat
/rcommands off        # Disable auto-delete for this chat
/rcommands status     # Check current auto-delete status
/rcommands enable     # Alternative enable command
/rcommands disable    # Alternative disable command
```

**Technical Implementation:**
- **Auto-Delete Handler**: Runs with `group=1` priority to execute after other handlers
- **Smart Detection**: Only deletes messages if auto-delete is enabled for that specific chat
- **Safe Operations**: Uses `contextlib.suppress` for clean exception handling
- **Memory Storage**: `REMOVE_COMMANDS_ENABLED` dictionary tracks chat-specific settings

**Usage:**
1. Send `/rcommands on` in a group to enable auto-deletion
2. Use any admin command - it will be automatically deleted after execution
3. Send `/rcommands status` to check current setting
4. Send `/rcommands off` to disable the feature

**Features:**
- ✅ Works with Pyrogram 2.x
- ✅ Preserves all existing admin functionality
- ✅ Chat-specific settings
- ✅ Proper error handling
- ✅ Admin permission verification

### 🎵 Enhanced Music & Social Media Module
Fully upgraded Telegram-exclusive music and social media system with MongoDB caching, ID3 tagging, auto-delete commands, and comprehensive social media support.

**Major Changes & Improvements:**

| Area | What Changed | Why |
|------|-------------|-----|
| **yt-dlp instead of pytube** | Switched to yt-dlp for faster, more reliable downloads | yt-dlp supports more sites and handles YouTube throttling better |
| **MongoDB cache** | Replaced old ARQ/temporary logic with persistent MongoDB collection | Fast lookups, no repeated downloads, permanent caching |
| **ID3 tagging** | Added via mutagen (title, artist, embedded cover) | Makes MP3s usable outside Telegram with full metadata |
| **Cache management commands** | `/cacheinfo`, `/cachelist`, `/purge` for SUDOERS | Easy admin control and cleanup |
| **Inline query support** | Instant song sending from cache | Telegram-style inline experience |
| **Temp cleanup & concurrency** | Each download isolated to its own temp dir; global + per-chat semaphores | Prevents corruption and overlapping downloads |
| **Thumbnail safety** | Tries to fetch and embed; handles errors silently | Robust thumbnail experience |
| **Storage channel + Mongo integration** | Uploads to channel for persistent file_id caching | Instant reuse of Telegram-hosted MP3s |
| **Auto-delete commands** | All commands auto-delete after execution | Clean chat experience |
| **Force download** | `/song!` command to bypass cache and force fresh download | Users get correct songs when cache has wrong entries |
| **Social media support** | `/tiktok` and `/instagram` commands for downloading from social platforms | Expanded beyond just YouTube |
| **Exact cache matching** | Changed from fuzzy matching to exact matching only | Prevents wrong songs from being returned |

**Commands:**
```python
# Music Commands
/song <query>         # Search cache → channel → download → cache result
/song! <query>        # Force fresh download (bypass cache)
/ytmusic <query/url>  # Direct download without caching
/video <query/url>    # Download video with audio
/lyrics <query>       # Fetch song lyrics

# Social Media Commands
/tiktok <link>        # Download TikTok videos
/instagram <link>     # Download Instagram posts/reels

# Admin Commands
/cacheinfo           # Show cache count & last entry (sudo only)
/cachelist           # Show 10 latest cached songs (sudo only)
/purge <query>       # Delete specific cache entries (sudo only)
```

**Inline Usage:**
```python
@YourBot <song name>  # Instantly send cached songs via inline query
```

**Configuration Requirements:**
- **MUSIC_CHANNEL_ID**: Dedicated channel for storing uploaded songs
- **yt-dlp**: For reliable YouTube/Spotify/TikTok/Instagram downloads
- **mutagen**: For ID3 metadata tagging
- **MongoDB**: For persistent cache storage

**Features:**
- ✅ Telegram-exclusive (no external hosting needed)
- ✅ Persistent MongoDB caching for instant reuse
- ✅ Full metadata embedding for external MP3 players
- ✅ Admin controls for cache management
- ✅ Smart exact matching for song searches
- ✅ Concurrent download protection
- ✅ Automatic thumbnail extraction and embedding
- ✅ Auto-delete commands for clean chat experience
- ✅ Social media platform support (TikTok, Instagram)
- ✅ Force download option for cache override

### 🤖 AI Provider Refactoring
Modular AI system with OpenRouter integration and easy provider switching.

**Key Changes:**
- ✅ **Generic AI Function**: `get_ai_response()` for all AI operations
- ✅ **OpenRouter Integration**: Uses OpenRouter API for AI responses
- ✅ **Easy Provider Switching**: Change AI backend in one place only
- ✅ **Shared AI Resource**: Both chatbot and summary commands use same function
- ✅ **Error Handling**: Graceful fallbacks when AI services fail

**Technical Implementation:**
- **Centralized AI Module**: `ai_provider.py` with generic AI function
- **Environment Configuration**: `OPENROUTER_API_KEY` in config files
- **Modular Design**: Easy to switch between AI providers (OpenRouter, OpenAI, etc.)
- **Backward Compatibility**: Existing chatbot functionality preserved

**Benefits:**
- 🔄 **Single AI Abstraction**: One place to change AI provider
- 🚀 **Easy Maintenance**: Update AI logic in one file
- 📈 **Scalable**: New AI features can reuse same function
- 🛡️ **Reliable**: Proper error handling and fallbacks

### 🗑️ Auto-Delete Commands System
Comprehensive auto-delete system for clean command management across all bot functionality.

**Features:**
- ✅ **Per-Group Control**: Admins can enable/disable in their groups
- ✅ **Global Control**: Sudo users can enable globally for all groups
- ✅ **Smart Deletion**: Works with ALL commands (/help, /song, /stats, etc.)
- ✅ **Priority Handler**: Runs before other handlers (group=-1)
- ✅ **Intelligent Delays**: /autodel commands deleted after showing response
- ✅ **Permission Handling**: Graceful fallback if bot lacks delete permissions

**Commands:**
```python
# Per-group control (admin only)
/autodel on          # Enable auto-delete in current group
/autodel off         # Disable auto-delete in current group
/autodel status      # Check current status

# Global control (sudo only)
/autodel global on   # Enable globally for all groups
/autodel global off  # Disable globally

# Aliases supported
/autodel, /autoclear, /delcmd
```

**Technical Implementation:**
- **Priority Handler**: Runs before all other command handlers (group=-1)
- **MongoDB Storage**: `auto_delete_commands` collection for settings
- **In-Memory Caching**: Settings cached for performance
- **Permission Checking**: Admin and sudo user validation

**Benefits:**
- 🧹 **Clean Chats**: Commands auto-deleted after execution
- ⚙️ **Admin Control**: Per-group and global management
- 🚀 **Zero Configuration**: Works with all existing commands
- 🛡️ **Error Resilient**: Handles permission issues gracefully

## 🛠 Deployment Options

### 🖥 Local Installation (Recommended for Development)

1. **Prerequisites**
   - Python 3.9 or higher
   - Git
   - Telegram API credentials from [my.telegram.org](https://my.telegram.org/)

2. **Setup**
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/AssistBot.git
   cd AssistBot
   
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Configure environment variables
   cp sample_config.py config.py
   # Edit config.py with your credentials
   # Set DB_URL to use a different SQL backend (optional)
   ```

3. **Running**
   ```bash
   python -m wbb
   ```

### 🐳 Docker Deployment (Recommended for Production)

1. **Prerequisites**
   - Docker and Docker Compose
   - MongoDB URI
   - Telegram API credentials

2. **Setup**
   ```bash
   git clone https://github.com/yourusername/AssistBot.git
   cd AssistBot
   
   # Copy and edit environment variables
   cp sample_config.env config.env
   nano config.env  # Edit with your credentials
   ```

3. **Build and Run**
   ```bash
   docker-compose up -d --build
   ```

4. **View Logs**
   ```bash
   docker-compose logs -f
   ```

### ☁️ Cloud Deployment

#### Option 1: Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/yourusername/AssistBot)

1. Click the Deploy to Heroku button
2. Fill in the required environment variables
3. Deploy!

#### Option 2: Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/yourusername/AssistBot)

### 🔄 Updating the Bot

```bash
# For local installations
git pull
pip install -r requirements.txt --upgrade

# For Docker
docker-compose pull
docker-compose up -d --build
```

## 🔧 Configuration

1. Get your bot token from [@BotFather](https://t.me/BotFather)
2. Create a `.env` file with your bot token:
   ```env
   BOT_TOKEN=your_bot_token_here
   ```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For support, join our [Support Group](https://t.me/AssistBotSupport).

---

<p align="center">
    Made with ❤️ by <a href="https://github.com/yourusername">Your Name</a> and <a href="https://github.com/yourusername/AssistBot/graphs/contributors">Contributors</a>
</p>
