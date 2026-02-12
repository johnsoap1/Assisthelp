"""
Music Downloader Module for Telegram

A high-performance music downloader with caching support for Telegram bots.
Supports YouTube and YouTube Music with automatic format conversion to MP3.

Features:
- Multi-source fallback (YouTube → YouTube Music → SoundCloud)
- Smart caching with exact query matching
- Support for age-restricted content via cookies
- MP3 format for maximum compatibility
- Automatic command cleanup
- Robust error recovery
"""
import os
import re
import datetime
import asyncio
import hashlib
import json
import random
import shutil
import tempfile
import time
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Bot imports
from wbb import app, SUDOERS, arq
from wbb.utils.dbfunctions import (
    get_cached_song, save_cached_song, delete_cached_song,
    get_music_cache_count, get_recent_cached_songs, purge_music_cache
)
from wbb.core.storage import db
from pyrogram import filters
from pyrogram.types import InlineQuery, InlineQueryResultAudio, Message
from yt_dlp import YoutubeDL

# Basic error handler decorator
def capture_err(func):
    """Simple error handler decorator for command handlers."""
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            print(f"Error in {func.__name__}: {error_message}")
            try:
                await message.reply_text(f"❌ {error_message[:200]}")
            except Exception as e:
                print(f"Failed to send error message: {e}")
    return wrapper

# ==================== MODULE INFO ====================

__MODULE__ = "Music"
__HELP__ = """
🎵 **Music Downloader**

Download music from YouTube, YouTube Music, and SoundCloud with smart caching.

**Commands:**
- `/song <query>` - Search and download songs (MP3, cached)
- `/song! <query>` - Force fresh download (bypass cache)
- `/ytmusic <query/link>` - YouTube Music download
- `/lyrics <song>` - Get song lyrics

**Admin Commands:**
- `/cacheinfo` - Show cache statistics
- `/cachelist` - List recent cached songs
- `/purge <query>` - Delete cached entries
- `/teststorage` - Test storage configuration

**Features:**
✅ Multi-source fallback (YouTube → YouTube Music → SoundCloud)
✅ Smart caching with exact query matching
✅ Age-restricted video support via cookies
✅ MP3 format for maximum compatibility
✅ Automatic command cleanup
✅ Robust error recovery

**Setup:**
1. Set `MUSIC_GROUP_ID` or `MUSIC_CHANNEL_ID` in config.env
2. (Optional) Place cookies.txt in `/root/cookies/` for age-restricted content
3. Ensure bot is admin in storage location with send permissions

**Examples:**
`/song shape of you` 
`/song! levitating dua lipa` 
`/ytmusic blinding lights` 
`/lyrics imagine dragons believer` 

**Note:** Use `/song!` to force re-download if cache has wrong song.
"""

# ==================== CONFIGURATION ====================

# Storage configuration
MUSIC_GROUP_ID = int(os.getenv("MUSIC_GROUP_ID", "0")) or None
MUSIC_CHANNEL_ID = int(os.getenv("MUSIC_CHANNEL_ID", "0")) or None

# Limits
MAX_DURATION = 3600  # 1 hour
MAX_FILESIZE_MB = 100
MIN_FILESIZE_BYTES = 50_000  # 50KB minimum valid file

# Directories
TEMP_DIR = Path(tempfile.gettempdir()) / "wbb_music"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
COOKIES_PATH = Path("/root/cookies/cookies.txt")

# Concurrency
GLOBAL_SEM = asyncio.Semaphore(10)  # Increased from 6 to 10
DOWNLOAD_TIMEOUT = 180  # Reduced from 300 to 180 (3 minutes)

# ==================== DATABASE ====================

# ==================== USER AGENTS ====================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ==================== INVIDIOUS INSTANCES ====================

INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://vid.puffyan.us",
    "https://inv.riverside.rocks",
    "https://invidious.snopyta.org",
]

# ==================== HELPER FUNCTIONS ====================

def setup_ytdlp_config():
    """Create clean yt-dlp config to prevent interference."""
    config_dir = Path.home() / ".config" / "yt-dlp"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config"
    if not config_file.exists():
        config_file.write_text("# Auto-generated - minimal config\n")

