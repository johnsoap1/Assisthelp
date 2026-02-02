"""
Enhanced Database Functions for William Butcher Bot

Provides abstraction layer for MongoDB operations with improved structure,
better error handling, and more efficient queries.
"""
import codecs
import pickle
from string import ascii_lowercase
from typing import Dict, List, Union, Optional

from wbb.core.storage import db

# Database collections
notesdb = db.notes
filtersdb = db.filters
warnsdb = db.warns
karmadb = db.karma
chatsdb = db.chats
usersdb = db.users
gbansdb = db.gban
coupledb = db.couple
captchadb = db.captcha
solved_captcha_db = db.solved_captcha
captcha_cachedb = db.captcha_cache
antiservicedb = db.antiservice
pmpermitdb = db.pmpermit
welcomedb = db.welcome_text
blacklist_filtersdb = db.blacklistFilters
pipesdb = db.pipes
sudoersdb = db.sudoers
blacklist_chatdb = db.blacklistChat
restart_stagedb = db.restart_stage
flood_toggle_db = db.flood_toggle
rssdb = db.rss
rulesdb = db.rules
chatbotdb = db.chatbot
summary_cooldown_db = db.summary_cooldowns
admin_logs_db = db.admin_logs
blacklist_stats_db = db.blacklist_stats
antiservice_db = db.antiservice
blacklist_settings_db = db.blacklist_settings
admin_log_db = db.admin_logs


# ==================== Utility Functions ====================

def obj_to_str(obj):
    """Convert Python object to base64 string."""
    if not obj:
        return False
    string = codecs.encode(pickle.dumps(obj), "base64").decode()
    return string


def str_to_obj(string: str):
    """Convert base64 string back to Python object."""
    obj = pickle.loads(codecs.decode(string.encode(), "base64"))
    return obj


async def int_to_alpha(user_id: int) -> str:
    """Convert integer user ID to alphabet string."""
    alphabet = list(ascii_lowercase)[:10]
    text = ""
    user_id = str(user_id)
    for i in user_id:
        text += alphabet[int(i)]
    return text


async def alpha_to_int(user_id_alphabet: str) -> int:
    """Convert alphabet string back to integer user ID."""
    alphabet = list(ascii_lowercase)[:10]
    user_id = ""
    for i in user_id_alphabet:
        index = alphabet.index(i)
        user_id += str(index)
    return int(user_id)


# ==================== Notes Functions ====================

async def get_notes_count() -> dict:
    """Get total count of notes and chats with notes."""
    chats_count = 0
    notes_count = 0
    async for chat in notesdb.find({"chat_id": {"$exists": 1}}):
        notes_name = await get_note_names(chat["chat_id"])
        notes_count += len(notes_name)
        chats_count += 1
    return {"chats_count": chats_count, "notes_count": notes_count}


async def _get_notes(chat_id: int) -> Dict[str, dict]:
    """Internal: Get all notes for a chat."""
    _notes = await notesdb.find_one({"chat_id": chat_id})
    return _notes.get("notes", {}) if _notes else {}


async def get_note_names(chat_id: int) -> List[str]:
    """Get list of note names for a chat."""
    _notes = await _get_notes(chat_id)
    return list(_notes.keys())


async def get_note(chat_id: int, name: str) -> Optional[dict]:
    """Get a specific note by name."""
    name = name.lower().strip()
    _notes = await _get_notes(chat_id)
    return _notes.get(name)


async def save_note(chat_id: int, name: str, note: dict):
    """Save or update a note."""
    name = name.lower().strip()
    _notes = await _get_notes(chat_id)
    _notes[name] = note
    await notesdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_note(chat_id: int, name: str) -> bool:
    """Delete a specific note."""
    notesd = await _get_notes(chat_id)
    name = name.lower().strip()
    if name in notesd:
        del notesd[name]
        await notesdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False


async def deleteall_notes(chat_id: int):
    """Delete all notes for a chat."""
    return await notesdb.delete_one({"chat_id": chat_id})


