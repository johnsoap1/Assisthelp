"""
SQLite Database Functions
Provides async database operations for William Butcher Bot using SQLite.
"""
import json
import sqlite3
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps

DB_PATH = Path("wbb.sqlite")

def get_db():
    """Get SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def async_db(func):
    """Decorator to run synchronous DB operations in executor."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper

def init_tables():
    """Initialize all required tables."""
    conn = get_db()
    
    # Blocklist table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocklist (
            chat_id INTEGER PRIMARY KEY,
            triggers TEXT,
            mode TEXT DEFAULT 'warn'
        )
    """)
    
    # Warnings table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            chat_id INTEGER,
            user_id TEXT,
            warns INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    
    # Filters table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS filters (
            chat_id INTEGER,
            keyword TEXT,
            filter_type TEXT,
            filter_data TEXT,
            PRIMARY KEY (chat_id, keyword)
        )
    """)
    
    # Rules table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            chat_id INTEGER PRIMARY KEY,
            rules TEXT
        )
    """)
    
    # Admin log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_log (
            chat_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        )
    """)
    
    # Restart stage table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS restart_stage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            message_id INTEGER
        )
    """)
    
    # Users table (for user management)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_bot INTEGER DEFAULT 0,
            joined_date INTEGER
        )
    """)
    
    # Chat members table (for tracking joins/leaves)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_members (
            chat_id INTEGER,
            user_id INTEGER,
            joined_date INTEGER,
            left_date INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize tables on import
init_tables()

# ==================== WARN FUNCTIONS ====================

@async_db
def add_warn(chat_id: int, user_id: str, warn_data: dict):
    """Add or update warning count."""
    conn = get_db()
    warns = warn_data.get("warns", 0)
    
    conn.execute("""
        INSERT INTO warnings (chat_id, user_id, warns)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id, user_id) 
        DO UPDATE SET warns = ?
    """, (chat_id, user_id, warns, warns))
    
    conn.commit()
    conn.close()

@async_db
def get_warn(chat_id: int, user_id: str) -> Optional[Dict[str, int]]:
    """Get warning count for user."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT warns FROM warnings WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"warns": row["warns"]}
    return None

@async_db
def remove_warns(chat_id: int, user_id: str):
    """Remove all warnings for user."""
    conn = get_db()
    conn.execute(
        "DELETE FROM warnings WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    )
    conn.commit()
    conn.close()

async def int_to_alpha(user_id: int) -> str:
    """Convert user ID to string (for compatibility)."""
    return str(user_id)

# ==================== FILTER FUNCTIONS ====================

@async_db
def save_filter(chat_id: int, keyword: str, filter_data: dict):
    """Save a filter."""
    conn = get_db()
    conn.execute("""
        INSERT INTO filters (chat_id, keyword, filter_type, filter_data)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id, keyword)
        DO UPDATE SET filter_type = ?, filter_data = ?
    """, (
        chat_id, keyword,
        filter_data.get("type"),
        json.dumps(filter_data),
        filter_data.get("type"),
        json.dumps(filter_data)
    ))
    conn.commit()
    conn.close()

@async_db
def get_filter(chat_id: int, keyword: str) -> Optional[dict]:
    """Get a specific filter."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT filter_type, filter_data FROM filters WHERE chat_id = ? AND keyword = ?",
        (chat_id, keyword)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row["filter_data"])
    return None