setup_ytdlp_config()

def human_time(sec: int) -> str:
    """Convert seconds to human readable format."""
    return str(datetime.timedelta(seconds=int(sec)))

def safe_filename(s: str) -> str:
    """Create a safe filename from string."""
    return "".join(c for c in s if c.isalnum() or c in (" ", "-", "_", ".", "(", ")")).strip()[:180]

def sanitize_template(name: str) -> str:
    """Sanitize yt-dlp template strings while preserving placeholders."""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_%.(){}")
    return "".join(ch if ch in allowed else "_" for ch in name)

def normalize_query(query: str) -> str:
    """Normalize query for exact matching."""
    return re.sub(r'\s+', ' ', query.lower().strip())

def normalize_song_query(q: str) -> str:
    """Normalize search query for better matching."""
    if q.startswith(("http://", "https://")):
        return q
    
    # Remove noise
    q = re.sub(r'\(.*?\)|\[.*?\]', '', q)
    q = re.sub(r'\b(lyrics|official.*?video?|official.*?audio|official|video|audio|hd|hq|4k|full|song|track)\b', 
               '', q, flags=re.IGNORECASE)
    
    # Clean and add hint for short queries
    q = ' '.join(q.split()).strip()
    if len(q.split()) <= 2 and not q.startswith(("http://", "https://")):
        q += " official audio"
    
    return q

def is_sudo(user_id: int) -> bool:
    """Check if user is sudo."""
    return user_id in SUDOERS

def is_valid_audio(path: Path) -> bool:
    """Validate audio file integrity (quick check)."""
    if not path.exists() or path.stat().st_size < MIN_FILESIZE_BYTES:
        return False
    # Skip ffprobe validation for speed - just check size
    return True

def debug_file_info(file_path: str, prefix: str = ""):
    """Debug helper to log file information."""
    try:
        p = Path(file_path)
        if not p.exists():
            print(f"[DEBUG {prefix}] ❌ File does not exist: {file_path}")
            return False
        
        size = p.stat().st_size
        print(f"[DEBUG {prefix}] ✓ File: {file_path}")
        print(f"[DEBUG {prefix}] ✓ Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
        
        return is_valid_audio(p)
    except Exception as e:
        print(f"[DEBUG {prefix}] ❌ Error: {e}")
        return False

# ==================== CACHE MANAGEMENT ====================

async def get_cached_song(query: str, exact_only: bool = True) -> Optional[Dict]:
    """Get cached song by query with access tracking (SQLite)."""
    query_norm = normalize_query(query)

    data = await get_cached_song(query_norm, exact_only)
    return data

async def save_cached_song(
    query: str,
    title: str,
    performer: str,
    duration: int,
    file_id: str,
    thumb_file_id: Optional[str],
    storage_msg_id: int,
):
    """Save song to cache with file_id for instant retrieval (SQLite)."""
    normalized_query = normalize_query(query)
    now = int(time.time())

    await save_cached_song(
        normalized_query, title, performer, duration, file_id, thumb_file_id, storage_msg_id
    )
    print(f"[CACHE] Saved: '{normalized_query}' -> file_id: {file_id[:20]}...")

async def delete_cached_song(query: str):
    """Delete cached song by exact query match."""
    await delete_cached_song(query)

# ==================== YT-DLP OPTIONS ====================

def get_base_opts(cookiefile: Optional[str] = None) -> Dict:
    """Get base yt-dlp options for audio downloads."""
    opts = {
        "format": "bestaudio/best",  # Simplified format selection for audio only
        "outtmpl": str(TEMP_DIR / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            },
            {"key": "FFmpegMetadata"}  # Preserve metadata
        ],
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "extract_flat": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/129.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        },
        "geo_bypass": True,
        "nocheckcertificate": True,
        "ignore_no_formats_error": True,  # Don't fail if preferred format isn't available
        "extractor_retries": 3,  # Retry extraction
        "noprogress": True,  # Don't show progress in logs
    }
    
    if cookiefile and Path(cookiefile).exists():
        opts["cookiefile"] = cookiefile
        print(f"[YT-DLP] Using cookies from {cookiefile}")
    
    return opts