# ==================== Filters Functions ====================

async def get_filters_count() -> dict:
    """Get total count of filters and chats with filters."""
    chats_count = 0
    filters_count = 0
    async for chat in filtersdb.find({"chat_id": {"$lt": 0}}):
        filters_name = await get_filters_names(chat["chat_id"])
        filters_count += len(filters_name)
        chats_count += 1
    return {
        "chats_count": chats_count,
        "filters_count": filters_count,
    }


async def _get_filters(chat_id: int) -> Dict[str, dict]:
    """Internal: Get all filters for a chat."""
    _filters = await filtersdb.find_one({"chat_id": chat_id})
    return _filters.get("filters", {}) if _filters else {}


async def get_filters_names(chat_id: int) -> List[str]:
    """Get list of filter names for a chat."""
    _filters = await _get_filters(chat_id)
    return list(_filters.keys())


async def get_filter(chat_id: int, name: str) -> Optional[dict]:
    """Get a specific filter by name."""
    name = name.lower().strip()
    _filters = await _get_filters(chat_id)
    return _filters.get(name)


async def save_filter(chat_id: int, name: str, _filter: dict):
    """Save or update a filter."""
    name = name.lower().strip()
    _filters = await _get_filters(chat_id)
    _filters[name] = _filter
    await filtersdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"filters": _filters}},
        upsert=True,
    )


async def delete_filter(chat_id: int, name: str) -> bool:
    """Delete a specific filter."""
    filtersd = await _get_filters(chat_id)
    name = name.lower().strip()
    if name in filtersd:
        del filtersd[name]
        await filtersdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"filters": filtersd}},
            upsert=True,
        )
        return True
    return False


async def deleteall_filters(chat_id: int):
    """Delete all filters for a chat."""
    return await filtersdb.delete_one({"chat_id": chat_id})


# ==================== Antiservice & Admin Logs (SQLite) ====================


async def is_antiservice_on(chat_id: int) -> bool:
    doc = await db.antiservice_settings.find_one({"chat_id": chat_id})
    return doc.get("enabled", False) if doc else False


async def antiservice_on(chat_id: int):
    await db.antiservice_settings.update_one({"chat_id": chat_id}, {"$set": {"enabled": True}}, upsert=True)


async def antiservice_off(chat_id: int):
    await db.antiservice_settings.update_one({"chat_id": chat_id}, {"$set": {"enabled": False}}, upsert=True)


async def get_antiservice_settings(chat_id: int) -> dict:
    doc = await db.antiservice_settings.find_one({"chat_id": chat_id})
    if not doc:
        return {
            "delete_joins": True,
            "delete_leaves": True,
            "delete_pins": True,
            "delete_changes": True,
            "delete_commands": True,
            "command_delay": 2,
            "admin_bypass": False,
        }
    return doc.get("data", {}) or {}


async def update_antiservice_settings(chat_id: int, settings: dict):
    await db.antiservice_settings.update_one({"chat_id": chat_id}, {"$set": {"data": settings}}, upsert=True)


async def is_admin_log_enabled(chat_id: int) -> bool:
    doc = await db.admin_logs.find_one({"chat_id": chat_id})
    return doc.get("enabled", False) if doc else False


async def toggle_admin_log(chat_id: int, enabled: bool):
    await db.admin_logs.update_one({"chat_id": chat_id}, {"$set": {"enabled": enabled}}, upsert=True)


# ==================== Rules Functions ====================

async def get_rules(chat_id: int) -> str:
    """Get chat rules."""
    chat = await rulesdb.find_one({"chat_id": chat_id})
    return chat.get("rules", "") if chat else ""


async def set_chat_rules(chat_id: int, rules: str):
    """Set chat rules."""
    await rulesdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"rules": rules}},
        upsert=True,
    )


async def delete_rules(chat_id: int):
    """Delete chat rules."""
    return await rulesdb.delete_one({"chat_id": chat_id})


# ==================== Warns Functions ====================

