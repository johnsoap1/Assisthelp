"""
wbb/core/mongo/helpers.py
-------------------------

A helper module for MongoDB operations used by William Butcher Bot.
This file defines generic async CRUD functions and a MongoHelper class
for managing collections and database operations cleanly.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Custom Exception
# ─────────────────────────────────────────────

class MongoDBError(Exception):
    """Custom exception for MongoDB-related issues."""
    pass


# ─────────────────────────────────────────────
#  Mongo Helper Class
# ─────────────────────────────────────────────

class MongoHelper:
    def __init__(self, uri: str, db_name: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        logger.info(f"Connected to MongoDB database '{db_name}'")

    def get_collection(self, name: str):
        """Return a MongoDB collection object."""
        return self.db[name]


# ─────────────────────────────────────────────
#  CRUD Helper Functions
# ─────────────────────────────────────────────

async def db_insert_one(collection, data: Dict[str, Any]) -> Optional[str]:
    try:
        result = await collection.insert_one(data)
        return str(result.inserted_id)
    except PyMongoError as e:
        logger.exception("MongoDB insert_one error: %s", e)
        raise MongoDBError(str(e))


async def db_insert_many(collection, data: List[Dict[str, Any]]) -> List[str]:
    try:
        result = await collection.insert_many(data)
        return [str(_id) for _id in result.inserted_ids]
    except PyMongoError as e:
        logger.exception("MongoDB insert_many error: %s", e)
        raise MongoDBError(str(e))


async def db_find_one(collection, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return await collection.find_one(query)
    except PyMongoError as e:
        logger.exception("MongoDB find_one error: %s", e)
        raise MongoDBError(str(e))


async def db_find_many(collection, query: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        cursor = collection.find(query)
        return await cursor.to_list(length=None)
    except PyMongoError as e:
        logger.exception("MongoDB find_many error: %s", e)
        raise MongoDBError(str(e))


async def db_update_one(
    collection,
    query: Dict[str, Any],
    update_data: Dict[str, Any],
    upsert: bool = False,
) -> int:
    try:
        result = await collection.update_one(query, {"$set": update_data}, upsert=upsert)
        return result.modified_count
    except PyMongoError as e:
        logger.exception("MongoDB update_one error: %s", e)
        raise MongoDBError(str(e))


async def db_update_many(
    collection,
    query: Dict[str, Any],
    update_data: Dict[str, Any],
    upsert: bool = False,
) -> int:
    try:
        result = await collection.update_many(query, {"$set": update_data}, upsert=upsert)
        return result.modified_count
    except PyMongoError as e:
        logger.exception("MongoDB update_many error: %s", e)
        raise MongoDBError(str(e))


async def db_delete_one(collection, query: Dict[str, Any]) -> int:
    try:
        result = await collection.delete_one(query)
        return result.deleted_count
    except PyMongoError as e:
        logger.exception("MongoDB delete_one error: %s", e)
        raise MongoDBError(str(e))


async def db_delete_many(collection, query: Dict[str, Any]) -> int:
    try:
        result = await collection.delete_many(query)
        return result.deleted_count
    except PyMongoError as e:
        logger.exception("MongoDB delete_many error: %s", e)
        raise MongoDBError(str(e))


async def db_count(collection, query: Optional[Dict[str, Any]] = None) -> int:
    try:
        return await collection.count_documents(query or {})
    except PyMongoError as e:
        logger.exception("MongoDB count error: %s", e)
        raise MongoDBError(str(e))


async def db_exists(collection, query: Dict[str, Any]) -> bool:
    try:
        doc = await collection.find_one(query, {"_id": 1})
        return bool(doc)
    except PyMongoError as e:
        logger.exception("MongoDB exists check error: %s", e)
        raise MongoDBError(str(e))


# ─────────────────────────────────────────────
#  Usage Example
# ─────────────────────────────────────────────

"""
🧠 Usage Example
Here's how you'd use it inside your bot's Mongo core or cogs:

# wbb/core/mongo/__init__.py

from .helpers import MongoHelper

mongo = MongoHelper(uri="mongodb://localhost:27017", db_name="william_butcher")

users_col = mongo.get_collection("users")

# Example usage
from .helpers import db_find_one, db_insert_one

async def get_user_data(user_id: int):
    return await db_find_one(users_col, {"user_id": user_id})

async def save_user(user_id: int, name: str):
    return await db_insert_one(users_col, {"user_id": user_id, "name": name})


✅ Key Advantages
- Full async support (via motor)
- Centralized error handling (MongoDBError)
- Reusable CRUD helpers
- Easy to extend with domain-specific logic later (like your inactive kick, translation, etc.)
"""
