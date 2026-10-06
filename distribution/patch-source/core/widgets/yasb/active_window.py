"""Windows/YASB command surface; Qt Widgets keeps existing bar ownership intact."""
from PyQt6.QtCore import QAbstractListModel,QEvent,QModelIndex,QPoint,QSize,Qt,QTimer
from PyQt6.QtGui import QActionGroup,QColor
from PyQt6.QtWidgets import (QApplication,QAbstractItemView,QFrame,QHBoxLayout,QLabel,QLineEdit,QListView,QMenu,QPushButton,
                            QSizePolicy,QStyle,QVBoxLayout,QWidget,QWidgetAction)
from core.validation.widgets.yasb.active_window import ActiveWindowConfig
from core.utils.win32.event_listener import SystemEventListener
from core.utils.utilities import refresh_widget_style
from core.widgets.base import BaseWidget
from core.widgets.services.active_app_center import ActiveAppService
from core.widgets.services.app_window_menu import AppPopup
from core.widgets.services.application_commands import CommandModel,flatten,search

MENU_STYLE='''QMenu { background:#292929; color:#eee; border:1px solid #555; border-radius:5px; padding:5px; menu-scrollable:1; }
QMenu::item { padding:6px 28px 6px 18px; }
QMenu::item:selected { background:#484848; }
QMenu::item:disabled { color:#888; }
QMenu::separator { height:1px; background:#505050; margin:4px 8px; }'''

class SearchModel(QAbstractListModel):
    def __init__(self,parent):super().__init__(parent);self.rows=[]
    def set_rows(self,rows):self.beginResetModel();self.rows=rows;self.endResetModel()
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def flags(self,index):
        if not index.isValid():return Qt.ItemFlag.NoItemFlags
        return (Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEnabled) if self.rows[index.row()]['enabled'] else Qt.ItemFlag.NoItemFlags
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row()>=len(self.rows):return None
        node=self.rows[index.row()]
        if role==Qt.ItemDataRole.DisplayRole:
            return ('✓ ' if node.get('checked') else '')+node['label']+'\n'+' > '.join(node['path'])+('   '+node['shortcut'] if node.get('shortcut') else '')
        if role in (Qt.ItemDataRole.ToolTipRole,Qt.ItemDataRole.AccessibleTextRole):
            return ' > '.join(node['path'])+(' — disabled' if not node['enabled'] else '')
        if role==Qt.ItemDataRole.SizeHintRole:return QSize(480,52)
        if role==Qt.ItemDataRole.ForegroundRole:return QColor('#eee' if node['enabled'] else '#888')
        return None

