# wbb/utils/decorators.py
"""
Legacy decorator imports for backward compatibility.
Redirects to new location in wbb.core.decorators
"""
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly, member_permissions

__all__ = ['capture_err', 'adminsOnly', 'member_permissions']
