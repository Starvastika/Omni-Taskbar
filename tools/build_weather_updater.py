"""Narrow live staging; wrappers reuse the exact installed widget code objects."""
import hashlib,json,marshal,shutil,types,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'.validation/weather-updater'
base=out/'before-library.zip';source=root/'shell-updater'
def wrap(name,code):
 return compile((source/name).read_text('utf-8'),'shell-updater/'+name,'exec').replace(
  co_consts=tuple(code if c=='__YASB_BASE_CODE__' else c for c in compile((source/name).read_text('utf-8'),'shell-updater/'+name,'exec').co_consts))
changes={'core/widgets/yasb/open_meteo.pyc':'weather_widget.py','core/widgets/yasb/power_menu.pyc':'power_widget.py'}
with zipfile.ZipFile(base) as a,zipfile.ZipFile(out/'library.zip','w',zipfile.ZIP_DEFLATED) as b:
 for item in a.infolist():
  data=a.read(item)
  if item.filename in changes:data=data[:16]+marshal.dumps(wrap(changes[item.filename],marshal.loads(data[16:])))
  elif item.filename=='core/widgets/services/application_commands.pyc':
   data=data[:16]+marshal.dumps(compile((root/'helpers/application_command_bar/model.py').read_text('utf-8'),'core/widgets/services/application_commands.py','exec'))
  b.writestr(item,data)
with zipfile.ZipFile(base) as a,zipfile.ZipFile(out/'library.zip') as b:
 changed=[n for n in a.namelist() if a.read(n)!=b.read(n)]
 assert set(changed)==set(changes)|{'core/widgets/services/application_commands.pyc'}
manifest={'before_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'after_sha256':hashlib.sha256((out/'library.zip').read_bytes()).hexdigest(),'changed':changed}
(out/'build.json').write_text(json.dumps(manifest,indent=2),'utf-8');print(json.dumps(manifest,indent=2))