async def get_warns_count() -> dict:
    """Get total count of warns and chats with warns."""
    chats_count = 0
    warns_count = 0
    async for chat in warnsdb.find({"chat_id": {"$lt": 0}}):
        for user in chat.get("warns", {}):
            warns_count += chat["warns"][user].get("warns", 0)
        chats_count += 1
    return {"chats_count": chats_count, "warns_count": warns_count}


async def get_warns(chat_id: int) -> Dict[str, dict]:
    """Get all warns for a chat."""
    warns = await warnsdb.find_one({"chat_id": chat_id})
    return warns.get("warns", {}) if warns else {}


async def get_warn(chat_id: int, name: str) -> Optional[dict]:
    """Get a specific warn."""
    name = name.lower().strip()
    warns = await get_warns(chat_id)
    return warns.get(name)


async def add_warn(chat_id: int, name: str, warn: dict):
    """Add or update a warn."""
    name = name.lower().strip()
    warns = await get_warns(chat_id)
    warns[name] = warn
    await warnsdb.update_one(
        {"chat_id": chat_id}, {"$set": {"warns": warns}}, upsert=True
    )


async def remove_warns(chat_id: int, name: str) -> bool:
    """Remove a specific warn."""
    warnsd = await get_warns(chat_id)
    name = name.lower().strip()
    if name in warnsd:
        del warnsd[name]
        await warnsdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"warns": warnsd}},
            upsert=True,
        )
        return True
    return False


# ==================== Karma Functions ====================

async def get_karmas_count() -> dict:
    """Get total count of karma and chats with karma."""
    chats_count = 0
    karmas_count = 0
    async for chat in karmadb.find({"chat_id": {"$lt": 0}}):
        for i in chat.get("karma", {}):
            karma_ = chat["karma"][i].get("karma", 0)
            if karma_ > 0:
                karmas_count += karma_
        chats_count += 1
    return {"chats_count": chats_count, "karmas_count": karmas_count}


async def user_global_karma(user_id: int) -> int:
    """Get total karma for a user across all chats."""
    total_karma = 0
    async for chat in karmadb.find({"chat_id": {"$lt": 0}}):
        user_alpha = await int_to_alpha(user_id)
        karma = chat.get("karma", {}).get(user_alpha)
        if karma and int(karma.get("karma", 0)) > 0:
            total_karma += int(karma["karma"])
    return total_karma


async def get_karmas(chat_id: int) -> Dict[str, dict]:
    """Get all karma for a chat."""
    karma = await karmadb.find_one({"chat_id": chat_id})
    return karma.get("karma", {}) if karma else {}


async def get_karma(chat_id: int, name: str) -> Optional[dict]:
    """Get a specific karma."""
    name = name.lower().strip()
    karmas = await get_karmas(chat_id)
    return karmas.get(name)


async def update_karma(chat_id: int, name: str, karma: dict):
    """Update karma for a user."""
    name = name.lower().strip()
    karmas = await get_karmas(chat_id)
    karmas[name] = karma
    await karmadb.update_one(
        {"chat_id": chat_id}, {"$set": {"karma": karmas}}, upsert=True
    )


async def is_karma_on(chat_id: int) -> bool:
    """Check if karma is enabled in chat."""
    chat = await karmadb.find_one({"chat_id_toggle": chat_id})
    return not chat


async def karma_on(chat_id: int):
    """Enable karma for a chat."""
    is_karma = await is_karma_on(chat_id)
    if is_karma:
        return
    return await karmadb.delete_one({"chat_id_toggle": chat_id})


async def karma_off(chat_id: int):
    """Disable karma for a chat."""
    is_karma = await is_karma_on(chat_id)
    if not is_karma:
        return
    return await karmadb.insert_one({"chat_id_toggle": chat_id})


# ==================== Served Chats/Users Functions ====================

async def is_served_chat(chat_id: int) -> bool:
    """Check if bot serves a chat."""
    chat = await chatsdb.find_one({"chat_id": chat_id})
    return bool(chat)


