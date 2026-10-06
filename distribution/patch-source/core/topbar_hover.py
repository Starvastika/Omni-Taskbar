"""Protected maximize/Snap hover, and zero-interaction fullscreen, YASB 2.0.7.

Window tracking uses the existing filtered native EventService. Only revealable
states sample cursor position at 8 Hz; there is never an input-sensor HWND or a
mouse hook. Native AppBar changes occur once per transition, not per frame.
"""
import ctypes
from ctypes import wintypes
import logging
import os
from time import perf_counter

import win32api
import win32gui
import win32process
from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication
from core.events.service import EventService
from core.events.win32 import WinEvent
from core.topbar_visibility import (
    area, covers, intersect, union_area, eligible, frame_bounds, root_owner,
    DESKTOP_CLASSES, SHELL_CLASSES, USER,
)
from core.utils.win32.app_bar import AppBarData, AppBarEdge, AppBarMessage, APPBAR_CALLBACK_MESSAGE

FLOATING = 'FLOATING_VISIBLE'
MAXIMIZED = 'MAXIMIZED_HIDDEN'
SNAP = 'SNAP_HIDDEN'
FULLSCREEN = 'FULLSCREEN_HIDDEN'
REVEALABLE = (MAXIMIZED, SNAP)
WS_THICKFRAME = 0x00040000
SHELL = ctypes.WinDLL('shell32').SHAppBarMessage
SHELL.argtypes = [wintypes.DWORD, ctypes.POINTER(AppBarData)]
SHELL.restype = ctypes.c_size_t
USER.GetPhysicalCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
USER.GetPhysicalCursorPos.restype = wintypes.BOOL
USER.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER.GetWindowDisplayAffinity.restype = wintypes.BOOL
USER.SetWindowPos.argtypes = [wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
USER.SetWindowPos.restype = wintypes.BOOL


def cursor_position():
    point = wintypes.POINT()
    if not USER.GetPhysicalCursorPos(ctypes.byref(point)):
        return None
    return point.x, point.y


def client_bounds(hwnd):
    client = win32gui.GetClientRect(hwnd)
    x, y = win32gui.ClientToScreen(hwnd, (0, 0))
    return x, y, x+client[2], y+client[3]


def classify(frame, monitor, work, zoomed=False, resizable=True, client=None,
             tolerance=3, was_snap=False, tiled=(), native_fullscreen=False):
    """Fullscreen has priority, including borderless work-area-sized modes.

    tiled is (HWND, frame) pairs in z-order. Return participating HWNDs with the
    decision so reveal checks every app that could occupy the reserved strip.
    """
    full_monitor = covers(frame, monitor, tolerance) or covers(client, monitor, tolerance)
    # If work == monitor, a normally styled maximized app is ambiguous solely
    # from geometry. Native resize chrome + maximize permits ordinary maximize.
    work_equals_monitor = all(abs(a-b) <= tolerance for a,b in zip(work,monitor))
    if native_fullscreen or (full_monitor and not (work_equals_monitor and zoomed and resizable)):
        return FULLSCREEN, 'physical monitor/client coverage or native fullscreen', []
    if not resizable and covers(frame, work, tolerance):
        return FULLSCREEN, 'borderless/windowed-fullscreen work-area coverage', []
    if zoomed:
        return MAXIMIZED, 'IsZoomed / SW_SHOWMAXIMIZED with ordinary resize chrome', []
    if resizable and covers(frame, work, tolerance):
        return MAXIMIZED, 'ordinary resizable work-area-sized frame', []
    if frame:
        hysteresis = 2 if was_snap else 0
        if (abs(frame[1]-work[1]) <= tolerance+hysteresis
                and frame[3] >= work[3]-tolerance-hysteresis
                and frame[2]-frame[0] >= (work[2]-work[0])*0.20
                and intersect(frame, work)):
            return SNAP, 'full-height work-area tile', []
    selected = [intersect(frame,work)] if frame and intersect(frame,work) else []
    participants = []
    for hwnd, rect in tiled:
        rect = intersect(rect,work)
        if not rect or area(rect) < area(work)*0.035 or area(rect) > area(work)*0.94:
            continue
        if any(area(intersect(rect,old)) > min(area(rect),area(old))*0.08 for old in selected):
            continue
        selected.append(rect)
        participants.append(hwnd)
    coverage = union_area(selected)/area(work) if area(work) else 0
    if len(selected)>1 and coverage >= (0.965 if was_snap else 0.975):
        return SNAP, f'participating tiled union {coverage:.1%}', participants
    return FLOATING, 'restored/floating foreground or exposed desktop', []


class WindowStateVisibility(QObject):
    changed = pyqtSignal(object, object)
    managed_appbar = True

    def __init__(self, bar_widget, parent=None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self.service = EventService()
        self.events = ('topbar_window_state',)
        self.mode = None
        self.phase = 'HIDDEN'
        self.reason = 'initializing'
        self.hidden = True
        self.last_local = None
        self.targets = []
        self.moving = None
        self.monitor_id = None
        self.locations = {}
        self.reservation = False
        self.reserved_rect = None
        self.base_work = None
        self.generation = 0
        self.guard_until = 0.0
        self.closed = False
        self.edge_armed = False
        self.native_fullscreen_hwnd = None
        self.evaluations = 0
        self.evaluation_ms = 0.0
        self.cursor_samples = 0
        self.reservation_updates = 0
        self.constructing = True
        self.presentation_hwnd = None
        self.placement_pending = {}
        self.placement_attempts = {}
        self.placement_checks = 0
        self.placement_moves = 0
        self.placement_suspended = False
        self.placement_safety = set()
        self.floating_blocked = {}
        self.placement_timer = self.single_timer(120,self.validate_placements)
        self.desktop_service = None
        try:
            from core.widgets.services.windows_desktops.service import WindowsDesktopService
            self.desktop_service=WindowsDesktopService._instance
            if self.desktop_service is not None:
                self.desktop_service.desktop_changed.connect(self.desktop_changed)
        except Exception:logging.debug('Existing desktop signal unavailable',exc_info=True)
        self._original_show = bar_widget.show
        self._original_show_bar = bar_widget.show_bar
        bar_widget.show = self.guarded_show
        bar_widget.show_bar = self.guarded_show_bar
        bar_widget._autohide_bar = False
        self.timer = self.single_timer(75, self.evaluate)
        self.dwell_timer = self.single_timer(100, self.begin_reveal)
        self.hide_timer = self.single_timer(450, self.begin_hide)
        self.reflow_timer = self.single_timer(20, self.verify_reflow)
        self.finish_timer = self.single_timer(20, self.finish_transition)
        self.pointer_timer = QTimer(self)
        self.pointer_timer.setInterval(125)
        self.pointer_timer.timeout.connect(self.pointer_probe)
        self.changed.connect(self.queue, Qt.ConnectionType.QueuedConnection)
        for event in self.events:
            self.service.register_event(event,self.changed)
        bar_widget._target_screen.geometryChanged.connect(self.screen_changed)
        bar_widget._target_screen.availableGeometryChanged.connect(self.screen_changed)
        # Classify before Bar.__init__'s final show. Fullscreen/max/Snap startup
        # must not briefly fade in merely because the bar was constructed.
        self.evaluate()
        self.constructing = False
        if self.mode != FLOATING:
            bar_widget._initial_show = False

    def single_timer(self, interval, callback):
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(interval)
        timer.timeout.connect(callback)
        return timer

    def monitor_info(self):
        if self.monitor_id is None:
            self.monitor_id = next((m[0] for m in win32api.EnumDisplayMonitors()
                                    if win32api.GetMonitorInfo(m[0])['Device'] == self.bar_widget._target_screen.name()),
                                   self.bar_widget.monitor_hwnd)
        return win32api.GetMonitorInfo(self.monitor_id)

    def screen_changed(self,*_):
        self.monitor_id = None
        if not self.closed:
            self.timer.start()

    def guarded_show(self):
        if self.reservation and not self.constructing and not self.placement_suspended and (self.mode == FLOATING or (self.mode in REVEALABLE and self.phase in ('REVEALING','REVEALED'))):
            self._original_show()

    def guarded_show_bar(self):
        if self.reservation and not self.constructing and not self.placement_suspended and (self.mode == FLOATING or (self.mode in REVEALABLE and self.phase in ('REVEALING','REVEALED'))):
            self._original_show_bar()

    def local_windows(self):
        result=[]
        def visit(hwnd,_):
            if eligible(hwnd) and win32api.MonitorFromWindow(hwnd,2)==self.monitor_id and root_owner(hwnd)==hwnd:
                result.append(hwnd)
        win32gui.EnumWindows(visit,None)
        return result

    def foreground(self):
        hwnd=win32gui.GetForegroundWindow()
        if hwnd and win32gui.GetClassName(hwnd) in DESKTOP_CLASSES:
            return 0
        hwnd=root_owner(hwnd) if hwnd else None
        if not eligible(hwnd):
            own=hwnd and win32process.GetWindowThreadProcessId(hwnd)[1]==os.getpid()
            return self.last_local if own and eligible(self.last_local) else None
        if win32api.MonitorFromWindow(hwnd,2)==self.monitor_id:
            return hwnd
        if eligible(self.last_local) and win32api.MonitorFromWindow(self.last_local,2)==self.monitor_id:
            return self.last_local
        windows=self.local_windows()
        return windows[0] if windows else 0

    def detect(self, hwnd, info, tiled=()):
        frame=frame_bounds(hwnd)
        tolerance=max(3,round((USER.GetDpiForWindow(hwnd) or 96)/96*3))
        zoomed=bool(USER.IsZoomed(hwnd) or win32gui.GetWindowPlacement(hwnd)[1]==3)
        resizable=bool(win32gui.GetWindowLong(hwnd,-16)&WS_THICKFRAME)
        result=classify(frame,info['Monitor'],info['Work'],zoomed,resizable,client_bounds(hwnd),
                        tolerance,self.mode==SNAP,tiled,self.native_fullscreen_hwnd==hwnd)
        # A just-created/restored tile may still use the pre-reservation rect.
        # Recognize its state before considering any restored-window correction.
        if result[0]==FLOATING and self.reservation and self.base_work:
            previous=classify(frame,info['Monitor'],self.base_work,zoomed,resizable,client_bounds(hwnd),
                              tolerance,self.mode==SNAP,tiled,self.native_fullscreen_hwnd==hwnd)
            if previous[0]==SNAP:return previous
        return result

    def queue(self,hwnd,event):
        if self.closed:return
        if event==WinEvent.EventObjectDestroy:
            self.placement_pending.pop(hwnd,None);self.placement_attempts.pop(hwnd,None)
            self.locations.pop(hwnd,None)
            self.placement_safety.discard(hwnd)
            self.floating_blocked.pop(hwnd,None)
        # Fullscreen entry must cancel an in-flight reveal, including resize
        # drags, before debounce or a work-area feedback guard can postpone it.
        if event in (WinEvent.EventSystemForeground,WinEvent.EventObjectLocationChange):
            try:
                info=self.monitor_info()
                candidate=root_owner(hwnd) if eligible(hwnd) else None
                if candidate and candidate==self.foreground() and win32api.MonitorFromWindow(candidate,2)==self.monitor_id:
                    if self.detect(candidate,info)[0]==FULLSCREEN:
                        self.last_local=candidate
                        self.set_mode(FULLSCREEN,'fullscreen entry: immediate protection',[candidate])
                        return
            except (OSError,win32gui.error):pass
        if event==WinEvent.EventSystemMoveSizeStart:
            self.placement_pending.pop(hwnd,None)
            self.moving=hwnd;self.timer.stop();return
        if event==WinEvent.EventSystemMoveSizeEnd:
            self.moving=None;self.timer.start()
            if self.placement_suspended:self.placement_timer.start()
            return
        if self.moving:
            if event==WinEvent.EventObjectDestroy and hwnd==self.moving:self.moving=None
            else:return
        if event not in (WinEvent.EventSystemForeground,WinEvent.EventSystemSwitchEnd):
            try:
                if hwnd and win32gui.IsWindow(hwnd):
                    if win32gui.GetAncestor(hwnd,2)!=hwnd:return
                    if win32process.GetWindowThreadProcessId(hwnd)[1]==os.getpid():return
                    if win32gui.GetClassName(hwnd) in SHELL_CLASSES:return
                    if event==WinEvent.EventObjectLocationChange:
                        bounds=frame_bounds(hwnd)
                        if self.locations.get(hwnd)==bounds:return
                        if len(self.locations)>=64:self.locations.clear()
                        self.locations[hwnd]=bounds
                elif event!=WinEvent.EventObjectDestroy:return
            except win32gui.error:return
        self.timer.start()
        if event in (WinEvent.EventObjectShow,WinEvent.EventSystemForeground,WinEvent.EventSystemMinimizeEnd):
            self.queue_placement(hwnd)
        if self.placement_suspended and not self.placement_timer.isActive():self.placement_timer.start()

    def evaluate(self):
        if self.closed:return
        start=perf_counter()
        try:
            info=self.monitor_info();hwnd=self.foreground()
            if hwnd is None:return  # harmless shell transient
            if hwnd==0:
                self.set_mode(FLOATING,'desktop active/exposed',[]);return
            self.last_local=hwnd
            mode,reason,participants=self.detect(hwnd,info)
            if mode==FLOATING:
                tiles=[(w,frame_bounds(w)) for w in self.local_windows() if w!=hwnd]
                mode,reason,participants=self.detect(hwnd,info,tiles)
            if mode==SNAP and not participants:
                # Full-height Snap can classify from the foreground alone,
                # but reveal must verify its other visible tiles as well.
                chosen=[intersect(frame_bounds(hwnd),info['Work'])]
                for other in self.local_windows():
                    if other==hwnd:continue
                    rect=intersect(frame_bounds(other),info['Work'])
                    if not rect or not 0.035<=area(rect)/area(info['Work'])<=0.94:continue
                    if any(area(intersect(rect,r))>min(area(rect),area(r))*0.08 for r in chosen):continue
                    chosen.append(rect);participants.append(other)
            if mode!=FULLSCREEN and perf_counter()<self.guard_until and hwnd in self.targets:
                # Self-induced Snap/work-area transitions may momentarily
                # report restored geometry. Keep the originating logical mode.
                if self.mode in REVEALABLE and not (self.mode==MAXIMIZED and not USER.IsZoomed(hwnd)):
                    if mode!=self.mode:
                        self.timer.start(max(1,round((self.guard_until-perf_counter())*1000)+10))
                    mode=self.mode;reason='native reflow guard: '+reason
            self.set_mode(mode,reason,[hwnd]+participants)
        except Exception:
            logging.debug('Protected top-bar evaluation unavailable',exc_info=True)
        finally:
            self.evaluations+=1
            self.evaluation_ms+=(perf_counter()-start)*1000

    def set_mode(self,mode,reason,targets):
        old=self.mode
        self.reason=reason
        new_foreground=bool(targets and targets[0]!=self.presentation_hwnd)
        self.targets=targets
        if old==mode and not (mode in REVEALABLE and new_foreground and self.phase in ('RESERVING','REVEALING','REVEALED','HIDING','PLACEMENT_SAFETY')):
            if mode==FLOATING and not self.bar_widget.isVisible() and self.bar_widget._animation_manager._animation is None:
                self.show_floating()
            return
        self.generation+=1
        self.mode=mode
        self.dwell_timer.stop();self.hide_timer.stop();self.reflow_timer.stop();self.finish_timer.stop()
        if mode==FULLSCREEN:
            self.placement_timer.stop();self.placement_pending.clear()
            self.placement_suspended=False;self.placement_safety.clear()
            self.pointer_timer.stop()
            self.dismiss_popups()
            self.hide_immediate()
            self.release_reservation()
            self.phase='HIDDEN';self.hidden=True;self.edge_armed=False
        elif mode==FLOATING:
            self.pointer_timer.stop()
            # Ownership changes MUST NOT drop a reservation underneath a
            # visible/revealing bar. Reuse it when switching to floating mode.
            self.show_floating()
        else:
            self.placement_timer.stop();self.placement_pending.clear()
            self.placement_suspended=False;self.placement_safety.clear()
            self.dismiss_popups()
            self.hide_immediate()
            self.release_reservation()
            self.phase='HIDDEN';self.hidden=True
            # Returning from fullscreen does not auto-open a bar under a
            # stationary top-edge pointer. New entry from outside is required.
            self.edge_armed=not self.at_edge(cursor_position())
            self.pointer_timer.start()
        self.presentation_hwnd=targets[0] if targets else None
        logging.info('Top-bar mode %s: %s',mode,reason)

    def show_floating(self):
        try:
            for hwnd,(identity,strip) in list(self.floating_blocked.items()):
                if eligible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)==identity and intersect(frame_bounds(hwnd),strip):
                    self.phase='HIDDEN';self.hidden=True;return
                self.floating_blocked.pop(hwnd,None)
            if not self.reservation:
                from core.bar_helper import SystrayAppBarHelper
                SystrayAppBarHelper.execute_without_systray_interference(self.reserve_native)
            self.position_bar()
            if self.monitor_info()['Work'][1]<self.reserved_rect[3]:
                raise RuntimeError('Floating reservation not yet reflected by Windows')
            # Initial/restore visibility is an event, not an idle enumerator.
            for hwnd in self.local_windows():self.queue_placement(hwnd)
            self.phase='PLACEMENT_SAFETY' if self.placement_suspended else 'VISIBLE'
            self.hidden=self.placement_suspended
            if not self.bar_widget.isVisible():self.guarded_show_bar()
        except Exception:
            logging.exception('Floating reservation unavailable; bar withheld')
            self.hide_immediate();self.release_reservation();self.phase='HIDDEN';self.hidden=True

    def desktop_changed(self,*_):
        # Keep the existing reservation across desktop transitions. Cloaking
        # and foreground classification filter inactive-desktop windows.
        self.timer.start()
        if self.reservation and self.mode!=FULLSCREEN:
            for hwnd in self.local_windows():self.queue_placement(hwnd)

    def ordinary_placement_target(self,hwnd):
        if self.closed or self.mode==FULLSCREEN or self.moving or not self.reservation or not eligible(hwnd):return False
        if win32api.MonitorFromWindow(hwnd,2)!=self.monitor_id or win32gui.GetAncestor(hwnd,2)!=hwnd:return False
        style=win32gui.GetWindowLong(hwnd,-16)
        # Caption + system menu distinguish ordinary secondary app/dialog
        # windows from dropdowns, notifications, frameless shell surfaces.
        if (style&0x00C80000)!=0x00C80000 or style&0x40000000:return False
        # Conservative rendering/game-window exclusion applies only to the
        # corrective fallback, never to taskbar eligibility or visibility.
        if win32gui.GetClassLong(hwnd,-26)&0x0020:return False  # GCL_STYLE / CS_OWNDC
        frame=frame_bounds(hwnd)
        if not frame or frame[1]>=self.reserved_rect[3] or not intersect(frame,self.reserved_rect):return False
        affinity=wintypes.DWORD()
        affinity_known=USER.GetWindowDisplayAffinity(hwnd,ctypes.byref(affinity))
        if affinity.value or (not affinity_known and win32gui.GetWindowLong(hwnd,-20)&0x80000):return False
        owner=root_owner(hwnd)
        info=self.monitor_info()
        if self.detect(hwnd,info)[0]!=FLOATING or (owner!=hwnd and self.detect(owner,info)[0]!=FLOATING):return False
        tiles=[(w,frame_bounds(w)) for w in self.local_windows() if w!=hwnd]
        if self.detect(hwnd,info,tiles)[0]!=FLOATING:return False
        return bool(frame and frame[1]<self.reserved_rect[3] and intersect(frame,self.reserved_rect))

    def queue_placement(self,hwnd):
        try:
            if not self.ordinary_placement_target(hwnd):return
            identity=win32process.GetWindowThreadProcessId(hwnd)
            if self.placement_attempts.get(hwnd)==identity:
                self.placement_safety.add(hwnd);self.placement_suspended=True
                self.hide_immediate();self.phase='PLACEMENT_SAFETY';self.hidden=True
                if not self.placement_timer.isActive():self.placement_timer.start()
                return
            if len(self.placement_pending)>=64:
                self.placement_safety.add(hwnd);self.placement_suspended=True
                self.hide_immediate();self.phase='PLACEMENT_SAFETY';self.hidden=True
                return
            # Coalesce launch/foreground/restore events without postponing a
            # candidate indefinitely under native location-event churn.
            self.placement_pending.setdefault(hwnd,{'identity':identity,'stage':0})
            self.placement_safety.add(hwnd)
            self.placement_suspended=True
            # Proven chrome overlap: withhold YASB pixels during the bounded
            # repair, without dropping work-area space in the launch race.
            self.finish_timer.stop();self.hide_timer.stop()
            self.hide_immediate();self.phase='PLACEMENT_SAFETY';self.hidden=True
            if not self.placement_timer.isActive():self.placement_timer.start()
        except (OSError,win32gui.error):return

    def validate_placements(self):
        if self.closed or self.mode==FULLSCREEN or not self.reservation:
            self.placement_pending.clear();return
        # Reclassify launch-time maximize/Snap/fullscreen before any correction.
        self.evaluate()
        reasserted=False
        for hwnd,entry in list(self.placement_pending.items()):
            try:
                if (win32process.GetWindowThreadProcessId(hwnd)!=entry['identity']
                        or not self.ordinary_placement_target(hwnd)):
                    self.placement_pending.pop(hwnd,None);continue
                self.placement_checks+=1
                if entry['stage']==2:
                    self.placement_pending.pop(hwnd,None);continue
                if entry['stage']==0:
                    if not reasserted:
                        from core.bar_helper import SystrayAppBarHelper
                        SystrayAppBarHelper.execute_without_systray_interference(self.reserve_native)
                        reasserted=True
                    entry['stage']=1
                    continue
                # Last-moment checks precede a single physical-pixel MOVE only:
                # retain native size, placement, z-order, focus and monitor.
                before=win32gui.GetWindowPlacement(hwnd)
                frame=frame_bounds(hwnd);rect=win32gui.GetWindowRect(hwnd)
                dy=self.reserved_rect[3]-frame[1]
                proposed=(frame[0],frame[1]+dy,frame[2],frame[3]+dy)
                if (before[1]!=1 or dy<=0 or self.moving
                        or win32api.MonitorFromRect(proposed,2)!=self.monitor_id):
                    self.placement_pending.pop(hwnd,None);continue
                if len(self.placement_attempts)>=256:self.placement_attempts.pop(next(iter(self.placement_attempts)))
                self.placement_attempts[hwnd]=entry['identity']
                flags=0x0001|0x0004|0x0010|0x0200|0x4000  # additionally ASYNCWINDOWPOS: never block on another app's queue
                if USER.SetWindowPos(hwnd,0,rect[0],rect[1]+dy,0,0,flags):
                    self.placement_moves+=1
                    logging.info('Top caption placement: one-shot corrected HWND %s by %s px',hwnd,dy)
                else:logging.warning('Top caption placement: one-shot move denied for HWND %s',hwnd)
                entry['stage']=2
            except (OSError,win32gui.error):self.placement_pending.pop(hwnd,None)
            except Exception:
                logging.exception('Top caption placement validation unavailable')
                self.placement_pending.pop(hwnd,None)
        if self.placement_pending:self.placement_timer.start()
        elif self.placement_suspended:
            self.resume_after_placement()

    def resume_after_placement(self):
        if self.moving:return
        unsafe=set()
        for hwnd in self.placement_safety:
            try:
                if self.ordinary_placement_target(hwnd):unsafe.add(hwnd)
            except (OSError,win32gui.error):pass
        self.placement_safety=unsafe
        if unsafe:
            # Failure must not leave a blank reserved strip or resurrect an
            # overlap. Await a native move/close/state event; no automatic retry.
            for hwnd in unsafe:
                self.floating_blocked[hwnd]=(win32process.GetWindowThreadProcessId(hwnd),self.reserved_rect)
            self.hide_immediate();self.release_reservation()
            self.placement_suspended=False;self.placement_safety.clear()
            self.phase='HIDDEN';self.hidden=True
            return
        self.placement_suspended=False
        if self.mode==FLOATING and self.reservation:
            self.phase='VISIBLE';self.hidden=False;self.position_bar();self.guarded_show_bar()
        elif self.mode in REVEALABLE and self.reservation:
            self.phase='REVEALING';self.hidden=False;self.position_bar();self.guarded_show_bar()
            self.finish_generation=self.generation;self.finish_timer.start()

    def hide_immediate(self):
        manager=self.bar_widget._animation_manager
        manager.cleanup()
        bar=self.bar_widget
        bar._skip_animation=True
        bar.hide()
        bar._skip_animation=False
        bar.setWindowOpacity(1.0)

    def dismiss_popups(self):
        for popup in self.owned_popups():
            animation=getattr(popup,'_fade_animation',None)
            if animation is not None:animation.stop()
            popup.hide()
            popup.close()

    def owned_popups(self):
        result=[]
        for popup in QApplication.topLevelWidgets():
            if popup is self.bar_widget or not popup.isVisible():continue
            owner=popup.parentWidget()
            while owner and owner is not self.bar_widget:owner=owner.parentWidget()
            if owner is self.bar_widget:result.append(popup)
        return result

    def at_edge(self,point):
        if point is None:return False
        monitor=self.monitor_info()['Monitor']
        return monitor[0]<=point[0]<monitor[2] and monitor[1]<=point[1]<monitor[1]+1

    def in_hold_region(self,point):
        if point is None:return False
        widgets=[self.bar_widget]+self.owned_popups()
        for widget in widgets:
            if not widget.isVisible():continue
            left,top,right,bottom=win32gui.GetWindowRect(int(widget.winId()))
            if left<=point[0]<right and top<=point[1]<bottom:return True
        return False

    def pointer_probe(self):
        if self.closed or self.mode not in REVEALABLE:
            self.pointer_timer.stop();self.dwell_timer.stop();return
        self.cursor_samples+=1
        point=cursor_position()
        if self.phase=='HIDDEN':
            if not self.at_edge(point):
                self.edge_armed=True;self.dwell_timer.stop()
            elif self.edge_armed and not self.dwell_timer.isActive():self.dwell_timer.start()
        elif self.phase in ('REVEALING','REVEALED'):
            if self.in_hold_region(point):self.hide_timer.stop()
            elif not self.hide_timer.isActive():self.hide_timer.start()

    def appbar_data(self):
        manager=self.bar_widget.app_bar_manager
        data=manager.app_bar_data
        if data is None:
            data=AppBarData();manager.app_bar_data=data
        data.cbSize=ctypes.sizeof(data)
        data.hWnd=int(self.bar_widget.winId())
        data.uCallbackMessage=APPBAR_CALLBACK_MESSAGE
        data.uEdge=AppBarEdge.Top
        return data

    def refresh_appbar(self):
        """Called by the narrow Bar.update_app_bar delegate, e.g. Explorer restart.

        Duplicate NEW does not reset position; only a newly registered shell
        entry needs a single restoration of an existing reservation.
        """
        if self.closed:return
        data=self.appbar_data()
        newly_registered=bool(SHELL(AppBarMessage.New,ctypes.byref(data)))
        if newly_registered and self.reservation:
            self.reserve_native()
        self.timer.start()

    def appbar_position_changed(self):
        if not self.closed:self.timer.start()

    def fullscreen_notice(self,opening):
        if self.closed:return
        if opening:
            self.monitor_info()
            foreground=win32gui.GetForegroundWindow()
            hwnd=root_owner(foreground) if foreground else None
            if hwnd and eligible(hwnd) and win32api.MonitorFromWindow(hwnd,2)==self.monitor_id:
                self.native_fullscreen_hwnd=hwnd
                self.last_local=hwnd
                self.set_mode(FULLSCREEN,'native ABN_FULLSCREENAPP',[hwnd])
        else:
            self.native_fullscreen_hwnd=None
            self.timer.start()

    def reserve_native(self):
        info=self.monitor_info()
        if not self.reservation:self.base_work=tuple(info['Work'])
        monitor=info['Monitor']
        native=win32gui.GetWindowRect(int(self.bar_widget.winId()))
        height=native[3]-native[1]
        if height<=0:height=round(self.bar_widget.height()*self.bar_widget._target_screen.devicePixelRatio())
        data=self.appbar_data()
        # Reuse the same registered AppBar HWND. Query excludes other bars,
        # then restore requested height as documented before SETPOS.
        data.rc.left,data.rc.top,data.rc.right,data.rc.bottom=monitor[0],monitor[1],monitor[2],monitor[1]+height
        if not SHELL(AppBarMessage.QueryPos,ctypes.byref(data)):raise RuntimeError('ABM_QUERYPOS failed')
        data.rc.bottom=data.rc.top+height
        self.reservation=True  # even a failed/partial SETPOS must be cleaned up
        if not SHELL(AppBarMessage.SetPos,ctypes.byref(data)):raise RuntimeError('ABM_SETPOS failed')
        self.reserved_rect=(data.rc.left,data.rc.top,data.rc.right,data.rc.bottom)
        self.reservation_updates+=1
        self.guard_until=perf_counter()+0.35

    def release_reservation(self):
        if not self.reservation:return
        from core.bar_helper import SystrayAppBarHelper
        data=self.appbar_data()
        monitor=self.monitor_info()['Monitor']
        def release():
            data.rc.left,data.rc.top,data.rc.right,data.rc.bottom=monitor[0],monitor[1],monitor[2],monitor[1]
            if not SHELL(AppBarMessage.SetPos,ctypes.byref(data)):
                # Only remove OUR AppBar; never SPI_SETWORKAREA or bottom bar.
                SHELL(AppBarMessage.Remove,ctypes.byref(data))
                SHELL(AppBarMessage.New,ctypes.byref(data))
        try:SystrayAppBarHelper.execute_without_systray_interference(release)
        except Exception:
            logging.exception('Top reservation release failed; removing own AppBar')
            SHELL(AppBarMessage.Remove,ctypes.byref(data))
        finally:
            self.reservation=False;self.reserved_rect=None
            self.reservation_updates+=1
            self.guard_until=perf_counter()+0.35

    def position_bar(self):
        if not self.reserved_rect:return False
        bar=self.bar_widget;screen=bar._target_screen
        monitor=self.monitor_info()['Monitor'];scale=screen.devicePixelRatio()
        r=self.reserved_rect
        bar.setGeometry(screen.geometry().x()+round((r[0]-monitor[0])/scale),
                        screen.geometry().y()+round((r[1]-monitor[1])/scale),
                        round((r[2]-r[0])/scale),bar.height())
        bar._bar_frame.setGeometry(0,0,bar.width(),bar.height())
        return True

    def begin_reveal(self):
        if self.closed or self.mode not in REVEALABLE or self.phase!='HIDDEN' or not self.at_edge(cursor_position()):return
        self.evaluate()  # confirm current state before making any reservation
        if self.mode not in REVEALABLE or self.phase!='HIDDEN' or self.foreground() is None:return
        self.generation+=1
        self.reflow_generation=self.generation
        self.phase='RESERVING';self.edge_armed=False
        try:
            self.target_placements={h:win32gui.GetWindowPlacement(h)[1] for h in self.targets if eligible(h)}
            from core.bar_helper import SystrayAppBarHelper
            SystrayAppBarHelper.execute_without_systray_interference(self.reserve_native)
            self.reflow_deadline=perf_counter()+0.7
            self.reflow_timer.start()
        except Exception:
            logging.exception('Top reservation failed; reveal canceled')
            self.hide_immediate();self.release_reservation();self.phase='HIDDEN'

    def verify_reflow(self):
        if self.closed or self.phase!='RESERVING' or self.reflow_generation!=self.generation:return
        if self.mode not in REVEALABLE:
            self.release_reservation();return
        try:
            info=self.monitor_info()
            hwnd=self.last_local
            if eligible(hwnd) and self.detect(hwnd,info)[0]==FULLSCREEN:
                self.set_mode(FULLSCREEN,'fullscreen entered during reservation',[hwnd]);return
            bottom=self.reserved_rect[3]
            safe=info['Work'][1]>=bottom and bool(self.target_placements)
            frames=[]
            for target,placement in self.target_placements.items():
                if not eligible(target) or win32gui.GetWindowPlacement(target)[1]!=placement:
                    safe=False;break
                frame=frame_bounds(target)
                tolerance=max(3,round((USER.GetDpiForWindow(target) or 96)/96*3))
                if (intersect(frame,self.reserved_rect) or not frame
                        or frame[0]<info['Work'][0]-tolerance
                        or frame[2]>info['Work'][2]+tolerance
                        or frame[3]>info['Work'][3]+tolerance):
                    safe=False;break
                if self.mode==SNAP and any(
                        overlap and overlap[2]-overlap[0]>tolerance and overlap[3]-overlap[1]>tolerance
                        for overlap in (intersect(frame,other) for other in frames)):
                    safe=False;break
                frames.append(frame)
            if safe:
                self.presentation_hwnd=self.last_local
                self.phase='REVEALING';self.hidden=False
                self.position_bar()
                self.guarded_show_bar()
                self.finish_generation=self.generation
                self.finish_timer.start()
                logging.info('Top-bar reveal: reserved/reflow verified; %s',self.mode)
                return
            if perf_counter()>=self.reflow_deadline:
                self.hide_immediate();self.release_reservation();self.phase='HIDDEN';self.hidden=True
                logging.warning('Top-bar reveal withheld: native app/layout did not safely reflow')
            else:self.reflow_timer.start()
        except Exception:
            logging.exception('Top-bar reflow verification failed')
            self.hide_immediate();self.release_reservation();self.phase='HIDDEN';self.hidden=True

    def begin_hide(self):
        if self.closed or self.mode not in REVEALABLE or self.phase not in ('REVEALING','REVEALED'):return
        if self.in_hold_region(cursor_position()):return
        self.generation+=1
        self.phase='HIDING'
        self.bar_widget.hide_bar()
        self.finish_generation=self.generation
        self.finish_timer.start()

    def finish_transition(self):
        if self.closed or self.finish_generation!=self.generation:return
        manager=self.bar_widget._animation_manager
        if manager._animation is not None:
            self.finish_timer.start();return
        if self.phase=='REVEALING':
            self.phase='REVEALED';self.pointer_probe()
        elif self.phase=='HIDING':
            self.hide_immediate()
            self.release_reservation()  # native HWND is hidden before expanding app
            self.phase='HIDDEN';self.hidden=True
            self.edge_armed=not self.at_edge(cursor_position())
            logging.info('Top-bar hide: animation finished; reservation released')

    def cleanup(self):
        if self.closed:return
        self.closed=True;self.generation+=1
        for timer in (self.timer,self.pointer_timer,self.dwell_timer,self.hide_timer,self.reflow_timer,self.finish_timer,self.placement_timer):timer.stop()
        self.placement_pending.clear();self.placement_attempts.clear()
        self.placement_safety.clear()
        self.floating_blocked.clear()
        if self.desktop_service is not None:
            try:self.desktop_service.desktop_changed.disconnect(self.desktop_changed)
            except (TypeError,RuntimeError):pass
        self.dismiss_popups();self.hide_immediate();self.release_reservation()
        for event in self.events:self.service.unregister_event(event,self.changed)
        self.bar_widget.show=self._original_show
        self.bar_widget.show_bar=self._original_show_bar
        self.managed_appbar=False
