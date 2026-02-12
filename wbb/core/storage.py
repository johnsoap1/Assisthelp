"""
SQLite Storage Module
Provides database connection for SQLite operations.
"""
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path("wbb.sqlite")

def get_db():
    """Get SQLite database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

async def init_storage():
    """Initialize SQLite storage."""
    try:
        # Ensure database file exists and is accessible
        conn = get_db()
        conn.close()
        logger.info("SQLite storage initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite storage: {e}")
        raise

# For backward compatibility, create a dummy 'db' object
class SQLiteDB:
    """Dummy class for compatibility with old MongoDB code."""
    def __getattr__(self, name):
        # This will catch attempts to access collections like db.blocklist
        raise AttributeError(
            f"MongoDB collection '{name}' not available. "
            "Use SQLite functions from wbb.utils.dbfunctions instead."
        )

db = SQLiteDB()

logger.info("SQLite storage initialized")
