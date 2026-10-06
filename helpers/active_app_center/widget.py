"""Compact active application identity and virtualized downward sibling menu."""
import win32gui
from PyQt6.QtCore import QAbstractListModel, QEvent, QModelIndex, QPoint, QSize, Qt, QTimer
from PyQt6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel,
                            QListView, QMenu, QPushButton, QStyle, QVBoxLayout, QWidget)
from core.validation.widgets.yasb.active_window import ActiveWindowConfig
from core.utils.win32.event_listener import SystemEventListener
from core.widgets.base import BaseWidget
from core.widgets.services.active_app_center import ActiveAppService, clean_title


class WindowListModel(QAbstractListModel):
    def __init__(self, service, key, parent):
        super().__init__(parent)
        self.service, self.key = service, key
        self.rows = service.members(key)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.rows):
            return None
        hwnd = self.rows[index.row()]
        record = self.service.records.get(hwnd)
        if not record:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            active = self.service.active
            mark = "✓  " if active and (active.get("owner") or active["hwnd"]) == hwnd else "    "
            return mark + record["title"] + ("  · Minimized" if record.get("minimized") else "")
        if role in (Qt.ItemDataRole.ToolTipRole, Qt.ItemDataRole.AccessibleTextRole):
            return record["title"] + (" (minimized)" if record.get("minimized") else "")
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(420, 36)
        return None

    def update_row(self, hwnd, membership):
        members = self.service.members(self.key)
        if members != self.rows:
            # Membership changes only; titles/state never rebuild the model.
            self.beginResetModel()
            self.rows = members
            self.endResetModel()
        elif hwnd in self.rows:
            idx = self.index(self.rows.index(hwnd))
            self.dataChanged.emit(idx, idx)


