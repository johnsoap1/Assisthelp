"""
Pyrogram 2.x Compatibility Module
Provides utilities for smooth migration from Pyrogram 1.x to 2.x
"""

from pyrogram import errors as pyrogram_errors


# ===== Error Compatibility =====

class UserNotParticipant(pyrogram_errors.PeerIdInvalid):
    """Compatibility wrapper for UserNotParticipant error."""
    pass


class ChatAdminRequired(pyrogram_errors.ChatAdminRequired):
    """Chat admin required error."""
    pass


class AccessDenied(pyrogram_errors.AccessDenied):
    """Access denied error."""
    pass


class ChatNotFound(pyrogram_errors.ChatNotFound):
    """Chat not found error."""
    pass


class PeerIdInvalid(pyrogram_errors.PeerIdInvalid):
    """Peer ID invalid error."""
    pass


# ===== Export all errors from pyrogram.errors =====

# Forbidden 403 errors
try:
    from pyrogram.errors.exceptions.forbidden_403 import (
        UserNotParticipant as _UserNotParticipant,
    )
    UserNotParticipant = _UserNotParticipant
except ImportError:
    pass

try:
    from pyrogram.errors import UserNotParticipant as _UserNotParticipant
    UserNotParticipant = _UserNotParticipant
except ImportError:
    pass

# Make common errors available
__all__ = [
    "UserNotParticipant",
    "ChatAdminRequired",
    "AccessDenied",
    "ChatNotFound",
    "PeerIdInvalid",
]
