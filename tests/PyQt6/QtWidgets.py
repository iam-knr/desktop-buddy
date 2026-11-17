from ._base import _Any, QObject, _sig
from .QtGui import QGuiApplication

class _CloseEvent:
    def __init__(self): self.accepted = True
    def ignore(self): self.accepted = False
    def accept(self): self.accepted = True

class QWidget(QObject):
    def __init__(self, *a, **k): self._shown = False
    def show(self): self._shown = True
    def hide(self):
        self._shown = False
        h = getattr(type(self), "hideEvent", None)
        if h and h is not QWidget.hideEvent: self.hideEvent(_Any())
    def hideEvent(self, e): pass
    def closeEvent(self, e): pass
    def isHidden(self): return not self._shown
    def isVisible(self): return self._shown
    def isActiveWindow(self): return self.__dict__.get("_active", False)
    def close(self):
        ev = _CloseEvent()
        self.closeEvent(ev)
        if ev.accepted: self._shown = False
        return True
class QFrame(QWidget): pass
class QLabel(QWidget):
    def __init__(self, t="", *a): super().__init__(); self._t = t
    def setText(self, t): self._t = t
    def text(self): return self._t
class QPushButton(QWidget):
    def __init__(self, t="", *a): super().__init__(); self._t = t
    @property
    def clicked(self): return _sig(self, "clicked")
    def setText(self, t): self._t = t
    def text(self): return self._t
class QCheckBox(QPushButton):
    @property
    def toggled(self): return _sig(self, "toggled")
class QLineEdit(QWidget):
    def __init__(self, *a): super().__init__(); self._t = ""
    @property
    def textChanged(self): return _sig(self, "textChanged")
    @property
    def returnPressed(self): return _sig(self, "returnPressed")
    def setText(self, t):
        self._t = t
        if not self.__dict__.get("_blocked"): self.textChanged.emit(t)
    def text(self): return self._t
    def clear(self): self.setText("")
    def hasFocus(self): return False
class _Cursor(_Any):
    def __init__(self, ed): self.ed = ed
    def position(self): return len(self.ed._t)
    def insertText(self, t): self.ed._undo.append(self.ed._t); self.ed._t += t; self.ed.textChanged.emit()
    def removeSelectedText(self): self.ed._undo.append(self.ed._t); self.ed._t = ""; self.ed.textChanged.emit()
    class MoveOperation: End = 0
class QPlainTextEdit(QWidget):
    def __init__(self, *a): super().__init__(); self._t = ""; self._undo = []
    @property
    def textChanged(self): return _sig(self, "textChanged")
    def setPlainText(self, t): self._t = t; self.textChanged.emit()
    def toPlainText(self): return self._t
    def textCursor(self): return _Cursor(self)
    def setTextCursor(self, c): pass
    def undo(self):
        if self._undo: self._t = self._undo.pop(); self.textChanged.emit()
    def hasFocus(self): return False
class QDateTimeEdit(QWidget): pass
class QTextBrowser(QWidget): pass
class QStackedWidget(QWidget):
    def __init__(self): super().__init__(); self._i = 0
    def setCurrentIndex(self, i): self._i = i
    def currentIndex(self): return self._i
class QComboBox(QWidget):
    def __init__(self): super().__init__(); self._items = []; self._i = -1
    @property
    def currentIndexChanged(self): return _sig(self, "cic")
    @property
    def activated(self): return _sig(self, "act")
    def addItem(self, label, data=None):
        self._items.append((label, data))
        if self._i < 0: self._i = 0
    def clear(self): self._items = []; self._i = -1
    def findData(self, d): return next((i for i, (_, x) in enumerate(self._items) if x == d), -1)
    def setCurrentIndex(self, i):
        changed = i != self._i; self._i = i
        if changed and not self.__dict__.get("_blocked"): self.currentIndexChanged.emit(i)
    def itemData(self, i): return self._items[i][1] if 0 <= i < len(self._items) else None
    def count(self): return len(self._items)
class QListWidgetItem(_Any):
    def __init__(self): self._d = {}
    def setData(self, role, v): self._d["d"] = v
    def data(self, role): return self._d.get("d")
class QListWidget(QWidget):
    def __init__(self): super().__init__(); self._items = []; self._cur = -1
    @property
    def currentItemChanged(self): return _sig(self, "cur")
    def clear(self): self._items = []; self._cur = -1
    def addItem(self, it): self._items.append(it)
    def setItemWidget(self, it, w): pass
    def count(self): return len(self._items)
    def currentRow(self): return self._cur
    def setCurrentItem(self, it): self._set(self._items.index(it))
    def setCurrentRow(self, r): self._set(r)
    def _set(self, r):
        prev = self._cur; self._cur = r
        if prev != r and not self.__dict__.get("_blocked"):
            self.currentItemChanged.emit(self._items[r] if 0 <= r < len(self._items) else None, None)
class _Layout(_Any):
    def __init__(self, *a): pass
QVBoxLayout = QHBoxLayout = QGridLayout = _Layout
class QScrollArea(QWidget): pass
class QApplication(QGuiApplication):
    @staticmethod
    def beep(): pass
