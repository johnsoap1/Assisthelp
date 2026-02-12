# wbb/core/storage.py
from pathlib import Path

db = None

async def init_storage():
    """Initialize SQLite storage"""
    global db
    
    # Create database file
    db_path = Path("wbb.sqlite")
    
    # Database is initialized in dbfunctions.py via init_tables()
    from wbb.utils.dbfunctions import init_tables
    init_tables()
    
    return db
