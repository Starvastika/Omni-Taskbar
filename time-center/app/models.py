from PySide6.QtCore import QAbstractListModel,QModelIndex,Property,Signal,Qt

class StableModel(QAbstractListModel):
    """Refresh row data without destroying delegates, menus or scroll positions."""
    sourceChanged=Signal()
    def __init__(self,parent=None):super().__init__(parent);self.rows=[]
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def roleNames(self):return {Qt.UserRole+1:b'rowData'}
    def data(self,index,role=Qt.DisplayRole):
        return self.rows[index.row()] if index.isValid() and role==Qt.UserRole+1 else None
    @Property('QVariantList',notify=sourceChanged)
    def source(self):return self.rows
    @source.setter
    def source(self,rows):
        rows=list(rows or [])
        if rows==self.rows:return
        if [r.get('id') for r in rows]!=[r.get('id') for r in self.rows]:
            self.beginResetModel();self.rows=rows;self.endResetModel()
        else:
            for i,row in enumerate(rows):
                if row!=self.rows[i]:self.rows[i]=row;self.dataChanged.emit(self.index(i),self.index(i),[Qt.UserRole+1])
        self.sourceChanged.emit()
