import logging
import os

import win32api
import win32gui
import win32process
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QPushButton, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.utils.win32.utils import get_app_name_from_pid, get_monitor_hwnd, is_window_maximized
from core.utils.win32.window_actions import (
    close_application,
    maximize_window,
    minimize_window,
    restore_window,
    set_foreground,
)
from core.validation.widgets.yasb.window_controls import WindowControlsConfig
from core.widgets.base import BaseWidget
from settings import APP_BAR_TITLE

CURRENT_PROCESS_ID = os.getpid()

IGNORED_TITLES = ["", " ", "FolderView", "Program Manager", "python", "pythonw", "YasbBar", "Search", "Start"]
IGNORED_CLASSES = [
    "WorkerW",
    "TopLevelWindowForOverflowXamlIsland",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
]
IGNORED_YASB_TITLES = [APP_BAR_TITLE]


class _ForegroundPollResult:
    """Lightweight container for a single poll cycle result."""

    __slots__ = ("hwnd", "valid", "maximized", "fg_monitor_hwnd", "app_name")

    def __init__(self, hwnd: int, valid: bool, maximized: bool, fg_monitor_hwnd: int, app_name: str):
        self.hwnd = hwnd
        self.valid = valid
        self.maximized = maximized
        self.fg_monitor_hwnd = fg_monitor_hwnd
        self.app_name = app_name


