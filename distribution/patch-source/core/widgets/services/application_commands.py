"""Provider-neutral, asynchronous application command model for the Qt widget."""
from collections import OrderedDict
import copy
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication
from core.widgets.services.active_app_center import ActiveAppService

log=logging.getLogger('application_commands')
ROOT=Path.home()/'.config/yasb/helpers/application_command_bar'
PYTHON=Path.home()/'AppData/Local/Python/pythoncore-3.14-64/pythonw.exe'


def flatten(nodes):
    result=[]
    for node in nodes:
        if node['kind']=='command':result.append(node)
        result.extend(flatten(node.get('children',[])))
    return result

def menu_signature(nodes):
    # Epoch/generation/context stamps are presentation guards, not menu
    # identity. Hashing them would change the generation on an unchanged read.
    def identity(items):
        return [(n['key'],n['kind'],n['label'],n.get('shortcut',''),n.get('selector'),n.get('method'),
                 identity(n.get('children',[]))) for n in items]
    return hashlib.sha256(json.dumps(identity(nodes),sort_keys=True).encode()).hexdigest()

def search(commands,query):
    terms=query.casefold().split()
    def match(n):
        hay=' '.join([n['label'],' > '.join(n['path']),n.get('shortcut','')]).casefold()
        return all(t in hay for t in terms)
    hits=[n for n in commands if match(n)]
    return sorted(hits,key=lambda n:(not n['label'].casefold().startswith(query.casefold()),not n['enabled']))[:150]


class ProviderJob(QObject):
    completed=pyqtSignal(object,dict)
    def __init__(self,request,parent):
        super().__init__(parent)
        self.request=request;self.cancelled=False;self.reported=False
        self.process=QProcess(self)
        self.process.setProgram(str(PYTHON));self.process.setArguments([str(ROOT/'worker.py')])
        self.process.started.connect(self.write)
        self.process.finished.connect(self.finish)
        self.process.errorOccurred.connect(self.error)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout)
        self.started=time.perf_counter()
    def start(self):
        self.timer.start(1600)
        self.process.start()
    def write(self):
        self.process.write(json.dumps(self.request).encode())
        self.process.closeWriteChannel()
    def cancel(self):
        self.cancelled=True
        self.timer.stop()
        self.process.kill()  # only this disposable provider process
    def timeout(self):
        self.request['_timeout']=True
        self.process.kill()
    def error(self,error):
        if error==QProcess.ProcessError.FailedToStart:self.finish()
    def finish(self,*args):
        if self.reported:return
        self.reported=True;self.timer.stop()
        result={'ok':False,'error':'cancelled' if self.cancelled else 'provider timeout' if self.request.get('_timeout') else 'provider failed'}
        if not self.cancelled and not self.request.get('_timeout'):
            try:
                raw=bytes(self.process.readAllStandardOutput())
                if len(raw)>1048576:raise ValueError('provider output exceeds budget')
                result=json.loads(raw)
            except Exception:pass
        result['total_ms']=(time.perf_counter()-self.started)*1000
        self.completed.emit(self,result)
        self.deleteLater()


