"""Readable patch recipe for the frozen base, against verified upstream 2.0.7."""
import importlib.util,marshal,types,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build(upstream,output):
 source=ROOT/'distribution/patch-source'
 def compile_file(p,name):return compile(p.read_text('utf-8'),name,'exec')
 methods={c.co_name:c for c in compile_file(source/'event-methods.py','core/event-methods.py').co_consts if isinstance(c,types.CodeType)}
 def replace(code):
  if code.co_name in methods:return methods[code.co_name].replace(co_filename=code.co_filename)
  return code.replace(co_consts=tuple(replace(c) if isinstance(c,types.CodeType) else c for c in code.co_consts))
 with zipfile.ZipFile(upstream) as a,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as b:
  files={p.relative_to(source).as_posix()+'c':p for p in (source/'core').rglob('*.py')}
  header=importlib.util.MAGIC_NUMBER+b'\0'*12
  for item in a.infolist():
   data=a.read(item)
   if item.filename in files:
    data=data[:16]+marshal.dumps(compile_file(files.pop(item.filename),item.filename))
   elif item.filename=='core/bar.pyc':
    original=marshal.loads(data[16:]);wrapper=compile_file(source/'bar-wrapper.py',item.filename)
    wrapper=wrapper.replace(co_consts=tuple(original if c=='__YASB_CURRENT_BAR_CODE__' else c for c in wrapper.co_consts))
    data=data[:16]+marshal.dumps(wrapper)
   elif item.filename=='core/utils/win32/event_listener.pyc':data=data[:16]+marshal.dumps(replace(marshal.loads(data[16:])))
   b.writestr(item,data)
  for name,p in files.items():b.writestr(name,header+marshal.dumps(compile_file(p,name)))
 return output
def fingerprint(code):
 def value(v):
  if isinstance(v,types.CodeType):return fingerprint(v)
  if isinstance(v,tuple):return tuple(value(x) for x in v)
  if isinstance(v,str) and 'Snapshot of the runtime state' in v:return '<doc>'
  return v
 return code.co_code,code.co_names,code.co_varnames,code.co_freevars,code.co_cellvars,tuple(value(x) for x in code.co_consts)
def verify(upstream,output):
 build(upstream,output)
 with zipfile.ZipFile(output) as a,zipfile.ZipFile(ROOT/'distribution/runtime-base.zip') as b:
  assert set(a.namelist())==set(b.namelist())
  mismatch=[]
  for name in a.namelist():
   x=a.read(name);y=b.read(name)
   if name.endswith('.pyc'):
    if fingerprint(marshal.loads(x[16:]))!=fingerprint(marshal.loads(y[16:])):mismatch.append(name)
   elif x!=y:mismatch.append(name)
  if mismatch:raise ValueError('Readable base source mismatch: '+', '.join(mismatch))
 return True
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--upstream',required=True);p.add_argument('--output',required=True);a=p.parse_args();verify(a.upstream,Path(a.output));print('Every modified frozen module has verified readable corresponding source')
