"""Read YASB's shipped Python modules without installing packages or starting a bar."""
import importlib.abc
import importlib.util
import os
from pathlib import Path
import shutil
import sys

INSTALL = Path(os.environ['YASB_NATIVE_RUNTIME'])
LIB = INSTALL / 'lib'
DLL_HANDLES = [os.add_dll_directory(str(INSTALL)), os.add_dll_directory(str(LIB))]
sys.path[:0] = [str(LIB / 'library.zip'), str(LIB)]
sys.dont_write_bytecode = True


class FrozenExtensions(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        for candidate in LIB.glob(fullname + '*.pyd'):
            if candidate.name == fullname + '.pyd' or candidate.name.startswith(fullname + '.cp'):
                return importlib.util.spec_from_file_location(fullname, candidate)
        return None


sys.meta_path.insert(0, FrozenExtensions())
