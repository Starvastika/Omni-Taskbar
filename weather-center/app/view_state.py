"""Retained Qt values with per-branch notifications, alongside Python state."""
import copy
from PySide6.QtQml import QQmlPropertyMap

class ViewState(QQmlPropertyMap):
    def __init__(self,state,parent=None):
        super().__init__(parent)
        self._previous={}
        self.sync(state)

    def sync(self,state):
        # Insert converts each changed branch once. Reads/notifications remain
        # in Qt; a page change does not recopy prefs, locations or chart settings.
        for key in self._previous.keys()-state.keys():self.clear(key);self._previous.pop(key)
        for key,value in state.items():
            if key not in self._previous or self._previous[key]!=value:
                self.insert(key,value)
                self._previous[key]=copy.deepcopy(value)
