"""Context-sensitive view of YASB's existing shared taskbar window manager.

No enumeration, hooks, launch logic or work-area policy lives here. Metadata is
resolved once per window lifetime, and app images/names have a bounded LRU.
"""
import logging
import ntpath
import os
from itertools import count
from collections import OrderedDict

import win32api
import win32con
import win32gui
import win32process
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle

from core.events.service import EventService
from core.events.win32 import WinEvent
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utils import get_app_name_from_aumid, get_app_name_from_pid, is_window_maximized
from core.utils.win32.window_actions import (
    close_application, maximize_window, minimize_window, resolve_base_and_focus,
    restore_window, set_foreground, show_window,
)
from core.widgets.services.taskbar.application_window import ApplicationWindow
from core.widgets.services.taskbar.pin_manager import PinManager
from core.widgets.services.taskbar.window_manager import get_shared_task_manager

log = logging.getLogger("active_app_center")


def clean_title(title, name):
    """Remove only an exact, delimiter-separated application name at an edge."""
    for sep in (" — ", " – ", " - ", " | "):
        if title.casefold().endswith((sep + name).casefold()):
            return title[:-len(sep + name)] or title
        if title.casefold().startswith((name + sep).casefold()):
            return title[len(name + sep):] or title
    return title


class ActiveAppService(QObject):
    changed = pyqtSignal()
    row_changed = pyqtSignal(int, bool)  # HWND, membership changed
    foreground_event = pyqtSignal(int, object)
    name_event = pyqtSignal(int, object)
    state_event = pyqtSignal(int, object)
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__(QApplication.instance())
        self.records = {}
        self.groups = {}
        self.assets = OrderedDict()
        self.lifetimes = count(1)
        self.active = None
        self.taskbar = None
        self.manager = get_shared_task_manager()
        self.manager.window_added.connect(self.upsert)
        self.manager.window_updated.connect(self.upsert)
        self.manager.window_removed.connect(self.remove)
        self.manager.window_minimize_changed.connect(self.minimized)
        self.manager.window_monitor_changed.connect(self.upsert)
        self.events = EventService()
        self.foreground_event.connect(self.native_foreground)
        self.name_event.connect(self.native_title)
        self.state_event.connect(self.native_state)
        self.subscriptions = [
            (WinEvent.EventSystemForeground, self.foreground_event),
            (WinEvent.EventSystemMoveSizeEnd, self.state_event),
            (WinEvent.EventObjectNameChange, self.name_event),
            (WinEvent.EventObjectStateChange, self.state_event),
        ]
        for event, signal in self.subscriptions:
            self.events.register_event(event, signal)
        QApplication.instance().aboutToQuit.connect(self.cleanup)
        QTimer.singleShot(0, self.initialize)

    def initialize(self):
        # The bottom widget starts/populates the SAME manager in showEvent.
        self.taskbar = next((w for w in QApplication.allWidgets()
                             if w.__class__.__name__ == "TaskbarWidget"), None)
        if self.taskbar:
            self.taskbar.destroyed.connect(self.taskbar_destroyed)
        for hwnd, window in tuple(self.manager._windows.items()):
            self.upsert(hwnd, window.as_dict())
        self.foreground({})

    def taskbar_destroyed(self):
        self.taskbar = None
        # A config/bar reload can replace widgets without changing processes.
        # Reattach once after reconstruction, not on a periodic scan.
        QTimer.singleShot(0, self.initialize)

    def cleanup(self):
        for event, signal in self.subscriptions:
            self.events.unregister_event(event, signal)
        self.subscriptions.clear()

    def native_foreground(self, hwnd, event):
        self.foreground({"hwnd": hwnd})

    def native_title(self, hwnd, event):
        self.title_event({"hwnd": hwnd})

    def native_state(self, hwnd, event):
        self.state_changed({"hwnd": hwnd})

    def eligible(self, hwnd, data):
        # The manager already applies ApplicationWindow.is_taskbar_window.
        # Mirror this user's broad bottom policy, never require a minimize box.
        if not win32gui.IsWindow(hwnd):
            return False
        try:
            if win32process.GetWindowThreadProcessId(hwnd)[1] == os.getpid():
                return False
            if win32gui.GetAncestor(hwnd, 2) != hwnd:
                return False
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & (win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE):
                return False
            if not win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                return False
            if not (data.get("title") or "").strip():
                return False
            if data.get("class_name") in ApplicationWindow.DEFAULT_IGNORED_CLASSES:
                return False
            if not win32gui.IsIconic(hwnd):
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                if right-left <= 1 or bottom-top <= 1:
                    return False
                if not win32api.MonitorFromRect((left, top, right, bottom), 0):
                    return False
            if self.taskbar:
                # Metadata failure alone must not remove the current app's
                # controls. Keep every configured ignore/monitor/cloak rule.
                candidate = data if data.get("process_name") else dict(data, process_name="Application")
                return self.taskbar._should_show_window(hwnd, candidate)
            return True
        except Exception:
            return False

    def identity(self, hwnd, data):
        # Reuse the existing taskbar/pin identity, including launcher arguments
        # for hosted apps. A folder pin is a location, not an application.
        key = None
        if self.taskbar:
            key = self.taskbar._hwnd_to_group.get(hwnd)
        if not key:
            key, _ = PinManager.get_app_identifier(hwnd, data)
        path = data.get("process_path") or ""
        if key and not key.startswith("explorer:"):
            return key
        if path:
            return "path:" + ntpath.normcase(ntpath.normpath(path))
        # Recovery without PID/title-based grouping; unknown host windows stay
        # distinct rather than incorrectly merging unrelated packaged apps.
        process = data.get("process_name") or ""
        if process and process.casefold() not in ("applicationframehost.exe", "rundll32.exe", "mmc.exe"):
            return "exe:" + process.casefold()
        return "window:" + str(hwnd)

    def upsert(self, hwnd, data):
        try:
            if not self.eligible(hwnd, data):
                self.remove(hwnd, data)
                return
            data = dict(data)
            if not data.get("process_pid"):
                data["process_pid"] = win32process.GetWindowThreadProcessId(hwnd)[1]
            old = self.records.get(hwnd)
            # A reused HWND gets fresh identity and actions, never the old PID.
            same = old and old.get("process_pid") == data.get("process_pid")
            key = old["key"] if same else self.identity(hwnd, data)
            if old and old["key"] != key:
                self.remove(hwnd, old)
                old = None
            token = old["token"] if same and old else (data.get("process_pid"), next(self.lifetimes))
            record = dict(data, key=key, token=token, minimized=bool(win32gui.IsIconic(hwnd)))
            self.records[hwnd] = record
            membership = not old
            if membership:
                self.groups.setdefault(key, []).append(hwnd)
            self.row_changed.emit(hwnd, membership)
            if self.active and self.active["hwnd"] == hwnd:
                self.active = record
                self.changed.emit()
            elif data.get("is_active"):
                self.foreground({})
        except Exception:
            log.debug("Window update failed for %s", hwnd, exc_info=True)

    def remove(self, hwnd, data=None):
        old = self.records.pop(hwnd, None)
        if old:
            members = self.groups.get(old["key"], [])
            if hwnd in members:
                members.remove(hwnd)
            if not members:
                self.groups.pop(old["key"], None)
            self.row_changed.emit(hwnd, True)
        if self.active and self.active["hwnd"] == hwnd:
            self.active = None
            self.changed.emit()
            QTimer.singleShot(0, lambda: self.foreground({}))

    def minimized(self, hwnd, value):
        if hwnd in self.records:
            self.records[hwnd]["minimized"] = bool(value)
            self.row_changed.emit(hwnd, False)
        self.state_changed({"hwnd": hwnd})

    def title_event(self, data):
        hwnd = data.get("hwnd")
        if hwnd in self.records:
            try:
                self.records[hwnd]["title"] = win32gui.GetWindowText(hwnd)
                self.row_changed.emit(hwnd, False)
                if self.active and self.active["hwnd"] == hwnd:
                    self.changed.emit()
            except Exception:
                self.remove(hwnd)
        elif self.active and self.active["hwnd"] == hwnd:
            try:
                self.active["title"] = win32gui.GetWindowText(hwnd)
                self.changed.emit()
            except Exception:
                self.foreground({})

    def state_changed(self, data):
        if self.active and (not data.get("hwnd") or data.get("hwnd") == self.active["hwnd"]):
            self.changed.emit()

    def foreground(self, data):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return self.clear()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == os.getpid():
                return  # bar/menu focus must not retarget the window controls
            cls = win32gui.GetClassName(hwnd)
            if cls in ("Progman", "WorkerW", "SHELLDLL_DefView"):
                return self.clear()
            if cls in ApplicationWindow.DEFAULT_IGNORED_CLASSES:
                return  # transient shell surfaces keep the underlying app
            record = self.records.get(hwnd)
            if not record:
                base = win32gui.GetAncestor(hwnd, 3)
                owner = self.records.get(base)
                if owner and win32gui.GetWindowText(hwnd):
                    # Owned modal: app identity comes from owner; window controls
                    # target the dialog itself, exactly as the displayed title.
                    record = dict(owner, hwnd=hwnd, process_pid=pid,
                                  title=win32gui.GetWindowText(hwnd), owner=base,
                                  token=(self.active["token"] if self.active and self.active["hwnd"] == hwnd
                                         else (pid, next(self.lifetimes))))
                else:
                    window = self.manager._windows.get(hwnd) or ApplicationWindow(hwnd)
                    if window.is_taskbar_window():
                        self.upsert(hwnd, window.as_dict())
                    record = self.records.get(hwnd)
            if record:
                self.active = record
                self.changed.emit()
            else:
                # Tool/menu/companion windows are transient, not a Desktop app.
                ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if not ex & (win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE):
                    self.clear()
        except Exception:
            log.debug("Foreground unavailable", exc_info=True)

    def clear(self):
        self.active = None
        self.changed.emit()

    def members(self, key):
        return [h for h in self.groups.get(key, ()) if h in self.records]

    def valid_target(self, hwnd, token=None):
        try:
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False
            record = self.records.get(hwnd)
            if not record and self.active and self.active["hwnd"] == hwnd:
                record = self.active
            if not record:
                return False
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            expected = record["token"] if isinstance(token, tuple) else pid
            return pid == record["process_pid"] and (token is None or token == expected)
        except Exception:
            return False

    def asset(self, record, dpr=1.0):
        key = (record["key"], round(dpr, 2))
        if key in self.assets:
            self.assets.move_to_end(key)
            return self.assets[key]
        hwnd = record["hwnd"]
        name = None
        icon = None
        try:
            if record["key"].startswith("aumid:"):
                name = get_app_name_from_aumid(record["key"][6:])
            if not name:
                name = get_app_name_from_pid(record.get("process_pid", 0))
        except Exception:
            pass
        name = (name or ntpath.splitext(ntpath.basename(record.get("process_name") or "Application"))[0]).strip()
        try:
            # Prefer the exact icon already extracted by the bottom taskbar.
            item = self.taskbar._window_buttons.get(hwnd) if self.taskbar else None
            if item and isinstance(item[1], QPixmap) and not item[1].isNull():
                icon = QIcon(item[1])
            else:
                image = get_window_icon(hwnd)
                if image:
                    image = image.convert("RGBA")
                    qi = QImage(image.tobytes(), image.width, image.height, QImage.Format.Format_RGBA8888).copy()
                    icon = QIcon(QPixmap.fromImage(qi))
        except Exception:
            pass
        if not icon or icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.assets[key] = (name, icon)
        while len(self.assets) > 128:
            self.assets.popitem(last=False)
        return name, icon

    def activate(self, hwnd, token=None):
        if not self.valid_target(hwnd, token):
            self.remove(hwnd)
            return False
        try:
            base, focus = resolve_base_and_focus(hwnd)
            if win32gui.IsIconic(base):
                restore_window(base)
            else:
                show_window(base)
            set_foreground(focus or base)
            return True  # Windows may decline foreground focus; never fake it.
        except Exception:
            log.debug("Window activation declined for %s", hwnd, exc_info=True)
            return False

    def action(self, hwnd, action, token=None):
        if not self.valid_target(hwnd, token):
            self.remove(hwnd)
            return
        try:
            if action == "minimize":
                minimize_window(hwnd)
            elif action == "close":
                close_application(hwnd)  # WM_CLOSE, never terminate a process
            elif action == "restore":
                restore_window(hwnd)
            elif action == "maximize":
                (restore_window if is_window_maximized(hwnd) else maximize_window)(hwnd)
        except Exception:
            log.debug("Window action declined for %s", hwnd, exc_info=True)
