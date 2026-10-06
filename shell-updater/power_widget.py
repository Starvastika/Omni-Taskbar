"""Extends the exact installed account/power popup, preserving its original actions."""
exec('__YASB_BASE_CODE__')
import sys
from pathlib import Path
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QComboBox,QTextBrowser
sys.path.insert(0,str(Path(__import__('os').environ.get('OMNI_PROGRAM_ROOT',str(Path.home()/'.config/yasb')))/'shell-updater'))
from service import UpdateService
from omni_layout import load_bar_fonts
_InstalledPowerMenuWidget=PowerMenuWidget
class PowerMenuWidget(_InstalledPowerMenuWidget):
 def __init__(self,config):
  load_bar_fonts()
  super().__init__(config);self.updates=UpdateService.instance();self.updates.changed.connect(self.update_state)
  self.update_dot=QLabel(self);self.update_dot.setObjectName('taskbarUpdateDot');self.update_dot.setAccessibleName('Taskbar update needs attention')
  self.update_dot.setFixedSize(5,5);self.update_dot.setStyleSheet('background:#ef5252;border-radius:2px;')
  self.update_dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);self.installEventFilter(self)
  self.update_panel=None;self.update_row=None;self.showing_updates=False;self.update_state()
 def eventFilter(self,source,event):
  if source is self and event.type() in (QEvent.Type.Resize,QEvent.Type.Show):self.position_dot()
  if source is getattr(self,'update_row',None) and event.type() in (QEvent.Type.Resize,QEvent.Type.Show):
   self.update_row_dot.move(max(0,source.width()-15),max(0,(source.height()-5)//2))
  return super().eventFilter(source,event)
 def position_dot(self):
  self.update_dot.move(max(0,self.width()-7),2);self.update_dot.raise_()
 def _show_popup_menu(self):
  if self._popup and is_valid_qobject(self._popup) and self._popup.isVisible():return super()._show_popup_menu()
  super()._show_popup_menu()
  if self.update_panel is None or not is_valid_qobject(self.update_panel):self.build_updates()
  self.switch_updates(False);self.update_state();self.place_popup()
 def place_popup(self):
  self._popup.adjustSize();c=self.config.popup
  self._popup.setPosition(alignment=c.alignment,direction=c.direction,offset_left=c.offset_left,offset_top=c.offset_top)
 def build_updates(self):
  layout=self._popup.layout();self.main_items=[layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
  self.update_row=QPushButton('Taskbar Updates');self.update_row.setObjectName('taskbarUpdatesRow')
  self.update_row_dot=QLabel(self.update_row);self.update_row_dot.setFixedSize(5,5)
  self.update_row_dot.setObjectName('taskbarUpdatesRowDot');self.update_row_dot.setStyleSheet('background:#ef5252;border-radius:2px;')
  self.update_row_dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);self.update_row.installEventFilter(self)
  self.update_row.setProperty('class','manage-accounts taskbar-updates-row')
  index=next((i+1 for i,w in enumerate(self.main_items) if w.property('class')=='profile-info'),0)
  layout.insertWidget(index,self.update_row);self.main_items.insert(index,self.update_row)
  self.update_row.clicked.connect(lambda:self.switch_updates(True))
  self.update_panel=QFrame(self._popup);self.update_panel.setObjectName('taskbarUpdatesView')
  self.update_panel.setStyleSheet("""
    QFrame#taskbarUpdatesView { background:#242424; color:#eeeeee; }
    QLabel { color:#eeeeee; background:transparent; }
    QPushButton, QComboBox { background:#363636; color:#eeeeee; border:1px solid #555555; border-radius:4px; padding:7px 10px; }
    QPushButton:hover, QComboBox:hover { background:#454545; }
    QPushButton:focus, QComboBox:focus { border:1px solid #aaaaaa; }
    QPushButton:disabled, QComboBox:disabled { background:#292929; color:#888888; }
    QComboBox QAbstractItemView { background:#303030; color:#eeeeee; selection-background-color:#555555; border:1px solid #666666; }
    QTextBrowser { background:#1d1d1d; color:#dddddd; border:1px solid #555555; padding:8px; }
  """)
  self.update_panel.setMinimumWidth(340);self.update_panel.setMaximumWidth(430)
  v=QVBoxLayout(self.update_panel);v.setContentsMargins(16,14,16,14);v.setSpacing(10)
  self.heading=QLabel('Taskbar Updates');self.heading.setStyleSheet('font-size:17px;font-weight:600;')
  self.installed=QLabel();self.installed.setObjectName('taskbarInstalledVersion')
  self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText)
  self.install_button=QPushButton('Install Update');self.install_button.clicked.connect(self.updates.install)
  self.check_button=QPushButton('Check for Updates');self.check_button.clicked.connect(lambda:self.updates.launch('check'))
  self.notes_button=QPushButton("What's New");self.notes_button.clicked.connect(self.toggle_notes)
  self.mode_label=QLabel('Update mode');self.mode=QComboBox();self.mode.setObjectName('taskbarUpdateMode')
  self.mode.addItem('Choose an update mode',None)
  for text,value in [('Automatic updates','automatic'),('Check automatically','check'),('Manual only','manual')]:self.mode.addItem(text,value)
  self.mode.activated.connect(lambda i:self.updates.launch('mode',self.mode.itemData(i)) if self.mode.itemData(i) else None)
  self.mode_help=QLabel('Automatic: verify and stage, apply on the next taskbar restart.\nCheck automatically: notify; install when you choose.\nManual only: no background checks. Windows is never rebooted.')
  self.mode_help.setWordWrap(True);self.mode_help.setStyleSheet('color:#aaa;font-size:11px;')
  self.notes=QTextBrowser();self.notes.setObjectName('taskbarReleaseNotes');self.notes.setMaximumHeight(210);self.notes.setOpenExternalLinks(False);self.notes.hide()
  nav=QFrame();row=QHBoxLayout(nav);row.setContentsMargins(0,0,0,0)
  back=QPushButton('Back');back.clicked.connect(lambda:self.switch_updates(False))
  close=QPushButton('Close');close.clicked.connect(self._popup.hide_animated);row.addWidget(back);row.addWidget(close)
  for w in (self.heading,self.installed,self.status,self.install_button,self.check_button,self.notes_button,self.mode_label,self.mode,self.mode_help,self.notes,nav):v.addWidget(w)
  layout.addWidget(self.update_panel);self.update_panel.hide()
 def switch_updates(self,value):
  self.showing_updates=value
  for w in self.main_items:w.setVisible(not value)
  self.update_panel.setVisible(value);self.place_popup()
 def toggle_notes(self):
  if self.notes.isVisible():self.notes.hide()
  else:
   text=self.updates.state.get('notes')
   if not text:
    try:text=(self.updates.root/'CHANGELOG.md').read_text('utf-8')
    except OSError:text='No release notes are available yet.'
   self.notes.setPlainText(text);self.notes.show()
  self.place_popup()
 def update_state(self):
  attention=bool(self.updates.state.get('attention'));self.update_dot.setVisible(attention);self.position_dot()
  if self.update_row is None:return
  self.update_row_dot.setVisible(attention)
  self.installed.setText('Version '+self.updates.version);self.status.setText(self.updates.state.get('status','Choose an update mode'))
  busy=self.updates.job is not None or bool(self.updates.state.get('busy'))
  staged=bool(self.updates.state.get('staged_version'));available=bool(self.updates.state.get('available'))
  self.install_button.setText('Restart & Update Now' if staged else 'Install Update')
  self.install_button.setVisible(staged or available);self.install_button.setEnabled(not busy)
  self.check_button.setEnabled(not busy);self.mode.setEnabled(not busy);self.mode.setCurrentIndex(max(0,self.mode.findData(self.updates.state.get('mode'))))
  self.notes_button.setEnabled(not busy)
