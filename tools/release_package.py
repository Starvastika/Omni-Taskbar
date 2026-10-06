"""Explicit source allowlist and deterministic release inventory; never glob the workspace."""
import argparse,datetime as dt,hashlib,json,marshal,re,sys,types,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell-updater'))
from engine import safe_name,semver,Updater

SOURCE_DIRS=('weather-center/app','weather-center/services','weather-center/qml','weather-center/assets','weather-center/vendor',
             'time-center/app','time-center/services','time-center/qml','time-center/map',
             'helpers/application_command_bar','helpers/active_app_center','shell-updater','distribution/defaults','distribution/licenses','distribution/fonts')
SOURCE_FILES=('version.json','LICENSE','omni_layout.py','CHANGELOG.md','README.md','THIRD_PARTY_NOTICES.md','helpers/yasb-watchdog.ps1','helpers/watchdog-maintenance.ps1',
              'weather-center/toggle.vbs','weather-center/toggle.ps1','time-center/toggle.vbs','time-center/requirements.txt',
              'weather-center/Launcher.exe','weather-center/Launcher.cpp','weather-center/build-launcher.ps1')
SOURCE_FILES=SOURCE_FILES+('distribution/runtime-base.json','distribution/source-access.json','SOURCE_ACCESS.md','distribution/font-source.json')
SUFFIXES={'.ttf','.py','.pyi','.qml','.js','.json','.geojson','.txt','.md','.ps1','.vbs','.css','.yaml','.dat','.csv','.png','.svg','.frag','.vert'}
def sources(root):
 root=Path(root);result={}
 for folder in SOURCE_DIRS:
  for p in (root/folder).rglob('*'):
   if not p.is_file() or any(x in p.parts for x in ('tests','__pycache__','data','logs','cache','exports','runtime-source')):continue
   notice=p.name.upper() in ('LICENSE','COPYING','NOTICE','METADATA') or p.name.upper().endswith(('__LICENSE','__COPYING'))
   if (p.suffix.lower() not in SUFFIXES and not notice) or p.name in ('runtime.json','runtime-settings.json'):continue
   name=p.relative_to(root).as_posix();safe_name(name);result[name]=p.read_bytes()
 for name in SOURCE_FILES:result[name]=(root/name).read_bytes()
 return result
def privacy(files):
 bad=[]
 forbidden=[re.compile(p,re.I) for p in (r'C:[\\/]+Users[\\/]+(?!Public[\\/])[^\\/ "\r\n]+',r'E:[\\/]+Downloads',r'\bgh[pousr]_[A-Za-z0-9]{25,}',r'\bgithub_pat_[A-Za-z0-9_]{30,}',r'\bsk-[A-Za-z0-9]{25,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\bBearer\s+[A-Za-z0-9_.-]{20,}')]
 for name,data in files.items():
  safe_name(name)
  text=data.decode('utf-8',errors='ignore')
  if any(pattern.search(text) for pattern in forbidden):bad.append(name)
 if bad:raise ValueError('Privacy review failed for files: '+', '.join(bad))
def sanitize_code(code,name):
 def value(v):
  if isinstance(v,types.CodeType):return sanitize_code(v,name)
  if isinstance(v,tuple):return tuple(value(x) for x in v)
  if isinstance(v,frozenset):return frozenset(value(x) for x in v)
  if isinstance(v,str) and re.search(r'C:[\\/]+Users[\\/]+',v,re.I):
   if name=='core/widgets/services/taskbar/pin_context.pyc' and v.startswith('\nSnapshot of the runtime state'):
    return re.sub(r"""C:[\\/]+Users[\\/]+[^'"\s]+""",'C:/Example/Documents',v)
   raise ValueError('Personal path constant in runtime module '+name)
  return v
 return code.replace(co_filename=name,co_consts=tuple(value(v) for v in code.co_consts))
def sanitized_library(path):
 import io
 buf=io.BytesIO()
 with zipfile.ZipFile(path) as original,zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as out:
  for item in original.infolist():
   data=original.read(item)
   if item.filename.endswith('.pyc'):data=data[:16]+marshal.dumps(sanitize_code(marshal.loads(data[16:]),item.filename))
   info=zipfile.ZipInfo(item.filename,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
   out.writestr(info,data)
 return buf.getvalue()
def build(root=ROOT,output=None,runtime=None):
 root=Path(root);output=Path(output or root/'dist');output.mkdir(parents=True,exist_ok=True)
 metadata=json.loads((root/'version.json').read_text('utf-8'));version=metadata['version'];semver(version)
 files=sources(root);privacy(files)
 overlay=root/'distribution/runtime-overlay.zip'
 files['.runtime/yasb-2.0.7/lib/library.zip']=sanitized_library(runtime or overlay)
 if (root/'dist/Omni-Taskbar.exe').exists():files['Omni-Taskbar.exe']=(root/'dist/Omni-Taskbar.exe').read_bytes()
 inventory={'version':version,'files':{n:hashlib.sha256(data).hexdigest() for n,data in sorted(files.items()) if n!='package-files.json'}}
 files['package-files.json']=json.dumps(inventory,sort_keys=True).encode()
 artifact=output/f'omni-taskbar-{version}-update.zip'
 with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as archive:
  for name,data in sorted(files.items()):
   info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,data)
 manifest={'product':'Omni Taskbar','repository':metadata['repository'],'version':version,'channel':'stable','published_at':dt.datetime.now(dt.UTC).isoformat(),'asset':artifact.name,
           'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'minimum_updater_version':metadata['updater_version'],
           'requires_shell_restart':True,'requires_windows_restart':False}
 (output/'release-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
 (output/'SHA256SUMS.txt').write_text(manifest['sha256']+'  '+artifact.name+'\n','utf-8')
 print(json.dumps({'version':version,'files':len(files),'bytes':artifact.stat().st_size,'sha256':manifest['sha256']}))
 return artifact,manifest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--runtime');a=p.parse_args();build(output=a.output,runtime=a.runtime)
