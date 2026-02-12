# wbb/core/decorators/__init__.py
"""Decorators package for WBB bot."""

from .errors import capture_err
from .permissions import adminsOnly

__all__ = ['capture_err', 'adminsOnly']