@async_db
def get_all_filters(chat_id: int) -> list:
    """Get all filters for a chat."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT keyword, filter_type, filter_data FROM filters WHERE chat_id = ?",
        (chat_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "keyword": row["keyword"],
            "type": row["filter_type"],
            "data": json.loads(row["filter_data"])
        }
        for row in rows
    ]

@async_db
def delete_filter(chat_id: int, keyword: str):
    """Delete a filter."""
    conn = get_db()
    conn.execute(
        "DELETE FROM filters WHERE chat_id = ? AND keyword = ?",
        (chat_id, keyword)
    )
    conn.commit()
    conn.close()

# ==================== RULES FUNCTIONS ====================

@async_db
def get_rules(chat_id: int) -> Optional[str]:
    """Get rules for chat."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT rules FROM rules WHERE chat_id = ?",
        (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row["rules"]
    return None

@async_db
def set_rules(chat_id: int, rules: str):
    """Set rules for chat."""
    conn = get_db()
    conn.execute("""
        INSERT INTO rules (chat_id, rules)
        VALUES (?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET rules = ?
    """, (chat_id, rules, rules))
    conn.commit()
    conn.close()

# ==================== ADMIN LOG FUNCTIONS ====================

@async_db
def toggle_admin_log(chat_id: int, enabled: bool):
    """Toggle admin logging."""
    conn = get_db()
    conn.execute("""
        INSERT INTO admin_log (chat_id, enabled)
        VALUES (?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET enabled = ?
    """, (chat_id, 1 if enabled else 0, 1 if enabled else 0))
    conn.commit()
    conn.close()

@async_db
def is_admin_log_enabled(chat_id: int) -> bool:
    """Check if admin logging is enabled."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT enabled FROM admin_log WHERE chat_id = ?",
        (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return bool(row["enabled"])
    return False

# ==================== RESTART STAGE FUNCTIONS ====================

@async_db
def clean_restart_stage() -> Optional[dict]:
    """Get and clear restart stage data."""
    conn = get_db()
    cursor = conn.execute("SELECT chat_id, message_id FROM restart_stage ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        data = {"chat_id": row["chat_id"], "message_id": row["message_id"]}
        conn.execute("DELETE FROM restart_stage")
        conn.commit()
        conn.close()
        return data
    
    conn.close()
    return None

@async_db
def set_restart_stage(chat_id: int, message_id: int):
    """Set restart stage data."""
    conn = get_db()
    conn.execute("DELETE FROM restart_stage")  # Clear old data
    conn.execute(
        "INSERT INTO restart_stage (chat_id, message_id) VALUES (?, ?)",
        (chat_id, message_id)
    )
    conn.commit()
    conn.close()

# ==================== USER MANAGEMENT FUNCTIONS ====================

@async_db
def save_user(user_id: int, username: str = None, first_name: str = None, 
              last_name: str = None, is_bot: bool = False):
    """Save or update user information."""
    conn = get_db()
    import time
    
    conn.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, is_bot, joined_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET username = ?, first_name = ?, last_name = ?
    """, (
        user_id, username, first_name, last_name, 1 if is_bot else 0, int(time.time()),
        username, first_name, last_name
    ))
    conn.commit()
    conn.close()

