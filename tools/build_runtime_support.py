"""Embed installed code objects without decompiling or replacing their behavior."""
from pathlib import Path
def wrapper(path,base):
 path=Path(path);compiled=compile(path.read_text('utf-8'),'shell-updater/'+path.name,'exec')
 return compiled.replace(co_consts=tuple(base if c=='__YASB_BASE_CODE__' else c for c in compiled.co_consts))
