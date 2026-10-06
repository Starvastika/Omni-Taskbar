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
        self.rows = [h for h in service.members(key) if not service.records[h].get('is_cloaked')]

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
        members = [h for h in self.service.members(self.key) if not self.service.records[h].get('is_cloaked')]
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