async def get_served_chats() -> list:
    """Get list of all served chats."""
    chats_list = []
    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(int(chat["chat_id"]))
    return chats_list


async def add_served_chat(chat_id: int):
    """Add a served chat."""
    is_served = await is_served_chat(chat_id)
    if is_served:
        return
    return await chatsdb.insert_one({"chat_id": chat_id})


async def remove_served_chat(chat_id: int):
    """Remove a served chat."""
    is_served = await is_served_chat(chat_id)
    if not is_served:
        return
    return await chatsdb.delete_one({"chat_id": chat_id})


async def is_served_user(user_id: int) -> bool:
    """Check if bot has interacted with a user."""
    user = await usersdb.find_one({"user_id": user_id})
    return bool(user)


async def get_served_users() -> list:
    """Get list of all served users."""
    users_list = []
    async for user in usersdb.find({"user_id": {"$gt": 0}}):
        users_list.append(int(user["user_id"]))
    return users_list


async def add_served_user(user_id: int):
    """Add a served user."""
    is_served = await is_served_user(user_id)
    if is_served:
        return
    return await usersdb.insert_one({"user_id": user_id})


# ==================== Global Ban Functions ====================

async def get_gbans_count() -> int:
    """Get count of globally banned users."""
    return len([i async for i in gbansdb.find({"user_id": {"$gt": 0}})])


async def is_gbanned_user(user_id: int) -> bool:
    """Check if user is globally banned."""
    user = await gbansdb.find_one({"user_id": user_id})
    return bool(user)


async def add_gban_user(user_id: int):
    """Add user to global ban list."""
    is_gbanned = await is_gbanned_user(user_id)
    if is_gbanned:
        return
    return await gbansdb.insert_one({"user_id": user_id})


async def remove_gban_user(user_id: int):
    """Remove user from global ban list."""
    is_gbanned = await is_gbanned_user(user_id)
    if not is_gbanned:
        return
    return await gbansdb.delete_one({"user_id": user_id})


# ==================== Couple Functions ====================

async def _get_lovers(chat_id: int) -> dict:
    """Internal: Get all couples for a chat."""
    lovers = await coupledb.find_one({"chat_id": chat_id})
    return lovers.get("couple", {}) if lovers else {}


async def get_couple(chat_id: int, date: str) -> Optional[dict]:
    """Get a specific couple for a date."""
    lovers = await _get_lovers(chat_id)
    return lovers.get(date)


async def save_couple(chat_id: int, date: str, couple: dict):
    """Save a couple."""
    lovers = await _get_lovers(chat_id)
    lovers[date] = couple
    await coupledb.update_one(
        {"chat_id": chat_id},
        {"$set": {"couple": lovers}},
        upsert=True,
    )


# ==================== Captcha Functions ====================

async def is_captcha_on(chat_id: int) -> bool:
    """Check if captcha is enabled in chat."""
    chat = await captchadb.find_one({"chat_id": chat_id})
    return not chat


async def captcha_on(chat_id: int):
    """Enable captcha for a chat."""
    is_captcha = await is_captcha_on(chat_id)
    if is_captcha:
        return
    return await captchadb.delete_one({"chat_id": chat_id})


async def captcha_off(chat_id: int):
    """Disable captcha for a chat."""
    is_captcha = await is_captcha_on(chat_id)
    if not is_captcha:
        return
    return await captchadb.insert_one({"chat_id": chat_id})


async def has_solved_captcha_once(chat_id: int, user_id: int) -> bool:
    """Check if user has solved captcha in a chat."""
    has_solved = await solved_captcha_db.find_one(
        {"chat_id": chat_id, "user_id": user_id}
    )
    return bool(has_solved)


async def save_captcha_solved(chat_id: int, user_id: int):
    """Mark captcha as solved for user."""
    return await solved_captcha_db.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"solved": True}},
        upsert=True,
    )