@async_db
def get_user(user_id: int) -> Optional[dict]:
    """Get user information."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


# ==================== AntiService Functions ====================

async def is_antiservice_on(chat_id: int) -> bool:
    """Check if antiservice is enabled for a chat."""
    data = await antiservicedb.find_one({"chat_id": chat_id})
    return bool(data and data.get("enabled", False))


async def antiservice_on(chat_id: int):
    """Enable antiservice for a chat."""
    await antiservicedb.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": True}},
        upsert=True
    )


async def antiservice_off(chat_id: int):
    """Disable antiservice for a chat."""
    await antiservicedb.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": False}},
        upsert=True
    )


async def get_antiservice_settings(chat_id: int) -> dict:
    """Get antiservice settings for a chat."""
    data = await antiservicedb.find_one({"chat_id": chat_id})
    if not data:
        return {
            "enabled": False,
            "delete_service": True,
            "delete_commands": False,
            "delete_new_members": True,
            "delete_left_members": True,
            "delete_channel_add": True,
            "delete_channel_remove": True,
            "delete_admin_changes": False,
            "delete_pinned_messages": False,
            "delete_game_messages": True,
            "delete_invite_links": True,
            "delete_video_chat": True,
            "whitelist_admins": True,
            "allowed_commands": []
        }
    return data.get("settings", {
        "enabled": data.get("enabled", False),
        "delete_service": True,
        "delete_commands": False,
        "delete_new_members": True,
        "delete_left_members": True,
        "delete_channel_add": True,
        "delete_channel_remove": True,
        "delete_admin_changes": False,
        "delete_pinned_messages": False,
        "delete_game_messages": True,
        "delete_invite_links": True,
        "delete_video_chat": True,
        "whitelist_admins": True,
        "allowed_commands": []
    })


async def update_antiservice_settings(chat_id: int, settings: dict):
    """Update antiservice settings for a chat."""
    await antiservicedb.update_one(
        {"chat_id": chat_id},
        {"$set": {"settings": settings, "enabled": settings.get("enabled", False)}},
        upsert=True
    )


# Autoapprove functions
async def get_autoapprove(chat_id: int) -> dict:
    """Get autoapprove settings for a chat."""
    return await async_db(
        "SELECT mode, settings, stats, pending_users FROM autoapprove WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )


async def set_autoapprove(chat_id: int, mode: str, settings: dict = None):
    """Set autoapprove mode and settings for a chat."""
    if settings is None:
        settings = {}
    
    # Convert settings to JSON
    settings_json = json.dumps(settings)
    
    await async_db(
        """INSERT OR REPLACE INTO autoapprove (chat_id, mode, settings, stats, pending_users) 
           VALUES (?, ?, ?, ?, ?)""",
        (chat_id, mode, settings_json, json.dumps({}), json.dumps([]))
    )


async def update_autoapprove(chat_id: int, mode: str = None, settings: dict = None, 
                           stats: dict = None, pending_users: list = None):
    """Update autoapprove data for a chat."""
    updates = []
    params = []
    
    if mode is not None:
        updates.append("mode = ?")
        params.append(mode)
    
    if settings is not None:
        updates.append("settings = ?")
        params.append(json.dumps(settings))
    
    if stats is not None:
        updates.append("stats = ?")
        params.append(json.dumps(stats))
    
    if pending_users is not None:
        updates.append("pending_users = ?")
        params.append(json.dumps(pending_users))
    
    if not updates:
        return
    
    query = f"UPDATE autoapprove SET {', '.join(updates)} WHERE chat_id = ?"
    params.append(chat_id)
    
    await async_db(query, tuple(params))


async def delete_autoapprove(chat_id: int):
    """Delete autoapprove settings for a chat."""
    await async_db("DELETE FROM autoapprove WHERE chat_id = ?", (chat_id,))


async def is_autoapprove_pending(chat_id: int, user_id: int) -> bool:
    """Check if a user is pending approval in a chat."""
    result = await async_db(
        "SELECT pending_users FROM autoapprove WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result and result[0]:
        pending = json.loads(result[0])
        return user_id in pending
    
    return False


async def add_pending_user(chat_id: int, user_id: int):
    """Add a user to pending approval list."""
    result = await async_db(
        "SELECT pending_users FROM autoapprove WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result and result[0]:
        pending = json.loads(result[0])
    else:
        pending = []
    
    if user_id not in pending:
        pending.append(user_id)
    
    await async_db(
        "UPDATE autoapprove SET pending_users = ? WHERE chat_id = ?",
        (json.dumps(pending), chat_id)
    )


async def remove_pending_user(chat_id: int, user_id: int):
    """Remove a user from pending approval list."""
    result = await async_db(
        "SELECT pending_users FROM autoapprove WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result and result[0]:
        pending = json.loads(result[0])
        if user_id in pending:
            pending.remove(user_id)
        
        await async_db(
            "UPDATE autoapprove SET pending_users = ? WHERE chat_id = ?",
            (json.dumps(pending), chat_id)
        )


async def clear_pending_users(chat_id: int):
    """Clear all pending users for a chat."""
    await async_db(
        "UPDATE autoapprove SET pending_users = ? WHERE chat_id = ?",
        (json.dumps([]), chat_id)
    )


async def get_pending_users(chat_id: int) -> list:
    """Get list of pending users for a chat."""
    result = await async_db(
        "SELECT pending_users FROM autoapprove WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result and result[0]:
        return json.loads(result[0])
    
    return []


async def increment_approval_stat(chat_id: int, stat_type: str):
    """Increment a stat counter for autoapprove."""
    result = await async_db(
        "SELECT stats FROM autoapprove WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result and result[0]:
        stats = json.loads(result[0])
    else:
        stats = {}
    
    stats[stat_type] = stats.get(stat_type, 0) + 1
    
    await async_db(
        "UPDATE autoapprove SET stats = ? WHERE chat_id = ?",
        (json.dumps(stats), chat_id)
    )


# Media deduplication functions
async def is_dedupe_enabled(chat_id: int) -> bool:
    """Check if deduplication is enabled for chat."""
    result = await async_db(
        "SELECT enabled FROM dedupe_settings WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    return bool(result and result[0])


async def set_dedupe_enabled(chat_id: int, enabled: bool):
    """Enable or disable deduplication for chat."""
    await async_db(
        """INSERT OR REPLACE INTO dedupe_settings (chat_id, enabled, updated_at) 
           VALUES (?, ?, ?)""",
        (chat_id, enabled, int(time.time()))
    )


async def check_duplicate_media(chat_id: int, file_hash: str) -> dict:
    """Check if media hash exists in chat."""
    result = await async_db(
        "SELECT user_id, message_id, timestamp FROM media_hashes WHERE chat_id = ? AND file_hash = ?",
        (chat_id, file_hash),
        fetchone=True
    )
    
    if result:
        return {
            "chat_id": chat_id,
            "file_hash": file_hash,
            "user_id": result[0],
            "message_id": result[1],
            "timestamp": result[2]
        }
    return None


async def save_media_hash(chat_id: int, file_hash: str, user_id: int, message_id: int):
    """Save media hash to prevent duplicates."""
    await async_db(
        """INSERT OR REPLACE INTO media_hashes (chat_id, file_hash, user_id, message_id, timestamp) 
           VALUES (?, ?, ?, ?, ?)""",
        (chat_id, file_hash, user_id, message_id, int(time.time()))
    )


async def increment_user_media(chat_id: int, user_id: int, media_type: str):
    """Increment user's media count."""
    # First try to update existing record
    if media_type == "photo":
        result = await async_db(
            "UPDATE user_media_stats SET photos = photos + 1, total = total + 1, last_media = ? WHERE chat_id = ? AND user_id = ?",
            (int(time.time()), chat_id, user_id)
        )
    elif media_type == "video":
        result = await async_db(
            "UPDATE user_media_stats SET videos = videos + 1, total = total + 1, last_media = ? WHERE chat_id = ? AND user_id = ?",
            (int(time.time()), chat_id, user_id)
        )
    
    # If no rows were updated, insert new record
    if result == 0:
        if media_type == "photo":
            await async_db(
                """INSERT INTO user_media_stats (chat_id, user_id, photos, videos, total, last_media) 
                   VALUES (?, ?, 1, 0, 1, ?)""",
                (chat_id, user_id, int(time.time()))
            )
        elif media_type == "video":
            await async_db(
                """INSERT INTO user_media_stats (chat_id, user_id, photos, videos, total, last_media) 
                   VALUES (?, ?, 0, 1, 1, ?)""",
                (chat_id, user_id, int(time.time()))
            )


