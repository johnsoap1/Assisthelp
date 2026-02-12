"""
SQLite Federation Database Functions
Replaces MongoDB federation operations with SQLite equivalents.
"""
import asyncio
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

# Database path
DB_PATH = Path("wbb.sqlite")

# ==================== DATABASE SETUP ====================

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


def init_federation_tables():
    """Initialize federation-related tables."""
    conn = get_db()

    # Main federation table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS federations (
            fed_id TEXT PRIMARY KEY,
            fed_name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            owner_mention TEXT,
            log_group_id INTEGER,
            created_date INTEGER
        )
    """)

    # Federation admins table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fed_admins (
            fed_id TEXT,
            user_id INTEGER,
            promoted_date INTEGER,
            PRIMARY KEY (fed_id, user_id),
            FOREIGN KEY (fed_id) REFERENCES federations(fed_id) ON DELETE CASCADE
        )
    """)

    # Federation banned users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fed_bans (
            fed_id TEXT,
            user_id INTEGER,
            reason TEXT,
            date TEXT,
            banned_by INTEGER,
            PRIMARY KEY (fed_id, user_id),
            FOREIGN KEY (fed_id) REFERENCES federations(fed_id) ON DELETE CASCADE
        )
    """)

    # Federation chats table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fed_chats (
            fed_id TEXT,
            chat_id INTEGER,
            chat_title TEXT,
            joined_date INTEGER,
            PRIMARY KEY (fed_id, chat_id),
            FOREIGN KEY (fed_id) REFERENCES federations(fed_id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()

# Initialize tables
init_federation_tables()

# ==================== FEDERATION CRUD OPERATIONS ====================

@async_db
def create_federation(fed_id: str, fed_name: str, owner_id: int,
                     owner_mention: str, log_group_id: int) -> bool:
    """Create a new federation."""
    try:
        conn = get_db()
        import time
        conn.execute("""
            INSERT INTO federations (fed_id, fed_name, owner_id, owner_mention, log_group_id, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fed_id, fed_name, owner_id, owner_mention, log_group_id, int(time.time())))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating federation: {e}")
        return False