class SearchPopup(QFrame):
    def __init__(self,owner):
        super().__init__(owner,Qt.WindowType.Popup|Qt.WindowType.FramelessWindowHint)
        self.owner=owner;self.disposed=False;self.context=owner.model.context;self.last_query=None
        self.setObjectName('appCommandSearch');self.setAccessibleName('Search App Commands')
        self.setStyleSheet('''#appCommandSearch { background:#292929; border:1px solid #555; border-radius:7px; }
QLineEdit { background:#353535; color:white; border:1px solid #777; padding:8px; border-radius:3px; }
QListView { background:transparent; border:0; color:#eee; }
QListView::item { padding:5px 8px; } QListView::item:selected { background:#494949; }
QLabel { color:#aaa; }''')
        layout=QVBoxLayout(self);layout.setContentsMargins(10,10,10,10)
        self.edit=QLineEdit(self);self.edit.setPlaceholderText('Search App Commands');self.edit.setAccessibleName('Search command names, paths and shortcuts')
        self.view=QListView(self);self.results=SearchModel(self);self.view.setModel(self.results)
        self.view.setUniformItemSizes(True);self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.caption=QLabel(self)
        layout.addWidget(self.edit);layout.addWidget(self.view,1);layout.addWidget(self.caption)
        self.edit.textChanged.connect(self.update_results);self.view.clicked.connect(self.execute)
        self.edit.installEventFilter(self);self.view.installEventFilter(self)
        owner.model.changed.connect(self.update_results);owner.service.row_changed.connect(self.rows_changed)
        owner.service.changed.connect(self.target_changed)
        self.resize(520,410);self.update_results();owner.model.index_lazy()
    def target_changed(self):
        if self.owner.model.context!=self.context:self.close()
    def rows_changed(self,*args):self.update_results()
    def update_results(self,*args):
        if self.owner.model.context!=self.context:return self.close()
        query=self.edit.text();selected=None;index=self.view.currentIndex()
        if query==self.last_query and index.isValid() and index.row()<len(self.results.rows):
            selected=self.results.rows[index.row()]['key']
        self.last_query=query
        self.results.set_rows(search(self.owner.model.commands(),query))
        provider=self.owner.model.snapshot['provider']
        self.caption.setText(f'{len(self.results.rows)} results · '+('Window actions; no app commands exposed' if provider=='fallback' else 'App commands and window actions'))
        if selected:
            for i,n in enumerate(self.results.rows):
                if n['key']==selected and n['enabled']:
                    self.view.setCurrentIndex(self.results.index(i));return
        for i,n in enumerate(self.results.rows):
            if n['enabled']:self.view.setCurrentIndex(self.results.index(i));break
    def execute(self,index):
        if index.isValid() and index.row()<len(self.results.rows):
            command=self.results.rows[index.row()]
            if not command['enabled']:return
            self.close();self.owner.model.invoke(command)
    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.KeyPress:
            if event.key()==Qt.Key.Key_Escape:self.close();return True
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.execute(self.view.currentIndex());return True
            if watched is self.edit and event.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down,Qt.Key.Key_PageUp,Qt.Key.Key_PageDown):
                QApplication.sendEvent(self.view,event);return True
        return super().eventFilter(watched,event)
    def dispose(self):
        if not self.disposed:
            self.disposed=True
            self.owner.model.stop_index()
            self.owner.model.changed.disconnect(self.update_results);self.owner.service.row_changed.disconnect(self.rows_changed)
            self.owner.service.changed.disconnect(self.target_changed)
            if self.owner.search_popup is self:self.owner.search_popup=None
            self.deleteLater()
    def hideEvent(self,event):self.dispose();super().hideEvent(event)
    def closeEvent(self,event):self.dispose();super().closeEvent(event)