class AppPopup(QFrame):
    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("activeAppPopup")
        self.owner = owner
        self.disposed = False
        self.service = owner.service
        self.key = self.service.active["key"]
        self.target = dict(self.service.active)
        self.setAccessibleName("Application windows")
        self.setStyleSheet("""
            #activeAppPopup { background:#292929; color:#f1f1f1; border:1px solid #555; border-radius:8px; }
            #activeAppPopup QLabel { color:#eee; padding:4px; }
            #activeAppPopup QListView { background:transparent; color:#dedede; border:0; outline:0; padding:2px; }
            #activeAppPopup QListView::item { padding:7px; border-radius:4px; }
            #activeAppPopup QListView::item:hover { background:#3b3b3b; }
            #activeAppPopup QListView::item:selected { background:#505050; color:white; border:1px solid #aaa; }
            #activeAppPopup QPushButton { background:#343434; color:#eee; padding:6px 10px; border:1px solid #525252; border-radius:4px; }
            #activeAppPopup QPushButton:hover { background:#484848; }
            #activeAppPopup QPushButton:focus { border:1px solid #aaa; }
            #activeAppPopup QPushButton:disabled { color:#888; }
            #activeAppPopup QScrollBar:vertical { width:8px; background:#292929; }
            #activeAppPopup QScrollBar::handle:vertical { background:#686868; min-height:24px; border-radius:3px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(7)
        self.heading = QLabel(self)
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.heading)
        self.view = QListView(self)
        self.model = WindowListModel(self.service, self.key, self)
        self.view.setModel(self.model)
        self.view.setUniformItemSizes(True)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setAccessibleName("Open windows of this application")
        self.view.clicked.connect(self.select)
        self.view.activated.connect(self.select)
        self.view.installEventFilter(self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.context)
        layout.addWidget(self.view)
        actions = QHBoxLayout()
        self.buttons = {}
        for name, text in (("minimize", "Minimize"), ("maximize", "Maximize / Restore"), ("close", "Close")):
            button = QPushButton(text, self)
            button.clicked.connect(lambda checked=False, a=name: self.window_action(a))
            actions.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(actions)
        self.service.row_changed.connect(self.rows_changed)
        self.service.changed.connect(self.active_changed)
        self.refresh_heading()
        if self.model.rows:
            row = self.model.rows.index(self.target.get("owner", self.target["hwnd"])) if self.target.get("owner", self.target["hwnd"]) in self.model.rows else 0
            self.view.setCurrentIndex(self.model.index(row))
        self.resize(440, min(480, 96 + max(1, self.model.rowCount()) * 36))

    def refresh_heading(self):
        name, _ = self.service.asset(self.target, self.owner.devicePixelRatioF())
        count = self.model.rowCount()
        self.heading.setText(f"{name}  ·  {count} open window{'s' if count != 1 else ''}")
        valid = self.service.valid_target(self.target["hwnd"], self.target["token"])
        for b in self.buttons.values():
            b.setEnabled(valid)

    def rows_changed(self, hwnd, membership):
        self.model.update_row(hwnd, membership)
        if membership:
            self.refresh_heading()
        if not self.model.rows:
            self.close()
        elif not self.view.currentIndex().isValid():
            self.view.setCurrentIndex(self.model.index(0))

    def active_changed(self):
        active = self.service.active
        if not active or active["key"] != self.key:
            self.close()
            return
        self.target = dict(active)
        self.refresh_heading()
        if self.model.rowCount():
            self.model.dataChanged.emit(self.model.index(0), self.model.index(self.model.rowCount()-1))

    def select(self, index):
        if index.isValid() and index.row() < len(self.model.rows):
            hwnd = self.model.rows[index.row()]
            record = self.service.records.get(hwnd)
            if record:
                token = record["token"]
                self.close()
                self.service.activate(hwnd, token)

    def window_action(self, action):
        target = self.target
        self.close()
        self.service.action(target["hwnd"], action, target["token"])

    def context(self, point):
        index = self.view.indexAt(point)
        if not index.isValid():
            return
        record = self.service.records.get(self.model.rows[index.row()])
        if record:
            self.owner.show_context(self.view.viewport().mapToGlobal(point), record, self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.close()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.select(self.view.currentIndex())
                return True
        return super().eventFilter(watched, event)

    def dispose(self):
        if not self.disposed:
            self.disposed = True
            self.service.row_changed.disconnect(self.rows_changed)
            self.service.changed.disconnect(self.active_changed)
            if self.owner.popup is self:
                self.owner.popup = None
            self.deleteLater()

    def hideEvent(self, event):
        self.dispose()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)


class ActiveWindowWidget(BaseWidget):
    validation_schema = ActiveWindowConfig
    event_listener = SystemEventListener

    def __init__(self, config):
        super().__init__(class_name=f"active-window-widget {config.class_name}")
        self.config = config
        self.service = ActiveAppService.instance()
        self.popup = None
        self._init_container()
        self.identity = QPushButton(self)
        self.identity.setProperty("class", "app-identity")
        self.identity.setIconSize(QSize(16, 16))
        self.identity.setMaximumWidth(160)
        self.identity.setAccessibleName("Current application, open window list")
        self.identity.clicked.connect(self.open_menu)
        self.identity.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.identity.customContextMenuRequested.connect(lambda p: self.show_context(self.identity.mapToGlobal(p)))
        self.title = QLabel(self)
        self.title.setProperty("class", "label app-title")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setFixedWidth(166)
        self.title.installEventFilter(self)
        self._widget_container_layout.addWidget(self.identity)
        self._widget_container_layout.addWidget(self.title)
        self.register_callback("toggle_label", self.open_menu)
        self.callback_left = "toggle_label"
        self.callback_middle = "do_nothing"
        self.callback_right = "do_nothing"
        self.service.changed.connect(self.refresh)
        self.service.row_changed.connect(self.group_changed)
        self.installEventFilter(self)
        self._full_title = ""
        self.refresh()

    def group_changed(self, hwnd, membership):
        if membership and self.service.active:
            self.refresh_tooltip()

    def refresh_tooltip(self):
        active = self.service.active
        if active:
            name, _ = self.service.asset(active, self.devicePixelRatioF())
            count = len(self.service.members(active["key"]))
            self.identity.setToolTip(f"{name}\n{active['title']}\n{count} open window{'s' if count != 1 else ''}")

    def refresh(self):
        active = self.service.active
        if not active:
            self.identity.setText("Desktop")
            self.identity.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
            self.identity.setEnabled(False)
            self._full_title = ""
            self.title.clear()
            self.title.hide()
            self.identity.setToolTip("Desktop")
            return
        name, icon = self.service.asset(active, self.devicePixelRatioF())
        self.identity.setEnabled(True)
        self.title.show()
        self.identity.setText(self.identity.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, 112) + "  ▾")
        self.identity.setIcon(icon)
        self._full_title = clean_title(active["title"], name)
        self.title.setToolTip(active["title"])
        self.elide()
        self.refresh_tooltip()

    def elide(self):
        width = min(172, max(0, self.title.width()-7)) if self.title.isVisible() else 172
        self.title.setText(self.title.fontMetrics().elidedText(self._full_title, Qt.TextElideMode.ElideRight, width))

    def open_menu(self):
        if self.popup:
            self.popup.close()
            return
        if not self.service.active or not self.window().isVisible():
            return
        self.popup = AppPopup(self)
        point = self.identity.mapToGlobal(QPoint(0, self.identity.height()+7))
        screen = self.screen().availableGeometry()
        point.setX(max(screen.left()+4, min(point.x(), screen.right()-self.popup.width()-4)))
        # Always downward; reduce height instead of flipping over the top bar.
        self.popup.setMaximumHeight(max(120, screen.bottom()-point.y()-4))
        self.popup.move(point)
        self.popup.show()
        self.popup.view.setFocus()

    def show_context(self, point, record=None, parent=None):
        target = dict(record or self.service.active or {})
        if not target:
            return
        menu = QMenu(parent or self)
        menu.setProperty("class", "context-menu")
        for text, action in (("Switch to window", "switch"), ("Minimize", "minimize"), ("Maximize / Restore", "maximize"), ("Close window", "close")):
            item = menu.addAction(text)
            item.setEnabled(self.service.valid_target(target["hwnd"], target["token"]))
            def invoke(checked=False, a=action, t=target):
                if self.popup:
                    self.popup.close()
                if a == "switch":
                    self.service.activate(t["hwnd"], t["token"])
                else:
                    self.service.action(t["hwnd"], a, t["token"])
            item.triggered.connect(invoke)
        menu.addSeparator()
        for text, action in (("Minimize all windows", "minimize"), ("Restore all windows", "restore")):
            item = menu.addAction(text)
            # Freeze per-window PID tokens at menu creation, guarding HWND reuse.
            targets = [(h, self.service.records[h]["token"]) for h in self.service.members(target["key"])]
            item.triggered.connect(lambda checked=False, a=action, ts=targets: [self.service.action(h, a, pid) for h, pid in ts])
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(point)

    def eventFilter(self, watched, event):
        if watched is self.title and event.type() == QEvent.Type.Resize:
            self.elide()
        if watched is self and event.type() == QEvent.Type.Hide and self.popup:
            self.popup.close()
        return super().eventFilter(watched, event)
