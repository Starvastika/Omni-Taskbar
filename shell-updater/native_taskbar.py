"""One-shot, owned Windows taskbar cutover for installed Omni only."""
from pathlib import Path
from engine import atomic,read

def state(value=None):
 import ctypes as C
 from ctypes import wintypes as W
 class AppBarData(C.Structure):
  _fields_=[('cbSize',W.DWORD),('hWnd',W.HWND),('uCallbackMessage',W.UINT),('uEdge',W.UINT),('rc',W.RECT),('lParam',W.LPARAM)]
 shell=C.windll.shell32.SHAppBarMessage;shell.argtypes=[W.DWORD,C.POINTER(AppBarData)];shell.restype=C.c_size_t
 data=AppBarData();data.cbSize=C.sizeof(data)
 find=C.windll.user32.FindWindowW;find.argtypes=[W.LPCWSTR,W.LPCWSTR];find.restype=W.HWND
 data.hWnd=find('Shell_TrayWnd',None)
 if not data.hWnd:raise RuntimeError('Windows desktop taskbar is unavailable')
 if value is not None:data.lParam=value;shell(10,C.byref(data))
 return int(shell(4,C.byref(data)))
def reserve_native_cutover(root,data):
 root=Path(root);data=Path(data)
 if not (root/'omni-installed.json').exists():return
 path=data/'shell-updater/data/native-taskbar.json';record=read(path)
 if record:return
 current=state()
 if not record:
  record={'previous':current,'applied':current|1};atomic(path,record)
 # Capture only once. Never continuously force a later user preference change.
 if current==record['previous']:state(record['applied'])
def restore_native_cutover(root,data):
 if not (Path(root)/'omni-installed.json').exists():return
 path=Path(data)/'shell-updater/data/native-taskbar.json';record=read(path)
 if record and state()==record['applied']:state(record['previous'])
 if record:path.unlink()
