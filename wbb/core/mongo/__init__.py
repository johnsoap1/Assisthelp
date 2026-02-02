"""
MongoDB Module for William Butcher Bot

Provides database connection and helper functions for MongoDB operations.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

# Get MongoDB URI from environment
MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    logger.warning("MONGO_URL not set in environment variables!")
    MONGO_URL = "mongodb://localhost:27017"

# Initialize MongoDB client
try:
    _client = AsyncIOMotorClient(MONGO_URL)
    db = _client.wbb_bot
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    db = None

# Import helpers for easy access
from wbb.core.mongo.helpers import (
    MongoHelper,
    MongoDBError,
    db_insert_one,
    db_insert_many,
    db_find_one,
    db_find_many,
    db_update_one,
    db_update_many,
    db_delete_one,
    db_delete_many,
    db_count,
    db_exists
)

__all__ = [
    "db",
    "MongoHelper",
    "MongoDBError",
    "db_insert_one",
    "db_insert_many",
    "db_find_one",
    "db_find_many",
    "db_update_one",
    "db_update_many",
    "db_delete_one",
    "db_delete_many",
    "db_count",
    "db_exists"
]
