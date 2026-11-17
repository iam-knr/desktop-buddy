from ._base import _Any, QObject, QTimer, pyqtSignal, _sig
class _Enum(_Any): pass
Qt = _Any()
class QPointF(_Any):
    def __init__(self, x=0, y=0): self._x, self._y = x, y
    def x(self): return self._x
    def y(self): return self._y
    def __add__(self, o): return QPointF(self._x + getattr(o, "_x", 0), self._y + getattr(o, "_y", 0))
    def __mul__(self, k): return QPointF(self._x * k, self._y * k)
class QPoint(QPointF): pass
class QRectF(_Any): pass
class QRect(_Any): pass
class QSize(_Any): pass
class QDateTime(_Any): pass
class QTime(_Any): pass
class QEvent(_Any): pass
class QProcess(QObject):
    def __init__(self, *a): pass
    @property
    def readyReadStandardOutput(self): return _sig(self, "rr")
    def start(self, *a): pass
    def readAllStandardOutput(self): return b""
    def terminate(self): pass
    def waitForFinished(self, *a): return True
    def kill(self): pass