class _ForegroundPoller:
    """Compatibility adapter: controls consume the Active App Center's HWND.

    The old independent 200ms poll and unbounded PID cache are eliminated.
    """
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        from core.widgets.services.active_app_center import ActiveAppService
        self.service = ActiveAppService.instance()
        self._callbacks = []
        self.service.changed.connect(self._poll)

    def register(self, callback):
        if callback not in self._callbacks:
            self._callbacks.append(callback)
        self._poll()

    def unregister(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _poll(self):
        record = self.service.active
        result = _ForegroundPollResult(0, False, False, 0, "")
        if record and self.service.valid_target(record["hwnd"], record["process_pid"]):
            try:
                hwnd = record["hwnd"]
                result = _ForegroundPollResult(hwnd, True, is_window_maximized(hwnd),
                                               int(win32api.MonitorFromWindow(hwnd)), "")
            except Exception:
                pass
        for cb in list(self._callbacks):
            try:
                cb(result)
            except RuntimeError:
                self.unregister(cb)



class WindowControlsWidget(BaseWidget):
    validation_schema = WindowControlsConfig

    def __init__(self, config: WindowControlsConfig):
        super().__init__(class_name=f"window-controls-widget {config.class_name}")
        self.config = config
        self._tracked_hwnd = None
        self._tracked_maximized = False
        self._is_visible = False
        self._show_anim = None
        self._hide_anim = None
        self._opacity_anim = None

        self._init_container()

        self._opacity_effect = QGraphicsOpacityEffect(self._widget_container)
        self._opacity_effect.setOpacity(0.0)
        self._widget_container.setGraphicsEffect(self._opacity_effect)

        # Optional app name label
        self._app_name_label: QLabel | None = None
        if self.config.show_app_name:
            self._app_name_label = QLabel()
            self._app_name_label.setProperty("class", "app-name")

        # Render app name before buttons when configured on the left.
        if self._app_name_label is not None and self.config.app_name_position == "left":
            self._widget_container_layout.addWidget(self._app_name_label)

        # Create buttons in configured order
        self._buttons: dict[str, QPushButton] = {}
        for btn_name in self.config.buttons:
            label_text = getattr(self.config.button_labels, btn_name, btn_name)
            btn = QPushButton(label_text)
            btn.setProperty("class", f"btn {btn_name}")
            set_tooltip(btn, btn_name.capitalize())
            btn.clicked.connect(self._make_button_handler(btn_name))
            self._widget_container_layout.addWidget(btn)
            self._buttons[btn_name] = btn

        # Render app name after buttons when configured on the right.
        if self._app_name_label is not None and self.config.app_name_position == "right":
            self._widget_container_layout.addWidget(self._app_name_label)

        # Start hidden
        self.setMaximumWidth(0)

        # Register with shared singleton poller
        self._poller = _ForegroundPoller.instance()
        self._poller_registered = False
        self._poller.register(self._on_poll_result)
        self._poller_registered = True
        self.destroyed.connect(self._cleanup_poller)

    def _cleanup_poller(self) -> None:
        if not getattr(self, "_poller_registered", False):
            return
        try:
            self._poller.unregister(self._on_poll_result)
        except Exception:
            pass
        self._poller_registered = False

    def closeEvent(self, event):
        self._cleanup_poller()
        self._stop_running_animations()
        super().closeEvent(event)

    def _make_button_handler(self, btn_name: str):
        def handler():
            service = self._poller.service
            target = service.active
            if target and target["hwnd"] == self._tracked_hwnd:
                service.action(target["hwnd"], btn_name, target["token"])
        return handler

    def _update_maximize_button(self, maximized: bool) -> None:
        """Toggle the maximize button icon, tooltip, and CSS class between maximize and restore."""
        btn = self._buttons.get("maximize")
        if btn:
            if maximized:
                btn.setText(self.config.button_labels.restore)
                btn.setProperty("class", "btn restore")
                set_tooltip(btn, "Restore")
            else:
                btn.setText(self.config.button_labels.maximize)
                btn.setProperty("class", "btn maximize")
                set_tooltip(btn, "Maximize")
            refresh_widget_style(btn)

    def _on_poll_result(self, result: _ForegroundPollResult) -> None:
        """Handle shared poll result, each widget applies its own monitor logic."""
        if not result.valid:
            if self._is_visible:
                self._tracked_hwnd = None
                self._tracked_maximized = False
                self._animate(show=False)
            return

        # Per-widget monitor exclusivity check
        if self.config.monitor_exclusive:
            try:
                widget_monitor = get_monitor_hwnd(int(QWidget.winId(self)))
                if result.fg_monitor_hwnd != widget_monitor:
                    mon_info = win32api.GetMonitorInfo(result.fg_monitor_hwnd)
                    if self.screen().name() != mon_info.get("Device"):
                        if self._is_visible:
                            self._tracked_hwnd = None
                            self._tracked_maximized = False
                            self._animate(show=False)
                        return
            except Exception:
                pass

        if self.config.maximized_only:
            # Only show when focused window is maximized
            if result.maximized and not self._is_visible:
                self._tracked_hwnd = result.hwnd
                self._tracked_maximized = True
                self._update_label(result.app_name)
                self._update_maximize_button(True)
                self._animate(show=True)
            elif not result.maximized and self._is_visible:
                self._tracked_hwnd = None
                self._tracked_maximized = False
                self._animate(show=False)
            elif result.maximized:
                self._tracked_hwnd = result.hwnd
                self._update_label(result.app_name)
            else:
                self._tracked_hwnd = None
                self._tracked_maximized = False
        else:
            # Show for any valid focused window
            self._tracked_hwnd = result.hwnd
            self._tracked_maximized = result.maximized
            self._update_label(result.app_name)
            self._update_maximize_button(result.maximized)
            if not self._is_visible:
                self._animate(show=True)

    def _update_label(self, app_name: str) -> None:
        """Update the app name label text."""
        if self._app_name_label:
            self._app_name_label.setText(app_name)

    def _set_visible(self) -> None:
        """Immediately show the widget without animation."""
        self._is_visible = True
        self._opacity_effect.setOpacity(1.0)
        self.setMaximumWidth(16777215)
        self.adjustSize()
        self.updateGeometry()

    def _set_hidden(self) -> None:
        """Immediately hide the widget without animation."""
        self._is_visible = False
        self._opacity_effect.setOpacity(0.0)
        self.setMaximumWidth(0)

    def _stop_running_animations(self) -> None:
        """Stop any currently running show/hide animations."""
        for anim in (self._show_anim, self._hide_anim, self._opacity_anim):
            if anim is not None:
                try:
                    anim.stop()
                    anim.deleteLater()
                except Exception:
                    pass
        self._show_anim = None
        self._hide_anim = None
        self._opacity_anim = None

    def _animate(self, show: bool) -> None:
        """Animate the widget sliding in/out with a fade effect."""
        if show == self._is_visible:
            return
        self._stop_running_animations()
        self._is_visible = show

        duration = self.config.animation_duration
        if duration == 0:
            self._set_visible() if show else self._set_hidden()
            return

        if show:
            # Measure natural width
            self.setMaximumWidth(16777215)
            self.adjustSize()
            target_width = self.sizeHint().width() or 100
            self.setMaximumWidth(0)
            start_width, end_width = 0, target_width
        else:
            current_width = self.width()
            if current_width <= 0:
                self._set_hidden()
                return
            start_width, end_width = current_width, 0

        start_opacity, end_opacity = (0.0, 1.0) if show else (1.0, 0.0)

        width_anim = QPropertyAnimation(self, b"maximumWidth", self)
        width_anim.setStartValue(start_width)
        width_anim.setEndValue(end_width)
        width_anim.setDuration(duration)
        width_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def on_finished():
            try:
                if show:
                    self.setMaximumWidth(16777215)
                    self.adjustSize()
                    self.updateGeometry()
                else:
                    self.setMaximumWidth(0)
            except Exception:
                pass

        width_anim.finished.connect(on_finished)
        if show:
            self._show_anim = width_anim
        else:
            self._hide_anim = width_anim

        opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        opacity_anim.setStartValue(start_opacity)
        opacity_anim.setEndValue(end_opacity)
        opacity_anim.setDuration(duration)
        opacity_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._opacity_anim = opacity_anim

        width_anim.start()
        opacity_anim.start()