def get_audio_m4a_opts(tmpdir: Path, cookiefile: Optional[str] = None) -> Dict:
    """Get M4A audio download options (preferred - fast, no re-encoding)."""
    opts = get_base_opts(cookiefile)
    opts.update({
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "outtmpl": str(tmpdir / "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",  # Higher quality for music
        }],
    })
    return opts

def get_audio_mp3_opts(tmpdir: Path, cookiefile: Optional[str] = None) -> Dict:
    """Get MP3 audio download options (fallback - requires re-encoding)."""
    opts = get_base_opts(cookiefile)
    opts.update({
        "format": "bestaudio/best",
        "outtmpl": str(tmpdir / "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",  # Higher quality for music
        }],
    })
    return opts

def get_video_opts(tmpdir: Path, cookiefile: Optional[str] = None) -> Dict:
    """YT-DLP options for full-size video downloads with fallback."""
    opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "outtmpl": str(tmpdir / sanitize_template("%(id)s.%(ext)s")),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "merge_output_format": "mp4",
        "prefer_ffmpeg": True,
        "http_headers": {"User-Agent": random.choice(USER_AGENTS)},
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            },
            {"key": "FFmpegMetadata"},
        ],
        "postprocessor_args": [
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
        ],
        "fixup": "detect_or_warn",
    }
    if cookiefile and Path(cookiefile).exists():
        opts["cookiefile"] = cookiefile
    return opts

# ==================== SEARCH QUERY BUILDERS ====================

def build_yt_search(query: str) -> str:
    """Build YouTube search query."""
    if query.startswith(("http://", "https://")):
        return query
    return f"ytsearch1:{normalize_song_query(query)}"  # Changed from ytsearch5 to ytsearch1 for speed

def build_ytmusic_search(query: str) -> str:
    """Build YouTube Music search query."""
    if query.startswith(("http://", "https://")):
        return query
    return f"ytmusicsearch1:{normalize_song_query(query)}"  # Changed from 5 to 1

def build_soundcloud_search(query: str) -> str:
    """Build SoundCloud search query."""
    if query.startswith(("http://", "https://")):
        return query
    return f"scsearch1:{normalize_song_query(query)}"  # Changed from 5 to 1

# ==================== DOWNLOAD FUNCTIONS ====================

def _download_blocking(search: str, opts: Dict, tmpdir: Path, 
                       allowed_exts: List[str]) -> Dict:
    """
    Blocking download function - runs in executor.
    
    Args:
        search: Search query or URL
        opts: YoutubeDL options
        tmpdir: Temporary directory for downloads
        allowed_exts: List of allowed file extensions (e.g., [".mp3", ".m4a"])
        
    Returns:
        Dict with metadata: {
            "file": str,       # Path to downloaded file
            "title": str,      # Title of the media
            "performer": str,  # Artist/uploader name
            "duration": int,   # Duration in seconds
            "tmpdir": str,     # Temporary directory path
            "thumb_url": str   # URL to thumbnail (optional)
        }
    """
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(search, download=True)
        if "entries" in info:
            info = info["entries"][0]
    
    # Find downloaded file
    files = []
    for ext in allowed_exts:
        files.extend(tmpdir.glob(f"*{ext}"))
        if files:
            break
    
    if not files:
        raise RuntimeError(f"Download produced no files with extensions: {allowed_exts}")
    
    file = files[0]
    
    # Validate file
    if not is_valid_audio(file):
        raise RuntimeError(f"Downloaded file is invalid: {file.name}")
    
    return {
        "file": str(file),
        "title": info.get("title", file.stem)[:64],
        "performer": (info.get("artist") or info.get("uploader") or "Unknown")[:64],
        "duration": int(info.get("duration", 0)),
        "tmpdir": str(tmpdir),
        "thumb_url": info.get("thumbnail"),
    }