async def update_captcha_cache(captcha_dict: dict):
    """Update captcha cache."""
    pickle_str = obj_to_str(captcha_dict)
    await captcha_cachedb.delete_one({"captcha": "cache"})
    if not pickle_str:
        return
    await captcha_cachedb.update_one(
        {"captcha": "cache"},
        {"$set": {"pickled": pickle_str}},
        upsert=True,
    )


async def get_captcha_cache() -> list:
    """Get captcha cache."""
    cache = await captcha_cachedb.find_one({"captcha": "cache"})
    if not cache:
        return []
    return str_to_obj(cache["pickled"])


# ==================== AntiService Functions ====================

async def get_antiservice_settings(chat_id: int) -> dict:
    """Get antiservice settings for a chat."""
    chat = await antiservice_db.find_one({"chat_id": chat_id})
    if not chat:
        return {
            'delete_joins': True,
            'delete_leaves': True,
            'delete_pins': True,
            'delete_changes': True,
            'delete_commands': True,
            'command_delay': 2,
            'admin_bypass': False
        }
    return chat.get('settings', {})


async def update_antiservice_settings(chat_id: int, settings: dict):
    """Update antiservice settings."""
    await antiservice_db.update_one(
        {"chat_id": chat_id},
        {"$set": {"settings": settings}},
        upsert=True
    )


# ==================== Admin Log Functions ====================

async def is_admin_log_enabled(chat_id: int) -> bool:
    """Check if admin logging is enabled."""
    chat = await admin_log_db.find_one({"chat_id": chat_id})
    return chat.get('enabled', False) if chat else False


async def toggle_admin_log(chat_id: int, enabled: bool):
    """Toggle admin logging."""
    await admin_log_db.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": enabled}},
        upsert=True
    )


# ==================== Blacklist Functions ====================

async def get_blacklist_settings(chat_id: int) -> dict:
    """Get blacklist settings."""
    settings = await blacklist_settings_db.find_one({"chat_id": chat_id})
    if not settings:
        return {
            'action': 'mute_1h',
            'send_warning': True,
            'exempt_admins': True,
            'case_sensitive': False,
            'whole_words': True
        }
    return settings.get('settings', {})


async def update_blacklist_settings(chat_id: int, settings: dict):
    """Update blacklist settings."""
    await blacklist_settings_db.update_one(
        {"chat_id": chat_id},
        {"$set": {"settings": settings}},
        upsert=True
    )


async def get_blacklist_stats(chat_id: int) -> dict:
    """Get blacklist statistics."""
    stats = await blacklist_stats_db.find_one({"chat_id": chat_id})
    return stats if stats else {}


async def update_blacklist_stats(chat_id: int, word: str, user_id: int):
    """Update blacklist trigger statistics."""
    await blacklist_stats_db.update_one(
        {"chat_id": chat_id},
        {
            "$inc": {
                "total_triggers": 1,
                f"by_word.{word}": 1,
                f"by_user.{user_id}": 1
            }
        },
        upsert=True
    )


# ==================== PMPermit Functions ====================

async def is_pmpermit_approved(user_id: int) -> bool:
    """Check if user is PMPermit approved."""
    user = await pmpermitdb.find_one({"user_id": user_id})
    return bool(user)


async def approve_pmpermit(user_id: int):
    """Approve user for PMPermit."""
    is_pmpermit = await is_pmpermit_approved(user_id)
    if is_pmpermit:
        return
    return await pmpermitdb.insert_one({"user_id": user_id})


async def disapprove_pmpermit(user_id: int):
    """Disapprove user for PMPermit."""
    is_pmpermit = await is_pmpermit_approved(user_id)
    if not is_pmpermit:
        return
    return await pmpermitdb.delete_one({"user_id": user_id})


# ==================== Welcome Functions ====================

async def get_welcome(chat_id: int) -> tuple:
    """Get welcome message for a chat."""
    data = await welcomedb.find_one({"chat_id": chat_id})
    if not data:
        return "", "", ""
    return (
        data.get("welcome", ""),
        data.get("raw_text", ""),
        data.get("file_id", "")
    )