class CommandModel(QObject):
    changed=pyqtSignal()
    status_changed=pyqtSignal(str)
    _instance=None
    @classmethod
    def instance(cls):
        if cls._instance is None:cls._instance=cls()
        return cls._instance
    def __init__(self):
        super().__init__(QApplication.instance())
        self.windows=ActiveAppService.instance()
        self.context=None;self.epoch=0;self.generation=0
        self.snapshot={'provider':'fallback','menus':[],'partial':False}
        self.cache=OrderedDict();self.job=None;self.pending=None;self.closed=False
        self.diagnostics={'started':0,'cancelled':0,'timeouts':0,'rejected':0,'cache_hits':0,'durations':[]}
        self.status=''
        self.indexing=False;self.indexed=set()
        self.windows.changed.connect(self.bind)
        self.windows.row_changed.connect(self.window_changed)
        QApplication.instance().aboutToQuit.connect(self.cleanup)
        QTimer.singleShot(0,self.bind)

    def current_context(self):
        r=self.windows.active
        if r is None:return None
        return (r['hwnd'],r['process_pid'],r['key'],r['token'])

    def bind(self):
        current=self.current_context()
        if current==self.context:return  # titles/state never rediscover menus
        self.context=current;self.epoch+=1;self.generation+=1
        self.indexing=False;self.indexed.clear()
        self.pending=None
        if self.job:self.job.cancel();self.diagnostics['cancelled']+=1
        self.snapshot={'provider':'fallback','menus':[],'partial':False}
        self.status=''
        if current and current in self.cache:
            self.diagnostics['cache_hits']+=1
            self.snapshot=copy.deepcopy(self.cache[current])
            self.cache.move_to_end(current)
        self.stamp();self.changed.emit()
        if current:
            # Cached headings publish synchronously. Discovery is coalesced
            # behind a single event-loop turn; no work on hover/title events.
            QTimer.singleShot(0,lambda e=self.epoch:self.discover(e))

    def window_changed(self,hwnd,membership):
        if membership and hwnd not in self.windows.records:
            for key in list(self.cache):
                if key[0]==hwnd:self.cache.pop(key,None)
        if self.context and self.context[0]==hwnd and not self.windows.valid_target(hwnd,self.context[3]):
            self.bind()

    def stamp(self):
        def tag(nodes):
            for n in nodes:
                n['context']=self.context;n['epoch']=self.epoch;n['generation']=self.generation
                tag(n.get('children',[]))
        tag(self.snapshot['menus'])

    def request(self,op,command=None):
        if not self.context:return None
        h,pid,key,token=self.context
        req=dict(op=op,hwnd=h,pid=pid,shell_pid=os.getpid(),epoch=self.epoch,generation=self.generation,
                 provider=self.snapshot.get('provider'),signature=self.snapshot.get('signature'),root=self.snapshot.get('root'))
        if command:
            req.update(command=command,selector=command.get('selector',{}),route=command.get('selector',{}).get('route',[]),path=command['path'])
        return req

    def discover(self,epoch=None):
        if self.closed or not self.context or epoch is not None and epoch!=self.epoch:return
        req=self.request('discover');req.pop('provider',None);req.pop('root',None)
        self.submit(req)

    def refresh(self,command):
        if self.accept(command):self.submit(self.request('refresh',command))

    def index_lazy(self):
        self.indexing=True
        self.advance_index()

    def stop_index(self):
        self.indexing=False
        if self.pending and self.pending.get('_indexing'):self.pending=None
        # Let the one bounded read finish its finally/Collapse cleanup. A new
        # foreground context/action still cancels it, and the hard deadline
        # remains active if that application's provider hangs.

    def advance_index(self):
        if not self.indexing or self.job or self.pending or self.snapshot['provider']!='uia':return
        def walk(nodes):
            for n in nodes:
                if n['kind']=='submenu' and n['enabled'] and n['key'] not in self.indexed:yield n
                yield from walk(n.get('children',[]))
        node=next(walk(self.snapshot['menus']),None)
        if node and len(self.indexed)<32:
            self.indexed.add(node['key'])
            if self.accept(node):
                req=self.request('refresh',node);req['_indexing']=True;self.submit(req)
        else:self.indexing=False

    def accept(self,command):
        good=(not self.closed and self.context is not None and command.get('context')==self.context
              and command.get('epoch')==self.epoch
              and (command.get('provider')=='shell' or command.get('generation')==self.generation)
              and self.windows.valid_target(self.context[0],self.context[3]))
        if not good:
            self.diagnostics['rejected']+=1
            self.status_changed.emit('Application changed. Reopen the menu or search.')
        return good

    def invoke(self,command):
        if not self.accept(command) or not command.get('enabled') or command['kind']!='command':return False
        if command['provider']=='shell':
            action=command['action'];target=self.context
            if action=='switch':
                h,token=command['target'];return self.windows.activate(h,token)
            if action in ('minimize_all','restore_all'):
                for h in self.windows.members(target[2]):
                    record=self.windows.records[h]
                    if not record.get('is_cloaked'):self.windows.action(h,action.split('_')[0],record['token'])
            else:self.windows.action(target[0],action,target[3])
            return True
        req=self.request('invoke',command)
        self.submit(req)
        return True

    def submit(self,request):
        if not request or self.closed:return
        self.pending=request
        if self.job:
            self.job.cancel();self.diagnostics['cancelled']+=1
        else:self.start_pending()

    def start_pending(self):
        if self.closed or not self.pending:return
        request=self.pending;self.pending=None
        if request['epoch']!=self.epoch:return
        self.job=ProviderJob(request,self)
        self.job.completed.connect(self.finished)
        self.diagnostics['started']+=1
        self.job.start()

    def finished(self,job,result):
        if self.job is job:self.job=None
        req=job.request
        if not self.closed and not job.cancelled and req['epoch']==self.epoch and self.context:
            durations=self.diagnostics['durations'];durations.append(round(result['total_ms'],2));del durations[:-64]
            if result.get('ok'):
                self.status=''
                if result.get('invoked'):
                    self.cache.pop(self.context,None)
                    self.status_changed.emit('Command sent to application.')
                    # Never retry an invocation; state refresh is a new read.
                    QTimer.singleShot(0,lambda e=self.epoch:self.discover(e))
                else:
                    previous=self.snapshot.get('signature')
                    if 'subtree' in result:
                        oldkey=req['command']['key'];subtree=result['subtree']
                        def replace(nodes):
                            for i,n in enumerate(nodes):
                                if n['key']==oldkey:nodes[i]=subtree;return True
                                if replace(n.get('children',[])):return True
                            return False
                        replace(self.snapshot['menus'])
                        self.snapshot['signature']=menu_signature(self.snapshot['menus'])
                    else:self.snapshot={k:v for k,v in result.items() if k in ('provider','menus','signature','root','partial')}
                    if self.snapshot.get('signature')!=previous:self.generation+=1
                    self.stamp()
                    self.cache[self.context]=copy.deepcopy(self.snapshot)
                    while len(self.cache)>32:self.cache.popitem(last=False)
                    self.changed.emit()
                    log.info('App command provider %s: %s headings, %.1f ms',self.snapshot['provider'],len(self.snapshot['menus']),result['total_ms'])
            else:
                if req.get('_timeout'):self.diagnostics['timeouts']+=1
                self.status=result.get('error','Commands unavailable')
                self.cache.pop(self.context,None)
                # Unavailable generation must not leave stale invokable items.
                self.snapshot={'provider':'fallback','menus':[],'partial':False}
                self.generation+=1;self.changed.emit();self.status_changed.emit(self.status)
                log.warning('App commands unavailable (%s): %s',req['op'],self.status)
        if self.pending:QTimer.singleShot(0,self.start_pending)
        elif self.indexing:QTimer.singleShot(0,self.advance_index)

    def shell_commands(self):
        if not self.context:return []
        result=[]
        def add(label,action,path,target=None):
            n=dict(provider='shell',kind='command',label=label,path=path,shortcut='',enabled=True,checked=False,
                   radio=False,has_submenu=False,children=[],action=action,context=self.context,epoch=self.epoch,generation=self.generation,
                   key='shell:'+action+':'+str(target))
            if target:n['target']=target
            result.append(n)
        for h in self.windows.members(self.context[2]):
            r=self.windows.records[h]
            if not r.get('is_cloaked'):add(r['title'],'switch',['Window',r['title']],(h,r['token']))
        for label,action in (('Minimize Current','minimize'),('Maximize / Restore Current','maximize'),('Restore Current','restore'),
                             ('Close Current Window','close'),('Minimize All Windows','minimize_all'),('Restore All Windows','restore_all')):
            add(label,action,['Actions',label])
        return result

    def commands(self):
        return flatten(self.snapshot['menus'])+self.shell_commands()

    def cleanup(self):
        self.closed=True;self.pending=None;self.indexing=False
        if self.job:self.job.cancel()
        self.cache.clear()
