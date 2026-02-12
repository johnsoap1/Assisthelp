# wbb/modules/__init__.py
import glob
from os.path import basename, dirname, isfile

def list_all_modules():
    mod_paths = glob.glob(dirname(__file__) + "/*.py")
    
    all_modules = [
        basename(f)[:-3]
        for f in mod_paths
        if isfile(f) and f.endswith(".py") and not f.endswith("__init__.py")
    ]
    
    return all_modules

ALL_MODULES = list_all_modules()