async def set_welcome(chat_id: int, welcome: str, raw_text: str, file_id: str):
    """Set welcome message for a chat."""
    update_data = {
        "welcome": welcome,
        "raw_text": raw_text,
        "file_id": file_id,
    }
    return await welcomedb.update_one(
        {"chat_id": chat_id}, {"$set": update_data}, upsert=True
    )


async def del_welcome(chat_id: int):
    """Delete welcome message for a chat."""
    return await welcomedb.delete_one({"chat_id": chat_id})


# ==================== Blacklist Functions ====================

async def get_blacklist_filters_count() -> dict:
    """Get count of blacklist filters and chats."""
    chats_count = 0
    filters_count = 0
    async for chat in blacklist_filtersdb.find({"chat_id": {"$lt": 0}}):
        filters = await get_blacklisted_words(chat["chat_id"])
        filters_count += len(filters)
        chats_count += 1
    return {
        "chats_count": chats_count,
        "filters_count": filters_count,
    }


async def get_blacklisted_words(chat_id: int) -> List[str]:
    """Get blacklisted words for a chat."""
    _filters = await blacklist_filtersdb.find_one({"chat_id": chat_id})
    return _filters.get("filters", []) if _filters else []


async def save_blacklist_filter(chat_id: int, word: str):
    """Add a blacklisted word."""
    word = word.lower().strip()
    _filters = await get_blacklisted_words(chat_id)
    if word not in _filters:
        _filters.append(word)
    await blacklist_filtersdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"filters": _filters}},
        upsert=True,
    )


async def delete_blacklist_filter(chat_id: int, word: str) -> bool:
    """Remove a blacklisted word."""
    filtersd = await get_blacklisted_words(chat_id)
    word = word.lower().strip()
    if word in filtersd:
        filtersd.remove(word)
        await blacklist_filtersdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"filters": filtersd}},
            upsert=True,
        )
        return True
    return False


async def blacklisted_chats() -> list:
    """Get list of blacklisted chats."""
    blacklist_chat = []
    async for chat in blacklist_chatdb.find({"chat_id": {"$lt": 0}}):
        blacklist_chat.append(chat["chat_id"])
    return blacklist_chat


async def blacklist_chat(chat_id: int) -> bool:
    """Add chat to blacklist."""
    if not await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.insert_one({"chat_id": chat_id})
        return True
    return False


async def whitelist_chat(chat_id: int) -> bool:
    """Remove chat from blacklist."""
    if await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.delete_one({"chat_id": chat_id})
        return True
    return False


# ==================== Pipes Functions ====================

async def activate_pipe(from_chat_id: int, to_chat_id: int, fetcher: str):
    """Activate a pipe between two chats."""
    pipes = await show_pipes()
    pipe = {
        "from_chat_id": from_chat_id,
        "to_chat_id": to_chat_id,
        "fetcher": fetcher,
    }
    pipes.append(pipe)
    return await pipesdb.update_one(
        {"pipe": "pipe"}, {"$set": {"pipes": pipes}}, upsert=True
    )


async def deactivate_pipe(from_chat_id: int, to_chat_id: int):
    """Deactivate a pipe between two chats."""
    pipes = await show_pipes()
    if not pipes:
        return
    for pipe in pipes:
        if (
            pipe["from_chat_id"] == from_chat_id
            and pipe["to_chat_id"] == to_chat_id
        ):
            pipes.remove(pipe)
    return await pipesdb.update_one(
        {"pipe": "pipe"}, {"$set": {"pipes": pipes}}, upsert=True
    )


async def is_pipe_active(from_chat_id: int, to_chat_id: int) -> bool:
    """Check if pipe between two chats is active."""
    for pipe in await show_pipes():
        if (
            pipe["from_chat_id"] == from_chat_id
            and pipe["to_chat_id"] == to_chat_id
        ):
            return True
    return False