def _download_video_blocking(search: str, tmpdir: Path, cookiefile: Optional[str]) -> Dict:
    """Blocking video download with fallback for best-only streams."""
    opts = get_video_opts(tmpdir, cookiefile)

    def run_download(current_opts: Dict) -> Dict:
        with YoutubeDL(current_opts) as ydl:
            extracted = ydl.extract_info(search, download=True)
        if "entries" in extracted:
            extracted = extracted["entries"][0]
        return extracted

    try:
        info = run_download(opts)
    except IndexError:
        fallback_opts = {**opts, "format": "best", "postprocessors": opts.get("postprocessors", [])}
        info = run_download(fallback_opts)

    formats = info.get("formats") or []
    if len(formats) <= 1 and opts["format"] != "best":
        fallback_opts = {**opts, "format": "best", "postprocessors": opts.get("postprocessors", [])}
        info = run_download(fallback_opts)

    files: List[Path] = []
    for ext in (".mp4", ".mkv", ".webm"):
        files.extend(tmpdir.glob(f"*{ext}"))
        if files:
            break

    if not files:
        raise RuntimeError("Download produced no video files")

    file_path = files[0]

    return {
        "file": str(file_path),
        "title": info.get("title", file_path.stem)[:100],
        "duration": int(info.get("duration", 0)),
        "uploader": (info.get("uploader") or info.get("channel") or "Unknown")[:64],
        "width": info.get("width"),
        "height": info.get("height"),
        "tmpdir": str(tmpdir),
    }

async def download_audio(query: str, sources: List[str] = None) -> Dict:
    """
    Download audio with multi-source fallback.
    
    Args:
        query: Search query or URL
        sources: List of sources to try (default: youtube, ytmusic, soundcloud)
        
    Returns:
        Dict with download metadata
    """
    if sources is None:
        sources = ["youtube", "ytmusic", "soundcloud"]
    
    cookiefile = str(COOKIES_PATH) if COOKIES_PATH.exists() else None
    last_error = None
    
    # Try each source
    for source in sources:
        try:
            print(f"[DOWNLOAD] Trying source: {source}")
            
            if source == "youtube":
                return await download_audio_youtube(query, cookiefile)
            elif source == "ytmusic":
                return await download_audio_ytmusic(query, cookiefile)
            elif source == "soundcloud":
                return await download_audio_soundcloud(query)
            else:
                print(f"[DOWNLOAD] Unknown source: {source}")
                continue
                
        except Exception as e:
            last_error = e
            print(f"[DOWNLOAD] Source {source} failed: {str(e)[:100]}")
            continue
    
    # All sources failed
    raise RuntimeError(f"All sources failed. Last error: {str(last_error)[:200]}")

async def download_audio_youtube(query: str, cookiefile: Optional[str] = None) -> Dict:
    """Download audio from YouTube."""
    tmpdir = TEMP_DIR / f"yt_{int(time.time())}_{random.randint(1000, 9999)}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    
    search = build_yt_search(query)
    print(f"[YOUTUBE] Downloading: {query}")
    
    # Use MP3 directly (more reliable than M4A)
    try:
        opts = get_audio_mp3_opts(tmpdir, cookiefile)
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_download_blocking, search, opts, 
                                              tmpdir, [".mp3", ".m4a", ".webm"])),
            timeout=DOWNLOAD_TIMEOUT
        )
        print(f"[YOUTUBE] Download successful")
        return result
    except asyncio.TimeoutError:
        print(f"[YOUTUBE] Download timed out")
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    except Exception as e:
        print(f"[YOUTUBE] Failed: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise

async def download_audio_ytmusic(query: str, cookiefile: Optional[str] = None) -> Dict:
    """Download audio from YouTube Music."""
    tmpdir = TEMP_DIR / f"ytm_{int(time.time())}_{random.randint(1000, 9999)}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    
    # YouTube Music doesn't work with ytmusicsearch, use regular ytsearch with "topic" hint
    search = f"ytsearch1:{normalize_song_query(query)} topic"  # Changed from 5 to 1
    print(f"[YTMUSIC] Downloading: {query}")
    
    try:
        opts = get_audio_mp3_opts(tmpdir, cookiefile)
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_download_blocking, search, opts, 
                                              tmpdir, [".mp3", ".m4a", ".webm"])),
            timeout=DOWNLOAD_TIMEOUT
        )
        print(f"[YTMUSIC] Download successful")
        return result
    except Exception as e:
        print(f"[YTMUSIC] Failed: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise

async def download_audio_soundcloud(query: str) -> Dict:
    """Download audio from SoundCloud."""
    tmpdir = TEMP_DIR / f"sc_{int(time.time())}_{random.randint(1000, 9999)}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    
    search = build_soundcloud_search(query)
    print(f"[SOUNDCLOUD] Downloading: {query}")
    
    try:
        opts = get_audio_mp3_opts(tmpdir)
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_download_blocking, search, opts, 
                                              tmpdir, [".mp3", ".m4a"])),
            timeout=DOWNLOAD_TIMEOUT
        )
        print(f"[SOUNDCLOUD] Download successful")
        return result
    except Exception as e:
        print(f"[SOUNDCLOUD] Failed: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise

async def download_video(query: str) -> Dict:
    """Download full-size video from YouTube or URL."""
    tmpdir = TEMP_DIR / f"vid_{int(time.time())}_{random.randint(1000,9999)}"
    tmpdir.mkdir(parents=True, exist_ok=True)

    search = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"

    cookiefile = str(COOKIES_PATH) if COOKIES_PATH.exists() else None
    loop = asyncio.get_running_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                partial(_download_video_blocking, search, tmpdir, cookiefile)
            ),
            timeout=DOWNLOAD_TIMEOUT
        )
        return result
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise e