async def get_user_media_stats(chat_id: int, user_id: int) -> dict:
    """Get user's media statistics."""
    result = await async_db(
        "SELECT photos, videos, total, last_media FROM user_media_stats WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
        fetchone=True
    )
    
    if result:
        return {
            "photos": result[0] or 0,
            "videos": result[1] or 0,
            "total": result[2] or 0,
            "last_media": result[3] or 0
        }
    
    return {"photos": 0, "videos": 0, "total": 0, "last_media": 0}


async def get_media_leaderboard(chat_id: int, limit: int = 10) -> list:
    """Get top media contributors."""
    results = await async_db(
        "SELECT user_id, photos, videos, total FROM user_media_stats WHERE chat_id = ? AND total > 0 ORDER BY total DESC LIMIT ?",
        (chat_id, limit),
        fetchall=True
    )
    
    return [
        {
            "user_id": row[0],
            "photos": row[1] or 0,
            "videos": row[2] or 0,
            "total": row[3] or 0
        }
        for row in results
    ]


async def get_inactive_media_users(chat_id: int, inactive_seconds: int) -> list:
    """Get list of user IDs inactive for specified time."""
    cutoff_time = int(time.time()) - inactive_seconds
    
    results = await async_db(
        "SELECT user_id FROM user_media_stats WHERE chat_id = ? AND (last_media < ? OR last_media IS NULL)",
        (chat_id, cutoff_time),
        fetchall=True
    )
    
    return [row[0] for row in results]


