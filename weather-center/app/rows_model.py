"""Retained rows shared by virtualized views and Python chart rendering."""
from PySide6.QtCore import QAbstractListModel,QModelIndex,Qt,Property,Signal,Slot

class RowsModel(QAbstractListModel):
    rowsChanged=Signal()
    ROLE=Qt.UserRole+1
    def __init__(self,parent=None):
        super().__init__(parent);self.rows=[]
    def roleNames(self):return {self.ROLE:b'rowData'}
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def data(self,index,role=Qt.DisplayRole):
        return self.rows[index.row()] if index.isValid() and role==self.ROLE and index.row()<len(self.rows) else None
    @Property(int,notify=rowsChanged)
    def count(self):return len(self.rows)
    @Slot(int,result='QVariantMap')
    def row(self,index):return self.rows[index] if 0<=index<len(self.rows) else {}
    def setRows(self,rows):
        rows=rows or []
        if rows is self.rows:return
        same=[r.get('epoch') for r in rows]==[r.get('epoch') for r in self.rows]
        if not same:self.beginResetModel()
        self.rows=rows
        if not same:self.endResetModel()
        elif rows:self.dataChanged.emit(self.index(0),self.index(len(rows)-1),[self.ROLE])
        self.rowsChanged.emit()