# ==================== STORAGE UPLOAD ====================

async def upload_to_storage(file_path: str, title: str, performer: str, 
                            duration: int, thumb_path: Optional[str]) -> Message:
    """
    Upload audio to storage location.
    
    Args:
        file_path: Path to audio file
        title: Title/caption
        performer: Performer/artist name
        duration: Duration in seconds
        thumb_path: Path to thumbnail
        
    Returns:
        Sent message object with the uploaded audio
    """
    # Validate file
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise RuntimeError(f"File not found: {file_path}")
    
    file_size = file_path_obj.stat().st_size
    if file_size < MIN_FILESIZE_BYTES:
        raise RuntimeError(f"File too small ({file_size} bytes), likely corrupted")
    
    # Get storage location
    storage_id = MUSIC_GROUP_ID or MUSIC_CHANNEL_ID
    
    if not storage_id:
        raise RuntimeError("No storage configured. Set MUSIC_GROUP_ID or MUSIC_CHANNEL_ID")
    
    try:
        # Upload as audio (music module only handles audio)
        sent = await app.send_audio(
            chat_id=storage_id,
            audio=file_path,
            caption=title,
            performer=performer,
            title=title,
            duration=duration,
            thumb=thumb_path,
            disable_notification=True
        )
        
        print(f"[STORAGE] ✅ Uploaded to {storage_id}")
        return sent
        
    except Exception as e:
        print(f"[STORAGE] ❌ Failed to upload: {str(e)[:100]}")
        raise RuntimeError(f"Failed to upload to storage: {str(e)[:200]}")

# ==================== COMMAND HANDLERS ====================

