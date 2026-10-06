"""Bounded, latest-only CPU/IO jobs; all result callbacks run on the Qt owner thread."""
import logging
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject,Signal,Qt

class WorkQueue(QObject):
 completed=Signal(object)
 def __init__(self,parent=None,workers=2,limit=32,name='weather-data'):
  super().__init__(parent);self.pool=ThreadPoolExecutor(max_workers=workers,thread_name_prefix=name);self.workers=workers;self.limit=limit;self.pending=OrderedDict();self.running={};self.serial=0;self.closed=False
  self.completed.connect(self.finish,Qt.QueuedConnection)
 def submit(self,key,task,callback):
  if self.closed:return False
  if key not in self.pending and key not in self.running and len(self.pending)+len(self.running)>=self.limit:return False
  self.serial+=1;job=(self.serial,task,callback);self.pending[key]=job;self.pump();return True
 def pump(self):
  for key in tuple(self.pending):
   if len(self.running)>=self.workers:break
   if key in self.running:continue
   job=self.pending.pop(key);self.running[key]=job
   def run(key=key,job=job):
    try:value=job[1]();error=None
    except Exception as exc:value=None;error=exc
    if not self.closed:self.completed.emit((key,job,value,error))
   self.pool.submit(run)
 def finish(self,result):
  key,job,value,error=result
  if self.closed:return
  if self.running.get(key) is job:self.running.pop(key)
  # An already queued replacement supersedes a completed result.
  if key not in self.pending:
   if error:logging.warning('Weather worker %s: %s',key,error)
   try:job[2](value,error)
   except Exception:logging.exception('Weather worker callback %s failed',key)
  self.pump()
 def cancel(self,key):self.pending.pop(key,None)
 def close(self):
  self.closed=True;self.pending.clear();self.pool.shutdown(wait=True,cancel_futures=True);self.running.clear()
