"""One sleeping writer, coalescing pending snapshots per file; atomic replace."""
import json
import logging
import os
import threading

class AtomicWriter:
    def __init__(self):
        self.condition=threading.Condition();self.pending={};self.closing=False;self.failure=None
        self.thread=threading.Thread(target=self.run,name='time-center-storage',daemon=True);self.thread.start()
    def submit(self,path,data):
        with self.condition:
            self.pending[path]=data;self.condition.notify()
    def run(self):
        while True:
            with self.condition:
                while not self.pending and not self.closing:self.condition.wait()
                if not self.pending:return
                path=next(iter(self.pending));data=self.pending.pop(path)
            try:
                temporary=path.with_suffix('.tmp')
                with temporary.open('w',encoding='utf-8') as f:
                    json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
                os.replace(temporary,path)
            except Exception as exc:
                self.failure=exc;logging.exception('Atomic state write failed; previous file retained')
    def close(self):
        with self.condition:self.closing=True;self.condition.notify()
        self.thread.join()
        if self.failure:raise self.failure