@app.on_message(filters.command(["song", "song!"]) & filters.group)
@capture_err
async def song_handler(_, m: Message):
    """Handle /song and /song! commands."""
    if len(m.command) < 2:
        return await m.reply_text("📝 Usage: `/song <query>`\n\nUse `/song!` to force fresh download.")
    
    force = m.command[0].endswith("!")
    query = m.text.split(None, 1)[1].strip()
    msg = await m.reply_text(f"🔎 {'Forcing fresh download' if force else 'Searching'}: `{query}`...")
    
    try:
        # Check cache first (unless forced)
        if not force:
            cached = await get_cached_song(query, exact_only=True)
            if cached:
                try:
                    file_id = cached.get("file_id")
                    title = cached.get("title")
                    await msg.edit(f"✅ Found in cache: **{title}**")
                    await m.reply_audio(file_id)
                    await msg.delete()
                    try:
                        await m.delete()
                    except:
                        pass
                    print(f"[CACHE HIT] Served from cache: {query}")
                    return
                except Exception as e:
                    # File ID might be invalid, continue to download
                    print(f"[CACHE] File ID invalid, re-downloading: {e}")
                    await delete_cached_song(query)
        else:
            # Force flag: delete cache and re-download
            await delete_cached_song(query)
            await msg.edit("🔄 Cache cleared, downloading fresh...")
        
        # Download new file
        async with GLOBAL_SEM:
            await msg.edit("⬇️ Downloading from YouTube...")
            result = await download_audio(query)
            
            # Validate downloaded file
            if not result or not result.get("file"):
                raise RuntimeError("Download failed - no file returned")
            
            file_path = Path(result["file"])
            if not file_path.exists():
                raise RuntimeError(f"Downloaded file not found: {file_path}")
            
            if file_path.stat().st_size < MIN_FILESIZE_BYTES:
                raise RuntimeError(f"Downloaded file too small, likely corrupted")
            
            # Upload to storage
            storage_id = MUSIC_GROUP_ID or MUSIC_CHANNEL_ID
            if storage_id:
                try:
                    await msg.edit("📤 Uploading to storage...")
                    sent = await upload_to_storage(
                        result["file"], 
                        result["title"], 
                        result["performer"],
                        result["duration"], 
                        result.get("thumb_path")
                    )
                    
                    # Save to cache with file_id
                    await save_cached_song(
                        query, 
                        result["title"], 
                        result["performer"], 
                        result["duration"],
                        sent.audio.file_id, 
                        sent.audio.thumbs[0].file_id if sent.audio.thumbs else None,
                        sent.id
                    )
                    
                    await msg.edit("✅ Done! Sending...")
                    await m.reply_audio(sent.audio.file_id)
                    print(f"[CACHED] Saved to storage: {query}")
                    
                except Exception as e:
                    # Storage upload failed, send directly without caching
                    print(f"[STORAGE ERROR] Failed to upload: {e}")
                    await msg.edit("⚠️ Storage unavailable, sending directly...")
                    await m.reply_audio(
                        result["file"], 
                        title=result["title"], 
                        performer=result["performer"],
                        duration=result["duration"], 
                        thumb=result.get("thumb_path")
                    )
            else:
                # No storage configured, send directly (no caching)
                await msg.edit("✅ Sending...")
                await m.reply_audio(
                    result["file"], 
                    title=result["title"], 
                    performer=result["performer"],
                    duration=result["duration"], 
                    thumb=result.get("thumb_path")
                )
                print(f"[NO STORAGE] Sent directly without caching")
            
            await msg.delete()
            try:
                await m.delete()
            except:
                pass
            
            # Cleanup temporary files
            shutil.rmtree(result["tmpdir"], ignore_errors=True)
            
    except asyncio.TimeoutError:
        await msg.edit("❌ Download timed out. Try again later.")
    except Exception as e:
        await msg.edit(f"❌ Error: {str(e)[:200]}")
        print(f"[ERROR] /song: {e}")
        import traceback
        traceback.print_exc()

@app.on_message(filters.command("lyrics"))
async def lyrics_handler(_, m: Message):
    """Handle /lyrics command."""
    if len(m.command) < 2:
        return await m.reply_text("🎵 Usage: `/lyrics <song name>`")
    
    query = m.text.split(None, 1)[1].strip()
    msg = await m.reply_text("🔍 Searching lyrics...")
    
    try:
        if arq is None:
            return await msg.edit("❌ Lyrics service unavailable.")
        
        resp = await arq.lyrics(query)
        if not (resp.ok and resp.result):
            return await msg.edit("❌ No lyrics found.")
        
        song = resp.result[0]
        text = f"**{song['song']}** | **{song['artist']}**\n\n{song['lyrics']}"
        
        if len(text) > 4096:
            text = text[:4090] + "..."
        
        await msg.edit(text)
        
        try:
            await m.delete()
        except:
            pass
            
    except Exception as e:
        await msg.edit(f"❌ Error: {str(e)[:200]}")
        print(f"[ERROR] /lyrics: {e}")

