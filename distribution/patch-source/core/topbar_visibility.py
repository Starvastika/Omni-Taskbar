"""Event-driven top-bar policy for installed YASB 2.0.7.

Runs inside YASB, subscribing to its existing EventService; no mouse hooks,
polling, daemon, or privileged operations. Geometry is in native pixels.
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

SHELL_CLASSES = frozenset({
    'Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd',
    'XamlExplorerHostIslandWindow', 'MultitaskingViewFrame',
    'TaskListThumbnailWnd', 'ForegroundStaging',
    'tooltips_class32', '#32768', 'EdgeUiInputTopWndClass',
})
DESKTOP_CLASSES = frozenset({'Progman', 'WorkerW'})
SHELL_PROCESSES = frozenset({'startmenuexperiencehost.exe', 'shellexperiencehost.exe',
                           'searchhost.exe', 'searchapp.exe', 'textinputhost.exe'})
KERNEL = ctypes.WinDLL('kernel32', use_last_error=True)
KERNEL.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL.OpenProcess.restype = wintypes.HANDLE
KERNEL.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                            wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]


def shell_process(pid):
    handle = KERNEL.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        path = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(path))
        return bool(KERNEL.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size))
                    and path.value.rsplit('\\', 1)[-1].lower() in SHELL_PROCESSES)
    finally:
        KERNEL.CloseHandle(handle)
DWMA = ctypes.WinDLL('dwmapi').DwmGetWindowAttribute
DWMA.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
DWMA.restype = ctypes.c_long
USER = ctypes.WinDLL('user32')
USER.GetDpiForWindow.argtypes = [wintypes.HWND]
USER.GetDpiForWindow.restype = wintypes.UINT
USER.IsZoomed.argtypes = [wintypes.HWND]
USER.IsZoomed.restype = wintypes.BOOL
OWN_PID = os.getpid()


def intersect(a, b):
    r = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return r if r[2] > r[0] and r[3] > r[1] else None


def area(r):
    return max(0, r[2]-r[0]) * max(0, r[3]-r[1]) if r else 0


def covers(r, target, tolerance):
    return bool(r and r[0] <= target[0]+tolerance and r[1] <= target[1]+tolerance
                and r[2] >= target[2]-tolerance and r[3] >= target[3]-tolerance)


def union_area(rects):
    """Exact rectangular union, including overlaps (never sums their areas)."""
    xs = sorted({x for r in rects for x in (r[0], r[2])})
    result = 0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted((r[1], r[3]) for r in rects if r[0] < right and r[2] > left)
        end = None
        height = 0
        for top, bottom in intervals:
            if end is None or top > end:
                height += bottom-top
                end = bottom
            elif bottom > end:
                height += bottom-end
                end = bottom
        result += (right-left)*height
    return result


def decide(frame, monitor, work, zoomed=False, tolerance=3, was_hidden=False, tiled=()):
    """Pure decision seam, shared by native adapter and representative tests."""
    if zoomed:
        return True, 'maximized (IsZoomed/GetWindowPlacement)'
    if covers(frame, monitor, tolerance):
        return True, 'fullscreen/borderless monitor coverage'
    if covers(frame, work, tolerance):
        return True, 'maximized work-area frame coverage'
    if frame:
        width = work[2]-work[0]
        hysteresis = 2 if was_hidden else 0
        if (abs(frame[1]-work[1]) <= tolerance+hysteresis
                and frame[3] >= work[3]-tolerance-hysteresis
                and frame[2]-frame[0] >= width*0.20
                and intersect(frame, work)):
            return True, 'full-height snapped window'
    # The foreground participates in the layout. Background maximized windows
    # and overlapping floating windows do not turn a restored foreground into
    # a tiled layout. Greedily accept other visible windows in native z-order.
    selected = [intersect(frame, work)] if frame and intersect(frame, work) else []
    for rect in tiled:
        rect = intersect(rect, work)
        if not rect or area(rect) < area(work)*0.035 or area(rect) > area(work)*0.94:
            continue
        if any(area(intersect(rect, old)) > min(area(rect), area(old))*0.08 for old in selected):
            continue
        selected.append(rect)
    coverage = union_area(selected)/area(work) if area(work) else 0
    if len(selected) > 1 and coverage >= (0.965 if was_hidden else 0.975):
        return True, f'tiled layout coverage {coverage:.1%}'
    return False, 'restored floating foreground / unused desktop space'


def frame_bounds(hwnd):
    rect = wintypes.RECT()
    if DWMA(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) == 0:
        return rect.left, rect.top, rect.right, rect.bottom
    return win32gui.GetWindowRect(hwnd)


def eligible(hwnd):
    try:
        if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return False
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        if pid == OWN_PID or shell_process(pid):
            return False
        if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
            return False
        style = win32gui.GetWindowLong(hwnd, -20)
        # tool/no-activate/transparent overlays, menus and helper windows
        if style & (0x80 | 0x08000000 | 0x20):
            return False
        if style & 0x80000:
            try:
                _, alpha, flags = win32gui.GetLayeredWindowAttributes(hwnd)
                if flags & 2 and alpha < 200:
                    return False
            except win32gui.error:
                pass  # per-pixel layered app can still be an opaque application
        cloaked = wintypes.DWORD()
        if DWMA(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0 and cloaked.value:
            return False
        bounds = frame_bounds(hwnd)
        return area(bounds) > 0 and bool(win32api.MonitorFromRect(bounds, 0))
    except (OSError, win32gui.error):
        return False


def root_owner(hwnd):
    # GA_ROOTOWNER, including native owned modal dialogs. Some frameworks do
    # not expose ownership; those retain their normal geometry-based decision.
    owner = win32gui.GetAncestor(hwnd, 3)
    return owner if eligible(owner) else hwnd


class WindowStateVisibility(QObject):
    changed = pyqtSignal(object, object)

    def __init__(self, bar_widget, parent=None):
        super().__init__(parent)
        self.bar_widget = bar_widget
        self.service = EventService()
        # The existing shared listener exposes this filtered channel so client
        # object create/destroy churn never wakes the layout controller. All
        # existing generic WinEvent subscribers retain their original payloads.
        self.events = ('topbar_window_state',)
        self.hidden = False
        self.reason = 'initializing'
        self.last_local = None
        self.moving = None
        self.evaluations = 0
        self.evaluation_ms = 0.0
        self.locations = {}
        self.monitor_id = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(75)
        self.timer.timeout.connect(self.evaluate)
        self.changed.connect(self.queue, Qt.ConnectionType.QueuedConnection)
        for event in self.events:
            self.service.register_event(event, self.changed)
        self.bar_widget._target_screen.geometryChanged.connect(self.screen_changed)
        self.bar_widget._target_screen.availableGeometryChanged.connect(self.screen_changed)
        # No AutoHideManager is ever created, including via the context menu.
        self.bar_widget._autohide_bar = False
        self.timer.start()

    def screen_changed(self, *_):
        self.monitor_id = None
        self.timer.start()

    def queue(self, hwnd, event):
        if event == WinEvent.EventSystemMoveSizeStart:
            self.moving = hwnd
            self.timer.stop()
            return
        if event == WinEvent.EventSystemMoveSizeEnd:
            self.moving = None
            self.timer.start()
            return
        if self.moving:
            if event == WinEvent.EventObjectDestroy and hwnd == self.moving:
                self.moving = None
            else:
                return
        if event not in (WinEvent.EventSystemForeground, WinEvent.EventSystemSwitchEnd):
            # Discard child-object events delivered by the shared listener;
            # this includes scrolling, tab content geometry and own animations.
            try:
                if hwnd and win32gui.IsWindow(hwnd):
                    if win32gui.GetAncestor(hwnd, 2) != hwnd:
                        return
                    if win32process.GetWindowThreadProcessId(hwnd)[1] == OWN_PID:
                        return
                    if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
                        return
                    if event == WinEvent.EventObjectLocationChange:
                        bounds = frame_bounds(hwnd)
                        if self.locations.get(hwnd) == bounds:
                            return
                        if len(self.locations) >= 64:
                            self.locations.clear()
                        self.locations[hwnd] = bounds
                elif event != WinEvent.EventObjectDestroy:
                    return
            except win32gui.error:
                return
        # Evaluate after 75 ms of stable geometry. Identical bounds and client
        # object chatter were already filtered; live move holds until its end.
        self.timer.start()

    def evaluate(self):
        start = perf_counter()
        try:
            bar = self.bar_widget
            # Bar slides off-screen; its native rect must never choose the
            # monitor above it. Resolve the configured QScreen device instead.
            if self.monitor_id is None:
                self.monitor_id = next((m[0] for m in win32api.EnumDisplayMonitors()
                                        if win32api.GetMonitorInfo(m[0])['Device'] == bar._target_screen.name()),
                                       bar.monitor_hwnd)
            monitor_id = self.monitor_id
            info = win32api.GetMonitorInfo(monitor_id)
            monitor, work = info['Monitor'], info['Work']
            hwnd = win32gui.GetForegroundWindow()
            cls = win32gui.GetClassName(hwnd) if hwnd else ''
            if cls in DESKTOP_CLASSES:
                self.apply(False, 'desktop active')
                return
            if hwnd:
                hwnd = root_owner(hwnd)
            # Shell transients, YASB popups and no foreground preserve state.
            if not eligible(hwnd):
                # Own top popups can be active while their underlying app is
                # resized/maximized. Recheck that application's last local
                # window, so a hide-required change dismisses owned popups.
                own = hwnd and win32process.GetWindowThreadProcessId(hwnd)[1] == OWN_PID
                if own and eligible(self.last_local):
                    hwnd = self.last_local
                else:
                    return
            hwnd = root_owner(hwnd)
            local = win32api.MonitorFromWindow(hwnd, 2) == monitor_id
            windows = None
            if local:
                self.last_local = hwnd
            else:
                # Do not import another monitor's maximize/fullscreen state.
                hwnd = self.last_local if eligible(self.last_local) else None
                if hwnd and win32api.MonitorFromWindow(hwnd, 2) != monitor_id:
                    hwnd = None
                if not hwnd:
                    windows = self.local_windows(monitor_id)
                    hwnd = windows[0] if windows else None
            if not hwnd:
                self.apply(False, 'desktop exposed on bar monitor')
                return
            frame = frame_bounds(hwnd)
            tol = max(3, round((USER.GetDpiForWindow(hwnd) or 96)/96*3))
            zoomed = bool(USER.IsZoomed(hwnd) or win32gui.GetWindowPlacement(hwnd)[1] == 3)
            hidden, reason = decide(frame, monitor, work, zoomed, tol, self.hidden)
            if not hidden:
                windows = windows if windows is not None else self.local_windows(monitor_id)
                tiled = [frame_bounds(w) for w in windows if w != hwnd and root_owner(w) == w]
                hidden, reason = decide(frame, monitor, work, zoomed, tol, self.hidden, tiled)
            self.apply(hidden, reason)
        except Exception:
            logging.debug('Window-state visibility evaluation unavailable', exc_info=True)
        finally:
            self.evaluations += 1
            self.evaluation_ms += (perf_counter()-start)*1000

    @staticmethod
    def local_windows(monitor_id):
        result = []
        def visit(hwnd, _):
            if eligible(hwnd) and win32api.MonitorFromWindow(hwnd, 2) == monitor_id:
                result.append(hwnd)
        win32gui.EnumWindows(visit, None)
        return result

    def apply(self, hidden, reason):
        self.reason = reason
        if hidden == self.hidden:
            return
        self.hidden = hidden
        bar = self.bar_widget
        if hidden:
            for popup in QApplication.topLevelWidgets():
                if popup is bar or not popup.isVisible():
                    continue
                owner = popup.parentWidget()
                while owner and owner is not bar:
                    owner = owner.parentWidget()
                if owner is bar:
                    popup.close()
            bar.hide_bar()
        else:
            bar.show_bar()
        logging.info('Top-bar visibility %s: %s', 'HIDE' if hidden else 'SHOW', reason)

    def cleanup(self):
        self.timer.stop()
        for event in self.events:
            self.service.unregister_event(event, self.changed)