async def show_pipes() -> list:
    """Get list of all active pipes."""
    pipes = await pipesdb.find_one({"pipe": "pipe"})
    return pipes.get("pipes", []) if pipes else []


# ==================== Sudoers Functions ====================

async def get_sudoers() -> list:
    """Get list of sudoers."""
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    return sudoers.get("sudoers", []) if sudoers else []


async def add_sudo(user_id: int) -> bool:
    """Add user to sudoers list."""
    sudoers = await get_sudoers()
    if user_id not in sudoers:
        sudoers.append(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def remove_sudo(user_id: int) -> bool:
    """Remove user from sudoers list."""
    sudoers = await get_sudoers()
    if user_id in sudoers:
        sudoers.remove(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


# ==================== Restart Stage Functions ====================

async def start_restart_stage(chat_id: int, message_id: int):
    """Store restart stage data."""
    await restart_stagedb.update_one(
        {"something": "something"},
        {
            "$set": {
                "chat_id": chat_id,
                "message_id": message_id,
            }
        },
        upsert=True,
    )


async def clean_restart_stage() -> dict:
    """Retrieve and clean restart stage data."""
    data = await restart_stagedb.find_one({"something": "something"})
    if not data:
        return {}
    await restart_stagedb.delete_one({"something": "something"})
    return {
        "chat_id": data["chat_id"],
        "message_id": data["message_id"],
    }


# ==================== Flood Functions ====================

async def is_flood_on(chat_id: int) -> bool:
    """Check if flood protection is enabled in chat."""
    chat = await flood_toggle_db.find_one({"chat_id": chat_id})
    return not chat


async def flood_on(chat_id: int):
    """Enable flood protection for a chat."""
    is_flood = await is_flood_on(chat_id)
    if is_flood:
        return
    return await flood_toggle_db.delete_one({"chat_id": chat_id})


async def flood_off(chat_id: int):
    """Disable flood protection for a chat."""
    is_flood = await is_flood_on(chat_id)
    if not is_flood:
        return
    return await flood_toggle_db.insert_one({"chat_id": chat_id})


# ==================== RSS Functions ====================

async def add_rss_feed(chat_id: int, url: str, last_title: str):
    """Add an RSS feed for a chat."""
    return await rssdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"url": url, "last_title": last_title}},
        upsert=True,
    )


async def remove_rss_feed(chat_id: int):
    """Remove an RSS feed."""
    return await rssdb.delete_one({"chat_id": chat_id})


async def update_rss_feed(chat_id: int, last_title: str):
    """Update RSS feed last title."""
    return await rssdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_title": last_title}},
        upsert=True,
    )


async def is_rss_active(chat_id: int) -> bool:
    """Check if RSS feed is active for a chat."""
    return bool(await rssdb.find_one({"chat_id": chat_id}))


async def get_rss_feeds() -> list:
    """Get list of all active RSS feeds."""
    data = []
    async for feed in rssdb.find({"chat_id": {"$exists": 1}}):
        data.append(
            dict(
                chat_id=feed["chat_id"],
                url=feed["url"],
                last_title=feed["last_title"],
            )
        )
    return data


async def get_rss_feeds_count() -> int:
    """Get count of active RSS feeds."""

# ==================== Chatbot Functions ====================

async def check_chatbot():
    """Get chatbot configuration."""
    return await chatbotdb.find_one({"chatbot": "chatbot"}) or {
        "bot": []
    }


async def add_chatbot(chat_id: int):
    """Enable chatbot for a chat."""
    config = await check_chatbot()
    if chat_id not in config["bot"]:
        config["bot"].append(chat_id)
    await chatbotdb.update_one(
        {"chatbot": "chatbot"}, {"$set": config}, upsert=True
    )


async def rm_chatbot(chat_id: int):
    """Disable chatbot for a chat."""
    config = await check_chatbot()
    if chat_id in config["bot"]:
        config["bot"].remove(chat_id)
    await chatbotdb.update_one(
        {"chatbot": "chatbot"}, {"$set": config}, upsert=True
    )


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