@app.on_message(filters.command("video") & (filters.group | filters.private))
@capture_err
async def video_handler(_, m: Message):
    """Universal video downloader."""
    if len(m.command) < 2:
        return await m.reply_text(
            "🎬 **Video Downloader**\n\n"
            "Usage:\n"
            "`/video <link>`\n"
            "`/video <artist title>`"
        )

    query = m.text.split(None, 1)[1].strip()
    msg = await m.reply_text(f"🎬 Downloading video...\n`{query}`")

    try:
        async with GLOBAL_SEM:
            result = await download_video(query)

        await msg.edit("📤 Uploading video...")

        file_path = Path(result["file"])
        safe_name = safe_filename(result["title"]) or file_path.stem

        try:
            await m.reply_video(
                video=str(file_path),
                supports_streaming=True,
                width=result.get("width"),
                height=result.get("height"),
                duration=result.get("duration", 0) or None,
            )
        except Exception as send_err:
            print(f"[VIDEO] Falling back to document upload: {send_err}")
            await m.reply_document(
                document=str(file_path),
                file_name=f"{safe_name}{file_path.suffix or '.mp4'}",
            )

        await msg.delete()
        try:
            await m.delete()
        except:
            pass

        shutil.rmtree(result["tmpdir"], ignore_errors=True)

    except asyncio.TimeoutError:
        await msg.edit("❌ Download timed out.")
    except Exception as e:
        await msg.edit(f"❌ Video failed:\n`{str(e)[:200]}`")


# ==================== CUSTOM FILTERS ====================

def sudo_filter(_, __, m: Message):
    """Check if the user is in SUDOERS or is the owner."""
    if not SUDOERS:
        return True
    return m.from_user and (m.from_user.id in SUDOERS or m.from_user.is_self)

# Create the filter
sudo_only = filters.create(sudo_filter, "SudoFilter")

# ==================== ADMIN COMMANDS ====================

@app.on_message(filters.command("cacheinfo") & sudo_only)
async def cache_info_handler(_, m: Message):
    """Show cache statistics."""
    try:
        audio_count = await get_music_cache_count()
        latest_songs = await get_recent_cached_songs(1)
        
        text = "📊 **Cache Statistics**\n\n"
        text += f"**🎵 Songs Cached:** {audio_count}\n"
        if latest_songs:
            text += f"**Last Added:** {latest_songs[0]['title']}\n"
        await m.reply_text(text)
    except Exception as e:
        error_msg = str(e)[:200]
        await m.reply_text(f"❌ Error: {error_msg}")
        print(f"[ERROR] /cacheinfo: {e}")

@app.on_message(filters.command("cachelist") & sudo_only)
async def cache_list_handler(_, m: Message):
    """List recent cached songs with access stats."""
    if not is_sudo(m.from_user.id):
        return await m.reply_text("❌ Sudo only")
    
    try:
        # Get top 15 by last access
        songs = await get_recent_cached_songs(15)
        text = "📋 **Recent Cached Songs**\n"
        text += "_Sorted by last access_\n\n"
        
        i = 1
        for song in songs:
            access_count = song.get("access_count", 0)
            last_access = song.get("last_accessed", song.get("created_at"))
            time_ago = datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(last_access)
            
            # Format time ago
            if time_ago.days > 0:
                time_str = f"{time_ago.days}d ago"
            elif time_ago.seconds > 3600:
                time_str = f"{time_ago.seconds // 3600}h ago"
            else:
                time_str = f"{time_ago.seconds // 60}m ago"
            
            text += f"{i}. **{song['title']}** - {song.get('performer', 'Unknown')}\n"
            text += f"   📊 {access_count} plays • 🕐 {time_str}\n"
            text += f"   `{song['query']}`\n\n"
            i += 1
        
        if i == 1:
            text = "📭 No cached songs yet"
        
        await m.reply_text(text)
    except Exception as e:
        await m.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("purge") & sudo_only)
async def purge_handler(_, m: Message):
    """Delete cached songs."""
    if not is_sudo(m.from_user.id):
        return await m.reply_text("❌ Sudo only")
    
    if len(m.command) < 2:
        return await m.reply_text("📝 Usage: `/purge <query>`")
    
    try:
        query = m.text.split(None, 1)[1].strip().lower()
        deleted_count = await purge_music_cache(query)
        await m.reply_text(f"🗑️ Deleted {deleted_count} entries matching `{query}`")
    except Exception as e:
        await m.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("teststorage"))