class ActiveWindowWidget(BaseWidget):
    validation_schema=ActiveWindowConfig
    event_listener=SystemEventListener
    def __init__(self,config):
        super().__init__(class_name=f'active-window-widget application-command-bar {config.class_name}')
        self.config=config;self.service=ActiveAppService.instance();self.model=CommandModel.instance()
        self.popup=None;self.search_popup=None;self.active_menu=None;self.open_key=None;self.menu_actions={}
        self.heading_buttons=[];self.hidden_headings=[];self.last_context=None;self.heading_signature=None
        self._init_container();self._widget_container_layout.setSpacing(1)
        self.identity=self.button('',self.open_app,'app-identity');self.identity.setIconSize(QSize(16,16));self.identity.setMaximumWidth(168)
        self.zone=QWidget(self);self.zone_layout=QHBoxLayout(self.zone);self.zone_layout.setContentsMargins(0,0,0,0);self.zone_layout.setSpacing(1)
        self._widget_container_layout.addWidget(self.zone)
        self.window_button=self.button('Window',self.open_windows)
        self.actions_button=self.button('Actions',self.open_actions)
        self.overflow_button=self.button('…',self.open_overflow);self.overflow_button.setAccessibleName('More application menus and Search App Commands')
        self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
        self.setMaximumWidth(760)
        self.service.changed.connect(self.identity_changed);self.model.changed.connect(self.sync)
        self.model.status_changed.connect(self.status_changed)
        self.installEventFilter(self);self.identity_changed();self.sync()
    def button(self,text,callback,role='command-heading'):
        b=QPushButton(text,self);b.setProperty('class',role);b.setCheckable(True);b.setAccessibleName(text or 'Current application menu')
        b.clicked.connect(callback);b.installEventFilter(self);self._widget_container_layout.addWidget(b);return b
    def status_changed(self,status):self.overflow_button.setToolTip('Search App Commands\n'+status)
    def identity_changed(self):
        r=self.service.active
        if not r:
            self.identity.setText('Desktop');self.identity.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
            self.identity.setEnabled(False);self.identity.setToolTip('Desktop');self.setAccessibleName('Desktop')
        else:
            name,icon=self.service.asset(r,self.devicePixelRatioF())
            self.identity.setText(self.identity.fontMetrics().elidedText(name,Qt.TextElideMode.ElideRight,138))
            self.identity.setIcon(icon);self.identity.setEnabled(True)
            title=f"{name}\n{r['title']}\n{len(self.service.members(r['key']))} open windows"
            self.identity.setToolTip(title);self.identity.setAccessibleName(title);self.setAccessibleName(title)
    def sync(self):
        if self.last_context!=self.model.context:
            self.close_surfaces();self.last_context=self.model.context
        menus=self.model.snapshot['menus']
        signature=tuple((n['key'],n['label']) for n in menus)
        if signature!=self.heading_signature:
            self.heading_signature=signature
            for b,n in self.heading_buttons:self.zone_layout.removeWidget(b);b.deleteLater()
            self.heading_buttons=[]
            for node in menus:
                b=QPushButton(node['label'],self.zone);b.setProperty('class','command-heading');b.setCheckable(True)
                b.setAccessibleName(node['label']);b.clicked.connect(lambda checked=False,k=node['key']:self.open_heading(k))
                b.installEventFilter(self);self.zone_layout.addWidget(b);self.heading_buttons.append((b,node['key']))
        self.window_button.setText('Windows' if menus else 'Window')  # preserve localized/native Window semantics rather than guessing a merge
        self.window_button.setEnabled(bool(self.model.context));self.actions_button.setEnabled(bool(self.model.context))
        self.actions_button.setVisible(not bool(menus) and bool(self.model.context));self.overflow_button.setEnabled(bool(self.model.context))
        self.window_button.setVisible(bool(self.model.context));self.overflow_button.setVisible(bool(self.model.context))
        self.fit_headings()
        if self.active_menu and self.open_key:
            node=self.node(self.open_key)
            if node:self.populate(self.active_menu,node.get('children',[]))
        if self.active_menu:
            for sub in self.active_menu.findChildren(QMenu):
                key=getattr(sub,'_command_key',None)
                node=self.node(key) if key else None
                if node and sub.isVisible():self.populate(sub,node.get('children',[]))
    def node(self,key):
        def find(nodes):
            for n in nodes:
                if n['key']==key:return n
                found=find(n.get('children',[]))
                if found:return found
        return find(self.model.snapshot['menus'])
    def fit_headings(self):
        bar=self.window();budget=600
        if isinstance(getattr(bar,'_widgets',None),dict):
            # Leave all current system/desktops/home widgets their full hints.
            other=[w for column,ws in bar._widgets.items() for w in ws if w is not self]
            budget=min(760,max(260,bar.width()-sum(max(w.sizeHint().width(),w.minimumWidth()) for w in other)-80))
        self.setMaximumWidth(budget)
        fixed=self.identity.sizeHint().width()+self.window_button.sizeHint().width()+self.overflow_button.sizeHint().width()+28
        if not self.actions_button.isHidden():fixed+=self.actions_button.sizeHint().width()
        left=budget-fixed;self.hidden_headings=[];overflow=False
        for b,key in self.heading_buttons:
            width=b.sizeHint().width()+1
            shown=not overflow and width<=left
            if not shown:overflow=True
            b.setVisible(shown)
            if shown:left-=width
            else:self.hidden_headings.append(key)
        self.zone.setVisible(bool(self.heading_buttons) and any(not b.isHidden() for b,k in self.heading_buttons))
    def close_surfaces(self):
        if self.popup:self.popup.close()
        if self.search_popup:self.search_popup.close()
        if self.active_menu:self.active_menu.close()
        for b in [self.identity,self.window_button,self.actions_button,self.overflow_button]+[b for b,k in self.heading_buttons]:b.setChecked(False)
    def menu(self,button):
        self.close_surfaces()
        m=QMenu(self);m.setStyleSheet(MENU_STYLE);m.installEventFilter(self)
        self.active_menu=m;self.open_key=None;m._node_keys=None;m._actions={}
        button.setChecked(True)
        def hidden():
            button.setChecked(False)
            if self.active_menu is m:self.active_menu=None;self.open_key=None
            m.deleteLater()
        m.aboutToHide.connect(hidden)
        return m
    def show_menu(self,menu,button):
        p=button.mapToGlobal(QPoint(0,button.height()+6));screen=self.screen().availableGeometry()
        p.setX(max(screen.left()+3,min(p.x(),screen.right()-menu.sizeHint().width()-3)))
        menu.popup(p)
    def populate(self,menu,nodes):
        keys=tuple((n['key'],n['kind']) for n in nodes)
        if getattr(menu,'_node_keys',None)==keys:
            for n in nodes:
                action=menu._actions.get(n['key'])
                if action:
                    action.setEnabled(n['enabled']);action.setCheckable(action.isCheckable() or bool(n.get('checked') or n.get('radio')))
                    action.setChecked(n.get('checked',False))
            return
        menu.clear();menu._node_keys=keys;menu._actions={}
        if not nodes:
            menu.addAction('No safe commands exposed yet').setEnabled(False)
        radios=None
        for n in nodes:
            if n['kind']=='separator':menu.addSeparator();radios=None;continue
            text=n['label']+('\t'+n['shortcut'] if n.get('shortcut') else '')
            if n['kind']=='submenu':
                child=QMenu(text,menu);child.setStyleSheet(MENU_STYLE);child.installEventFilter(self)
                child._command_key=n['key']
                self.populate(child,n.get('children',[]));action=menu.addMenu(child)
                child.aboutToShow.connect(lambda key=n['key'],sub=child:self.refresh_submenu(key,sub))
            else:
                action=menu.addAction(text);action.triggered.connect(lambda checked=False,command=n:self.execute(command))
            action.setEnabled(n['enabled']);action.setCheckable(bool(n.get('checked') or n.get('radio')));action.setChecked(n.get('checked',False))
            if n.get('radio'):
                if radios is None:radios=QActionGroup(menu);radios.setExclusive(True)
                radios.addAction(action)
            else:radios=None
            action.setToolTip(' > '.join(n['path']));menu._actions[n['key']]=action
    def refresh_submenu(self,key,menu):
        n=self.node(key)
        if n:
            self.populate(menu,n.get('children',[]));self.model.refresh(n)
    def execute(self,command):
        # An unchanged visible action may outlive a state refresh. Resolve its
        # identity in this context only; never retarget across foreground epochs.
        if command['provider']!='shell' and command.get('context')==self.model.context and command.get('epoch')==self.model.epoch:
            command=self.node(command['key']) or command
        self.close_surfaces();self.model.invoke(command)
    def open_heading(self,key):
        node=self.node(key)
        if not node:return
        if node['kind']=='command':return self.execute(node)
        button=next((b for b,k in self.heading_buttons if k==key),self.overflow_button)
        m=self.menu(button);self.open_key=key;self.populate(m,node.get('children',[]));self.show_menu(m,button);self.model.refresh(node)
    def open_app(self,*args):
        if not self.service.active:return
        m=self.menu(self.identity);r=self.service.active;name,_=self.service.asset(r)
        header=QLabel(f"{name}\n{r['title']}\n{len(self.service.members(r['key']))} open windows",m)
        header.setTextFormat(Qt.TextFormat.PlainText);header.setWordWrap(True);header.setMaximumWidth(420);header.setStyleSheet('color:#ddd;padding:8px;')
        action=QWidgetAction(m);action.setDefaultWidget(header);m.addAction(action);m.addSeparator()
        m.addAction('Search App Commands…',self.open_search);m.addAction('Switch Window…',self.open_windows)
        m.addSeparator();self.add_shell_actions(m);self.show_menu(m,self.identity)
    def add_shell_actions(self,menu):
        for command in self.model.shell_commands():
            if command['action']=='switch':continue
            a=menu.addAction(command['label']);a.triggered.connect(lambda checked=False,n=command:self.execute(n))
    def open_actions(self,*args):
        if not self.model.context:return
        m=self.menu(self.actions_button);self.add_shell_actions(m);self.show_menu(m,self.actions_button)
    def open_overflow(self,*args):
        if not self.model.context:return
        m=self.menu(self.overflow_button)
        for key in self.hidden_headings:
            node=self.node(key)
            if node:
                if node['kind']=='submenu':
                    child=QMenu(node['label'],m);child.setStyleSheet(MENU_STYLE);child.installEventFilter(self)
                    child._command_key=key
                    self.populate(child,node.get('children',[]));m.addMenu(child)
                    child.aboutToShow.connect(lambda k=key,s=child:self.refresh_submenu(k,s))
                else:m.addAction(node['label'],lambda n=node:self.execute(n))
        if self.hidden_headings:m.addSeparator()
        m.addAction('Search App Commands…',self.open_search)
        child=m.addMenu('Window Actions');child.setStyleSheet(MENU_STYLE);self.add_shell_actions(child)
        if self.model.status:m.addSeparator();m.addAction('App commands unavailable').setEnabled(False)
        self.show_menu(m,self.overflow_button)
    def open_windows(self,*args):
        self.close_surfaces()
        if not self.service.active or not self.window().isVisible():return
        self.popup=AppPopup(self);self.popup.setAccessibleName('Sibling application windows')
        # Current specification excludes cloaked helpers from the top list.
        self.popup.model.rows=[h for h in self.popup.model.rows if not self.service.records[h].get('is_cloaked')]
        p=self.window_button.mapToGlobal(QPoint(0,self.window_button.height()+6));screen=self.screen().availableGeometry()
        p.setX(max(screen.left()+3,min(p.x(),screen.right()-self.popup.width()-3)))
        self.popup.move(p);self.popup.setMaximumHeight(max(120,screen.bottom()-p.y()-3));self.popup.show();self.popup.view.setFocus()
        self.window_button.setChecked(True);self.popup.installEventFilter(self);self.popup.view.installEventFilter(self)
    def show_context(self,point,record=None,parent=None):
        target=record or self.service.active
        if not target:return
        m=QMenu(parent or self);m.setStyleSheet(MENU_STYLE)
        for name,action in (('Switch to Window','switch'),('Minimize','minimize'),('Maximize / Restore','maximize'),('Close Window','close')):
            def execute(checked=False,a=action,t=dict(target)):
                self.close_surfaces()
                if a=='switch':self.service.activate(t['hwnd'],t['token'])
                else:self.service.action(t['hwnd'],a,t['token'])
            m.addAction(name,execute)
        m.aboutToHide.connect(m.deleteLater);m.popup(point)
    def open_search(self,*args):
        self.close_surfaces()
        if not self.model.context or not self.window().isVisible():return
        self.search_popup=SearchPopup(self)
        p=self.identity.mapToGlobal(QPoint(0,self.identity.height()+6));screen=self.screen().availableGeometry()
        p.setX(max(screen.left()+3,min(p.x(),screen.right()-self.search_popup.width()-3)))
        self.search_popup.move(p);self.search_popup.setMaximumHeight(max(150,screen.bottom()-p.y()-3))
        self.search_popup.show();self.search_popup.edit.setFocus()
    def switch_heading(self,step):
        buttons=[self.identity]+[b for b,k in self.heading_buttons if b.isVisible()]+[self.window_button]
        if self.actions_button.isVisible():buttons.append(self.actions_button)
        buttons.append(self.overflow_button)
        checked=next((i for i,b in enumerate(buttons) if b.isChecked()),0)
        buttons[(checked+step)%len(buttons)].click()
    def eventFilter(self,watched,event):
        if watched is self.popup and event.type()==QEvent.Type.Hide:self.window_button.setChecked(False)
        if watched is self and event.type()==QEvent.Type.Hide:self.close_surfaces()
        if watched is self and event.type() in (QEvent.Type.Show,QEvent.Type.Resize):QTimer.singleShot(0,self.fit_headings)
        if event.type()==QEvent.Type.Enter and isinstance(watched,QPushButton) and (self.active_menu or self.popup) and not watched.isChecked():watched.click()
        if event.type()==QEvent.Type.KeyPress and (self.active_menu or self.popup):
            if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right):
                if isinstance(watched,QMenu):
                    if isinstance(watched.parentWidget(),QMenu):return False
                    a=watched.activeAction()
                    if event.key()==Qt.Key.Key_Right and a and a.menu():return False
                self.switch_heading(-1 if event.key()==Qt.Key.Key_Left else 1);return True
        return super().eventFilter(watched,event)
