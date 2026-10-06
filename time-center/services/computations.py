"""One compute worker with at most one waiting request per module."""
import threading
class Computations:
    def __init__(self,complete):
        self.complete=complete;self.pending={};self.closing=False;self.condition=threading.Condition()
        self.thread=threading.Thread(target=self.run,name='time-center-compute',daemon=True);self.thread.start()
    def submit(self,kind,generation,work):
        with self.condition:self.pending[kind]=(generation,work);self.condition.notify()
    def run(self):
        while True:
            with self.condition:
                while not self.pending and not self.closing:self.condition.wait()
                if self.closing:return
                kind=next(iter(self.pending));generation,work=self.pending.pop(kind)
            try:value=work();error=''
            except Exception as exc:value=None;error=str(exc)
            self.complete(kind,generation,value,error)
    def close(self):
        with self.condition:self.closing=True;self.pending.clear();self.condition.notify()
        self.thread.join()
