"""One hidden shell host. Clients use a user-scoped Windows local socket."""
import argparse
import ctypes
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import site
site.addsitedir(str(ROOT/".venv/Lib/site-packages"))
NAME='YasbTimeCenter-'+hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:16]
from PySide6.QtCore import QCoreApplication,QLockFile,QTimer,QUrl,Qt,qInstallMessageHandler
from PySide6.QtNetwork import QLocalServer,QLocalSocket

def send(command):
    client=QLocalSocket();client.connectToServer(NAME)
    if not client.waitForConnected(350):return None
    client.write((json.dumps(command)+'\n').encode());client.waitForBytesWritten(500)
    deadline=time.monotonic()+2;raw=b''
    while time.monotonic()<deadline:
        if client.bytesAvailable() or client.waitForReadyRead(200):
            raw+=bytes(client.readAll())
            if b'\n' in raw:
                try:return json.loads(raw.split(b'\n')[0])
                except ValueError:return {'error':'Invalid host response'}
    return {'error':'Host did not respond'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--toggle',action='store_true');parser.add_argument('--hide',action='store_true');parser.add_argument('--quit',action='store_true');parser.add_argument('--status',action='store_true');parser.add_argument('--command');args=parser.parse_args()
    command=json.loads(args.command) if args.command else {'command':'toggle' if args.toggle else 'hide' if args.hide else 'quit' if args.quit else 'status'}
    if command.get('command')=='toggle':
        existing=send({'command':'status'})
        if existing and existing.get('pid'):ctypes.windll.user32.AllowSetForegroundWindow(existing['pid'])
    response=send(command)
    if response is not None:
        if sys.stdout:print(json.dumps(response,ensure_ascii=False))
        return 0
    if args.hide or args.quit or args.status or args.command:
        if sys.stdout:print(json.dumps({'running':False}))
        return 1
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine,qmlRegisterType
    from PySide6.QtQuickControls2 import QQuickStyle
    from app.bridge import Bridge
    from app.models import StableModel
    from shiboken6 import isValid
    qmlRegisterType(StableModel,'TimeCenter',1,0,'StableModel')
    (ROOT/'logs').mkdir(exist_ok=True);(ROOT/'data').mkdir(exist_ok=True)
    handler=RotatingFileHandler(ROOT/'logs/time-center.log',maxBytes=131072,backupCount=2,encoding='utf-8');handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));logging.basicConfig(level=logging.INFO,handlers=[handler])
    sys.excepthook=lambda kind,error,trace:logging.error('Unhandled exception',exc_info=(kind,error,trace))
    qInstallMessageHandler(lambda mode,context,message:logging.warning('Qt: %s',message))
    QQuickStyle.setStyle('Basic');app=QGuiApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setApplicationName('YASB Time Center')
    lock=QLockFile(str(ROOT/'data/host.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):send(command);return 0
    server=QLocalServer();server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption);QLocalServer.removeServer(NAME)
    if not server.listen(NAME):logging.error('IPC socket failed: %s',server.errorString());return 1
    bridge=Bridge(ROOT);engine=QQmlApplicationEngine();engine.addImageProvider('world',bridge.mapImages);engine.rootContext().setContextProperty('bridge',bridge)
    engine.load(QUrl.fromLocalFile(str(ROOT/'qml/Main.qml')))
    if not engine.rootObjects():logging.error('QML did not load');return 1
    window=engine.rootObjects()[0]
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.GetForegroundWindow.restype=ctypes.c_void_p;user32.SetForegroundWindow.argtypes=[ctypes.c_void_p]
    user32.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
    def activate():
        target=int(window.winId())
        if user32.SetForegroundWindow(target):return
        # Only the explicit clock toggle uses this short input-queue attachment.
        foreground=user32.GetForegroundWindow()
        thread=user32.GetWindowThreadProcessId(foreground,None) if foreground else 0
        current=ctypes.windll.kernel32.GetCurrentThreadId()
        attached=bool(thread and thread!=current and user32.AttachThreadInput(current,thread,True))
        try:user32.SetForegroundWindow(target)
        finally:
            if attached:user32.AttachThreadInput(current,thread,False)
    previous=[None]
    def show(focus=False):
        if not window.isVisible():previous[0]=user32.GetForegroundWindow()
        screen=app.primaryScreen();area=screen.availableGeometry();window.setGeometry(area)
        bridge.setVisible(True);window.reveal()
        if focus:activate()
    def hide():
        if window.isVisible():window.conceal()
        bridge.setVisible(False)
        if previous[0] and user32.GetForegroundWindow()==int(window.winId()):user32.SetForegroundWindow(previous[0])
    def toggle():hide() if window.isVisible() else show(True)
    bridge.hideRequested.connect(hide);bridge.alertRaised.connect(lambda message:show())
    clients=[]
    def connected():
        while server.hasPendingConnections():
            socket=server.nextPendingConnection();clients.append(socket);socket.setProperty('buffer',b'')
            def read(s=socket):
                raw=s.property('buffer')+bytes(s.readAll())
                if b'\n' not in raw:s.setProperty('buffer',raw);return
                try:
                    message=json.loads(raw.split(b'\n')[0]);cmd=message.get('command','status')
                    if cmd=='toggle':toggle()
                    elif cmd=='hide':hide()
                    elif cmd=='quit':QTimer.singleShot(100,lambda:app.exit(0))
                    elif cmd=='action':bridge.act(message['action'],json.dumps(message.get('payload',{})))
                    elif cmd=='page':window.setProperty('page',max(0,min(8,int(message['page']))))
                    elif cmd=='calendar':bridge.calendarGo(message['year'],message['month'],message['selected'])
                    elif cmd=='search':bridge.searchCity(message['query'])
                    response={'running':True,'pid':os.getpid(),'visible':window.isVisible(),'geometry':[window.x(),window.y(),window.width(),window.height()],'state':bridge.engine.snapshot() if cmd in ('status','action') else None,'status':bridge.status,'results':bridge.results if cmd=='status' else []}
                except Exception as exc:response={'error':str(exc)}
                s.write((json.dumps(response,ensure_ascii=False)+'\n').encode());s.flush();s.disconnectFromServer()
            socket.readyRead.connect(read)
            def disconnected(s=socket):
                if s in clients:clients.remove(s)
                if isValid(s):s.deleteLater()
            socket.disconnected.connect(disconnected)
    server.newConnection.connect(connected)
    pidfile=ROOT/'data/host.json';pidfile.write_text(json.dumps({'pid':os.getpid(),'started':time.time(),'executable':sys.executable,'baseExecutable':sys._base_executable}),encoding='utf-8')
    def quit_cleanly():
        bridge.shutdown();server.close();lock.unlock()
        try:pidfile.unlink()
        except OSError:pass
        logging.info('Host stopped')
    app.aboutToQuit.connect(quit_cleanly)
    logging.info('Host started hidden; pid=%s',os.getpid())
    if args.toggle:QTimer.singleShot(0,lambda:show(True))
    return app.exec()

if __name__=='__main__':raise SystemExit(main())
