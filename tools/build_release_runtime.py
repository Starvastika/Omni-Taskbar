"""Build new integration modules on the reviewed, sanitized frozen 2.0.7 base."""
import hashlib,importlib.util,json,marshal,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build():
 meta=json.loads((ROOT/'distribution/runtime-base.json').read_text('utf-8'));base=ROOT/'distribution/runtime-base.zip'
 if hashlib.sha256(base.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Frozen base checksum mismatch')
 with zipfile.ZipFile(base) as a:
  if a.read('core/widgets/yasb/open_meteo.pyc')[:4]!=importlib.util.MAGIC_NUMBER:raise RuntimeError('Build requires the pinned Python 3.14 bytecode ABI')
  sys.path.insert(0,str(ROOT/'tools'));from build_runtime_support import wrapper
  destination=ROOT/'distribution/runtime-overlay.zip'
  with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as b:
   for item in a.infolist():
    data=a.read(item)
    if item.filename in ('core/widgets/yasb/open_meteo.pyc','core/widgets/yasb/power_menu.pyc'):
     name='weather_widget.py' if '/open_meteo.' in item.filename else 'power_widget.py'
     data=data[:16]+marshal.dumps(wrapper(ROOT/'shell-updater'/name,marshal.loads(data[16:])))
    elif item.filename=='core/widgets/services/application_commands.pyc':
     data=data[:16]+marshal.dumps(compile((ROOT/'helpers/application_command_bar/model.py').read_text('utf-8'),'core/widgets/services/application_commands.py','exec'))
    b.writestr(item,data)
 return destination
if __name__=='__main__':print(build())