async def get_low_media_users(chat_id: int, threshold: int) -> list:
    """Get users with media count below threshold."""
    results = await async_db(
        "SELECT user_id FROM user_media_stats WHERE chat_id = ? AND total < ?",
        (chat_id, threshold),
        fetchall=True
    )
    
    return [row[0] for row in results]


async def get_chat_media_stats(chat_id: int) -> dict:
    """Get overall chat media statistics."""
    result = await async_db(
        "SELECT SUM(photos), SUM(videos), SUM(total), COUNT(*) FROM user_media_stats WHERE chat_id = ? AND total > 0",
        (chat_id,),
        fetchone=True
    )
    
    if result:
        return {
            "total_photos": result[0] or 0,
            "total_videos": result[1] or 0,
            "total_media": result[2] or 0,
            "active_users": result[3] or 0
        }
    
    return {
        "total_photos": 0,
        "total_videos": 0,
        "total_media": 0,
        "active_users": 0
    }


# Region blocking functions
async def add_blocked_country(chat_id: int, countries: list):
    """Add blocked countries to chat."""
    countries_json = json.dumps([c.lower().strip() for c in countries])
    
    # Get existing blocked countries
    result = await async_db(
        "SELECT blocked_countries FROM region_blocker WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    existing = []
    if result and result[0]:
        existing = json.loads(result[0])
    
    # Add new countries without duplicates
    for country in countries:
        country = country.lower().strip()
        if country not in existing:
            existing.append(country)
    
    await async_db(
        "INSERT OR REPLACE INTO region_blocker (chat_id, blocked_countries, blocked_languages) VALUES (?, ?, ?)",
        (chat_id, json.dumps(existing), json.dumps([]))
    )


async def add_blocked_lang(chat_id: int, languages: list):
    """Add blocked language scripts to chat."""
    languages_json = json.dumps([l.lower().strip() for l in languages])
    
    # Get existing blocked languages
    result = await async_db(
        "SELECT blocked_languages FROM region_blocker WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    existing = []
    if result and result[0]:
        existing = json.loads(result[0])
    
    # Add new languages without duplicates
    for lang in languages:
        lang = lang.lower().strip()
        if lang not in existing:
            existing.append(lang)
    
    await async_db(
        "INSERT OR REPLACE INTO region_blocker (chat_id, blocked_countries, blocked_languages) VALUES (?, ?, ?)",
        (chat_id, json.dumps([]), json.dumps(existing))
    )


async def remove_blocked_country(chat_id: int, countries: list):
    """Remove blocked countries from chat."""
    countries_lower = [c.lower().strip() for c in countries]
    
    # Get existing blocked countries
    result = await async_db(
        "SELECT blocked_countries FROM region_blocker WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result and result[0]:
        existing = json.loads(result[0])
        # Remove specified countries
        existing = [c for c in existing if c not in countries_lower]
        
        await async_db(
            "UPDATE region_blocker SET blocked_countries = ? WHERE chat_id = ?",
            (json.dumps(existing), chat_id)
        )


async def remove_blocked_lang(chat_id: int, languages: list):
    """Remove blocked languages from chat."""
    languages_lower = [l.lower().strip() for l in languages]
    
    # Get existing blocked languages
    result = await async_db(
        "SELECT blocked_languages FROM region_blocker WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result and result[0]:
        existing = json.loads(result[0])
        # Remove specified languages
        existing = [l for l in existing if l not in languages_lower]
        
        await async_db(
            "UPDATE region_blocker SET blocked_languages = ? WHERE chat_id = ?",
            (json.dumps(existing), chat_id)
        )


async def get_chat_blocks(chat_id: int) -> dict:
    """Get blocked countries and languages for chat."""
    result = await async_db(
        "SELECT blocked_countries, blocked_languages FROM region_blocker WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result:
        return {
            "countries": json.loads(result[0]) if result[0] else [],
            "languages": json.loads(result[1]) if result[1] else []
        }
    
    return {"countries": [], "languages": []}


async def clear_chat_blocks(chat_id: int):
    """Clear all blocks for chat."""
    await async_db("DELETE FROM region_blocker WHERE chat_id = ?", (chat_id,))


# Translation history functions
async def save_translation_history(user_id: int, source_text: str, translated_text: str, 
                                 source_lang: str, target_lang: str, service: str):
    """Save translation history."""
    await async_db(
        """INSERT INTO translate_history 
           (user_id, source_text, translated_text, source_lang, target_lang, service, timestamp) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, source_text[:500], translated_text[:500], source_lang, target_lang, service, int(time.time()))
    )


# Rules functions
async def get_rules(chat_id: int):
    """Get rules for a chat."""
    result = await async_db(
        "SELECT rules FROM rules WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    return result[0] if result else None


async def set_chat_rules(chat_id: int, rules: str):
    """Set rules for a chat."""
    await async_db(
        "INSERT OR REPLACE INTO rules (chat_id, rules) VALUES (?, ?)",
        (chat_id, rules)
    )


async def delete_rules(chat_id: int):
    """Delete rules for a chat."""
    result = await async_db("DELETE FROM rules WHERE chat_id = ?", (chat_id,))
    return result > 0


# Antiflood functions
async def save_translation_history(user_id: int, source_text: str, translated_text: str, 
                                 source_lang: str, target_lang: str, service: str):
    """Save translation history."""
    await async_db(
        """INSERT INTO translate_history 
           (user_id, source_text, translated_text, source_lang, target_lang, service, timestamp) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, source_text[:500], translated_text[:500], source_lang, target_lang, service, int(time.time()))
    )


# Antiflood functions
async def get_flood_settings(chat_id: int):
    """Get antiflood settings for chat."""
    result = await async_db(
        "SELECT limit_count, limit_time, action FROM antiflood WHERE chat_id = ?",
        (chat_id,),
        fetchone=True
    )
    
    if result:
        return {
            "limit": result[0],
            "time": result[1], 
            "action": result[2]
        }
    return None


async def set_flood_settings(chat_id: int, limit: int, time_val: int, action: str):
    """Set antiflood settings."""
    await async_db(
        """INSERT OR REPLACE INTO antiflood (chat_id, limit_count, limit_time, action) 
           VALUES (?, ?, ?, ?)""",
        (chat_id, limit, time_val, action)
    )


async def delete_flood_settings(chat_id: int):
    """Delete antiflood settings."""
    await async_db("DELETE FROM antiflood WHERE chat_id = ?", (chat_id,))


# Trigger functions
async def save_translation_history(user_id: int, source_text: str, translated_text: str, 
                                 source_lang: str, target_lang: str, service: str):
    """Save translation history."""
    await async_db(
        """INSERT INTO translate_history 
           (user_id, source_text, translated_text, source_lang, target_lang, service, timestamp) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, source_text[:500], translated_text[:500], source_lang, target_lang, service, int(time.time()))
    )


# Trigger functions
async def add_trigger_db(chat_id: int, trigger: str, response: str,
                        is_global: bool = False, is_media: bool = False,
                        file_id: str = None, file_type: str = None, use_regex: bool = False):
    """Create or append a trigger response."""
    actual_chat_id = 0 if is_global else chat_id
    trigger_lower = trigger.lower()
    
    # Check if trigger exists
    result = await async_db(
        "SELECT responses FROM triggers WHERE chat_id = ? AND trigger = ?",
        (actual_chat_id, trigger_lower),
        fetchone=True
    )
    
    response_entry = {
        "text": response,
        "is_media": is_media,
        "file_id": file_id,
        "file_type": file_type,
        "added_at": int(time.time())
    }
    response_json = json.dumps(response_entry)
    
    if result and result[0]:
        # Append to existing responses
        existing_responses = json.loads(result[0])
        existing_responses.append(response_entry)
        await async_db(
            "UPDATE triggers SET responses = ? WHERE chat_id = ? AND trigger = ?",
            (json.dumps(existing_responses), actual_chat_id, trigger_lower)
        )
    else:
        # Create new trigger
        await async_db(
            """INSERT INTO triggers 
               (chat_id, trigger, use_regex, created_at, usage_count, responses) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (actual_chat_id, trigger_lower, use_regex, int(time.time()), 0, json.dumps([response_entry]))
        )


async def remove_trigger_db(chat_id: int, trigger: str, is_global: bool = False) -> bool:
    """Remove a trigger."""
    actual_chat_id = 0 if is_global else chat_id
    trigger_lower = trigger.lower()
    
    result = await async_db(
        "DELETE FROM triggers WHERE chat_id = ? AND trigger = ?",
        (actual_chat_id, trigger_lower)
    )
    
    return result > 0


async def get_chat_triggers_db(chat_id: int, include_global: bool = True) -> list:
    """Get triggers for a chat."""
    if include_global:
        results = await async_db(
            "SELECT chat_id, trigger, use_regex, created_at, usage_count, responses FROM triggers WHERE chat_id = ? OR chat_id = 0",
            (chat_id,),
            fetchall=True
        )
    else:
        results = await async_db(
            "SELECT chat_id, trigger, use_regex, created_at, usage_count, responses FROM triggers WHERE chat_id = ?",
            (chat_id,),
            fetchall=True
        )
    
    triggers = []
    for row in results:
        triggers.append({
            "chat_id": row[0],
            "trigger": row[1],
            "use_regex": bool(row[2]),
            "created_at": row[3],
            "usage_count": row[4],
            "responses": json.loads(row[5]) if row[5] else []
        })
    
    return triggers


async def record_trigger_usage_db(chat_id: int, trigger: str):
    """Record trigger usage for statistics."""
    trigger_lower = trigger.lower()
    
    # Update trigger usage count
    await async_db(
        "UPDATE triggers SET usage_count = usage_count + 1 WHERE chat_id = ? AND trigger = ?",
        (chat_id, trigger_lower)
    )
    
    # Update or insert stats
    result = await async_db(
        "SELECT count FROM trigger_stats WHERE chat_id = ? AND trigger = ?",
        (chat_id, trigger_lower),
        fetchone=True
    )
    
    if result:
        await async_db(
            "UPDATE trigger_stats SET count = count + 1, last_used = ? WHERE chat_id = ? AND trigger = ?",
            (int(time.time()), chat_id, trigger_lower)
        )
    else:
        await async_db(
            "INSERT INTO trigger_stats (chat_id, trigger, count, last_used) VALUES (?, ?, ?, ?)",
            (chat_id, trigger_lower, 1, int(time.time()))
        )