@async_db
def get_fed_info(fed_id: str) -> Optional[Dict[str, Any]]:
    """Get federation information."""
    conn = get_db()

    # Get main fed info
    cursor = conn.execute(
        "SELECT * FROM federations WHERE fed_id = ?",
        (fed_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    # Get admins
    cursor = conn.execute(
        "SELECT user_id FROM fed_admins WHERE fed_id = ?",
        (fed_id,)
    )
    admins = [r["user_id"] for r in cursor.fetchall()]

    # Get banned users
    cursor = conn.execute(
        "SELECT user_id, reason, date FROM fed_bans WHERE fed_id = ?",
        (fed_id,)
    )
    banned_users = [
        {"user_id": r["user_id"], "reason": r["reason"], "date": r["date"]}
        for r in cursor.fetchall()
    ]

    # Get chats
    cursor = conn.execute(
        "SELECT chat_id FROM fed_chats WHERE fed_id = ?",
        (fed_id,)
    )
    chat_ids = [r["chat_id"] for r in cursor.fetchall()]

    conn.close()

    return {
        "fed_id": row["fed_id"],
        "fed_name": row["fed_name"],
        "owner_id": row["owner_id"],
        "owner_mention": row["owner_mention"],
        "fadmins": admins,
        "banned_users": banned_users,
        "chat_ids": chat_ids,
        "log_group_id": row["log_group_id"]
    }


@async_db
def search_fed_by_id(fed_id: str) -> Optional[Dict[str, Any]]:
    """Search for federation by ID."""
    return get_fed_info(fed_id)


@async_db
def delete_federation(fed_id: str) -> bool:
    """Delete a federation and all related data."""
    try:
        conn = get_db()
        # CASCADE will automatically delete related records
        conn.execute("DELETE FROM federations WHERE fed_id = ?", (fed_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting federation: {e}")
        return False


@async_db
def rename_federation(fed_id: str, new_name: str) -> bool:
    """Rename a federation."""
    try:
        conn = get_db()
        conn.execute(
            "UPDATE federations SET fed_name = ? WHERE fed_id = ?",
            (new_name, fed_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error renaming federation: {e}")
        return False

# ==================== FEDERATION OWNER OPERATIONS ====================

@async_db
def get_feds_by_owner(owner_id: int) -> List[Dict[str, str]]:
    """Get all federations owned by a user."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT fed_id, fed_name FROM federations WHERE owner_id = ?",
        (owner_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [{"fed_id": r["fed_id"], "fed_name": r["fed_name"]} for r in rows]


@async_db
def is_user_fed_owner(fed_id: str, user_id: int) -> bool:
    """Check if user is federation owner."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT owner_id FROM federations WHERE fed_id = ?",
        (fed_id,)
    )
    row = cursor.fetchone()
    conn.close()

    return row and row["owner_id"] == user_id


@async_db
def transfer_owner(fed_id: str, old_owner_id: int, new_owner_id: int) -> bool:
    """Transfer federation ownership."""
    try:
        conn = get_db()
        cursor = conn.execute(
            "SELECT owner_id FROM federations WHERE fed_id = ?",
            (fed_id,)
        )
        row = cursor.fetchone()

        if not row or row["owner_id"] != old_owner_id:
            conn.close()
            return False

        conn.execute(
            "UPDATE federations SET owner_id = ? WHERE fed_id = ?",
            (new_owner_id, fed_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error transferring ownership: {e}")
        return False

# ==================== FEDERATION ADMIN OPERATIONS ====================

@async_db
def user_join_fed(fed_id: str, user_id: int) -> bool:
    """Add a user as federation admin."""
    try:
        import time
        conn = get_db()
        conn.execute("""
            INSERT INTO fed_admins (fed_id, user_id, promoted_date)
            VALUES (?, ?, ?)
            ON CONFLICT(fed_id, user_id) DO NOTHING
        """, (fed_id, user_id, int(time.time())))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding fed admin: {e}")
        return False


@async_db
def user_demote_fed(fed_id: str, user_id: int) -> bool:
    """Remove a user from federation admins."""
    try:
        conn = get_db()
        conn.execute(
            "DELETE FROM fed_admins WHERE fed_id = ? AND user_id = ?",
            (fed_id, user_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error demoting fed admin: {e}")
        return False


@async_db
def search_user_in_fed(fed_id: str, user_id: int) -> bool:
    """Check if user is a federation admin."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT user_id FROM fed_admins WHERE fed_id = ? AND user_id = ?",
        (fed_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None

# ==================== FEDERATION CHAT OPERATIONS ====================

@async_db
def chat_join_fed(fed_id: str, chat_title: str, chat_id: int) -> bool:
    """Add a chat to federation."""
    try:
        import time
        conn = get_db()
        conn.execute("""
            INSERT INTO fed_chats (fed_id, chat_id, chat_title, joined_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(fed_id, chat_id) DO UPDATE SET chat_title = ?
        """, (fed_id, chat_id, chat_title, int(time.time()), chat_title))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding chat to fed: {e}")
        return False


@async_db
def chat_leave_fed(chat_id: int) -> bool:
    """Remove a chat from all federations."""
    try:
        conn = get_db()
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM fed_chats WHERE chat_id = ?",
            (chat_id,)
        )
        row = cursor.fetchone()

        if row["count"] == 0:
            conn.close()
            return False

        conn.execute("DELETE FROM fed_chats WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error removing chat from fed: {e}")
        return False


@async_db
def get_fed_id(chat_id: int) -> Optional[str]:
    """Get federation ID for a chat."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT fed_id FROM fed_chats WHERE chat_id = ?",
        (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()

    return row["fed_id"] if row else None


@async_db
def chat_id_and_names_in_fed(fed_id: str) -> tuple:
    """Get all chat IDs and names in federation."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT chat_id, chat_title FROM fed_chats WHERE fed_id = ?",
        (fed_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    chat_ids = [r["chat_id"] for r in rows]
    chat_names = [r["chat_title"] for r in rows]

    return chat_ids, chat_names

# ==================== FEDERATION BAN OPERATIONS ====================

@async_db
def add_fban_user(fed_id: str, user_id: int, reason: str, banned_by: int = None) -> bool:
    """Add a user to federation ban list."""
    try:
        from datetime import datetime
        conn = get_db()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            INSERT INTO fed_bans (fed_id, user_id, reason, date, banned_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(fed_id, user_id) DO UPDATE SET reason = ?, date = ?
        """, (fed_id, user_id, reason, date, banned_by, reason, date))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding fban: {e}")
        return False


@async_db
def remove_fban_user(fed_id: str, user_id: int) -> bool:
    """Remove a user from federation ban list."""
    try:
        conn = get_db()
        conn.execute(
            "DELETE FROM fed_bans WHERE fed_id = ? AND user_id = ?",
            (fed_id, user_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error removing fban: {e}")
        return False


@async_db
def check_banned_user(fed_id: str, user_id: int) -> Optional[Dict[str, str]]:
    """Check if user is banned in federation."""
    conn = get_db()
    cursor = conn.execute(
        "SELECT reason, date FROM fed_bans WHERE fed_id = ? AND user_id = ?",
        (fed_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {"reason": row["reason"], "date": row["date"]}
    return None


@async_db
def get_user_fstatus(user_id: int) -> List[Dict[str, str]]:
    """Get all federations where user is banned."""
    conn = get_db()
    cursor = conn.execute("""
        SELECT f.fed_id, f.fed_name, fb.reason, fb.date
        FROM fed_bans fb
        JOIN federations f ON fb.fed_id = f.fed_id
        WHERE fb.user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "fed_id": r["fed_id"],
            "fed_name": r["fed_name"],
            "reason": r["reason"],
            "date": r["date"]
        }
        for r in rows
    ]

# ==================== LOG OPERATIONS ====================

@async_db
def set_log_chat(fed_id: str, log_group_id: int) -> bool:
    """Set log group for federation."""
    try:
        conn = get_db()
        conn.execute(
            "UPDATE federations SET log_group_id = ? WHERE fed_id = ?",
            (log_group_id, fed_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting log chat: {e}")
        return False

# ==================== COMPATIBILITY LAYER ====================

# For MongoDB-style access (backward compatibility)
class FakeCollection:
    """Fake MongoDB collection for compatibility."""

    async def update_one(self, query, update, upsert=False):
        """MongoDB-style update_one."""
        if "fed_id" in query:
            fed_id = query["fed_id"]
            data = update.get("$set", {})

            if "fed_name" in data:
                # Creating or updating federation
                result = await create_federation(
                    fed_id,
                    data.get("fed_name", ""),
                    data.get("owner_id", 0),
                    data.get("owner_mention", ""),
                    data.get("log_group_id", 0)
                )
                return type('obj', (object,), {'acknowledged': result})

        return type('obj', (object,), {'acknowledged': False})

    async def delete_one(self, query):
        """MongoDB-style delete_one."""
        if "fed_id" in query:
            result = await delete_federation(query["fed_id"])
            return type('obj', (object,), {'acknowledged': result})
        return type('obj', (object,), {'acknowledged': False})

# Create instance for backward compatibility
fedsdb = FakeCollection()
