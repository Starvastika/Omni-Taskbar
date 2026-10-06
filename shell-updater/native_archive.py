"""Read MSI tables/CAB streams only. Never execute installer/custom actions."""
import ctypes as C,os,shutil,subprocess,tempfile
from ctypes import wintypes as W
from pathlib import Path
def extract(msi,target):
 if os.name!='nt':raise RuntimeError('Windows archive APIs required')
 api=C.WinDLL('msi');H=W.UINT
 def method(name,args):
  fn=getattr(api,name);fn.argtypes=args;fn.restype=W.UINT;return fn
 open_db=method('MsiOpenDatabaseW',[W.LPCWSTR,C.c_void_p,C.POINTER(H)])
 view_open=method('MsiDatabaseOpenViewW',[H,W.LPCWSTR,C.POINTER(H)])
 execute=method('MsiViewExecute',[H,H]);fetch=method('MsiViewFetch',[H,C.POINTER(H)])
 string=method('MsiRecordGetStringW',[H,W.UINT,W.LPWSTR,C.POINTER(W.DWORD)])
 stream=method('MsiRecordReadStream',[H,W.UINT,C.c_void_p,C.POINTER(W.DWORD)])
 close=method('MsiCloseHandle',[H])
 def ok(code):
  if code:raise OSError('MSI archive read failed: '+str(code))
 def text(record,column):
  size=W.DWORD(0);code=string(record,column,None,C.byref(size))
  if code not in (0,234):ok(code)
  buffer=C.create_unicode_buffer(size.value+1);size.value+=1;ok(string(record,column,buffer,C.byref(size)));return buffer.value
 db=H();ok(open_db(str(Path(msi).resolve()),None,C.byref(db)))
 quote=lambda value:chr(96)+value+chr(96)
 def rows(table,columns):
  view=H();sql='SELECT '+','.join(quote(x) for x in columns)+' FROM '+quote(table);ok(view_open(db,sql,C.byref(view)))
  try:
   ok(execute(view,0));result=[]
   while True:
    record=H();code=fetch(view,C.byref(record))
    if code==259:break
    ok(code)
    try:result.append(tuple(text(record,i+1) for i in range(len(columns))))
    finally:close(record)
   return result
  finally:close(view)
 try:
  files=rows('File',('File','Component_','FileName'));components=dict(rows('Component',('Component','Directory_')))
  directories={key:(parent,name) for key,parent,name in rows('Directory',('Directory','Directory_Parent','DefaultDir'))}
  executables=[r for r in files if r[2].split('|')[-1].casefold()=='yasb.exe']
  if len(executables)!=1:raise ValueError('Ambiguous YASB runtime archive')
  base=components[executables[0][1]]
  def relative(directory):
   parts=[];seen=set()
   while directory!=base:
    if directory in seen or directory not in directories:raise ValueError('Directory outside native runtime')
    seen.add(directory);parent,name=directories[directory];part=name.split(':')[0].split('|')[-1]
    if part not in ('.',''):parts.insert(0,part)
    directory=parent
   if any(x in ('..','') or '/' in x or '\\' in x or ':' in x for x in parts):raise ValueError('Unsafe MSI directory')
   return Path(*parts)
  cabinets=[cab[1:] for _,cab in rows('Media',('DiskId','Cabinet')) if cab.startswith('#')]
  if not cabinets:raise ValueError('No embedded cabinets')
  target=Path(target);target.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='yasb-native-cab-') as tmp:
   folder=Path(tmp);flat=folder/'files';flat.mkdir()
   for index,cabinet in enumerate(cabinets):
    # Media identifiers are data, never shell command strings.
    if "'" in cabinet:raise ValueError('Unexpected cabinet identifier')
    view=H();sql='SELECT '+quote('Data')+' FROM '+quote('_Streams')+' WHERE '+quote('Name')+"='"+cabinet+"'"
    ok(view_open(db,sql,C.byref(view)))
    record=H()
    try:
     ok(execute(view,0));ok(fetch(view,C.byref(record)));cab=folder/f'{index}.cab'
     with cab.open('wb') as output:
      total=0
      while True:
       buffer=C.create_string_buffer(65536);size=W.DWORD(len(buffer));ok(stream(record,1,buffer,C.byref(size)))
       if not size.value:break
       total+=size.value
       if total>256*1024*1024:raise ValueError('Cabinet exceeds limit')
       output.write(buffer.raw[:size.value])
     result=subprocess.run([str(Path(os.environ['WINDIR'])/'System32/expand.exe'),'-F:*',str(cab),str(flat)],capture_output=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
     if result.returncode:raise RuntimeError('Native cabinet extraction failed')
    finally:
     if record.value:close(record)
     close(view)
   count=0
   for key,component,name in files:
    try:directory=relative(components[component])
    except ValueError:continue
    filename=name.split('|')[-1]
    if any(x in filename for x in ('/','\\',':')) or filename in ('.','..'):raise ValueError('Unsafe native filename')
    source=flat/key
    if not source.exists():raise ValueError('Native archive file missing')
    if source.is_symlink():raise ValueError('Native archive symlink')
    dest=target/directory/filename;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);count+=1
   if not (target/'yasb.exe').exists() or not (target/'lib/library.zip').exists():raise ValueError('Native runtime incomplete')
   return count
 finally:close(db)
