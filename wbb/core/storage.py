"""
SQLAlchemy-backed SQLite storage with Mongo-like async API.
Tables: users, chats, bans, settings, feds (extensible). Operators: $set, $inc, $push, $pull, $addToSet, $unset. Filters: equality, $in, $lt, $lte, $gt, $gte, $or.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, Integer, JSON, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


# -------------------
# Table definitions
# -------------------


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    name = Column(String, default="")
    admin = Column(Boolean, default=False)
    data = Column(JSON, default={})


class Chat(Base):
    __tablename__ = "chats"
    chat_id = Column(Integer, primary_key=True)
    welcome_message = Column(String, default="")
    data = Column(JSON, default={})


class Ban(Base):
    __tablename__ = "bans"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, nullable=True)
    reason = Column(Text, default="")
    data = Column(JSON, default={})


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(JSON, default={})


class Fed(Base):
    __tablename__ = "feds"
    id = Column(Integer, primary_key=True)
    fed_id = Column(String, unique=True, nullable=False)
    owner_id = Column(Integer, nullable=True)
    data = Column(JSON, default={})


class Sudoer(Base):
    __tablename__ = "sudoers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sudo = Column(String, default="sudo")
    data = Column(JSON, default={"sudoers": []})


class MusicCache(Base):
    __tablename__ = "music_cache"
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, unique=True, nullable=False, index=True)
    title = Column(String)
    performer = Column(String)
    duration = Column(Integer)
    file_id = Column(String)
    thumb_file_id = Column(String)
    storage_msg_id = Column(Integer)
    created_at = Column(Integer)
    last_accessed = Column(Integer)
    access_count = Column(Integer, default=0)
    data = Column(JSON, default={})


class TriggerData(Base):
    __tablename__ = "triggers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False, index=True)
    trigger = Column(String, nullable=False, index=True)
    use_regex = Column(Boolean, default=False)
    created_at = Column(Integer)
    usage_count = Column(Integer, default=0)
    data = Column(JSON, default={"responses": []})


class TriggerStats(Base):
    __tablename__ = "trigger_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False)
    trigger = Column(String, nullable=False)
    count = Column(Integer, default=0)
    last_used = Column(Integer)
    data = Column(JSON, default={})


class TranslateHistory(Base):
    __tablename__ = "translate_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    source_text = Column(Text)
    translated_text = Column(Text)
    source_lang = Column(String)
    target_lang = Column(String)
    service = Column(String)
    timestamp = Column(Integer)
    data = Column(JSON, default={})


class AntiServiceSettings(Base):
    __tablename__ = "antiservice_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    enabled = Column(Boolean, default=False)
    data = Column(JSON, default={
        "delete_joins": True,
        "delete_leaves": True,
        "delete_pins": True,
        "delete_changes": True,
        "delete_commands": True,
        "command_delay": 2,
        "admin_bypass": False
    })


class AdminLog(Base):
    __tablename__ = "admin_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False)
    enabled = Column(Boolean, default=False)
    data = Column(JSON, default={})


class DedupeSettings(Base):
    __tablename__ = "dedupe_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, unique=True, nullable=False, index=True)
    enabled = Column(Boolean, default=False)
    updated_at = Column(Integer)  # Unix timestamp
    data = Column(JSON, default={})


class MediaHash(Base):
    __tablename__ = "media_hashes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False, index=True)
    file_hash = Column(String, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    message_id = Column(Integer)
    timestamp = Column(Integer)  # Unix timestamp
    data = Column(JSON, default={})


class UserMediaStats(Base):
    __tablename__ = "user_media_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    photos = Column(Integer, default=0)
    videos = Column(Integer, default=0)
    total = Column(Integer, default=0, index=True)  # Index for leaderboard queries
    last_media = Column(Integer)  # Unix timestamp
    data = Column(JSON, default={})


class Document(Base):
    """Generic collection-backed document storage."""
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    collection = Column(String, index=True, nullable=False)
    data = Column(JSON, default={})


# -------------------
# Engine / Session
# -------------------

_engine = None
_SessionLocal = None
_locks: Dict[str, asyncio.Lock] = {}


def _get_lock(name: str) -> asyncio.Lock:
    if name not in _locks:
        _locks[name] = asyncio.Lock()
    return _locks[name]


# -------------------
# Helpers
# -------------------


def _split_data(table, payload: Dict[str, Any], collection_name: Optional[str] = None):
    column_names = {c.name for c in table.__table__.columns}
    direct = {}
    extra = {}
    for k, v in payload.items():
        if k in column_names and k != "data":
            direct[k] = v
        elif k == "data" and isinstance(v, dict):
            extra.update(v)
        else:
            extra[k] = v
    if collection_name and "collection" in column_names:
        direct["collection"] = collection_name
    if "data" in column_names:
        direct["data"] = extra
    return direct


def _row_to_dict(row) -> Dict[str, Any]:
    result = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        result[col.name] = val
    if isinstance(result.get("data"), dict):
        result.update(result["data"])
    return result


def _match_condition(value, condition) -> bool:
    if isinstance(condition, dict):
        for op, op_val in condition.items():
            if op == "$in" and value not in op_val:
                return False
            if op == "$lt" and not (value < op_val):
                return False
            if op == "$lte" and not (value <= op_val):
                return False
            if op == "$gt" and not (value > op_val):
                return False
            if op == "$gte" and not (value >= op_val):
                return False
            if op == "$exists":
                exists = value is not None
                if bool(op_val) != exists:
                    return False
            if op == "$regex":
                import re

                pattern = op_val
                flags = 0
                if condition.get("$options") == "i":
                    flags |= re.IGNORECASE
                if not re.search(pattern, str(value), flags=flags):
                    return False
    else:
        return value == condition
    return True


def _match_query(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    for key, value in query.items():
        if key == "$or" and isinstance(value, list):
            if not any(_match_query(doc, clause) for clause in value):
                return False
            continue
        if key not in doc:
            return False
        if not _match_condition(doc[key], value):
            return False
    return True


def _apply_update(doc: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(doc)
    for op, payload in update.items():
        if op == "$set":
            updated.update(payload)
        elif op == "$inc":
            for k, v in payload.items():
                updated[k] = updated.get(k, 0) + v
        elif op == "$push":
            for k, v in payload.items():
                updated.setdefault(k, [])
                if isinstance(v, dict) and "$each" in v:
                    updated[k].extend(v["$each"])
                else:
                    updated[k].append(v)
        elif op == "$pull":
            for k, v in payload.items():
                if k in updated and isinstance(updated[k], list):
                    updated[k] = [item for item in updated[k] if item != v]
        elif op == "$addToSet":
            for k, v in payload.items():
                updated.setdefault(k, [])
                if isinstance(v, dict) and "$each" in v:
                    for item in v["$each"]:
                        if item not in updated[k]:
                            updated[k].append(item)
                else:
                    if v not in updated[k]:
                        updated[k].append(v)
        elif op == "$unset":
            for k in payload.keys():
                updated.pop(k, None)
    return updated


# -------------------
# Result wrappers
# -------------------


class InsertOneResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(self, modified_count: int, upserted_id: Optional[Any]):
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class DeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class Cursor:
    def __init__(self, data: List[Dict[str, Any]]):
        self._data = data
        self._index = 0

    def sort(self, key: str, direction: int = 1):
        reverse = direction == -1
        self._data.sort(key=lambda x: x.get(key), reverse=reverse)
        return self

    def limit(self, limit: int):
        self._data = self._data[:limit]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._data):
            raise StopAsyncIteration
        item = self._data[self._index]
        self._index += 1
        return item

    async def to_list(self, length: Optional[int] = None):
        return self._data if length is None else self._data[:length]


# -------------------
# Collection wrapper
# -------------------


class Collection:
    def __init__(self, name: str, table):
        self.name = name
        self.table = table

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with _get_lock(self.name):
            def _find():
                with _SessionLocal() as session:
                    q = session.query(self.table)
                    if self.table is Document:
                        q = q.filter(Document.collection == self.name)
                    rows = q.all()
                    for row in rows:
                        data = _row_to_dict(row)
                        if _match_query(data, query):
                            return data
                return None

            return await asyncio.to_thread(_find)

    async def find(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, int]] = None):
        if query is None:
            query = {}

        async with _get_lock(self.name):
            def _find_many():
                with _SessionLocal() as session:
                    q = session.query(self.table)
                    if self.table is Document:
                        q = q.filter(Document.collection == self.name)
                    rows = q.all()
                    matched = []
                    for row in rows:
                        data = _row_to_dict(row)
                        if _match_query(data, query):
                            if projection:
                                projected = {}
                                for key, include in projection.items():
                                    if include and key in data:
                                        projected[key] = data[key]
                                matched.append(projected)
                            else:
                                matched.append(data)
                    return matched

            data = await asyncio.to_thread(_find_many)
            return Cursor(data)

    async def insert_one(self, data: Dict[str, Any]):
        async with _get_lock(self.name):
            def _insert():
                with _SessionLocal() as session:
                    payload = _split_data(self.table, data, self.name)
                    obj = self.table(**payload)
                    session.add(obj)
                    session.commit()
                    session.refresh(obj)
                    return obj

            obj = await asyncio.to_thread(_insert)
            return InsertOneResult(getattr(obj, obj.__mapper__.primary_key[0].name))

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        async with _get_lock(self.name):
            def _update():
                with _SessionLocal() as session:
                    q = session.query(self.table)
                    if self.table is Document:
                        q = q.filter(Document.collection == self.name)
                    rows = q.all()
                    for row in rows:
                        data = _row_to_dict(row)
                        if _match_query(data, query):
                            merged = _apply_update(data, update)
                            payload = _split_data(self.table, merged, self.name)
                            for k, v in payload.items():
                                setattr(row, k, v)
                            session.commit()
                            return UpdateResult(1, None)
                    if upsert:
                        merged = _apply_update(query.copy(), update)
                        payload = _split_data(self.table, merged, self.name)
                        obj = self.table(**payload)
                        session.add(obj)
                        session.commit()
                        session.refresh(obj)
                        pk = getattr(obj, obj.__mapper__.primary_key[0].name)
                        return UpdateResult(0, pk)
                    return UpdateResult(0, None)

            return await asyncio.to_thread(_update)

    async def delete_one(self, query: Dict[str, Any]):
        async with _get_lock(self.name):
            def _delete():
                with _SessionLocal() as session:
                    q = session.query(self.table)
                    if self.table is Document:
                        q = q.filter(Document.collection == self.name)
                    rows = q.all()
                    for row in rows:
                        data = _row_to_dict(row)
                        if _match_query(data, query):
                            session.delete(row)
                            session.commit()
                            return DeleteResult(1)
                    return DeleteResult(0)

            return await asyncio.to_thread(_delete)

    async def count_documents(self, query: Optional[Dict[str, Any]] = None) -> int:
        if query is None:
            query = {}
        async with _get_lock(self.name):
            def _count():
                with _SessionLocal() as session:
                    q = session.query(self.table)
                    if self.table is Document:
                        q = q.filter(Document.collection == self.name)
                    rows = q.all()
                    return sum(1 for row in rows if _match_query(_row_to_dict(row), query))

            return await asyncio.to_thread(_count)


# -------------------
# Entrypoint
# -------------------


class DB:
    def __init__(self):
        self.users = Collection("users", User)
        self.chats = Collection("chats", Chat)
        self.bans = Collection("bans", Ban)
        self.settings = Collection("settings", Setting)
        self.feds = Collection("feds", Fed)
        self.sudoers = Collection("sudoers", Sudoer)
        self.music_cache = Collection("music_cache", MusicCache)
        self.triggers = Collection("triggers", TriggerData)
        self.trigger_stats = Collection("trigger_stats", TriggerStats)
        self.translate_history = Collection("translate_history", TranslateHistory)
        self.antiservice_settings = Collection("antiservice_settings", AntiServiceSettings)
        self.admin_logs = Collection("admin_logs", AdminLog)
        # NEW: Media deduplication collections
        self.dedupe_settings = Collection("dedupe_settings", DedupeSettings)
        self.media_hashes = Collection("media_hashes", MediaHash)
        self.user_media_stats = Collection("user_media_stats", UserMediaStats)
        self._generic = {}

    def __getattr__(self, item: str):
        if item.startswith("_"):
            raise AttributeError
        if item not in self._generic:
            self._generic[item] = Collection(item, Document)
        return self._generic[item]


db = DB()


async def init_storage(db_url: Optional[str] = None):
    """Initialize SQLite storage (idempotent)."""
    global _engine, _SessionLocal
    if db_url is None:
        db_url = os.getenv("DB_URL", "sqlite:///wbb.sqlite")
    _engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
    _SessionLocal = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)
    logger.info("SQLite storage initialized at %s", db_url)
    return db
