"""One program/data resolver; legacy source checkouts keep their existing paths."""
import os,sys
from pathlib import Path
def program_root(fallback=None):
 if fallback:return Path(fallback).resolve()
 value=os.environ.get('OMNI_PROGRAM_ROOT')
 if value:return Path(value).resolve()
 return Path.home()/'.config/yasb'
def user_root(program=None):
 value=os.environ.get('OMNI_USER_ROOT')
 if value:return Path(value).resolve()
 root=program_root(program)
 marker=root/'omni-installed.json'
 if marker.exists():
  import json
  metadata=json.loads(marker.read_text('utf-8'))
  return Path(os.path.expandvars(metadata['user_root'])).resolve()
 return root
def component_data(name,program=None):
 return user_root(program)/name
def runtime_python(program=None):
 root=program_root(program);embedded=root/'runtime/python/python.exe'
 if embedded.exists():return embedded
 import json
 try:return Path(json.loads((user_root(root)/'helpers/runtime-settings.json').read_text('utf-8'))['python'])
 except (OSError,ValueError,KeyError):return Path(sys.executable)
def child_environment(program=None,user=None):
 root=program_root(program);data=Path(user).resolve() if user else user_root(root)
 return dict(os.environ,OMNI_PROGRAM_ROOT=str(root),OMNI_USER_ROOT=str(data),YASB_CONFIG_HOME=str(data))

_fonts_loaded=False
def load_bar_fonts():
 """Private application fonts; no system font registration or elevation."""
 global _fonts_loaded
 if _fonts_loaded:return
 from PyQt6.QtGui import QFontDatabase
 for font in (program_root()/'distribution/fonts').glob('*.ttf'):
  QFontDatabase.addApplicationFont(str(font))
 _fonts_loaded=True