async def test_storage_handler(_, m: Message):
    """Test storage configuration."""
    if SUDOERS and m.from_user.id not in SUDOERS:
        return await m.reply_text("❌ Sudo only")
    
    msg = await m.reply_text("🔍 Testing storage...")
    
    try:
        # Show config
        storage_info = []
        if MUSIC_GROUP_ID:
            storage_info.append(f"Group: `{MUSIC_GROUP_ID}`")
        if MUSIC_CHANNEL_ID:
            storage_info.append(f"Channel: `{MUSIC_CHANNEL_ID}`")
        
        if not storage_info:
            return await msg.edit("❌ No storage configured\n\nSet `MUSIC_GROUP_ID` or `MUSIC_CHANNEL_ID`")
        
        await msg.edit(f"📡 Testing storage...\n\n{chr(10).join(storage_info)}")
        
        # Create test file
        test_file = TEMP_DIR / "test_audio.ogg"
        test_thumb = TEMP_DIR / "test_thumb.jpg"
        
        # Create 1-second silent audio
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
            "-acodec", "libopus", "-b:a", "64k", str(test_file),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        if not test_file.exists():
            return await msg.edit("❌ Failed to create test file\n\nEnsure ffmpeg is installed")
        
        # Create test thumbnail
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:100x100",
            "-frames:v", "1", str(test_thumb),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        # Try upload
        sent = await upload_to_storage(
            str(test_file), "🎵 Test Audio", "Test Bot", 1, 
            str(test_thumb) if test_thumb.exists() else None
        )
        
        await msg.edit(
            f"✅ **Storage Test Successful!**\n\n"
            f"• File ID: `{sent.audio.file_id}`\n"
            f"• Storage: `{sent.chat.id}`\n"
            f"• Message ID: `{sent.id}`"
        )
        
        # Cleanup
        test_file.unlink(missing_ok=True)
        test_thumb.unlink(missing_ok=True)
        
    except Exception as e:
        await msg.edit(f"❌ **Test Failed**\n\n```{str(e)[:300]}```\n\nEnsure bot is admin with send permissions")

# ==================== INLINE QUERIES ====================

@app.on_inline_query()
async def inline_query_handler(_, q: InlineQuery):
    """Handle inline queries for cached songs."""
    query = q.query.strip()
    if not query:
        return await q.answer([], cache_time=1)
    
    try:
        matches = cache_col.find(
            {"query": {"$regex": query, "$options": "i"}}
        ).sort("created_at", -1).limit(5)
        
        results = []
        i = 0
        async for doc in matches:
            results.append(
                InlineQueryResultAudio(
                    id=str(i),
                    audio_file_id=doc["file_id"],
                    title=doc["title"],
                    performer=doc.get("performer", "Unknown")
                )
            )
            i += 1
        
        await q.answer(results, cache_time=10)
    except Exception as e:
        print(f"[ERROR] Inline query: {e}")
        await q.answer([], cache_time=1)

# ==================== CLEANUP HANDLERS ====================

async def cleanup():
    """Cleanup resources on shutdown."""
    try:
        # Close MongoDB connections
        if 'client' in globals():
            client = globals()['client']
            if client:
                client.close()
        
        # Close any other resources if needed
        if 'arq' in globals() and arq is not None:
            if hasattr(arq, 'close'):
                await arq.close()
            elif hasattr(arq, 'session') and hasattr(arq.session, 'close'):
                await arq.session.close()
            
        print("✅ Cleanup completed successfully")
    except Exception as e:
        print(f"⚠️ Error during cleanup: {e}")

# Register cleanup handler
import atexit
import asyncio

def register_cleanup():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(cleanup())

atexit.register(register_cleanup)

# ==================== EXPORTS ====================

__all__ = [
    "download_audio",
    "upload_to_storage",
    "get_cached_song",
    "save_cached_song",
    "delete_cached_song",
    "cleanup"
]

print("✅ Music module loaded successfully (video and social media features removed)")
