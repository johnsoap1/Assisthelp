"""
WBB Modules Init
"""
import glob
import importlib
import sys
from os.path import basename, dirname, isfile, join

from wbb import MOD_LOAD, MOD_NOLOAD


def __list_all_modules():
    """Dynamically list all Python modules in the modules directory."""
    mod_paths = glob.glob(join(dirname(__file__), "*.py"))
    return [
        basename(f)[:-3]
        for f in mod_paths
        if isfile(f)
        and not f.endswith("__init__.py")
        and not f.endswith("__main__.py")
    ]


def get_available_modules():
    """Get list of available modules, respecting MOD_LOAD and MOD_NOLOAD."""
    all_modules = __list_all_modules()
    
    if MOD_LOAD:
        # Only load explicitly listed modules that exist
        to_load = [m for m in MOD_LOAD if m in all_modules]
        missing = set(MOD_LOAD) - set(to_load)
        if missing:
            print(f"[WARNING] Some modules not found: {', '.join(missing)}")
    else:
        # Load all modules except those in MOD_NOLOAD
        to_load = [m for m in all_modules if m not in (MOD_NOLOAD or [])]
    
    return sorted(to_load)


print("[INFO]: IMPORTING MODULES")

# Import main module first
importlib.import_module("wbb.modules.__main__")

# Get the list of available modules
ALL_MODULES = get_available_modules()

# Module loading completed
ALL_MODULES.sort()

print(f"[INFO] Loaded modules: {', '.join(ALL_MODULES)}")
__all__ = ALL_MODULES + ["ALL_MODULES"]
